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
    def test_small_image_keeps_its_size_but_is_re_encoded(self):
        # Re-encoding is what drops embedded metadata (see test_storage for the EXIF cases).
        result = downscale_image(_upload((100, 80)), 512)
        assert Image.open(result).size == (100, 80)

    def test_aspect_ratio_preserved(self):
        result = downscale_image(_upload((1600, 800)), 400)
        img = Image.open(result)
        assert img.size == (400, 200)

    def test_jpeg_survives_roundtrip(self):
        result = downscale_image(_upload((1200, 1200), fmt="JPEG"), 512)
        img = Image.open(result)
        assert img.format == "JPEG"
        assert max(img.size) == 512
