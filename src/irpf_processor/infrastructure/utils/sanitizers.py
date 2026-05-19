"""Funções de sanitização e limpeza de dados extraídos."""

import re
from typing import Any


# logger = get_logger("doc-extractor.sanitizers")

# Campos que NUNCA devem aparecer no output (dumps de texto livre)
CAMPOS_PROIBIDOS = {
    "texto", "text", "conteudo", "corpo", "body", "descricao_geral",
    "mensagem", "carta", "observacao", "observacoes", "not",
    "transcricao", "raw_content", "content", "paragrafos",
}

# Limite de caracteres para considerar um valor como texto livre (alucinação)
MAX_VALOR_LEN = 300

# Chaves que indicam declaração completa de IR (não recibo)
CHAVES_DECLARACAO = {
    "identificacao_declarante", "identificacao_contribuinte",
    "dependentes", "alimentados",
    "rendimentos_pj_titular", "rendimentos_pj_dependentes",
    "rendimentos_pf_exterior_titular", "rendimentos_pf_exterior_dependentes",
    "rendimentos_isentos_nao_tributaveis", "rendimentos_tributacao_exclusiva",
    "rendimentos_pj_titular_exigibilidade_suspensa",
    "rendimentos_pj_dependentes_exigibilidade_suspensa",
    "rendimentos_pj_acumulados_titular", "rendimentos_pj_acumulados_dependentes",
    "imposto_pago_retido", "pagamentos_efetuados", "doacoes_efetuadas",
    "bens_direitos", "dividas_onus",
    "atividade_rural_brasil", "atividade_rural_exterior",
    "ganhos_capital", "renda_variavel_titular", "renda_variavel_dependentes",
    "fundos_imobiliarios_titular", "fundos_imobiliarios_dependentes",
    "doacoes_eca", "doacoes_idoso", "doacoes_partidos_politicos", "resumo",
}

def extract_json_from_text(text: str) -> str | None:
    """Tenta extrair bloco JSON de dentro de markdown (```json ... ``` ou diretamente).
    
    Args:
        text: Texto contendo JSON
        
    Returns:
        String JSON extraída ou None se não encontrar
    """
    # Tenta extrair de blocos markdown
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Tenta achar { ... } direto
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]

    return None
