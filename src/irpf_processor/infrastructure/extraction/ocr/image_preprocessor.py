import io
from typing import Optional

from PIL import Image, ImageEnhance, ImageFilter

from irpf_processor.shared.logging import get_logger

from .interfaces import IImagePreprocessor

logger = get_logger(__name__)


class ImagePreprocessor(IImagePreprocessor):

    DEFAULT_TARGET_DPI = 300
    CONTRAST_FACTOR = 1.5
    SHARPNESS_FACTOR = 1.3

    def __init__(
        self,
        target_dpi: int = DEFAULT_TARGET_DPI,
        enable_deskew: bool = True,
        enable_denoise: bool = True,
        enable_binarize: bool = False,
    ):
        self._target_dpi = target_dpi
        self._enable_deskew = enable_deskew
        self._enable_denoise = enable_denoise
        self._enable_binarize = enable_binarize

    def preprocess(self, image_bytes: bytes) -> bytes:
        image = Image.open(io.BytesIO(image_bytes))

        if image.mode == "RGBA":
            background = Image.new("RGB", image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[3])
            image = background
        elif image.mode != "RGB":
            image = image.convert("RGB")

        image = self._resize_if_needed(image)
        image = self.enhance_contrast(image)
        image = self._sharpen(image)

        if self._enable_denoise:
            image = self._apply_denoise(image)

        if self._enable_binarize:
            image = self._apply_binarize(image)

        output = io.BytesIO()
        image.save(output, format="PNG", optimize=True)
        return output.getvalue()

    def deskew(self, image_bytes: bytes) -> bytes:
        try:
            import cv2
            import numpy as np

            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            gray = cv2.bitwise_not(gray)

            coords = np.column_stack(np.where(gray > 0))
            if len(coords) < 10:
                return image_bytes

            angle = cv2.minAreaRect(coords)[-1]

            if angle < -45:
                angle = 90 + angle
            elif angle > 45:
                angle = angle - 90

            if abs(angle) < 0.5:
                return image_bytes

            (h, w) = img.shape[:2]
            center = (w // 2, h // 2)
            matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
            rotated = cv2.warpAffine(
                img,
                matrix,
                (w, h),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_REPLICATE,
            )

            _, buffer = cv2.imencode(".png", rotated)
            return buffer.tobytes()

        except ImportError:
            logger.warning("OpenCV not available, skipping deskew")
            return image_bytes
        except Exception as e:
            logger.warning("Deskew failed", error=str(e))
            return image_bytes

    def denoise(self, image_bytes: bytes) -> bytes:
        return self._apply_denoise_bytes(image_bytes)

    def binarize(self, image_bytes: bytes) -> bytes:
        image = Image.open(io.BytesIO(image_bytes))
        image = self._apply_binarize(image)
        output = io.BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()

    def enhance_contrast(self, image: Image.Image) -> Image.Image:
        enhancer = ImageEnhance.Contrast(image)
        return enhancer.enhance(self.CONTRAST_FACTOR)

    def _resize_if_needed(self, image: Image.Image) -> Image.Image:
        current_dpi = image.info.get("dpi", (72, 72))
        if isinstance(current_dpi, tuple):
            current_dpi = current_dpi[0]

        if current_dpi < self._target_dpi:
            scale = self._target_dpi / current_dpi
            new_size = (int(image.width * scale), int(image.height * scale))
            image = image.resize(new_size, Image.Resampling.LANCZOS)

        return image

    def _sharpen(self, image: Image.Image) -> Image.Image:
        enhancer = ImageEnhance.Sharpness(image)
        return enhancer.enhance(self.SHARPNESS_FACTOR)

    def _apply_denoise(self, image: Image.Image) -> Image.Image:
        return image.filter(ImageFilter.MedianFilter(size=3))

    def _apply_denoise_bytes(self, image_bytes: bytes) -> bytes:
        image = Image.open(io.BytesIO(image_bytes))
        image = self._apply_denoise(image)
        output = io.BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()

    def _apply_binarize(self, image: Image.Image) -> Image.Image:
        grayscale = image.convert("L")
        threshold = 128
        return grayscale.point(lambda x: 255 if x > threshold else 0, "1")

    def normalize_whitespace(self, text: str) -> str:
        import re
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
