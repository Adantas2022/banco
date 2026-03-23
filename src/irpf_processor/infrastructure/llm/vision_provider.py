"""Adapter - Implementação Azure OpenAI do LLMProvider.

Este adapter implementa a interface LLMProvider usando Azure OpenAI GPT-4o.
Migrado de app/extractor.py para seguir arquitetura DDD.
"""

import json
import time
from typing import Any

from openai import AzureOpenAI, RateLimitError, APIError, APITimeoutError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from src.application.interfaces.llm_provider import LLMProvider
from src.infrastructure.config.doc_extractor_config import settings
from src.domain.models.document import Document, DocumentType
from src.domain.models.extraction import (
    ExtractionResult,
    Confianca,
    ProcessingMetrics,
    QualityMetrics,
)
from src.infrastructure.observability.logging import get_logger
from src.infrastructure.observability.langfuse import observe
from src.infrastructure.observability.metrics import (
    API_CALL_DURATION,
    PDF_CONVERSION_DURATION,
    PDF_PAGES,
)

from src.domain.prompts.doc_extractor.system import SYSTEM_PROMPT
from src.domain.prompts.doc_extractor.extraction_full import EXTRACTION_PROMPT

from src.infrastructure.utils import make_image_content, IMAGE_MIMES
from src.infrastructure.utils.pdf import pdf_to_images
from src.infrastructure.utils.office_processors import extract_xlsx_content, extract_docx_content
from src.infrastructure.utils.qr_decoder import decode_qr_from_bytes, decode_qr_all_pages, build_qr_context
from src.infrastructure.utils.sanitizers import sanitize_output, extract_json_from_text
from src.infrastructure.utils.helpers import count_fields
from src.domain.validators.dre_validators import add_dre_totals

logger = get_logger("doc-extractor.infrastructure.azure_openai")

# Seed fixo para reprodutibilidade
_FIXED_SEED = 20260212

# Azure OpenAI aceita no máximo 50 imagens por chamada; usamos 45 por segurança.
_MAX_IMAGES_PER_CALL = 45

# Chaves cujos arrays de períodos devem ser mesclados entre chunks
_PERIODOS_KEYS = (
    "dre",
    "balanco_patrimonial",
    "fluxo_caixa",
    "mutacoes_patrimonio_liquido",
    "balanco_pagamentos",
)


class AzureOpenAIProvider(LLMProvider):
    """
    Implementação Azure OpenAI do LLMProvider.
    
    Características:
    - GPT-4o com visão
    - Retry automático (3 tentativas)
    - Seed fixo para reprodutibilidade
    - Suporte a PDF, imagens e texto
    """
    
    def __init__(self):
        """Inicializa o provider Azure OpenAI."""
        self._client: AzureOpenAI | None = None
        self._validate_config()
    
    def _validate_config(self) -> None:
        """Valida configuração do Azure OpenAI."""
        if not settings.azure_openai_api_key:
            raise RuntimeError(
                "AZURE_OPENAI_API_KEY não configurada. "
                "Defina no .env ou como variável de ambiente."
            )
        if not settings.azure_openai_endpoint:
            raise RuntimeError(
                "AZURE_OPENAI_ENDPOINT não configurado. "
                "Defina no .env ou como variável de ambiente."
            )
    
    def _get_client(self) -> AzureOpenAI:
        """Retorna cliente Azure OpenAI (singleton)."""
        if self._client is None:
            self._client = AzureOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                api_key=settings.azure_openai_api_key,
                api_version=settings.azure_openai_api_version,
            )
        return self._client
    
    @staticmethod
    def _merge_chunked_data(chunks: list[dict]) -> dict:
        """
        Mescla resultados de múltiplos chunks de páginas em um único dict.

        Regras:
        - Metadados (tipo_documento, empresa, cnpj, etc.) vêm do primeiro chunk
          que os tiver preenchidos.
        - Para cada seção que contenha 'periodos' (dre, balanco_patrimonial, etc.):
          acumula todos os itens e deduplica por (ano, entidade), mantendo o
          último valor encontrado (chunks posteriores têm mais contexto).
        - Campos escalares de todos os chunks são mesclados com 'último valor
          não-nulo vence'.
        """
        if not chunks:
            return {}
        if len(chunks) == 1:
            return chunks[0]

        merged: dict = {}

        # Metadados escalares — primeiro chunk não-nulo vence
        scalar_keys = (
            "tipo_documento", "tipo_balanco", "confianca",
            "empresa", "cnpj", "periodo_inicio", "periodo_fim",
        )
        for key in scalar_keys:
            for chunk in chunks:
                if chunk.get(key) is not None:
                    merged[key] = chunk[key]
                    break

        # Seções com periodos — acumula e deduplica
        for section_key in _PERIODOS_KEYS:
            all_periodos: list[dict] = []
            section_meta: dict = {}  # dados fora do array periodos

            for chunk in chunks:
                section = chunk.get(section_key)
                if not isinstance(section, dict):
                    continue
                # Copia metadados da seção (ex: 'pais' no balanco_pagamentos)
                for k, v in section.items():
                    if k != "periodos":
                        section_meta[k] = v
                all_periodos.extend(
                    p for p in section.get("periodos", []) if isinstance(p, dict)
                )

            if all_periodos:
                # Deduplica por (ano, entidade) — campo não-nulo vence
                # (nunca sobrescrever valor preenchido com null de outro chunk)
                seen: dict[tuple, dict] = {}
                for p in all_periodos:
                    entidade = (p.get("entidade") or "unico").lower()
                    ano = p.get("ano") or p.get("exercicio")
                    key_tuple = (str(ano), entidade)
                    if key_tuple not in seen:
                        seen[key_tuple] = dict(p)
                    else:
                        base = seen[key_tuple]
                        # Mescla "valores" sub-dict: campo não-nulo sempre vence
                        new_vals = p.get("valores") or {}
                        base_vals = base.get("valores") or {}
                        if new_vals or base_vals:
                            merged_vals: dict = {**base_vals}
                            for k, v in new_vals.items():
                                # Sobrescreve apenas se novo valor não for None
                                # (ou se o campo ainda não estiver no base)
                                if v is not None:
                                    merged_vals[k] = v
                                elif k not in merged_vals:
                                    merged_vals[k] = v
                            base["valores"] = merged_vals
                        # Mescla campos de nível período (ano, entidade, datas…)
                        for k, v in p.items():
                            if k != "valores" and v is not None and base.get(k) is None:
                                base[k] = v
                        seen[key_tuple] = base
                deduped = list(seen.values())
                logger.info(
                    "chunked_merge_periodos",
                    section=section_key,
                    total_raw=len(all_periodos),
                    deduped=len(deduped),
                    anos_entidades=[
                        f"{p.get('ano')}/{p.get('entidade')}" for p in deduped
                    ],
                )
                merged[section_key] = {**section_meta, "periodos": deduped}

        # Outros campos de topo nao mapeados — copiar de qualquer chunk
        for chunk in chunks:
            for key, val in chunk.items():
                if key not in merged:
                    merged[key] = val

        return merged

    def _call_pdf_chunked(
        self,
        document: Document,
        user_prompt: str,
        images: list[bytes],
        qr_payloads: list[str] | None,
    ) -> tuple[dict, ProcessingMetrics]:
        """
        Divide as imagens do PDF em chunks de _MAX_IMAGES_PER_CALL páginas,
        faz uma chamada por chunk e mescla os resultados.
        """
        chunks_data: list[dict] = []
        total_tokens_input = 0
        total_tokens_output = 0
        total_api_duration = 0.0
        total_images_sent = 0

        num_chunks = (len(images) + _MAX_IMAGES_PER_CALL - 1) // _MAX_IMAGES_PER_CALL
        logger.info(
            "pdf_chunked_extraction_start",
            filename=document.filename,
            total_pages=len(images),
            num_chunks=num_chunks,
        )

        for chunk_idx in range(num_chunks):
            start = chunk_idx * _MAX_IMAGES_PER_CALL
            end = min(start + _MAX_IMAGES_PER_CALL, len(images))
            chunk_images = images[start:end]

            # Informa o LLM que está vendo um trecho do documento
            chunk_prompt = user_prompt + self._get_chunk_annotation(start, end, len(images))
            # QR payloads apenas no primeiro chunk
            chunk_qr = qr_payloads if chunk_idx == 0 else None
            content = self._build_content(document, chunk_prompt, chunk_images, chunk_qr)

            t_chunk_start = time.time()
            try:
                response = self._call_openai_with_retry(
                    messages=[
                        {"role": "system", "content": self._get_system_prompt()},
                        {"role": "user", "content": content},
                    ]
                )
            except (RateLimitError, APITimeoutError, APIError) as e:
                logger.warning(
                    "pdf_chunk_failed",
                    chunk_idx=chunk_idx,
                    pages=f"{start+1}-{end}",
                    error=str(e),
                )
                continue  # Tenta próximo chunk mesmo se este falhar

            chunk_duration = time.time() - t_chunk_start
            total_api_duration += chunk_duration
            total_images_sent += len(chunk_images)

            if response.usage:
                total_tokens_input += response.usage.prompt_tokens
                total_tokens_output += response.usage.completion_tokens

            raw_text = response.choices[0].message.content or ""
            logger.info(
                "chunk_response_preview",
                chunk_idx=chunk_idx,
                pages=f"{start+1}-{end}",
                preview=raw_text[:1500],
            )
            chunk_data = self._parse_response(raw_text)
            chunks_data.append(chunk_data)

            logger.info(
                "pdf_chunk_extracted",
                filename=document.filename,
                chunk_idx=chunk_idx,
                pages=f"{start+1}-{end}",
                duration_s=round(chunk_duration, 2),
            )

        merged_data = self._merge_chunked_data(chunks_data)
        metrics = ProcessingMetrics(
            tokens_input=total_tokens_input,
            tokens_output=total_tokens_output,
            tokens_total=total_tokens_input + total_tokens_output,
            api_call_duration_seconds=round(total_api_duration, 3),
            images_sent=total_images_sent,
            qr_codes_decoded=len(qr_payloads) if qr_payloads else 0,
        )
        return merged_data, metrics

    @retry(
        retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    def _call_openai_with_retry(
        self,
        messages: list[dict],
    ) -> Any:
        """
        Chama Azure OpenAI com retry exponential backoff.
        
        Configuração:
        - 3 tentativas máximas
        - Backoff: 2s, 4s, 8s, ... até 30s
        - Apenas para rate limit, timeout e API errors
        """
        client = self._get_client()
        logger.info("azure_openai_call_attempt", model=settings.azure_openai_deployment)
        
        return client.chat.completions.create(
            model=settings.azure_openai_deployment,
            messages=messages,
            max_tokens=32768,
            temperature=0,
            top_p=1,
            seed=_FIXED_SEED,
            response_format={"type": "json_object"},
        )
    
    def _get_system_prompt(self) -> str:
        """Retorna o system prompt a usar na chamada ao LLM.
        Subclasses podem sobrescrever para usar um system prompt diferente."""
        return SYSTEM_PROMPT

    def _post_process_data(self, data: dict) -> dict:
        """Pós-processa o dict extraído pelo LLM.
        Subclasses podem sobrescrever para aplicar (ou pular) etapas específicas."""
        data, _ = sanitize_output(data)
        data = add_dre_totals(data)
        return data

    def _get_chunk_annotation(self, start: int, end: int, total: int) -> str:
        """Retorna o texto de anotação para chamadas em chunk.
        Subclasses podem sobrescrever para adaptar a língua/contexto do chunk."""
        return (
            f"\n\nATENÇÃO: Você está analisando as páginas {start + 1} a {end} "
            f"de um documento de {total} páginas no total. "
            "Extraia TODOS os dados financeiros visíveis nestas páginas usando o mesmo schema JSON. "
            "Não trunque os arrays de períodos — inclua todos os anos/entidades visíveis.\n\n"
            "REGRAS PARA EXTRAÇÃO EM CHUNKS:\n"
            "• Se nestas páginas houver Balanço Patrimonial → preencha `balanco_patrimonial.periodos`\n"
            "• Se nestas páginas houver DRE / Demonstração do Resultado do Exercício → preencha `dre.periodos`\n"
            "• Se nestas páginas houver Demonstração dos Fluxos de Caixa → preencha `fluxo_caixa.periodos`\n"
            "• OMITA a chave de uma seção SOMENTE se ela não aparecer de forma alguma nestas páginas.\n"
            "• Para seções PRESENTES: preencha TODOS os valores numéricos visíveis; "
            "use null SOMENTE para campos que genuinamente não constam no documento.\n"
            "• IMPORTANTE: mesmo que `tipo_balanco` seja 'demonstracao_contabil_outro', "
            "você DEVE extrair `dre.periodos` e `fluxo_caixa.periodos` se esses dados forem visíveis nestas páginas. "
            "Nunca retorne uma resposta sem nenhuma seção quando houver dados financeiros nas páginas."
        )

    def _prepare_prompt(self, custom_prompt: str | None) -> str:
        """Prepara prompt do usuário."""
        user_prompt = EXTRACTION_PROMPT
        if custom_prompt:
            user_prompt += f"\n\nInstruções adicionais:\n{custom_prompt}"
        return user_prompt
    
    def _process_pdf(self, document: Document) -> tuple[list[bytes], list[str]]:
        """
        Processa PDF: converte para imagens e decodifica QR codes.
        
        Returns:
            Tuple (images, qr_payloads)
        """
        t_start = time.time()
        images = pdf_to_images(document.content, dpi=settings.pdf_dpi)
        duration = time.time() - t_start
        
        PDF_CONVERSION_DURATION.observe(duration)
        PDF_PAGES.observe(len(images))
        
        logger.info(
            "pdf_converted",
            filename=document.filename,
            pages=len(images),
            duration_seconds=round(duration, 3),
        )
        
        # Decodifica QR codes
        qr_payloads = decode_qr_all_pages(images)
        if qr_payloads:
            logger.info("qr_codes_decoded", count=len(qr_payloads))
        
        return images, qr_payloads
    
    def _process_image(self, document: Document) -> list[str]:
        """
        Processa imagem: decodifica QR codes.
        
        Returns:
            Lista de QR payloads
        """
        qr_payloads = decode_qr_from_bytes(document.content)
        if qr_payloads:
            logger.info("qr_codes_decoded_from_image", count=len(qr_payloads))
        return qr_payloads
    
    def _build_content(
        self,
        document: Document,
        user_prompt: str,
        images: list[bytes] | None = None,
        qr_payloads: list[str] | None = None,
    ) -> list[dict]:
        """Constrói content blocks para Azure OpenAI."""
        # Adiciona QR context ao prompt
        prompt_with_qr = user_prompt
        if qr_payloads:
            qr_context = build_qr_context(qr_payloads)
            if qr_context:
                prompt_with_qr += qr_context
        
        content: list[dict] = [{"type": "text", "text": prompt_with_qr}]
        
        # Adiciona imagens (PDF convertido ou imagem direta)
        if images:
            # PDF: múltiplas imagens (páginas)
            for i, img in enumerate(images):
                content.append(make_image_content(img, "image/png"))
                logger.debug("pdf_page_added", page=i + 1)
        elif document.content_type.value in IMAGE_MIMES:
            # Imagem direta
            content.append(make_image_content(document.content, document.content_type.value))
        elif document.content_type == DocumentType.XLSX:
            # Planilha Excel: converte para representação textual estruturada
            text_content = self._xlsx_to_text(document)
            if text_content:
                content[0]["text"] += f"\n\n--- CONTEÚDO DA PLANILHA ---\n{text_content}\n--- FIM DO CONTEÚDO ---\n"
                logger.info("xlsx_converted_to_text", filename=document.filename, chars=len(text_content))
            else:
                logger.warning("xlsx_to_text_failed", filename=document.filename)
        elif document.content_type == DocumentType.DOCX:
            # Documento Word: converte para representação textual
            text_content = self._docx_to_text(document)
            if text_content:
                content[0]["text"] += f"\n\n--- CONTEÚDO DO DOCUMENTO ---\n{text_content}\n--- FIM DO CONTEÚDO ---\n"
                logger.info("docx_converted_to_text", filename=document.filename, chars=len(text_content))
            else:
                logger.warning("docx_to_text_failed", filename=document.filename)
        elif document.content_type.is_text():
            # Arquivo de texto: adiciona conteúdo como texto
            text_content = self._decode_text(document.content)
            if text_content:
                content[0]["text"] += f"\n\n--- CONTEÚDO DO ARQUIVO ---\n{text_content}\n--- FIM DO CONTEÚDO ---\n"
            else:
                # Fallback: tenta como imagem
                logger.warning("text_decode_failed", filename=document.filename)
                content.append(make_image_content(document.content, document.content_type.value))
        else:
            # Outros formatos: tenta como imagem (fallback)
            content.append(make_image_content(document.content, document.content_type.value))
        
        return content
    
    def _xlsx_to_text(self, document: Document) -> str | None:
        """Converte planilha XLSX para representação textual para o LLM."""
        try:
            xlsx_content = extract_xlsx_content(document.content, max_rows_per_sheet=5000)
            parts: list[str] = []

            for sheet in xlsx_content.sheets:
                name = sheet.get("name", "")
                parts.append(f"=== ABA: {name} ===")

                # Metadados pré-header
                metadata = sheet.get("sheet_metadata")
                if metadata:
                    for k, v in metadata.items():
                        parts.append(f"{k}: {v}")
                    parts.append("")

                layout = sheet.get("layout", "flat")

                if layout == "side_by_side" and sheet.get("sections"):
                    # Layout lado a lado (ex: Balanço Patrimonial)
                    for section in sheet["sections"]:
                        label_col = section.get("label_column", "conta")
                        value_col = section.get("value_column", "valor")
                        parts.append(f"-- {label_col} | {value_col} --")
                        for row in section.get("rows", []):
                            conta = row.get("conta") or ""
                            valor = row.get(value_col, row.get("valor", ""))
                            if conta or valor is not None:
                                parts.append(f"  {conta}\t{valor}")
                        parts.append("")
                else:
                    # Layout plano (DRE, Fluxo de Caixa, etc.)
                    header = sheet.get("header", [])
                    if header:
                        parts.append("\t".join(str(h) for h in header))
                        parts.append("-" * 80)
                    for row in sheet.get("rows", []):
                        vals = [str(row.get(h, "") or "") for h in header]
                        line = "\t".join(vals)
                        if line.strip().replace("\t", ""):
                            parts.append(line)
                    parts.append("")

            return "\n".join(parts)
        except Exception as exc:
            logger.warning("xlsx_to_text_error", filename=document.filename, error=str(exc))
            return None

    def _docx_to_text(self, document: Document) -> str | None:
        """Converte documento DOCX para representação textual para o LLM."""
        try:
            docx_content = extract_docx_content(document.content)
            parts: list[str] = []

            if docx_content.full_text:
                parts.append(docx_content.full_text)

            for table in docx_content.tables:
                header = table.get("header", [])
                if header:
                    parts.append("\t".join(str(h) for h in header))
                for row in table.get("rows", []):
                    parts.append("\t".join(str(c) for c in row))
                parts.append("")

            return "\n".join(parts)
        except Exception as exc:
            logger.warning("docx_to_text_error", filename=document.filename, error=str(exc))
            return None

    def _decode_text(self, content: bytes) -> str | None:
        """Tenta decodificar bytes como texto (múltiplas encodings)."""
        for encoding in ["utf-8", "latin-1", "cp1252", "iso-8859-1"]:
            try:
                text = content.decode(encoding)
                logger.info("text_decoded", encoding=encoding, length=len(text))
                return text
            except (UnicodeDecodeError, AttributeError):
                continue
        return None
    
    def _parse_response(self, raw_text: str) -> dict[str, Any]:
        """Parseia response do LLM (com fallback)."""
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            # Tenta extrair JSON
            cleaned = extract_json_from_text(raw_text)
            if cleaned:
                return json.loads(cleaned)
            
            logger.warning("json_parse_failed", raw_length=len(raw_text))
            return {"raw_text": raw_text, "parse_error": True}
    
    @observe(name="azure_openai_extract")
    async def extract(
        self,
        document: Document,
        custom_prompt: str | None = None,
    ) -> ExtractionResult:
        """
        Extrai dados do documento usando Azure OpenAI.
        
        Fluxo:
        1. Prepara prompt
        2. Processa documento (PDF → imagens, QR codes, etc)
        3. Chama Azure OpenAI
        4. Parseia response
        5. Pós-processa (sanitização, validadores)
        6. Retorna ExtractionResult
        """
        t_start = time.time()
        
        logger.info(
            "extraction_started",
            filename=document.filename,
            content_type=document.content_type.value,
            size=str(document.size),
        )
        
        # 1. Prepara prompt
        user_prompt = self._prepare_prompt(custom_prompt)
        
        # 2. Processa documento
        images: list[bytes] | None = None
        qr_payloads: list[str] | None = None
        
        if document.content_type == DocumentType.PDF:
            images, qr_payloads = self._process_pdf(document)
        elif document.content_type.value in IMAGE_MIMES:
            qr_payloads = self._process_image(document)
        
        # 3. Chama Azure OpenAI (chunked se necessário)
        t_api_start = time.time()
        try:
            if images and len(images) > _MAX_IMAGES_PER_CALL:
                logger.info(
                    "pdf_exceeds_limit_using_chunks",
                    filename=document.filename,
                    total_pages=len(images),
                    max_per_call=_MAX_IMAGES_PER_CALL,
                )
                data, processing_metrics = self._call_pdf_chunked(
                    document, user_prompt, images, qr_payloads
                )
                api_duration = processing_metrics.api_call_duration_seconds
            else:
                # Caminho padrão: chamada única
                content = self._build_content(document, user_prompt, images, qr_payloads)
                try:
                    response = self._call_openai_with_retry(
                        messages=[
                            {"role": "system", "content": self._get_system_prompt()},
                            {"role": "user", "content": content},
                        ]
                    )
                except RateLimitError as e:
                    logger.error("rate_limit_exceeded", error=str(e))
                    raise RuntimeError(
                        "Limite de quota do Azure OpenAI excedido. Tente novamente mais tarde."
                    ) from e
                except APITimeoutError as e:
                    logger.error("api_timeout", error=str(e))
                    raise RuntimeError(
                        "Timeout na chamada ao Azure OpenAI após várias tentativas."
                    ) from e
                except APIError as e:
                    logger.error("api_error", error=str(e))
                    raise RuntimeError(f"Erro na API do Azure OpenAI: {str(e)}") from e

                api_duration = time.time() - t_api_start
                API_CALL_DURATION.observe(api_duration)

                raw_text = response.choices[0].message.content or ""
                logger.info("response_preview", preview=raw_text[:2000])
                data = self._parse_response(raw_text)

                processing_metrics = ProcessingMetrics(
                    tokens_input=response.usage.prompt_tokens if response.usage else 0,
                    tokens_output=response.usage.completion_tokens if response.usage else 0,
                    tokens_total=response.usage.total_tokens if response.usage else 0,
                    api_call_duration_seconds=round(api_duration, 3),
                    images_sent=len([c for c in content if c.get("type") == "image_url"]),
                    qr_codes_decoded=len(qr_payloads) if qr_payloads else 0,
                )
        except RuntimeError:
            raise  # Repassa erros já tratados
        except Exception as e:
            logger.error("extraction_unexpected_error", error=str(e))
            raise RuntimeError(f"Erro inesperado na extração: {str(e)}") from e

        # 4. Pós-processa
        data = self._post_process_data(data)
        sanitize_metrics: dict = {}

        # 5. Constrói quality metrics
        quality_metrics = QualityMetrics(
            fields_extracted=count_fields(data),
            json_parse_success="parse_error" not in data,
            sanitization_applied=sanitize_metrics.get("fields_removed", 0) > 0,
            fields_removed=sanitize_metrics.get("fields_removed", 0),
        )

        # 6. Cria ExtractionResult
        total_time = time.time() - t_start

        result = ExtractionResult.from_extraction(
            document_filename=document.filename,
            extracted_data=data,
            processing_time=round(total_time, 3),
            processing_metrics=processing_metrics,
            quality_metrics=quality_metrics,
        )

        logger.info(
            "extraction_completed",
            filename=document.filename,
            tipo_documento=result.tipo_documento,
            confianca=result.confianca.valor,
            fields=quality_metrics.fields_extracted,
            duration_seconds=result.processing_time_seconds,
        )

        return result
    
    async def health_check(self) -> bool:
        """Verifica saúde do Azure OpenAI."""
        try:
            client = self._get_client()
            # Tenta listar modelos (operação leve)
            await client.models.list()
            return True
        except Exception as e:
            logger.warning("health_check_failed", error=str(e))
            return False
