#!/usr/bin/env python3
"""Gerador de PDFs escaneados sinteticos para testes de OCR.

Este script gera PDFs que simulam documentos escaneados:
- Converte PDFs digitais para imagens
- Adiciona ruido, rotacao e outros artefatos tipicos de scan
- Cria PDFs com as imagens resultantes

Uso:
    python -m irpf_processor.cli.generate_scanned_pdfs --input-dir pdfs/ --output-dir tests/fixtures/ocr/scanned/

Options:
    --input-dir: Diretorio com PDFs digitais de origem
    --output-dir: Diretorio para salvar PDFs escaneados
    --max-pdfs: Maximo de PDFs para processar (default: 5)
    --quality: Qualidade do scan (low, medium, high)
    --add-noise: Adicionar ruido (default: True)
    --add-rotation: Adicionar rotacao aleatoria (default: True)
"""

import argparse
import random
import sys
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from irpf_processor.shared.logging import get_logger

logger = get_logger(__name__)


class ScannedPdfGenerator:

    QUALITY_SETTINGS = {
        "low": {"dpi": 100, "noise": 0.05, "blur": 2, "rotation": 5},
        "medium": {"dpi": 150, "noise": 0.02, "blur": 1, "rotation": 2},
        "high": {"dpi": 300, "noise": 0.01, "blur": 0, "rotation": 1},
    }

    def __init__(self, quality: str = "medium"):
        self.settings = self.QUALITY_SETTINGS.get(quality, self.QUALITY_SETTINGS["medium"])

    def convert_pdf_to_scanned(
        self,
        input_path: Path,
        output_path: Path,
        add_noise: bool = True,
        add_rotation: bool = True,
    ) -> bool:
        try:
            from pdf2image import convert_from_path
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas

            images = convert_from_path(input_path, dpi=self.settings["dpi"])
            processed_images = []

            for img in images:
                processed = self._process_image(img, add_noise, add_rotation)
                processed_images.append(processed)

            self._save_images_as_pdf(processed_images, output_path)

            logger.info(
                "Scanned PDF generated",
                input=input_path.name,
                output=output_path.name,
                pages=len(processed_images),
            )
            return True

        except Exception as e:
            logger.error("Failed to generate scanned PDF", error=str(e))
            return False

    def _process_image(
        self,
        image: Image.Image,
        add_noise: bool,
        add_rotation: bool,
    ) -> Image.Image:
        if image.mode != "RGB":
            image = image.convert("RGB")

        if add_rotation and self.settings["rotation"] > 0:
            angle = random.uniform(-self.settings["rotation"], self.settings["rotation"])
            image = image.rotate(angle, expand=True, fillcolor=(255, 255, 255))

        if self.settings["blur"] > 0:
            image = image.filter(ImageFilter.GaussianBlur(radius=self.settings["blur"]))

        if add_noise and self.settings["noise"] > 0:
            image = self._add_noise(image, self.settings["noise"])

        image = self._add_scan_artifacts(image)

        return image

    def _add_noise(self, image: Image.Image, intensity: float) -> Image.Image:
        import numpy as np

        img_array = np.array(image)
        noise = np.random.normal(0, intensity * 255, img_array.shape)
        noisy = np.clip(img_array + noise, 0, 255).astype(np.uint8)
        return Image.fromarray(noisy)

    def _add_scan_artifacts(self, image: Image.Image) -> Image.Image:
        draw = ImageDraw.Draw(image)

        if random.random() < 0.3:
            for _ in range(random.randint(1, 3)):
                x = random.randint(0, image.width)
                y = random.randint(0, image.height)
                size = random.randint(1, 3)
                gray = random.randint(100, 200)
                draw.ellipse([x, y, x + size, y + size], fill=(gray, gray, gray))

        if random.random() < 0.2:
            y = random.randint(0, image.height)
            gray = random.randint(200, 240)
            draw.line([(0, y), (image.width, y)], fill=(gray, gray, gray), width=1)

        return image

    def _save_images_as_pdf(self, images: list[Image.Image], output_path: Path) -> None:
        if not images:
            return

        output_path.parent.mkdir(parents=True, exist_ok=True)

        first_image = images[0]
        other_images = images[1:] if len(images) > 1 else []

        first_image.save(
            output_path,
            "PDF",
            resolution=self.settings["dpi"],
            save_all=True,
            append_images=other_images,
        )

    def generate_synthetic_scanned_irpf(
        self,
        output_path: Path,
        taxpayer_name: str = "JOAO DA SILVA",
        cpf: str = "123.456.789-00",
    ) -> bool:
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas

            width, height = A4
            img = Image.new("RGB", (int(width * 2), int(height * 2)), "white")
            draw = ImageDraw.Draw(img)

            try:
                font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
                font_normal = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
            except Exception:
                font_large = ImageFont.load_default()
                font_normal = ImageFont.load_default()

            y_pos = 100
            draw.text((100, y_pos), "DECLARACAO DE AJUSTE ANUAL", fill="black", font=font_large)
            y_pos += 80

            draw.text((100, y_pos), "IMPOSTO SOBRE A RENDA - PESSOA FISICA", fill="black", font=font_normal)
            y_pos += 60

            draw.text((100, y_pos), f"EXERCICIO 2025 - ANO-CALENDARIO 2024", fill="black", font=font_normal)
            y_pos += 80

            draw.text((100, y_pos), "IDENTIFICACAO DO CONTRIBUINTE", fill="black", font=font_large)
            y_pos += 60

            draw.text((100, y_pos), f"CPF: {cpf}", fill="black", font=font_normal)
            y_pos += 40

            draw.text((100, y_pos), f"NOME: {taxpayer_name}", fill="black", font=font_normal)
            y_pos += 80

            draw.text((100, y_pos), "BENS E DIREITOS", fill="black", font=font_large)
            y_pos += 60

            assets = [
                ("01", "Imovel Residencial", "500.000,00"),
                ("02", "Veiculo Automotor", "80.000,00"),
                ("03", "Conta Corrente", "15.000,00"),
            ]
            for code, desc, value in assets:
                draw.text((100, y_pos), f"{code} - {desc}: R$ {value}", fill="black", font=font_normal)
                y_pos += 35

            processed = self._process_image(img, add_noise=True, add_rotation=True)

            processed.save(output_path, "PDF", resolution=150)

            logger.info(
                "Synthetic scanned IRPF generated",
                output=output_path.name,
                taxpayer=taxpayer_name,
            )
            return True

        except Exception as e:
            logger.error("Failed to generate synthetic scanned PDF", error=str(e))
            return False


def main():
    parser = argparse.ArgumentParser(
        description="Generate scanned PDFs for OCR testing"
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        help="Directory with digital PDFs to convert",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("tests/fixtures/ocr/scanned"),
        help="Output directory for scanned PDFs",
    )
    parser.add_argument(
        "--max-pdfs",
        type=int,
        default=5,
        help="Maximum number of PDFs to process",
    )
    parser.add_argument(
        "--quality",
        choices=["low", "medium", "high"],
        default="medium",
        help="Scan quality simulation",
    )
    parser.add_argument(
        "--synthetic",
        type=int,
        default=0,
        help="Generate N synthetic scanned IRPFs",
    )
    parser.add_argument(
        "--no-noise",
        action="store_true",
        help="Disable noise addition",
    )
    parser.add_argument(
        "--no-rotation",
        action="store_true",
        help="Disable rotation",
    )

    args = parser.parse_args()

    generator = ScannedPdfGenerator(quality=args.quality)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    generated = 0

    if args.synthetic > 0:
        names = [
            "MARIA SILVA SANTOS",
            "JOSE OLIVEIRA LIMA",
            "ANA PAULA COSTA",
            "PEDRO HENRIQUE SOUZA",
            "CARLA FERNANDA ALVES",
        ]
        for i in range(args.synthetic):
            name = random.choice(names)
            cpf = f"{random.randint(100, 999)}.{random.randint(100, 999)}.{random.randint(100, 999)}-{random.randint(10, 99)}"
            output_path = args.output_dir / f"synthetic_scan_{i + 1:03d}.pdf"

            if generator.generate_synthetic_scanned_irpf(output_path, name, cpf):
                generated += 1

        logger.info(f"Generated {generated} synthetic scanned PDFs")

    if args.input_dir and args.input_dir.exists():
        pdf_files = list(args.input_dir.glob("*.pdf"))[:args.max_pdfs]

        for pdf_path in pdf_files:
            output_path = args.output_dir / f"scan_{pdf_path.stem}.pdf"

            if generator.convert_pdf_to_scanned(
                pdf_path,
                output_path,
                add_noise=not args.no_noise,
                add_rotation=not args.no_rotation,
            ):
                generated += 1

        logger.info(f"Converted {generated} PDFs to scanned format")

    if generated == 0:
        logger.warning("No PDFs generated. Use --input-dir or --synthetic")
        sys.exit(1)

    logger.info(
        "Scanned PDF generation complete",
        total_generated=generated,
        output_dir=str(args.output_dir),
    )


if __name__ == "__main__":
    main()
