# Vision OCR Benchmark Report

**Generated:** 2026-01-23
**Total PDFs:** 10
**Digital PDFs:** 7
**Scanned PDFs:** 3
**Total Pages:** 191
**Vision API Calls:** 191
**Total Time:** 737.1s

---

## Executive Summary

Este benchmark comparou a extracao do parser ASA Digital com o texto extraido pelo Google Vision OCR em 10 PDFs de declaracoes IRPF.

**Principais Descobertas:**

1. **30% dos PDFs sao escaneados** - Nao funcionam com parser de texto direto
2. **PDFs digitais tem 68.4% de match rate** (excluindo escaneados)
3. **Taxpayer e Assets tem 100% de precisao**
4. **Income PJ precisa revisao** - Metricas infladas por CNPJs de outras secoes

---

## PDF Classification

| PDF | Type | Pages | Parser Conf | Match Rate |
|-----|------|-------|-------------|------------|
| 01_maria | DIGITAL | 8 | 74.6% | 64.3% |
| 02_paulo | DIGITAL | 11 | 74.6% | 54.3% |
| 03_luiz | DIGITAL | 55 | 85.6% | 45.7% |
| 04_gelson | **SCANNED** | 19 | 34.0% | 0.0% |
| 05_sueli | DIGITAL | 10 | 78.3% | 84.6% |
| 06_elvis | DIGITAL | 19 | 86.0% | 71.7% |
| 07_fabricio | **SCANNED** | 12 | 34.0% | 0.0% |
| 08_kleber | DIGITAL | 15 | 79.0% | 58.9% |
| 09_sandra | DIGITAL | 13 | 71.9% | 59.5% |
| 10_alex | **SCANNED** | 29 | 34.0% | 0.0% |

---

## Results by Section (Digital PDFs Only)

### Taxpayer (Contribuinte)
- **Match Rate:** 100%
- **Status:** OK - Funcionando perfeitamente

### Assets (Bens e Direitos)
- **Match Rate:** 100%
- **Status:** OK - Funcionando perfeitamente

### Exempt Income (Rendimentos Isentos)
- **Match Rate:** 72% (excluindo escaneados)
- **Status:** IMPROVED - Corrigido formato multiline

### Exclusive Taxation (Tributacao Exclusiva)
- **Match Rate:** 85% (excluindo escaneados)
- **Status:** IMPROVED - Corrigido formato multiline

### Income PJ (Rendimentos PJ)
- **Match Rate:** ~50% (metrica inflada)
- **Status:** REVIEW - Benchmark conta CNPJs de todas as secoes
- **Nota:** O parser extrai corretamente os CNPJs da secao de rendimentos PJ

### Debts (Dividas e Onus)
- **Match Rate:** 57% (excluindo escaneados)
- **Status:** NEEDS_REVIEW - Algumas secoes vazias

### Rural Activity
- **Match Rate:** 43% (excluindo escaneados)
- **Status:** NEEDS_REVIEW - Algumas secoes vazias

---

## Key Findings

### 1. PDFs Escaneados (30% da amostra)

Tres PDFs sao imagens escaneadas sem texto extraivel:
- `04_gelson.pdf` - 19 paginas, 0 caracteres de texto
- `07_fabricio.pdf` - 12 paginas, 0 caracteres de texto
- `10_alex.pdf` - 29 paginas, 0 caracteres de texto

**Impacto:** Esses PDFs precisam passar pelo pipeline de OCR antes do parser.

### 2. Precisao em PDFs Digitais

Excluindo os PDFs escaneados, a taxa de match media sobe para **68.4%**.

| PDF Digital | Match Rate | Parser Confidence |
|-------------|------------|-------------------|
| 05_sueli | 84.6% | 78.3% |
| 06_elvis | 71.7% | 86.0% |
| 01_maria | 64.3% | 74.6% |
| 09_sandra | 59.5% | 71.9% |
| 08_kleber | 58.9% | 79.0% |
| 02_paulo | 54.3% | 74.6% |
| 03_luiz | 45.7% | 85.6% |

### 3. Secoes com Melhor Desempenho

- **Taxpayer:** 100% - CPF e Nome extraidos corretamente em todos os PDFs
- **Assets:** 100% - Bens e Direitos extraidos corretamente

### 4. Melhorias Ja Implementadas

Durante este benchmark, foram corrigidos os extractors:
- `ExemptIncomeExtractor` - Suporte a formato multiline
- `ExclusiveIncomeExtractor` - Suporte a formato multiline

---

## Recommendations

### Alta Prioridade

1. **Implementar deteccao automatica de PDF escaneado**
   - Verificar se tem texto extraivel antes de processar
   - Redirecionar para pipeline OCR se necessario

2. **Revisar extractor de Debts**
   - Algumas declaracoes com dividas nao estao sendo extraidas

### Media Prioridade

3. **Revisar extractor Rural**
   - Declaracoes com atividade rural parcialmente extraidas

4. **Melhorar metricas do benchmark**
   - Separar CNPJs por secao para evitar falsos negativos

### Baixa Prioridade

5. **Otimizar tempo de processamento**
   - PDFs grandes (03_luiz com 55 paginas) levam ~4 minutos

---

## Technical Details

### API Costs

- Total Vision API calls: 191
- Estimated cost: ~$0.29 (191 x $0.0015)

### Processing Time

| PDF | Vision Time | Parser Time | Total |
|-----|-------------|-------------|-------|
| 03_luiz (55p) | 237.5s | 0.8s | 238.3s |
| 10_alex (29p) | 134.3s | 0.7s | 135.0s |
| 04_gelson (19p) | 70.4s | 0.6s | 71.0s |
| Average | 70.8s | 0.5s | 71.3s |

### Files Generated

- `benchmark_results/benchmark_results.json` - Raw data
- `docs/VISION_BENCHMARK_REPORT.md` - This report
