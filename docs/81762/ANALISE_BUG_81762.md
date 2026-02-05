# Análise e Correção - BUG #81762

## Problema Reportado

A seção `calculation_of_rural_results_in_brazil` estava extraindo corretamente os dados de apuração do resultado, **mas também estava incluindo incorretamente dados da seção subsequente `livestock_movement_in_brazil`**.

### Dados Incorretamente Incluídos

Os seguintes itens de "Movimentação do Rebanho" estavam aparecendo na seção de "Apuração do Resultado":

- Bovinos e bufalinos
- Suínos
- Caprinos e ovinos
- Asininos, equinos
- Outros

## Análise da Causa Raiz

### Estrutura do PDF

No PDF IRPF, as seções aparecem na seguinte ordem:

```
APURAÇÃO DO RESULTADO - BRASIL
├── INFORMAÇÃO DO EXERCÍCIO ANTERIOR
├── APURAÇÃO DO RESULTADO TRIBUTÁVEL
├── INFORMAÇÕES PARA O EXERCÍCIO SEGUINTE
└── APURAÇÃO DO RESULTADO NÃO TRIBUTÁVEL

MOVIMENTAÇÃO DO REBANHO - BRASIL   <-- Seção separada
├── Bovinos e bufalinos
├── Suínos
├── Caprinos e ovinos
├── Asininos, equinos
└── Outros
```

### Problema no Código

O extrator `RuralResultsExtractor` em `rural/results.py` não possuía marcadores de fim de seção (`SECTION_END_MARKERS`). Isso fazia com que o método `_extract_from_page` continuasse processando linhas além do limite da seção de Apuração do Resultado, entrando na seção de Movimentação do Rebanho.

## Solução Implementada

### Arquivo Modificado

`src/irpf_processor/infrastructure/extraction/extractors/rural/results.py`

### Alterações

1. **Adicionados `SECTION_END_MARKERS`** para definir os limites da seção:

```python
SECTION_END_MARKERS = [
    "MOVIMENTAÇÃO DO REBANHO",
    "MOVIMENTACAO DO REBANHO",
    "BENS DA ATIVIDADE RURAL",
    "DÍVIDAS VINCULADAS À ATIVIDADE RURAL",
    "DIVIDAS VINCULADAS A ATIVIDADE RURAL",
    "DÍVIDAS VINCULADAS A ATIVIDADE RURAL",
]
```

2. **Verificação de fim de seção no loop de processamento**:

```python
def _extract_from_page(self, page_text: str, page_num: int) -> dict:
    # ...
    for line in lines:
        upper = line.strip().upper()
        
        # BUG #81762 fix: Verificar se chegamos ao fim da seção
        if any(end_marker in upper for end_marker in self.SECTION_END_MARKERS):
            current_section = None
            break  # Parar completamente o processamento desta página
        
        # ... resto do processamento
```

## Validação

### Teste Executado

Script: `scripts/test_81762_fix.py`

### Resultado

```
================================================================================
TEST BUG #81762 FIX
================================================================================

[OK] Seção encontrada: calculation_of_rural_results_in_brazil
  - previous_exercise_info: 1 items
  - calculation_of_taxable_result: 7 items
  - next_exercise_info: 1 items
  - calculation_of_exempt_result: 3 items

================================================================================
RESULTADO:
================================================================================

SUCCESS: Nenhum dado de MOVIMENTAÇÃO DO REBANHO foi incluído incorretamente!
Total de items válidos: 12

Items extraídos corretamente:
  - Saldo de prejuízo(s) a compensar de exercício(s) anterior(es: 0.0
  - Receita bruta total: 200000.0
  - Despesa de custeio e investimento total: 40000.0
  - Resultado: 160000.0
  - Limite de 20% sobre a receita bruta total: 40000.0
  - Opção pela forma de apuração do resultado tributável: Pelo resultado
  - Compensação de prejuízo(s) de exercício(s) anterior(es): 0.0
  - RESULTADO TRIBUTÁVEL: 160000.0
  - Saldo de prejuízo(s) a compensar: 0.0
  - Adiantamento(s) recebido(s) em 2024: 0.0
  - Adiantamento(s) recebido(s) até 2023: 0.0
  - RESULTADO NÃO TRIBUTÁVEL: 0.0

================================================================================
VERIFICANDO SEÇÃO livestock_movement_in_brazil:
================================================================================
[OK] Seção encontrada com 5 items
  - Bovinos e bufalinos: inicial=20000.0, final=9000.0
  - Suínos: inicial=0.0, final=0.0
  - Caprinos e ovinos: inicial=800000.0, final=587000.0
  - Asininos, equinos: inicial=0.0, final=0.0
  - Outros: inicial=0.0, final=0.0

================================================================================
TEST PASSED: BUG #81762 fix is working correctly!
================================================================================
```

## Impacto

- **Baixo risco**: A alteração é cirúrgica e afeta apenas a condição de parada do loop de processamento
- **Sem regressão**: Os dados válidos continuam sendo extraídos corretamente
- **Separação correta**: Cada seção agora extrai apenas seus dados correspondentes

## Consistência com Extratores Existentes

O extrator `RuralResultsAbroadExtractor` (exterior) já implementava essa lógica corretamente com `SECTION_END_MARKERS`. A correção alinha o extrator Brasil com o padrão já estabelecido no extrator Exterior.
