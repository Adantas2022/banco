"""
Adapter IR — extensão do AzureOpenAIProvider para extração de Imposto de Renda.
"""

from irpf_processor.infrastructure.llm.vision_provider import AzureOpenAIProvider
from irpf_processor.domain.prompts.doc_extractor.ir_system import IR_SYSTEM_PROMPT


class IRAzureOpenAIProvider(AzureOpenAIProvider):
    """
    Provider Azure OpenAI especializado em documentos de Imposto de Renda.

    Herda toda a lógica de PDF, imagens, retry e parsing do provider base;
    substitui o prompt, o system prompt e os pós-processamentos.
    """

    def _get_system_prompt(self) -> str:
        return IR_SYSTEM_PROMPT

    def _prepare_prompt(self, custom_prompt: str | None) -> str:
        """Use the extractor's own LLM_PROMPT directly."""
        if not custom_prompt:
            raise ValueError(
                "IRAzureOpenAIProvider requires a custom_prompt (the extractor's LLM_PROMPT). "
                "Set LLM_PROMPT on the extractor class."
            )
        return custom_prompt

    def _post_process_data(self, data: dict) -> dict:
        """
        Não aplica pós-processamentos financeiros.
        Documentos IR não têm DRE/Balanço; sanitize_output pode remover campos válidos.
        """
        return data

    def _get_chunk_annotation(self, start: int, end: int, total: int) -> str:
        return (
            f"\n\nATENÇÃO: Você está analisando as páginas {start + 1} a {end} "
            f"de um documento de IR de {total} páginas no total. "
            "Extraia TODOS os dados de imposto de renda visíveis nestas páginas "
            "usando o mesmo schema JSON solicitado.\n\n"
            "REGRAS PARA EXTRAÇÃO EM CHUNKS IR:\n"
            "• Mantenha o mesmo objeto JSON root — não crie sub-objetos por chunk.\n"
            "• rendimentos_tributaveis, rendimentos_isentos, rendimentos_exclusivos_fonte, "
            "deducoes, bens_direitos, dividas_onus, pagamentos_efetuados e dependentes "
            "são arrays acumulativos: inclua TODOS os itens visíveis nestas páginas.\n"
            "• Se os dados do contribuinte/cabeçalho aparecerem neste chunk, preencha contribuinte{}.\n"
            "• Se os totais e situação do IR (a pagar/restituir) aparecerem, preencha os campos numéricos.\n"
            "• Nunca retorne um JSON vazio se houver dados nestas páginas."
        )
