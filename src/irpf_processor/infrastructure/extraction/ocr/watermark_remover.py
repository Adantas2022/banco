"""Pré-processamento de PDF para remoção de marcas d'água.

PDFs de declaração de IRPF frequentemente contêm marcas d'água
diagonais (ex: "PROTEGIDA", "SIGILO FISCAL") que são renderizadas
em cinza claro sobre o texto. Essas marcas d'água confundem o
Document AI, ocultando valores monetários e impedindo a extração
correta.

Este módulo remove as marcas d'água convertendo cada página do PDF
em imagem, eliminando pixels de cinza claro (faixa da marca d'água),
e reconstruindo o PDF limpo.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Optional

import cv2
import fitz
import numpy as np

from irpf_processor.shared.logging import get_logger

logger = get_logger(__name__)

# Configuração padrão do limiar de cinza para remoção de watermark.
# Pixels com intensidade entre WM_GRAY_LOW e WM_GRAY_HIGH são
# considerados parte da marca d'água e substituídos por branco.
WM_GRAY_LOW = 150
WM_GRAY_HIGH = 230
RESIDUE_THRESHOLD = 220

# DPI para renderização das páginas (trade-off: qualidade vs tamanho).
RENDER_DPI = 200

# Qualidade JPEG para reconstrução (preserva distinção vírgula/ponto).
JPEG_QUALITY = 92


class WatermarkRemover:
    """Remove marcas d'água de PDFs escaneados."""

    def __init__(
        self,
        gray_low: int = WM_GRAY_LOW,
        gray_high: int = WM_GRAY_HIGH,
        render_dpi: int = RENDER_DPI,
        jpeg_quality: int = JPEG_QUALITY,
        residue_threshold: int = RESIDUE_THRESHOLD,
    ):
        self._gray_low = gray_low
        self._gray_high = gray_high
        self._render_dpi = render_dpi
        self._jpeg_quality = jpeg_quality,
        self._residue_threshold = residue_threshold


    def clean_pdf_bytes(self, pdf_bytes: bytes) -> bytes:
        """Remove marcas d'água de um PDF e retorna bytes do PDF limpo.

        Para cada página:
        1. Renderiza em imagem (grayscale) no DPI configurado
        2. Remove pixels na faixa de cinza do watermark (substitui por branco)
        3. Reconstrui a página como imagem PNG no PDF

        Returns:
            bytes do PDF limpo
        """
        src_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        out_doc = fitz.open()

        pages_cleaned = 0

        for page_num in range(len(src_doc)):
            page = src_doc[page_num]

            pix = page.get_pixmap(dpi=self._render_dpi)
            img = np.frombuffer(
                pix.samples, dtype=np.uint8
            ).reshape(pix.height, pix.width, 3)

            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

            # Detectar se a página tem pixels na faixa de watermark
            wm_mask = (gray > self._gray_low) & (gray < self._gray_high)
            wm_pixel_ratio = wm_mask.sum() / gray.size

            if wm_pixel_ratio > 0.001:  # >0.1% de pixels na faixa
                # Remover watermark: substituir faixa cinza por branco
                cleaned = gray.copy()
                cleaned[wm_mask] = 255
                # Clean nearly-white leftover residues
                cleaned[cleaned > self._residue_threshold] = 255
                pages_cleaned += 1
            else:
                cleaned = gray
                
            # Convert back to RGB for embedding
            rgb = cv2.cvtColor(cleaned, cv2.COLOR_GRAY2RGB)

            # SAVE AS LOSSLESS PNG
            png_ok, png_bytes = cv2.imencode('.png', rgb)
            png_bytes = png_bytes.tobytes()

            # Criar página com mesmas dimensões
            new_page = out_doc.new_page(
                width=page.rect.width,
                height=page.rect.height,
            )
            rect = fitz.Rect(0, 0, page.rect.width, page.rect.height)

            new_page.insert_image(rect, stream=png_bytes)

        result = out_doc.tobytes(deflate=True, garbage=4)

        logger.info(
            "Watermark removal completed",
            total_pages=len(src_doc),
            pages_cleaned=pages_cleaned,
            original_size=len(pdf_bytes),
            cleaned_size=len(result),
        )

        out_doc.close()
        src_doc.close()

        return result

    def clean_pdf_file(self, pdf_path: Path) -> Path:
        """Remove marcas d'água e salva como arquivo temporário.

        Returns:
            Path para o PDF limpo (mesmo diretório, sufixo _clean)
        """
        pdf_bytes = pdf_path.read_bytes()
        clean_bytes = self.clean_pdf_bytes(pdf_bytes)

        clean_path = pdf_path.with_stem(pdf_path.stem + "_clean")
        clean_path.write_bytes(clean_bytes)

        return clean_path
