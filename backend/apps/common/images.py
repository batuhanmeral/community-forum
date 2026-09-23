from io import BytesIO

from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import Image, ImageOps

AVATAR_MAX_SIDE = 512
POST_IMAGE_MAX_SIDE = 1920


def downscale_image(file, max_side: int):
    """Re-encode an uploaded image so its longest side is at most `max_side`.

    Returns the original file untouched when it is already small enough,
    animated, or unreadable (upstream validators handle rejection).
    """
    try:
        img = Image.open(file)
        fmt = (img.format or "JPEG").upper()
    except OSError:
        file.seek(0)
        return file
    if getattr(img, "is_animated", False) or max(img.size) <= max_side:
        file.seek(0)
        return file

    img = ImageOps.exif_transpose(img)
    img.thumbnail((max_side, max_side), Image.LANCZOS)
    if fmt == "JPEG" and img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    buf = BytesIO()
    save_kwargs = {"format": fmt}
    if fmt in ("JPEG", "WEBP"):
        save_kwargs["quality"] = 85
    img.save(buf, **save_kwargs)
    buf.seek(0)
    return InMemoryUploadedFile(
        file=buf,
        field_name=getattr(file, "field_name", None),
        name=file.name,
        content_type=f"image/{fmt.lower()}",
        size=buf.getbuffer().nbytes,
        charset=None,
    )
