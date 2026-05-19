import io
import pytest
from unittest.mock import MagicMock, patch
from PIL import Image

from irpf_processor.infrastructure.extraction.ocr.image_preprocessor import ImagePreprocessor


class TestImagePreprocessorInit:

    def test_default_initialization(self):
        preprocessor = ImagePreprocessor()

        assert preprocessor._target_dpi == 300
        assert preprocessor._enable_deskew is True
        assert preprocessor._enable_denoise is True
        assert preprocessor._enable_binarize is False

    def test_custom_initialization(self):
        preprocessor = ImagePreprocessor(
            target_dpi=600,
            enable_deskew=False,
            enable_denoise=False,
            enable_binarize=True
        )

        assert preprocessor._target_dpi == 600
        assert preprocessor._enable_deskew is False
        assert preprocessor._enable_denoise is False
        assert preprocessor._enable_binarize is True

    def test_constants(self):
        assert ImagePreprocessor.DEFAULT_TARGET_DPI == 300
        assert ImagePreprocessor.CONTRAST_FACTOR == 1.5
        assert ImagePreprocessor.SHARPNESS_FACTOR == 1.3


class TestPreprocess:

    @pytest.fixture
    def rgb_image_bytes(self):
        img = Image.new("RGB", (100, 100), color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()

    @pytest.fixture
    def rgba_image_bytes(self):
        img = Image.new("RGBA", (100, 100), color=(255, 255, 255, 128))
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()

    @pytest.fixture
    def grayscale_image_bytes(self):
        img = Image.new("L", (100, 100), color=128)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()

    def test_preprocess_rgb_image(self, rgb_image_bytes):
        preprocessor = ImagePreprocessor(enable_denoise=False, enable_binarize=False)
        result = preprocessor.preprocess(rgb_image_bytes)

        assert isinstance(result, bytes)
        assert len(result) > 0

        result_image = Image.open(io.BytesIO(result))
        assert result_image.mode == "RGB"

    def test_preprocess_rgba_image(self, rgba_image_bytes):
        preprocessor = ImagePreprocessor(enable_denoise=False, enable_binarize=False)
        result = preprocessor.preprocess(rgba_image_bytes)

        assert isinstance(result, bytes)
        result_image = Image.open(io.BytesIO(result))
        assert result_image.mode == "RGB"

    def test_preprocess_grayscale_image(self, grayscale_image_bytes):
        preprocessor = ImagePreprocessor(enable_denoise=False, enable_binarize=False)
        result = preprocessor.preprocess(grayscale_image_bytes)

        assert isinstance(result, bytes)
        result_image = Image.open(io.BytesIO(result))
        assert result_image.mode == "RGB"

    def test_preprocess_with_denoise(self, rgb_image_bytes):
        preprocessor = ImagePreprocessor(enable_denoise=True, enable_binarize=False)
        result = preprocessor.preprocess(rgb_image_bytes)

        assert isinstance(result, bytes)

    def test_preprocess_with_binarize(self, rgb_image_bytes):
        preprocessor = ImagePreprocessor(enable_denoise=False, enable_binarize=True)
        result = preprocessor.preprocess(rgb_image_bytes)

        assert isinstance(result, bytes)


class TestDeskew:

    @pytest.fixture
    def simple_image_bytes(self):
        img = Image.new("RGB", (100, 100), color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()

    def test_deskew_returns_bytes(self, simple_image_bytes):
        preprocessor = ImagePreprocessor()
        result = preprocessor.deskew(simple_image_bytes)

        assert isinstance(result, bytes)


class TestDenoise:

    @pytest.fixture
    def image_bytes(self):
        img = Image.new("RGB", (100, 100), color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()

    def test_denoise_returns_bytes(self, image_bytes):
        preprocessor = ImagePreprocessor()
        result = preprocessor.denoise(image_bytes)

        assert isinstance(result, bytes)
        assert len(result) > 0


class TestBinarize:

    @pytest.fixture
    def image_bytes(self):
        img = Image.new("RGB", (100, 100), color="gray")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()

    def test_binarize_returns_bytes(self, image_bytes):
        preprocessor = ImagePreprocessor()
        result = preprocessor.binarize(image_bytes)

        assert isinstance(result, bytes)
        assert len(result) > 0


class TestEnhanceContrast:

    def test_enhance_contrast_returns_image(self):
        preprocessor = ImagePreprocessor()
        img = Image.new("RGB", (100, 100), color="gray")

        result = preprocessor.enhance_contrast(img)

        assert isinstance(result, Image.Image)


class TestResizeIfNeeded:

    def test_resize_low_dpi_image(self):
        preprocessor = ImagePreprocessor(target_dpi=300)
        img = Image.new("RGB", (100, 100))
        img.info["dpi"] = (72, 72)

        result = preprocessor._resize_if_needed(img)

        assert isinstance(result, Image.Image)

    def test_no_resize_high_dpi_image(self):
        preprocessor = ImagePreprocessor(target_dpi=300)
        img = Image.new("RGB", (100, 100))
        img.info["dpi"] = (300, 300)

        result = preprocessor._resize_if_needed(img)

        assert result.size == (100, 100)


class TestSharpen:

    def test_sharpen_returns_image(self):
        preprocessor = ImagePreprocessor()
        img = Image.new("RGB", (100, 100), color="gray")

        result = preprocessor._sharpen(img)

        assert isinstance(result, Image.Image)


class TestApplyDenoise:

    def test_apply_denoise_returns_image(self):
        preprocessor = ImagePreprocessor()
        img = Image.new("RGB", (100, 100), color="gray")

        result = preprocessor._apply_denoise(img)

        assert isinstance(result, Image.Image)


class TestApplyBinarize:

    def test_apply_binarize_returns_binary_image(self):
        preprocessor = ImagePreprocessor()
        img = Image.new("RGB", (100, 100), color="gray")

        result = preprocessor._apply_binarize(img)

        assert isinstance(result, Image.Image)
        assert result.mode == "1"


class TestNormalizeWhitespace:

    def test_normalize_multiple_spaces(self):
        preprocessor = ImagePreprocessor()
        text = "Hello    world"

        result = preprocessor.normalize_whitespace(text)

        assert result == "Hello world"

    def test_normalize_multiple_newlines(self):
        preprocessor = ImagePreprocessor()
        text = "Hello\n\n\n\nworld"

        result = preprocessor.normalize_whitespace(text)

        assert result == "Hello\n\nworld"

    def test_normalize_tabs(self):
        preprocessor = ImagePreprocessor()
        text = "Hello\t\tworld"

        result = preprocessor.normalize_whitespace(text)

        assert result == "Hello world"

    def test_normalize_strips_whitespace(self):
        preprocessor = ImagePreprocessor()
        text = "  Hello world  "

        result = preprocessor.normalize_whitespace(text)

        assert result == "Hello world"

    def test_normalize_complex_whitespace(self):
        preprocessor = ImagePreprocessor()
        text = "  Hello   \t  world  \n\n\n\n  test  "

        result = preprocessor.normalize_whitespace(text)

        assert "  " not in result.replace("\n\n", "xx")
