#!/usr/bin/env python
"""
Test script for LLM-based assets extraction using IRPFParser.

This script demonstrates the simplified workflow:
1. Load PDF (teste_ocr.pdf)
2. Use IRPFParser.parse() which automatically:
   - Creates ExtractionContext
   - Detects AssetsExtractor has LLM flag
   - Calls extract_with_llm() automatically
3. Display results

This is the recommended approach - let IRPFParser handle everything.
"""

import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from irpf_processor.infrastructure.extraction.irpf_parser import IRPFParser


def test_llm_extraction_with_parser():
    """Test LLM extraction using IRPFParser with teste_ocr.pdf file."""
    
    print("\n" + "="*70)
    print("🧪 LLM EXTRACTION TEST - Using IRPFParser")
    print("="*70)
    
    # Find teste_ocr.pdf
    pdf_path = Path(__file__).parent / "teste_ocr.pdf"
    
    if not pdf_path.exists():
        # Try alternative paths
        possible_paths = [
            Path(__file__).parent / "test_digital.pdf",
            Path(__file__).parent / "exemplos" / "teste_ocr.pdf",
            Path(__file__).parent / "exemplos" / "GENESIS" / "teste_ocr.pdf",
        ]
        
        for alt_path in possible_paths:
            if alt_path.exists():
                pdf_path = alt_path
                break
        else:
            print(f"\n❌ ERROR: Could not find teste_ocr.pdf or test_digital.pdf")
            print(f"Looked in:")
            print(f"  - {Path(__file__).parent / 'teste_ocr.pdf'}")
            print(f"  - {Path(__file__).parent / 'test_digital.pdf'}")
            for alt_path in possible_paths[1:]:
                print(f"  - {alt_path}")
            return
    
    print(f"\n📄 Found PDF: {pdf_path}")
    print(f"📏 File size: {pdf_path.stat().st_size / 1024:.2f} KB")
    
    try:
        # Step 1: Initialize IRPFParser
        print("\n" + "-"*70)
        print("STEP 1: Initializing IRPFParser...")
        print("-"*70)
        
        parser = IRPFParser(auto_detect=True, enable_validation=False)
        print("✓ IRPFParser initialized")
        print("✓ Auto-detect: enabled")
        print("✓ Validation: disabled (for faster test)")
        
        # Step 2: Parse PDF (this will automatically use LLM for assets!)
        print("\n" + "-"*70)
        print("STEP 2: Parsing PDF with IRPFParser...")
        print("-"*70)
        print("⏳ Processing... (this may take 2-5 seconds)")
        print("   IRPFParser will:")
        print("   1. Create ExtractionContext")
        print("   2. Detect document sections")
        print("   3. Call AssetsExtractor._run_extractor()")
        print("   4. Check LLM flag → calls extract_with_llm()")
        print("   5. Automatically fall back to extract() if LLM fails")
        
        result = parser.parse(str(pdf_path))
        
        # Step 3: Display results
        print("\n" + "="*70)
        print("✅ PARSING COMPLETE")
        print("="*70)
        
        print("\n📋 DOCUMENT INFO:")
        print("-"*70)
        print(f"Detected Version: {parser.detected_version}")
        print(f"Total Pages: {result.total_pages}")
        print(f"Confidence: {result.confidence:.2%}")
        
        if parser.current_template:
            print(f"Template: {parser.current_template.description}")
            print(f"Template Version: {parser.current_template.version}")
        
        print(f"Warnings: {len(result.warnings)}")
        if result.warnings:
            print("\nDetailed Warnings:")
            for warning in result.warnings:
                print(f"  • {warning}")
        
        # Step 4: Display assets extraction results
        print("\n" + "="*70)
        print("📊 ASSETS EXTRACTION RESULTS")
        print("="*70)
        
        assets = result.assets_declaration
        
        if assets:
            print("\n✅ ASSETS SECTION FOUND AND EXTRACTED")
            print("-"*70)
            
            print(f"Section Name: {assets.get('section_name', 'N/A')}")
            print(f"Extraction Method: {assets.get('extraction_method', 'regex')}")
            print(f"Items Extracted: {len(assets.get('items', []))}")
            
            print(f"\n💰 TOTALS:")
            print(f"  Last Year Total: R$ {assets.get('last_year_total_value', 0):,.2f}")
            print(f"  Current Year Total: R$ {assets.get('current_year_total_value', 0):,.2f}")
            
            # Show items
            items = assets.get('items', [])
            if items:
                print(f"\n📦 ITEMS ({len(items)} total):")
                print("-"*70)
                
                for idx, item in enumerate(items, 1):
                    description = item.get('asset_description', 'N/A')
                    group_code = item.get('asset_group_code', '--')
                    asset_code = item.get('asset_code', '--')
                    country = item.get('country_name', 'N/A')
                    before = item.get('before_year_asset_value', 0)
                    current = item.get('current_year_asset_value', 0)
                    
                    print(f"\n{idx}. {description[:60]}")
                    print(f"   Group: {group_code} | Asset: {asset_code} | Country: {country}")
                    print(f"   Before: R$ {before:,.2f} | Current: R$ {current:,.2f}")
                    
                    add_info = item.get('additional_info', {})
                    if add_info and any(v for v in add_info.values() if v):
                        fields = [f for f, v in add_info.items() if v]
                        print(f"   Additional: {', '.join(fields[:3])}")
            
            # Display total values breakdown
            totals = assets.get('total_values', {})
            if totals:
                print(f"\n💎 TOTAL VALUES VALIDATION:")
                print("-"*70)
                
                before = totals.get('before_year_asset_value', {})
                current = totals.get('current_year_asset_value', {})
                
                if isinstance(before, dict):
                    print(f"Before Year Asset Value:")
                    print(f"  Extracted Sum: R$ {before.get('value', 0):,.2f}")
                    print(f"  PDF Total: R$ {before.get('pdf_total', 0):,.2f}")
                    print(f"  Match: {'✓ YES' if before.get('valid', False) else '✗ NO'}")
                
                if isinstance(current, dict):
                    print(f"Current Year Asset Value:")
                    print(f"  Extracted Sum: R$ {current.get('value', 0):,.2f}")
                    print(f"  PDF Total: R$ {current.get('pdf_total', 0):,.2f}")
                    print(f"  Match: {'✓ YES' if current.get('valid', False) else '✗ NO'}")
            
            # Save results
            json_output_path = Path(__file__).parent / "llm_extraction_results.json"
            with open(json_output_path, 'w', encoding='utf-8') as f:
                json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
            print(f"\n💾 Full results saved to: {json_output_path}")
        
        else:
            print("\n⚠️  ASSETS SECTION NOT FOUND")
            print("\nThe document may not contain:")
            print("  • DECLARAÇÃO DE BENS E DIREITOS")
            print("  • DECLARACAO DE BENS E DIREITOS")
            print("\nOther sections extracted:")
            if result.taxpayer_identification:
                print("  ✓ Taxpayer Identification")
            if result.exempt_income:
                print("  ✓ Exempt Income")
            if result.income_from_individual_to_holder:
                print("  ✓ Income from Individual")
            if result.payments_made:
                print("  ✓ Payments Made")
        
        print("\n" + "="*70)
        print("✅ TEST COMPLETED SUCCESSFULLY")
        print("="*70 + "\n")
    
    except RuntimeError as e:
        print(f"\n❌ CONFIGURATION ERROR: {str(e)}")
        print("\nFor LLM extraction, ensure Azure OpenAI is configured in .env:")
        print("  AZURE_OPENAI_API_KEY=your-api-key")
        print("  AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/")
        print("  AZURE_OPENAI_DEPLOYMENT=your-deployment-name")
        print("  AZURE_OPENAI_API_VERSION=2024-02-15-preview")
        print("\nWithout LLM configuration, the parser will fall back to regex extraction.")
    
    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {str(e)}")
        import traceback
        print("\nFull traceback:")
        traceback.print_exc()


def compare_extraction_methods():
    """Compare regex vs LLM extraction results (advanced)."""
    
    print("\n" + "="*70)
    print("🔬 ADVANCED: Comparing Both Extraction Methods")
    print("="*70)
    
    pdf_path = Path(__file__).parent / "teste_ocr.pdf"
    if not pdf_path.exists():
        print(f"PDF not found: {pdf_path}")
        return
    
    try:
        from irpf_processor.infrastructure.extraction.extractors.assets import AssetsExtractor
        from irpf_processor.infrastructure.extraction.extractors.base import ExtractionContext
        from irpf_processor.infrastructure.extraction.irpf_parser import IRPFParser
        import asyncio
        import unicodedata
        
        # Create context
        parser = IRPFParser()
        context = parser._create_context(str(pdf_path))
        
        extractor = AssetsExtractor()
        
        if not extractor.can_extract(context):
            print("Assets section not found in this PDF")
            return
        
        print("\n📊 Method 1: Regex-based (extract)")
        print("-"*70)
        
        regex_result = extractor.extract(context)
        if regex_result:
            print(f"✓ Extracted {len(regex_result.get('items', []))} items")
            print(f"✓ Total (before year): R$ {regex_result.get('last_year_total_value', 0):,.2f}")
            print(f"✓ Total (current year): R$ {regex_result.get('current_year_total_value', 0):,.2f}")
        else:
            print("✗ No items extracted")
        
        print("\n📊 Method 2: LLM-based (extract_with_llm)")
        print("-"*70)
        
        llm_result = asyncio.run(extractor.extract_with_llm(context))
        if llm_result:
            print(f"✓ Extracted {len(llm_result.get('items', []))} items")
            print(f"✓ Total (before year): R$ {llm_result.get('last_year_total_value', 0):,.2f}")
            print(f"✓ Total (current year): R$ {llm_result.get('current_year_total_value', 0):,.2f}")
        else:
            print("✗ No items extracted (LLM may not be configured)")
        
        if regex_result and llm_result:
            print("\n📈 COMPARISON:")
            print("-"*70)
            
            regex_count = len(regex_result.get('items', []))
            llm_count = len(llm_result.get('items', []))
            
            print(f"Item count difference: {llm_count - regex_count:+d}")
            
            regex_before = regex_result.get('last_year_total_value', 0)
            llm_before = llm_result.get('last_year_total_value', 0)
            diff_before = llm_before - regex_before
            
            print(f"Before year total difference: R$ {diff_before:+,.2f}")
        
        print("\n" + "="*70 + "\n")
    
    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║      LLM-Based Assets Extraction Test using IRPFParser                ║
║      Demonstrates automatic LLM extraction via parser                 ║
╚══════════════════════════════════════════════════════════════════════╝
""")
    
    # Run main test
    test_llm_extraction_with_parser()
    
    # Optional: compare both methods
    print("\n" + "="*70)
    response = input("Run advanced comparison (regex vs LLM)? (y/n): ").strip().lower()
    if response == 'y':
        compare_extraction_methods()
