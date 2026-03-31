"""Interface base para extratores de seção - Strategy Pattern."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional
from pathlib import Path
import tempfile, os, asyncio
from pypdf import PdfWriter, PdfReader
from ..table_extractor import parse_currency
from irpf_processor.config import get_settings
from irpf_processor.shared.logging import get_logger

logger = get_logger(__name__)


# Descobre raiz do projeto automaticamente
PROJECT_ROOT = Path(__file__).resolve().parents[4]
TMP_DIR = PROJECT_ROOT / "tmp"
TMP_DIR.mkdir(exist_ok=True)


@dataclass
class ExtractionContext:
    """Contexto compartilhado entre extratores."""
    
    full_text: str
    pages_text: dict[int, str]
    total_pages: int = 0
    pdf_path: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    
    def add_warning(self, message: str) -> None:
        self.warnings.append(message)
    
    def get_page_text(self, page_num: int) -> str:
        return self.pages_text.get(page_num, "")
    
    def find_pages_containing(self, text: str) -> list[int]:
        return [
            page_num 
            for page_num, page_text in self.pages_text.items()
            if text.upper() in page_text.upper()
        ]


class ISectionExtractor(ABC):
    """Interface para extratores de seção (Strategy Pattern)."""

    LLM_PROMPT = ""
    SECTION_MARKERS = []
    SECTION_END_MARKERS = []

    @property
    def llm_extraction_enabled(self) -> bool:
        """Check if LLM extraction is enabled for this section via env var."""
        settings = get_settings()
        key = f"llm_extraction_{self.section_name}"
        return getattr(settings, key, False)

    @property
    @abstractmethod
    def section_name(self) -> str:
        """Nome da seção que este extrator processa."""
        pass
    
    @abstractmethod
    def can_extract(self, context: ExtractionContext) -> bool:
        """Verifica se há dados desta seção no documento."""
        pass
    
    @abstractmethod
    def extract(self, context: ExtractionContext) -> Optional[dict[str, Any]]:
        """Extrai dados da seção."""
        pass

    def extract_section_pages(self, context: ExtractionContext) -> dict[int, str]:
        """
        Extract page numbers from SECTION_MARKERS until SECTION_END_MARKERS.
        
        Returns a dict mapping page numbers to their text for the section.
        
        Args:
            context: ExtractionContext with document pages
            
        Returns:
            Dict of {page_number: page_text} (0-indexed) in the section, or empty dict if not found
        """
        section_pages: dict[int, str] = {}
        sorted_pages = sorted(context.pages_text.items(), key=lambda x: x[0])
        
        # Temporarily manage state for this operation
        original_section_started = self._section_started
        original_section_start_page = self._section_start_page
        
        try:
            self._section_started = False
            self._section_start_page = -1
            
            for page_idx, (page_num, page_text) in enumerate(sorted_pages):
                upper_text = page_text.upper()
                
                # Check for section start
                if not self._section_started and any(marker in upper_text for marker in self.SECTION_MARKERS):
                    self._section_started = True
                    self._section_start_page = page_num
                    section_pages[page_num] = page_text
                    continue
                
                # Only process if section has started
                if not self._section_started:
                    continue
                
                # Check for section end
                if self._has_section_end_heading(page_text, page_num):
                    section_pages[page_num] = page_text  # incluir página de fronteira
                    break
                
                # Add pages within the section
                section_pages[page_num] = page_text
        
        finally:
            # Restore original state
            self._section_started = original_section_started
            self._section_start_page = original_section_start_page
        
        return section_pages

    def save_section_pages_as_pdf(self, context: ExtractionContext, pages: list[int]) -> str:
        """
        Create a temporary PDF file from selected pages.
        
        Args:
            context: ExtractionContext with PDF path
            pages: List of page numbers (0-indexed) to include in temp PDF
            
        Returns:
            Path to the temporary PDF file, or None if creation failed
        """
        selected_pages = set(pages)
        temp_pdf_path = None
        
        if not context.pdf_path:
            context.add_warning(f"Cannot create temp PDF: pdf_path is None (OCR flow may not have provided it)")
            return temp_pdf_path
        
        if not selected_pages:
            context.add_warning(f"Cannot create temp PDF: no pages selected")
            return temp_pdf_path
        
        if context.pdf_path and selected_pages:
            try:
                reader = PdfReader(context.pdf_path)
                writer = PdfWriter()
                
                for page_num in sorted(selected_pages):
                    if 0 <= page_num < len(reader.pages):
                        writer.add_page(reader.pages[page_num - 1])  # reader is 0-indexed, but page_num is 1-indexed
                
                with tempfile.NamedTemporaryFile(
                    suffix=".pdf",
                    delete=False,
                    dir=TMP_DIR
                ) as tmp:
                    writer.write(tmp)
                    temp_pdf_path = tmp.name
                    logger.info("temp_pdf_created", path=temp_pdf_path, pages=sorted(selected_pages))

            except Exception as e:
                context.add_warning(f"Failed to create temporary PDF: {str(e)}")
                
        return temp_pdf_path
    
    async def get_llm_extraction_data(
        self, 
        context: ExtractionContext,
        custom_prompt: Optional[str] = None
    ) -> Optional[list[dict]]:
        """
        Extract section using LLM (with temp PDF from selected pages).
        
        Returns a list of chunk dicts (one per LLM call). Each extractor
        is responsible for merging the chunks according to its own JSON schema.
        
        Returns None if extraction fails.
            custom_prompt: Optional custom prompt to pass to the LLM provider
            
        Returns:
            Dictionary with extracted data in the same format as extract() method,
            or None if extraction fails
        """
        try:
            # Step 1: Extract section pages
            section_pages = self.extract_section_pages(context)
            if not section_pages:
                context.add_warning("No assets section pages found")
                return None
            
            # Step 2: Create temporary PDF with selected pages
            temp_pdf_path = self.save_section_pages_as_pdf(context, list(section_pages.keys()))
            
            if not temp_pdf_path:
                context.add_warning("Failed to create temporary PDF for LLM extraction")
                return None
            
            try:
                # Step 3: Read temp PDF and create Document object
                with open(temp_pdf_path, "rb") as f:
                    pdf_content = f.read()
                
                # Import Document here to avoid circular imports
                from irpf_processor.domain.entities.document import Document
                from irpf_processor.domain.enums import DocumentStatus
                doc = Document(
                    tenant_id="llm_extraction",
                    filename=os.path.basename(context.pdf_path),
                    content_type="application/pdf",
                    storage_uri=temp_pdf_path,
                    status=DocumentStatus.RECEIVED
                )
                doc.sha256 = Document.calculate_sha256(pdf_content)
                doc.content = pdf_content  # Set content for LLM provider
                
                # Step 4: Use LLMProvider for LLM extraction
                from irpf_processor.infrastructure.llm.llm_provider import LLMProvider
                
                try:
                    context.add_warning(f"[LLM] About to initialize LLMProvider...")
                    provider = LLMProvider()
                    context.add_warning(f"[LLM] LLMProvider initialized successfully")
                except Exception as init_err:
                    context.add_warning(f"[LLM] Failed to initialize provider: {type(init_err).__name__}: {str(init_err)}")
                    raise
                
                # Use the extractor's own LLM_PROMPT if no custom_prompt provided
                user_prompt = custom_prompt or getattr(self, 'LLM_PROMPT', None)
                
                context.add_warning(f"[LLM] Provider initialized, calling extract...")
                
                # Choose method: skip chunking overhead when section fits in a single call
                max_per_call = provider._get_max_images_per_call()
                method = "pdf_images" if len(section_pages) <= max_per_call else "pdf_images_chunked"
                context.add_warning(f"[LLM] Using method={method} ({len(section_pages)} pages, max_per_call={max_per_call})")
                
                # Call LLM extraction (breaking async if needed)
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If already in async context, use run_in_executor
                    chunks = await loop.run_in_executor(
                        None,
                        lambda: asyncio.run(provider.extract(
                            doc, user_prompt, method=method,
                        ))
                    )
                else:
                    chunks = await provider.extract(
                        doc, user_prompt, method=method,
                    )

                logger.info("llm_extract_chunks_returned", chunks_count=len(chunks))

                return chunks

            finally:
                # Clean up temp PDF
                if os.path.exists(temp_pdf_path):
                    try:
                        os.unlink(temp_pdf_path)
                    except Exception as e:
                        context.add_warning(f"Failed to clean up temp PDF: {str(e)}")

        except Exception as e:
            context.add_warning(f"LLM extraction failed: {type(e).__name__}: {str(e)}")
            return None

    def _parse_llm_currency(self, value: Any) -> float:
        """
        Parse currency value from LLM response.
        
        Args:
            value: Value that could be string, float, int, or dict
            
        Returns:
            Float representation of the currency value
        """
        if value is None:
            return 0.0
        
        if isinstance(value, (int, float)):
            return float(value)
        
        if isinstance(value, str):
            return parse_currency(value)
        
        if isinstance(value, dict) and "value" in value:
            return self._parse_llm_currency(value["value"])
        
        return 0.0