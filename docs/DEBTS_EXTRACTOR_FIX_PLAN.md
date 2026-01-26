# Plano de Correções - Extrator de Dívidas

**Data:** 2026-01-23  
**Status:** Pendente  
**Branch:** feature/dimensa-parity

## Contexto

Após correções no extrator de assets (100% paridade), o extrator de dívidas ainda apresenta diferenças em 2 dos 6 documentos testados.

## Diagnóstico

| Documento | ASA | Gabarito | Problema |
|-----------|-----|----------|----------|
| WIENFRIED | 26 (pág 40, 54-79) | 11 (pág 40) | Extrai páginas extras (54-79) |
| Peter (9750982991) | 63 (pág 25-26, 30-35) | 53 (pág 25-28) | Pula pág 27-28 + extrai 30-35 indevido |

### Detalhes WIENFRIED

```
ASA páginas: 40(11), 54(1), 56(2), 60(1), 61(1), 62(2), 63(1), 64(1), 68(1), 70(2), 72(1), 73(1), 79(1)
GAB páginas: 40(11)

Páginas só em ASA: [54, 56, 60, 61, 62, 63, 64, 68, 70, 72, 73, 79]
```

- Página 40 tem 11 dívidas corretas
- Páginas 54-79 são de outra seção (provavelmente Pagamentos ou Doações)
- O extrator não está parando no fim da seção de dívidas

### Detalhes Peter

```
ASA páginas: 25(18), 26(18), 30(2), 31(7), 32(4), 33(5), 34(7), 35(2)
GAB páginas: 25(18), 26(17), 27(17), 28(1)

Páginas só em ASA: [30, 31, 32, 33, 34, 35]
Páginas só em GAB: [27, 28]
```

- Páginas 27-28 têm dívidas reais mas estão sendo puladas
- `_has_rural_section_heading()` está detectando falso positivo
- Páginas 30-35 são de outra seção mas estão sendo extraídas como dívidas

## Problemas Identificados

1. **Falso positivo em páginas extras (WIENFRIED)**
   - Extrator continua após fim da seção de dívidas
   - Páginas 54-79 pertencem a outras seções

2. **Detecção incorreta de seção rural (Peter)**
   - Páginas 27-28 estão sendo puladas incorretamente
   - Provavelmente "ATIVIDADE RURAL" aparece no sidebar dessas páginas

3. **Extração de seções não-dívida (Peter)**
   - Páginas 30-35 não são dívidas regulares
   - Provavelmente são de seção intermediária

## Correções Propostas

### Fase 1: Melhorar marcadores de fim de seção

**Arquivo:** `src/irpf_processor/infrastructure/extraction/extractors/debts.py`

```python
SECTION_END_MARKERS = [
    "DOAÇÕES A PARTIDOS",
    "RENDIMENTOS ISENTOS",
    "RENDIMENTOS TRIBUTÁVEIS",
    "ATIVIDADE RURAL",
    "PROPRIEDADES RURAIS",
    # Adicionar:
    "PAGAMENTOS EFETUADOS",
    "DOAÇÕES EFETUADAS", 
    "RENDIMENTOS RECEBIDOS",
    "ESPÓLIO",
    "INFORMAÇÕES DO CÔNJUGE",
]
```

### Fase 2: Refinar detecção de seção rural

**Arquivo:** `src/irpf_processor/infrastructure/extraction/extractors/debts.py`

Melhorar `_has_rural_section_heading()`:
- Só considerar rural se "ATIVIDADE RURAL" aparecer como TÍTULO de seção
- Verificar se há "BRASIL" ou "EXTERIOR" junto
- Não disparar em texto de sidebar/menu lateral

```python
def _has_rural_section_heading(self, page_text: str) -> bool:
    lines = page_text.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip().upper()
        if not stripped:
            continue
        
        # Deve ser linha dedicada, não parte de menu
        if len(stripped) > 60:
            continue
            
        # Padrões de heading rural
        rural_patterns = [
            "ATIVIDADE RURAL - BRASIL",
            "ATIVIDADE RURAL BRASIL", 
            "DÍVIDAS E ÔNUS REAIS - ATIVIDADE RURAL",
            "PROPRIEDADES RURAIS EXPLORADAS",
        ]
        
        for pattern in rural_patterns:
            if stripped.startswith(pattern):
                return True
                
    return False
```

### Fase 3: Validação por padrão de dados

**Arquivo:** `src/irpf_processor/infrastructure/extraction/extractors/debts.py`

Adicionar validação de padrão de dívida:
- Código deve ser 11-14 (códigos válidos de dívida IRPF)
- Se muitos itens consecutivos não casarem com padrão, parar extração

```python
VALID_DEBT_CODES = {"11", "12", "13", "14", "15", "16", "17", "18", "19"}

def _is_valid_debt_item(self, item: dict) -> bool:
    code = item.get("debt_code", "")
    return code in self.VALID_DEBT_CODES
```

### Fase 4: Controle por intervalo de páginas

Para casos complexos, adicionar heurística:
- Se encontrar gap grande de páginas (ex: pág 26 → pág 30), verificar se é mesmo seção
- Dívidas normalmente são contíguas

## Arquivos a Modificar

| Arquivo | Mudanças |
|---------|----------|
| `debts.py` | SECTION_END_MARKERS, _has_section_end_heading, _has_rural_section_heading, validação de códigos |

## Testes de Validação

1. **WIENFRIED** - deve ter exatamente 11 dívidas (página 40)
2. **Peter** - deve ter exatamente 53 dívidas (páginas 25-28)
3. **Roberto** - deve manter 8 dívidas (não regredir)
4. **Maria** - deve manter 0 dívidas (não regredir)
5. **Renato** - deve manter 0 dívidas (não regredir)
6. **ROZANY** - deve manter 1 dívida (não regredir)

## Critérios de Sucesso

- [ ] Dívidas: 6/6 documentos em paridade (100%)
- [ ] Sem regressão em Bens (manter 100%)
- [ ] Sem regressão em CPF (manter 100%)

## Histórico

| Data | Ação | Resultado |
|------|------|-----------|
| 2026-01-23 | Correção inicial assets.py e debts.py | Bens 100%, Dívidas 67% |
| - | Fase 1 - Marcadores | Pendente |
| - | Fase 2 - Rural detection | Pendente |
| - | Fase 3 - Validação códigos | Pendente |
