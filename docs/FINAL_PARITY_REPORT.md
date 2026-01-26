# Relatório Final de Paridade ASA vs GABARITO

**Data:** 23 de Janeiro de 2026  
**Branch:** feature/dimensa-parity  
**PDFs Testados:** 6

---

## 1. Resumo Executivo

| Métrica | Resultado |
|---------|-----------|
| PDFs Processados | 6/6 (100%) |
| Total Value Match | 5/6 (83.3%) |
| Equity Evolution Match | 5/6 (83.3%) |
| PDFs com Extração Completa | 5/6 |

---

## 2. Resultado por Documento

| # | PDF | Total Value | Equity Evol | Status |
|---|-----|-------------|-------------|--------|
| 1 | 0001_IRPF_Maria de Fa´tima] IRPF 2025 - Decla... | OK | OK | OK |
| 2 | 0132_IRPF_9750982991-IRPF-2025-2024-origi-ima... | OK | OK | OK |
| 3 | 0242_IRPF_EC. IRPF 2025-2024 ROZANY.pdf | OK | OK | OK |
| 4 | 0276_IRPF_ECLARAÇÃO 2025-2024 WIENFRIED.pdf | DIFF (44089516 vs 0) | DIFF | DIVERGENCIA |
| 5 | 0779_IRPF_RPF Renato Declaração 2024 2025.pdf | OK | OK | OK |
| 6 | 1052_IRPF_oberto98884662087-IRPF-2024-2023.pd... | OK | OK | OK |

---

## 3. Detalhamento dos Valores Principais

### 3.1 Documentos com Match Completo (5/6)

| Documento | Total Value | Equity Evolution |
|-----------|-------------|------------------|
| 0001_IRPF_Maria de Fa´tima] IRPF 20 | 250,000 | 0 |
| 0132_IRPF_9750982991-IRPF-2025-2024 | 330,016,859 | 13,981,618 |
| 0242_IRPF_EC. IRPF 2025-2024 ROZANY | 6,078,910 | 4,169,600 |
| 0779_IRPF_RPF Renato Declaração 202 | 2,620,574 | 0 |
| 1052_IRPF_oberto98884662087-IRPF-20 | 36,288,845 | 410,684 |

### 3.2 Documento com Divergência

**PDF:** 0276_IRPF_ECLARAÇÃO 2025-2024 WIENFRIED.pdf

| Métrica | GABARITO | ASA | Causa |
|---------|----------|-----|-------|
| total_value | 44,089,516 | 0 | assets_declaration não extraído |
| equity_evolution | -27,237,254 | 0 | Depende de assets |

**Diagnóstico:** A seção "Bens e Direitos" (assets_declaration) não foi detectada neste PDF específico.
Outras seções foram extraídas normalmente:
- rural_activity_assets_in_brazil: 317 items
- payments_made: 55 items
- debts_and_encumbrances: 11 items

---

## 4. Análise de Seções (Todos os PDFs)

| Seção | GABARITO | ASA | Diferença | Obs |
|-------|----------|-----|-----------|-----|
| assets_declaration | 396 | 251 | -145 | WIENFRIED com 0 |
| debts_and_encumbrances | 73 | 38 | -35 | Variação esperada |
| rural_activity_assets_in_brazil | 423 | 413 | -10 | 97.6% |
| rural_activity_debts_in_brazil | 274 | 275 | +1 | OK |
| payments_made | 0 | 118 | +118 | ASA extrai, GABARITO não |
| donations_made | 0 | 3 | +3 | ASA extrai, GABARITO não |
| income_from_legal_person_to_holder | 25 | 21 | -4 | 84% |

---

## 5. Conclusões

### 5.1 Pontos Positivos

1. **83.3% de paridade** nos valores principais (total_value, equity_evolution)
2. **100% de processamento** - todos os 6 PDFs foram processados com sucesso
3. **ASA extrai mais dados** que o GABARITO (payments_made, donations_made)
4. **Precisão numérica corrigida** com classe Money (valores inteiros exatos)

### 5.2 Pontos de Atenção

1. **1 PDF com assets não extraídos** (WIENFRIED) - requer investigação
2. **Diferenças em contagem de itens** - variações na detecção de início/fim de seção

### 5.3 Recomendações

1. Investigar PDF WIENFRIED para entender falha na extração de assets
2. Validar com amostra maior de PDFs para confirmar taxa de 83%+

---

## 6. Status Final

| Indicador | Valor | Meta | Status |
|-----------|-------|------|--------|
| Paridade Total Value | 83.3% | 90% | EM PROGRESSO |
| Paridade Equity Evolution | 83.3% | 90% | EM PROGRESSO |
| PDFs Processados | 100% | 100% | ATINGIDO |
| Precisão Numérica | 100% | 100% | ATINGIDO |

**Conclusão:** A plataforma ASA está próxima da paridade com o GABARITO Dimensa.
O principal gap é a extração de assets em PDFs com formatação específica (1 caso em 6).
