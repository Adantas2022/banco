# Analysis: TRIBUTAÇÃO EXCLUSIVA Section Format

## PDF File
`/Users/camilooscargirardellibaptista/asa/ASA.IRPF.JSON.MIRROR/JsonMirro/quality/fixtures/0739_IRPF_RPF_Declarac_a_o_-_Maria_Luiza_-_2025/0739_IRPF_RPF Declaração - Maria Luiza - 2025.pdf`

## Findings

### Page 3 - Main Section

**Line-by-line format:**

```
Line 20: 'TOTAL 1.963.818,93'  (from previous section - ISENTOS)
Line 21: 'RENDIMENTOS SUJEITOS À TRIBUTAÇÃO EXCLUSIVA / DEFINITIVA (Valores em Reais)'
Line 22: 'TOTAL 0,00'
Line 23: 'RENDIMENTOS TRIBUTÁVEIS RECEBIDOS DE PESSOA JURÍDICA PELO TITULAR...'
```

### Exact Format Details

1. **Section Header**: 
   - **Line 21**: `'RENDIMENTOS SUJEITOS À TRIBUTAÇÃO EXCLUSIVA / DEFINITIVA (Valores em Reais)'`
   - Contains: "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO EXCLUSIVA / DEFINITIVA (Valores em Reais)"
   - Note: There's a space before and after the "/" character

2. **TOTAL Line**:
   - **Line 22**: `'TOTAL 0,00'`
   - Format: `TOTAL` followed by space(s), then the value
   - Value format: `0,00` (using comma as decimal separator)
   - **TOTAL and value are on the SAME line**
   - **TOTAL line is SEPARATE from the section header line** (next line after header)

### Key Observations

1. **Line Separation**: 
   - Section header is on line 21
   - TOTAL is on line 22 (immediately following, separate line)
   - **TOTAL and value are on the same line** (line 22)
   - **Section header and TOTAL are on separate lines** (lines 21 and 22)

2. **Spacing**:
   - Section header has spaces around "/": "EXCLUSIVA / DEFINITIVA"
   - TOTAL line format: "TOTAL 0,00" (space between TOTAL and value)

3. **Value Format**:
   - Uses comma as decimal separator: `0,00`
   - No thousands separator for zero value
   - For non-zero values, format would be: `132.130,34` (dot for thousands, comma for decimals)

### Current Extractor Behavior

The extractor's `_extract_section_total` method uses this regex:
```python
match = re.match(r"^\s*TOTAL\s+([\d.,]+)\s*$", line, re.IGNORECASE)
```

This should match `'TOTAL 0,00'` correctly. However, the issue might be:
1. The section is detected but returns `None` when total is 0,00
2. The extractor might be looking for subsections first and failing before checking the TOTAL

### Page 12 - Summary Section

There's also a summary on page 12:
- Line 11: `'Rendimentos sujeitos à tributação exclusiva/definitiva 0,00'`
- This is a different format (lowercase, value on same line as text, no "TOTAL" keyword)

## Conclusion

**Format**: 
- Section header: Line N
- TOTAL: Line N+1 (immediately following)
- TOTAL and value: Same line
- Section header and TOTAL: Separate lines

**Example**:
```
Line 21: RENDIMENTOS SUJEITOS À TRIBUTAÇÃO EXCLUSIVA / DEFINITIVA (Valores em Reais)
Line 22: TOTAL 0,00
```
