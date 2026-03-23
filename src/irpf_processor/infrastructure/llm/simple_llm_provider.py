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

from openai import AzureOpenAI, RateLimitError, APIError, APITimeoutError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from irpf_processor.domain.entities.document import Document
from irpf_processor.domain.entities.extraction_result import ExtractionResult
from irpf_processor.infrastructure.config.doc_extractor_config import settings

from irpf_processor.infrastructure.utils import make_image_content
from irpf_processor.infrastructure.utils.pdf import pdf_to_images
from irpf_processor.infrastructure.utils.sanitizers import extract_json_from_text

# Fixed seed for reproducibility
_FIXED_SEED = 20260212

# Default system and user prompts (can be overridden by subclasses)
DEFAULT_SYSTEM_PROMPT = "You are an expert document extraction assistant."
DEFAULT_USER_PROMPT = "Extract all relevant data from the provided document in JSON format."


class SimpleLLMProvider(ABC):
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
        if not settings.azure_openai_api_key:
            raise RuntimeError(
                "AZURE_OPENAI_API_KEY not configured. "
                "Set it in .env or as environment variable."
            )
        if not settings.azure_openai_endpoint:
            raise RuntimeError(
                "AZURE_OPENAI_ENDPOINT not configured. "
                "Set it in .env or as environment variable."
            )

    def _get_client(self) -> AzureOpenAI:
        """Get or create Azure OpenAI client (singleton)."""
        if self._client is None:
            self._client = AzureOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                api_key=settings.azure_openai_api_key,
                api_version=settings.azure_openai_api_version,
            )
        return self._client

    def _get_system_prompt(self) -> str:
        """Return the system prompt to use.
        Override in subclasses to customize."""
        return DEFAULT_SYSTEM_PROMPT

    def _prepare_prompt(self, custom_prompt: Optional[str] = None) -> str:
        """Prepare the user prompt.
        Override in subclasses to customize."""
        prompt = DEFAULT_USER_PROMPT
        if custom_prompt:
            prompt += f"\n\nAdditional instructions:\n{custom_prompt}"
        return prompt

    def _post_process_data(self, data: dict) -> dict:
        """Post-process extracted data.
        Override in subclasses to apply sanitization, validation, etc."""
        return data

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

        return content

    def _process_pdf(self, document: Document) -> list[bytes]:
        """Convert PDF to images."""
        images = pdf_to_images(document.content, dpi=settings.pdf_dpi)
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
            model=settings.azure_openai_deployment,
            messages=messages,
            max_tokens=32768,
            temperature=0,
            top_p=1,
            seed=_FIXED_SEED,
            response_format={"type": "json_object"},
        )

    async def extract(
        self,
        document: Document,
        custom_prompt: Optional[str] = None,
    ) -> ExtractionResult:
        """
        Extract data from document using Azure OpenAI.
        
        Flow:
        1. Prepare prompt
        2. Process document (PDF → images, etc.)
        3. Call Azure OpenAI
        4. Parse response
        5. Post-process
        6. Return ExtractionResult
        """
        t_start = time.time()

        # 1. Prepare prompt
        user_prompt = self._prepare_prompt(custom_prompt)

        # 2. Process document
        images: Optional[list[bytes]] = None
        images = self._process_pdf(document)

        # 3. Call Azure OpenAI
        t_api_start = time.time()
        try:
            content = self._build_content(user_prompt, images)
            response = self._call_openai_with_retry(
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
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

        # 4. Parse response
        data = self._parse_response(raw_text)

        # 5. Post-process
        data = self._post_process_data(data)

        total_time = time.time() - t_start

        result = ExtractionResult.from_extraction(
            document_filename=document.filename,
            extracted_data=data,
            processing_time=round(total_time, 3),
        )

        return result

    async def health_check(self) -> bool:
        """Check Azure OpenAI connectivity."""
        try:
            client = self._get_client()
            # Lightweight operation to verify connectivity
            await client.models.list()
            return True
        except Exception as e:
            return False
