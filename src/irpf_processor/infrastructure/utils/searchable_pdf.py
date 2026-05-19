"""
Utilitário para tornar PDFs escaneados pesquisáveis (searchable).

Quando um PDF não possui camada de texto (ex.: digitalização/scan),
este módulo usa PyMuPDF + Tesseract para:
  1. Detectar que o PDF é escaneado (sem texto selecionável)
  2. Executar OCR em cada página via Tesseract (por+eng)
  3. Inserir texto invisível (render_mode=3) nas posições corretas
  4. Retornar um novo PDF visualmente idêntico, mas com texto selecionável

Dependências de sistema: tesseract-ocr, tesseract-ocr-por (já no Dockerfile).
"""
from __future__ import annotations

import io

import fitz  # PyMuPDF

# Quantidade mínima de páginas amostradas para verificar presença de texto
_SAMPLE_PAGES = 3


def pdf_has_text(pdf_bytes: bytes, sample_pages: int = _SAMPLE_PAGES) -> bool:
    """Verifica se o PDF já possui camada de texto pesquisável."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        for i in range(min(sample_pages, len(doc))):
            if doc[i].get_text("text").strip():
                return True
        return False
    finally:
        doc.close()


def make_pdf_searchable(
    pdf_bytes: bytes,
    language: str = "por+eng",
    dpi: int = 200,
) -> tuple[bytes, bool]:
    """
    Adiciona camada de texto invisível (OCR) a um PDF escaneado.

    Parâmetros
    ----------
    pdf_bytes : bytes
        Conteúdo do PDF original.
    language : str
        Idiomas para Tesseract (padrão: português + inglês).
    dpi : int
        Resolução para renderização das páginas antes do OCR.

    Retorna
    -------
    (pdf_bytes, was_modified) : tuple[bytes, bool]
        O PDF com camada de texto e flag indicando se houve modificação.
        Se o PDF já era pesquisável, retorna o original inalterado.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    # Verifica se já possui texto
    has_text = False
    for i in range(min(_SAMPLE_PAGES, len(doc))):
        if doc[i].get_text("text").strip():
            has_text = True
            break

    if has_text:
        doc.close()
        return pdf_bytes, False

    page_count = len(doc)
    pages_with_text = 0

    for page in doc:
        try:
            # Executa OCR via Tesseract integrado ao PyMuPDF
            tp = page.get_textpage_ocr(language=language, dpi=dpi, full=True)

            # Extrai blocos de texto com posições detalhadas
            blocks = page.get_text("dict", textpage=tp).get("blocks", [])

            tw = fitz.TextWriter(page.rect)

            for block in blocks:
                if block.get("type") != 0:  # apenas blocos de texto
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "")
                        if not text.strip():
                            continue

                        origin = fitz.Point(span["origin"])
                        fontsize = span.get("size", 10)

                        # Garante tamanho mínimo legível
                        fontsize = max(fontsize, 4)

                        try:
                            tw.append(
                                origin,
                                text,
                                fontsize=fontsize,
                            )
                        except Exception:
                            # Fallback: tenta inserir direto se TextWriter falhar
                            try:
                                page.insert_text(
                                    origin,
                                    text,
                                    fontsize=fontsize,
                                    render_mode=3,  # invisível
                                )
                            except Exception:
                                pass

            # Escreve todo o texto da página de uma vez (invisível)
            tw.write_text(page, render_mode=3)
            pages_with_text += 1

        except Exception as exc:
            pass

    buf = io.BytesIO()
    doc.save(buf, garbage=4, deflate=True)
    doc.close()

    result = buf.getvalue()
    
    return result, True
