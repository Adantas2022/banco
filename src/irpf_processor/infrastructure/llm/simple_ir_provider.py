"""
Example: IR Provider built on SimpleLLMProvider.

This shows how to extend SimpleLLMProvider for the specific use case of
extracting IR (Income Tax) documents with custom prompts and behavior.
"""

from irpf_processor.infrastructure.llm.simple_llm_provider import SimpleLLMProvider
from irpf_processor.domain.prompts.doc_extractor.ir_system import IR_SYSTEM_PROMPT


class SimpleIRProvider(SimpleLLMProvider):
    """
    Simplified IR (Income Tax) document extraction provider.
    
    Customizes:
    - System prompt for IR documents
    - User prompt with IR-specific instructions
    - Skips unnecessary post-processing for IR documents
    """

    def _get_system_prompt(self) -> str:
        """Return IR-specific system prompt."""
        return IR_SYSTEM_PROMPT

    def _prepare_prompt(self, custom_prompt: str | None = None) -> str:
        """Use the extractor's own LLM_PROMPT directly."""
        if not custom_prompt:
            raise ValueError(
                "SimpleIRProvider requires a custom_prompt (the extractor's LLM_PROMPT). "
                "Set LLM_PROMPT on the extractor class."
            )
        return custom_prompt

    def _post_process_data(self, data: dict) -> dict:
        """
        IR documents don't need the financial sanitization that DRE/Balanço need.
        Return data as-is.
        """
        return data
