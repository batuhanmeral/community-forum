from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.common.images import downscale_image


def _upload(size: tuple[int, int], fmt: str = "PNG") -> SimpleUploadedFile:
    buf = BytesIO()
    Image.new("RGB", size, "red").save(buf, format=fmt)
    buf.seek(0)
    return SimpleUploadedFile(
        f"test.{fmt.lower()}", buf.read(), content_type=f"image/{fmt.lower()}"
    )


class TestDownscaleImage:
    def test_large_image_resized(self):
        result = downscale_image(_upload((2000, 1000)), 512)
        img = Image.open(result)
        assert max(img.size) == 512

    def test_small_image_untouched(self):
        original = _upload((100, 80))
        result = downscale_image(original, 512)
        assert result is original

    def test_aspect_ratio_preserved(self):
        result = downscale_image(_upload((1600, 800)), 400)
        img = Image.open(result)
        assert img.size == (400, 200)

    def test_jpeg_survives_roundtrip(self):
        result = downscale_image(_upload((1200, 1200), fmt="JPEG"), 512)
        img = Image.open(result)
        assert img.format == "JPEG"
        assert max(img.size) == 512
