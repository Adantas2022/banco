"""Funções auxiliares gerais."""

from typing import Any


def count_fields(data: dict[str, Any], prefix: str = "") -> int:
    """Conta recursivamente o número de campos extraídos.
    
    Ignora campos internos que começam com _ (como _metadata).
    
    Args:
        data: Dicionário de dados
        prefix: Prefixo para campos aninhados (usado na recursão)
        
    Returns:
        Número total de campos extraídos
    """
    if not isinstance(data, dict):
        return 0
    
    count = 0
    for key, value in data.items():
        # Ignora metadados internos
        if key.startswith("_"):
            continue
        
        count += 1
        
        # Conta campos aninhados
        if isinstance(value, dict):
            count += count_fields(value, prefix=f"{prefix}{key}.")
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    count += count_fields(item, prefix=f"{prefix}{key}[].")
    
    return count
