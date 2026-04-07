"""Utilitários para conversão e processamento de PDF."""

import fitz  # PyMuPDF

def pdf_to_images(file_bytes: bytes, dpi: int = 200) -> list[bytes]:
    """Converte cada página do PDF em uma imagem PNG usando PyMuPDF.
    
    Args:
        file_bytes: Bytes do arquivo PDF
        dpi: Resolução da imagem de saída (default: 200)
        
    Returns:
        Lista de bytes de imagens PNG, uma por página
    """
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    images: list[bytes] = []
    zoom = dpi / 72  # 72 é o DPI padrão do PDF
    matrix = fitz.Matrix(zoom, zoom)
    for page in doc:
        pix = page.get_pixmap(matrix=matrix)
        images.append(pix.tobytes("png"))
    doc.close()
    # logger.info("pdf_convertido", pages=len(images), dpi=dpi)
    return images
