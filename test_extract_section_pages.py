#!/usr/bin/env python
"""
Test script for extract_section_pages and get_selected_pages functions.
Tests the assets section extraction independently.
"""

import sys
import os
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from irpf_processor.infrastructure.extraction.extractors.assets import AssetsExtractor
from irpf_processor.infrastructure.extraction.extractors.base import ExtractionContext
from pypdf import PdfReader


def test_extract_section_pages(pdf_path: str) -> None:
    """Test extracting section pages from a PDF."""
    print(f"\n{'='*60}")
    print(f"Testing extract_section_pages")
    print(f"PDF: {pdf_path}")
    print(f"{'='*60}\n")
    
    # Verify PDF exists
    if not os.path.exists(pdf_path):
        print(f"❌ Error: PDF file not found: {pdf_path}")
        return
    
    try:
        # Read PDF and extract text from each page
        reader = PdfReader(pdf_path)
        pages_text = {}
        
        print(f"📄 Reading PDF with {len(reader.pages)} pages...")
        for page_num, page in enumerate(reader.pages):
            text = page.extract_text()
            pages_text[page_num] = text
            print(f"   Page {page_num}: {len(text)} characters")
        
        # Create full text
        full_text = "\n".join(pages_text.values())
        
        # Create extraction context
        context = ExtractionContext(
            pdf_path=pdf_path,
            full_text=full_text,
            pages_text=pages_text
        )
        
        # Initialize extractor
        extractor = AssetsExtractor()
        
        # Check if can extract
        can_extract = extractor.can_extract(context)
        print(f"\n✓ Can extract assets section: {can_extract}")
        
        if not can_extract:
            print("❌ Assets section not found in PDF")
            return
        
        # Extract section pages
        section_pages = extractor.extract_section_pages(context)
        print(f"\n✓ Extracted section pages: {section_pages}")
        
        if not section_pages:
            print("❌ No section pages found")
            return
        
        print(f"✓ Found {len(section_pages)} page(s) in assets section")
        
        # Show page content preview
        print(f"\n📋 Page Content Preview:")
        print(f"{'-'*60}")
        for page_num in section_pages[:min(2, len(section_pages))]:  # Show first 2 pages
            text = pages_text.get(page_num, "")
            preview = text[:300].replace("\n", " ")
            print(f"Page {page_num}: {preview}...")
            print()
        
        # Test get_selected_pages
        print(f"\n{'='*60}")
        print(f"Testing get_selected_pages")
        print(f"{'='*60}\n")
        
        temp_pdf_path = extractor.get_selected_pages(context, section_pages)
        
        if temp_pdf_path:
            print(f"✓ Created temporary PDF: {temp_pdf_path}")
            
            # Verify temp PDF
            temp_reader = PdfReader(temp_pdf_path)
            print(f"✓ Temporary PDF has {len(temp_reader.pages)} page(s)")
            
            # Show summary
            print(f"\n{'='*60}")
            print(f"✅ SUCCESS - Summary")
            print(f"{'='*60}")
            print(f"Original PDF pages: {len(reader.pages)}")
            print(f"Section pages extracted: {len(section_pages)}")
            print(f"Page numbers: {section_pages}")
            print(f"Temporary PDF pages: {len(temp_reader.pages)}")
            print(f"Temporary PDF path: {temp_pdf_path}")
            
        else:
            print(f"❌ Failed to create temporary PDF")
    
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()


async def test_extract_with_llm(pdf_path: str) -> None:
    """Test LLM-based extraction."""
    print(f"\n{'='*60}")
    print(f"Testing extract_with_llm (LLM Extraction)")
    print(f"PDF: {pdf_path}")
    print(f"{'='*60}\n")
    
    # Verify PDF exists
    if not os.path.exists(pdf_path):
        print(f"❌ Error: PDF file not found: {pdf_path}")
        return
    
    try:
        # Read PDF and extract text from each page
        reader = PdfReader(pdf_path)
        pages_text = {}
        
        print(f"📄 Reading PDF with {len(reader.pages)} pages...")
        for page_num, page in enumerate(reader.pages):
            text = page.extract_text()
            pages_text[page_num] = text
        
        # Create full text
        full_text = "\n".join(pages_text.values())
        
        # Create extraction context
        context = ExtractionContext(
            pdf_path=pdf_path,
            full_text=full_text,
            pages_text=pages_text
        )
        
        # Initialize extractor
        extractor = AssetsExtractor()
        
        # Check if can extract
        if not extractor.can_extract(context):
            print("❌ Assets section not found in PDF")
            return
        
        print("⏳ Calling LLM for extraction (this may take a moment)...")
        
        # Call LLM extraction
        result = await extractor.extract_with_llm(context)
        
        if result:
            print(f"\n✅ LLM Extraction Successful!")
            print(f"{'='*60}")
            print(f"Items extracted: {len(result.get('items', []))}")
            print(f"Last year total: {result.get('last_year_total_value')}")
            print(f"Current year total: {result.get('current_year_total_value')}")
            print(f"Extraction method: {result.get('extraction_method', 'unknown')}")
            
            # Show first item as example
            items = result.get('items', [])
            if items:
                print(f"\n📦 First Item Example:")
                print(f"{'-'*60}")
                first_item = items[0]
                for key, value in first_item.items():
                    if not key.startswith('_'):
                        print(f"  {key}: {value}")
        else:
            print("❌ LLM extraction returned no results")
            print("Note: Make sure Azure OpenAI is configured (check .env file)")
    
    except RuntimeError as e:
        print(f"❌ Configuration Error: {str(e)}")
        print("Make sure Azure OpenAI credentials are set in .env:")
        print("  - AZURE_OPENAI_API_KEY")
        print("  - AZURE_OPENAI_ENDPOINT")
        print("  - AZURE_OPENAI_DEPLOYMENT")
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()


def find_pdf_sample() -> str:
    """Find a PDF sample in the project structure."""
    # Try common PDF locations
    pdf_paths = [
        "exemplos/GENESIS/teste_ocr.pdf",
        "exemplos/MARIA_FATIMA/teste_ocr.pdf",
        "exemplos/NATALIA/teste_ocr.pdf",
        "compare/AMOSTR1/0001_IRPF_Maria de Fá tima IRPF 2025 - Declarac¸a~o_resultado.pdf",
    ]
    
    root = Path(__file__).parent
    for pdf_path in pdf_paths:
        full_path = root / pdf_path
        if full_path.exists():
            return str(full_path)
    
    # Try to find any PDF in exemplos
    exemplos = root / "exemplos"
    if exemplos.exists():
        for pdf in exemplos.rglob("*.pdf"):
            return str(pdf)
    
    return None


if __name__ == "__main__":
    print("🧪 Testing Assets Section Extraction")
    
    # Get PDF path from CLI or find sample
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        use_llm = "--llm" in sys.argv or "-llm" in sys.argv
    else:
        pdf_path = find_pdf_sample()
        use_llm = False
        if pdf_path:
            print(f"📦 Using sample PDF: {pdf_path}")
        else:
            print("\n❌ No PDF provided or found")
            print("Usage: python test_extract_section_pages.py <pdf_path> [--llm]")
            print("Options:")
            print("  --llm : Use LLM extraction instead of regex-based extraction")
            print("Or place a PDF in exemplos/ folder")
            sys.exit(1)
    
    if use_llm:
        # Run async LLM extraction test
        asyncio.run(test_extract_with_llm(pdf_path))
    else:
        # Run regex-based extraction test
        test_extract_section_pages(pdf_path)
