"""
SimpleLLMProvider Usage Guide

This module provides a simplified alternative to the full-featured providers 
(vision_provider.py and ir_provider.py). Use this when you need:

1. Basic LLM extraction without complex infrastructure
2. Easy-to-understand code for subclassing
3. Reduced complexity (no chunking, QR codes, multi-doc formats)
4. Document type-specific providers (IR, DRE, etc.)

== ARCHITECTURE ==

SimpleLLMProvider (base class)
├── Override _get_system_prompt() → Customize system behavior
├── Override _prepare_prompt() → Customize user instructions
├── Override _post_process_data() → Add document-specific validation
└── extract() → Main extraction flow (usually doesn't need override)

SimpleIRProvider extends SimpleLLMProvider
└── Customizes all three methods for IR documents


== USAGE EXAMPLE ==

```python
from src.infrastructure.llm.simple_ir_provider import SimpleIRProvider
from src.domain.models.document import Document

provider = SimpleIRProvider()

# Extract from IR document
result = await provider.extract(
    document=my_ir_document,
    custom_prompt="Focus on deductions")
    
print(f"Extracted: {result.extracted_data}")
print(f"Confidence: {result.confianca}")
```


== CREATING YOUR OWN PROVIDER ==

```python
from src.infrastructure.llm.simple_llm_provider import SimpleLLMProvider

class MyCustomProvider(SimpleLLMProvider):
    def _get_system_prompt(self) -> str:
        return "You are expert at extracting financial statements..."
    
    def _prepare_prompt(self, custom_prompt=None):
        base = "Extract from invoices..."
        if custom_prompt:
            base += f"\n{custom_prompt}"
        return base
    
    def _post_process_data(self, data):
        # Validate, clean, or transform extracted data
        data['validated'] = True
        return data
```


== COMPARISON ==

Feature                   SimpleLLMProvider    vision_provider.py
────────────────────────────────────────────────────────────────
PDF support               ✓                    ✓
Image support             ✓                    ✓
Retry logic               ✓                    ✓
QR code decoding          ✗                    ✓
PDF chunking (>45 pages)  ✗                    ✓
Multiple doc types        ✗                    ✓ (XLSX, DOCX)
Easy to understand        ✓                    ✗
Extensibility             ✓                    ✓
Lines of code             ~250                 ~700


== WHEN TO USE EACH ==

SimpleLLMProvider:
- You need a simple, understandable base
- Your documents are <45 pages
- You're creating document-specific providers (IR, invoices, contracts)
- You want minimal dependencies

vision_provider.py:
- You handle very large PDFs (>45 pages)
- You need QR code extraction
- You support multiple formats (PDF, images, XLSX, DOCX)
- You need complex merging logic for chunked data


== KEY METHODS ==

extract(document, custom_prompt=None):
    Main method — processes document and returns ExtractionResult
    
_get_system_prompt():
    Returns system instruction (customize in subclasses)
    
_prepare_prompt(custom_prompt=None):
    Builds user prompt with optional custom additions
    
_post_process_data(data):
    Final cleanup/validation before returning result
    
_build_content(prompt, images=None):
    Constructs content blocks for Azure OpenAI
    
_call_openai_with_retry(messages):
    Calls Azure OpenAI with 3-retry exponential backoff


== ERROR HANDLING ==

Rate Limit:
    Automatic retry with exponential backoff (2s → 4s → 8s)
    After 3 attempts, raises RuntimeError
    
Timeout:
    Same retry strategy as rate limit
    
Parse Error:
    Attempts to extract JSON from raw text
    If fails, returns {"raw_text": "...", "parse_error": True}
"""
