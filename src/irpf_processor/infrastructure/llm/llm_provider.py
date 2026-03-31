"""
Simplified LLM Provider - Easy to use base class for Azure OpenAI integration.

This simplified version removes complexity like chunking, QR decoding, and
multiple document types per se. Subclasses can override key methods to
customize behavior for specific document types (e.g., IR documents).
"""

import json
import time
from typing import Any, Optional
from abc import ABC, abstractmethod
import multiprocessing as mp

from openai import AzureOpenAI, RateLimitError, APIError, APITimeoutError
from irpf_processor.shared.logging import get_logger

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from irpf_processor.domain.entities import document
from irpf_processor.domain.entities.document import Document
from irpf_processor.config import get_settings

from irpf_processor.infrastructure.utils import make_image_content
from irpf_processor.infrastructure.utils.pdf import pdf_to_images
from irpf_processor.infrastructure.utils.sanitizers import extract_json_from_text

# Fixed seed for reproducibility
_FIXED_SEED = 20260212

DEFAULT_USER_PROMPT = "Extraia todos os dados relevantes do documento fornecido em formato JSON."

IR_SYSTEM_PROMPT = """
Você é um especialista em análise de documentos tributários brasileiros da Receita Federal.
Sua tarefa é extrair com precisão todos os dados de declarações de Imposto de Renda (DIRPF, DIRPJ),
informes de rendimentos e recibos de entrega.

FORMATO DE SAÍDA:
• Retorne SOMENTE um JSON válido, sem markdown, sem blocos de código, sem texto adicional.
• Siga rigorosamente o schema e regras solicitado no prompt do usuário.

PRECISÃO E LITERALIDADE:
• Copie valores numéricos EXATAMENTE como aparecem no documento (formato brasileiro: 1.234,56).
• Copie nomes, CPFs, CNPJs e códigos caractere por caractere — não corrija nem reformate.
• Preserve acentuação e capitalização originais.
• Transcreva o que for legível e use null para o que não for.

CAMPOS AUSENTES:
• NUNCA invente, deduza ou estime valores que não estejam explícitos no documento.
"""

logger = get_logger(__name__)

class LLMProvider(ABC):
    """
    Simplified base class for LLM-based document extraction.
    
    Features:
    - Simple Azure OpenAI integration
    - Automatic retry with exponential backoff
    - Basic PDF and image support
    - Easy to extend for specific document types
    
    Subclass and override these methods to customize:
    - _get_system_prompt()
    - _prepare_prompt()
    - _post_process_data()
    """

    def __init__(self):
        """Initialize the LLM provider."""
        self._client: AzureOpenAI | None = None
        self._validate_config()

    def _validate_config(self) -> None:
        """Validate Azure OpenAI configuration."""
        s = get_settings()
        if not s.azure_openai_api_key:
            raise RuntimeError(
                "AZURE_OPENAI_API_KEY not configured. "
                "Set it in .env or as environment variable."
            )
        if not s.azure_openai_endpoint:
            raise RuntimeError(
                "AZURE_OPENAI_ENDPOINT not configured. "
                "Set it in .env or as environment variable."
            )

    def _get_client(self) -> AzureOpenAI:
        """Get or create Azure OpenAI client (singleton)."""
        if self._client is None:
            s = get_settings()
            self._client = AzureOpenAI(
                azure_endpoint=s.azure_openai_endpoint,
                api_key=s.azure_openai_api_key,
                api_version=s.azure_openai_api_version,
            )
        return self._client

    def _get_system_prompt(self) -> str:
        """Return the system prompt to use.
        Override in subclasses to customize."""
        return IR_SYSTEM_PROMPT

    def _prepare_prompt(self, custom_prompt: Optional[str] = None) -> str:
        """Prepare the user prompt.
        Se o extractor forneceu LLM_PROMPT, ele É o prompt principal.
        DEFAULT_USER_PROMPT é apenas fallback."""
        if custom_prompt:
            return custom_prompt
        return DEFAULT_USER_PROMPT

    def _post_process_data(self, data: dict) -> dict:
        """Post-process extracted data.
        Override in subclasses to apply sanitization, validation, etc."""
        return data

    def _get_max_images_per_call(self) -> int:
        """Max pages per LLM call when chunking. Configurable via LLM_MAX_IMAGES_PER_CALL env var."""
        return get_settings().llm_max_images_per_call

    def _get_chunk_annotation(self, start: int, end: int, total: int) -> str:
        """Per-chunk prompt suffix — apenas regras de paginação."""
        annotation = (
            f"\n\nATENÇÃO: Você está analisando as páginas {start + 1} a {end} "
            f"de um documento de {total} páginas no total.\n\n"
            "REGRAS PARA EXTRAÇÃO EM CHUNKS:\n"
            "• Extraia TODOS os itens que aparecem nestas páginas — NÃO resuma, NÃO omita.\n"
            "• Mantenha o mesmo schema JSON solicitado acima.\n"
            "• Se um item começa em uma página e terminar na outra, crie um item parcial com os campos disponíveis.\n"
            "• Arrays são acumulativos: inclua cada item individual visível nestas páginas.\n"
            "• É MELHOR retornar itens duplicados (serão deduplicados depois) do que omitir itens.\n"
            "• NUNCA retorne total > 0 com array vazio — isso indica itens não extraídos.\n"
            "• Se a tabela tem linha de 'Total', extraia-a como campo numérico, NÃO como item do array."
        )

        return annotation

    def _get_overlap_annotation(self, last_item: dict) -> str:
        """Instrução para completar item parcial do chunk anterior."""
        item_json = json.dumps(last_item, ensure_ascii=False, indent=2)
        return (
            "\n\nULTIMO ITEM DO CHUNK ANTERIOR:\n"
            
            "Preste muita atenção na PRIMEIRA página deste chunk e verifique se contém continuação deste item, "
            "retorne-o COMPLETO (dados do chunk anterior + dados novos) "
            'e adicione o campo "item_overlap": true.\n'
            'Se NÃO houver continuação, repita o item e adicione o campo "item_overlap": false.\n'
            'Adicione item_overlap apenas neste item, não em outros itens do chunk.\n'
            'Ultimo item:\n'
            f"{item_json}"
        )

    @staticmethod
    def _extract_last_item(parsed: dict) -> Optional[dict]:
        """Extrai o último item do primeiro array encontrado no JSON parseado."""
        if not isinstance(parsed, dict):
            return None
        for value in parsed.values():
            if isinstance(value, list) and len(value) > 0 and isinstance(value[-1], dict):
                return value[-1]
        return None

    def _build_content(
        self,
        user_prompt: str,
        images: Optional[list[bytes]] = None,
    ) -> list[dict]:
        """Build content blocks for Azure OpenAI API."""
        content: list[dict] = [{"type": "text", "text": user_prompt}]

        if images:
            for i, img in enumerate(images):
                content.append(make_image_content(img, "image/png"))

        logger.debug("build_content", images=len(images) if images else 0)

        return content

    def _process_pdf(self, document: Document) -> list[bytes]:
        """Convert PDF to images."""
        images = pdf_to_images(document.content, dpi=get_settings().pdf_dpi)
        return images

    def _parse_response(self, raw_text: str) -> dict[str, Any]:
        """Parse LLM response (with fallback)."""
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            # Try extracting JSON from text
            cleaned = extract_json_from_text(raw_text)
            if cleaned:
                return json.loads(cleaned)

            return {"raw_text": raw_text, "parse_error": True}

    @retry(
        retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    def _call_openai_with_retry(self, messages: list[dict]) -> Any:
        """Call Azure OpenAI with automatic retry (3 attempts, exponential backoff)."""
        client = self._get_client()

        return client.chat.completions.create(
            model=get_settings().azure_openai_deployment,
            messages=messages,
            max_tokens=get_settings().azure_openai_max_tokens,
            temperature=0,
            top_p=1,
            seed=_FIXED_SEED,
            response_format={"type": "json_object"},
        )

    def _call_pdf_chunked(
        self,
        user_prompt: str,
        images: list[bytes],
    ) -> list[dict]:
        """Split images into chunks and call the LLM once per chunk.

        Handles output truncation automatically: if finish_reason == \"length\",
        the chunk is split in half and both halves are retried.

        Returns a list of parsed dicts, one per successful chunk.
        The caller is responsible for merging them.
        """
        max_per_call = self._get_max_images_per_call()
        overlap = 1  # páginas sobrepostas entre chunks consecutivos
        total_pages = len(images)
        # Calcular chunks com sliding window
        if total_pages <= max_per_call:
            num_chunks = 1
        else:
            stride = max_per_call - overlap
            num_chunks = 1 + ((total_pages - max_per_call + stride - 1) // stride)

        logger.info(
            "pdf_chunked_extraction_start",
            total_pages=total_pages,
            chunk_size=max_per_call,
            num_chunks=num_chunks,
            prompt_length=len(user_prompt),
        )

        chunks_data: list[dict] = []
        last_item: Optional[dict] = None  # Para overlap entre chunks

        for chunk_idx in range(num_chunks):
            stride = max_per_call - overlap
            start = chunk_idx * stride
            end = min(start + max_per_call, total_pages)
            chunk_images = images[start:end]

            logger.info("pdf_chunk_start", chunk_idx=chunk_idx, page_start=start, page_end=end, images=len(chunk_images))

            chunk_prompt = user_prompt + self._get_chunk_annotation(
                start, end, total_pages,
            )

            content = self._build_content(
                chunk_prompt, chunk_images,
            )

            logger.debug(
                "pdf_chunk_content_built",
                chunk_idx=chunk_idx,
                content_blocks=len(content),
                text_blocks=sum(1 for c in content if c.get('type') == 'text'),
                image_blocks=sum(1 for c in content if c.get('type') == 'image_url'),
            )

            system_prompt = self._get_system_prompt()

            try:
                response = self._call_openai_with_retry(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": content},
                    ]
                )
            except (RateLimitError, APITimeoutError, APIError) as e:
                logger.warning(
                    "pdf_chunk_failed",
                    chunk_idx=chunk_idx,
                    pages=f"{start + 1}-{end}",
                    error=str(e),
                )
                continue

            finish_reason = response.choices[0].finish_reason
            raw_text = response.choices[0].message.content or ""
            logger.info(
                "pdf_chunk_response",
                chunk_idx=chunk_idx,
                pages=f"{start + 1}-{end}",
                finish_reason=finish_reason,
                raw_length=len(raw_text),
            )
            logger.debug("pdf_chunk_raw_response", chunk_idx=chunk_idx, raw_text=raw_text)

            parsed = self._parse_response(raw_text)
            logger.debug("pdf_chunk_parsed", chunk_idx=chunk_idx, parsed_keys=list(parsed.keys()) if isinstance(parsed, dict) else "NOT_A_DICT")
            chunks_data.append(parsed)

            # Guardar último item para overlap no próximo chunk
            last_item = self._extract_last_item(parsed)

        logger.info("pdf_chunked_extraction_complete", successful_chunks=len(chunks_data))

        return chunks_data

    async def extract(
        self,
        document: Document,
        custom_prompt: Optional[str] = None,
        method: str = "pdf_images",
    ) -> list[dict]:
        """
        Extract data from document using Azure OpenAI.

        Returns a **list of chunk dicts** so each extractor can apply
        its own merge logic (since each has a different JSON structure).

        method options:
        - "pdf_images"         → single API call, returns [parsed_dict]
        - "pdf_images_chunked" → one call per chunk, returns [chunk0, chunk1, ...]
        - "pdf_docling"        → text via Docling, returns [parsed_dict]
        """
        t_start = time.time()

        logger.info(
            "llm_extract_start",
            filename=document.filename,
            method=method,
            has_custom_prompt=bool(custom_prompt),
        )

        # 1. Prepare prompt
        user_prompt = self._prepare_prompt(custom_prompt)

        # 2. Process document
        images: Optional[list[bytes]] = None
        doc_text: Optional[str] = None

        if method in ("pdf_images", "pdf_images_chunked"):
            images = self._process_pdf(document)
            logger.info("llm_extract_pdf_processed", images=len(images))
        elif method == "pdf_docling":
            doc_text = self.safe_docling_extract(document)
        else:
            raise ValueError(f"Invalid extract method: {method}")

        # 3. Call Azure OpenAI
        t_api_start = time.time()
        try:
            if method == "pdf_images_chunked":
                chunks = self._call_pdf_chunked(user_prompt, images)
                logger.info("llm_extract_chunked_complete", chunks=len(chunks))
                return chunks

            if method == "pdf_images":
                content = self._build_content(
                    user_prompt, images,
                )
            else:
                content = [
                    {"type": "text", "text": user_prompt},
                    {"type": "text", "text": doc_text},
                ]

            system_prompt = self._get_system_prompt()
            logger.debug(
                "llm_extract_single_call_content",
                system_prompt_length=len(system_prompt),
                content_blocks=len(content),
                text_blocks=sum(1 for c in content if c.get('type') == 'text'),
                image_blocks=sum(1 for c in content if c.get('type') == 'image_url'),
            )

            response = self._call_openai_with_retry(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": content},
                ]
            )
        except RateLimitError as e:
            raise RuntimeError(
                "Azure OpenAI rate limit exceeded. Please try again later."
            ) from e
        except APITimeoutError as e:
            raise RuntimeError(
                "Azure OpenAI timeout after multiple retry attempts."
            ) from e
        except APIError as e:
            raise RuntimeError(f"Azure OpenAI API error: {str(e)}") from e

        api_duration = time.time() - t_api_start
        raw_text = response.choices[0].message.content or ""
        logger.info("llm_extract_api_response", duration_seconds=round(api_duration, 2), raw_length=len(raw_text))
        logger.debug("llm_extract_raw_response", raw_text=raw_text)

        # 4. Parse response
        data = self._parse_response(raw_text)

        # 5. Post-process
        data = self._post_process_data(data)

        logger.info("llm_extract_single_call_complete")
        return [data]

    def run_docling(self, path: str, return_dict: dict):
        try:
            from irpf_processor.infrastructure.extraction.ocr import DoclingEngine

            engine = DoclingEngine(timeout=1200, vision_model="smoldocling")
            if engine.is_available():
                logger.info("Docling engine available")

        except ImportError:
            logger.info("Docling not installed")


        result = engine.extract(path)
        logger.info("docling_extraction_complete", text_length=len(result.text) if result else 0)
        return_dict["text"] = result.text

    
    def safe_docling_extract(self, document: Document):

        manager = mp.Manager()
        d = manager.dict()

        p = mp.Process(target=self.run_docling, args=(document.storage_uri, d))
        p.start()
        p.join()

        if p.exitcode != 0:
            raise RuntimeError("Docling failed in subprocess")

        return d["text"]


    async def health_check(self) -> bool:
        """Check Azure OpenAI connectivity."""
        try:
            client = self._get_client()
            # Lightweight operation to verify connectivity
            await client.models.list()
            return True
        except Exception as e:
            return False
