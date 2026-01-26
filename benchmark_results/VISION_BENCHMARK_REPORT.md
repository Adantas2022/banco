# Vision OCR Benchmark Report

**Generated:** 2026-01-23T05:26:56.788261
**Total PDFs:** 10
**Successful:** 10
**Total Pages:** 191
**Vision API Calls:** 191
**Total Time:** 737.1s

---

## Overall Results

- **Average Match Rate:** 43.9%
- **Average Parser Confidence:** 65.2%

---

## Results by PDF

| PDF | Pages | Vision Chars | Parser Conf | Match Rate | Time (s) |
|-----|-------|--------------|-------------|------------|----------|
| 01_maria | 8 | 9,343 | 74.6% | 64.3% | 22.4 |
| 02_paulo | 11 | 14,365 | 74.6% | 54.3% | 32.7 |
| 03_luiz | 55 | 135,804 | 85.6% | 45.7% | 238.3 |
| 04_gelson | 19 | 30,973 | 34.0% | 0.0% | 71.0 |
| 05_sueli | 10 | 15,027 | 78.3% | 84.6% | 34.6 |
| 06_elvis | 19 | 30,165 | 86.0% | 71.7% | 64.1 |
| 07_fabricio | 12 | 18,427 | 34.0% | 0.0% | 44.9 |
| 08_kleber | 15 | 23,591 | 79.0% | 58.9% | 51.7 |
| 09_sandra | 13 | 18,648 | 71.9% | 59.5% | 42.4 |
| 10_alex | 29 | 52,692 | 34.0% | 0.0% | 135.0 |

---

## Results by Section

### taxpayer

- **Average Match Rate:** 100.0%
- **Total Items (Vision):** 14
- **Total Items (Parser):** 14
- **Total Matched:** 14

### income_pj

- **Average Match Rate:** 9.7%
- **Total Items (Vision):** 258
- **Total Items (Parser):** 15
- **Total Matched:** 15

**Missing in Parser:**
- CNPJ: 08.337.337/0001-09
- CNPJ: 39.427.632/0001-71
- CNPJ: 04.467.958/0001-48
- CNPJ: 02.246.046/0001-10
- CNPJ: 47.270.887/0001-00
- CNPJ: 06.063.672/0001-22
- CNPJ: 41.980.319/0001-08
- CNPJ: 10.559.336/0002-23
- CNPJ: 30.306.294/0001-45
- CNPJ: 07.093.380/0001-03

### exempt_income

- **Average Match Rate:** 50.0%
- **Total Items (Vision):** 18
- **Total Items (Parser):** 13
- **Total Matched:** 13

**Missing in Parser:**
- Section present in Vision but empty in parser
- Section present in Vision but empty in parser
- Section present in Vision but empty in parser
- Section present in Vision but empty in parser
- Section present in Vision but empty in parser

### exclusive_taxation

- **Average Match Rate:** 60.0%
- **Total Items (Vision):** 28
- **Total Items (Parser):** 24
- **Total Matched:** 24

**Missing in Parser:**
- Section present in Vision but empty in parser
- Section present in Vision but empty in parser
- Section present in Vision but empty in parser

### assets

- **Average Match Rate:** 100.0%
- **Total Items (Vision):** 142
- **Total Items (Parser):** 142
- **Total Matched:** 142

### debts

- **Average Match Rate:** 40.0%
- **Total Items (Vision):** 25
- **Total Items (Parser):** 19
- **Total Matched:** 19

**Missing in Parser:**
- Section present in Vision but empty in parser
- Section present in Vision but empty in parser
- Section present in Vision but empty in parser
- Section present in Vision but empty in parser
- Section present in Vision but empty in parser
- Section present in Vision but empty in parser

### rural

- **Average Match Rate:** 30.0%
- **Total Items (Vision):** 43
- **Total Items (Parser):** 36
- **Total Matched:** 36

**Missing in Parser:**
- Rural section present in Vision but empty in parser
- Rural section present in Vision but empty in parser
- Rural section present in Vision but empty in parser
- Rural section present in Vision but empty in parser
- Rural section present in Vision but empty in parser
- Rural section present in Vision but empty in parser
- Rural section present in Vision but empty in parser

---

## Gaps Identified

- **income_pj**: Match rate 9.7%
- **exempt_income**: Match rate 50.0%
- **exclusive_taxation**: Match rate 60.0%
- **debts**: Match rate 40.0%
- **rural**: Match rate 30.0%

---

## Recommendations

1. Review **income_pj** extractor - low match rate
1. Review **exempt_income** extractor - low match rate
1. Review **exclusive_taxation** extractor - low match rate
1. Review **debts** extractor - low match rate
1. Review **rural** extractor - low match rate