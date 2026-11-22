from io import BytesIO

from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import Image, ImageOps, ImageSequence

AVATAR_MAX_SIDE = 512
POST_IMAGE_MAX_SIDE = 1920

# Formats browsers display everywhere; anything else is converted to PNG. The stored extension
# comes from the re-encoded content, never from the client's filename.
_WEB_FORMATS = {"JPEG": "jpg", "PNG": "png", "GIF": "gif", "WEBP": "webp"}


def downscale_image(file, max_side: int):
    """Re-encode an uploaded image: longest side at most `max_side`, metadata removed.

    Always re-encoding drops EXIF (GPS position, camera, timestamps) and other embedded metadata
    even when the picture is small; the EXIF orientation is applied first so it still looks
    right. Returns the original file untouched when it is animated or unreadable (upstream
    validators handle rejection). The result is named after its real format.
    """
    try:
        img = Image.open(file)
        fmt = (img.format or "").upper()
    except OSError:
        file.seek(0)
        return file
    if getattr(img, "is_animated", False):
        if fmt in _WEB_FORMATS:
            return _reencode_animated(file, img, fmt)
        img.seek(0)  # animated but not a web format: keep the first frame as a still PNG

    icc_profile = img.info.get("icc_profile")
    transparency = img.info.get("transparency")
    img = ImageOps.exif_transpose(img)
    if max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.LANCZOS)

    if fmt not in _WEB_FORMATS:
        fmt = "PNG"
        if img.mode not in ("RGB", "RGBA", "L", "LA", "P"):
            img = img.convert("RGBA" if "A" in img.getbands() else "RGB")
    if fmt == "JPEG" and img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    buf = BytesIO()
    save_kwargs = {"format": fmt}
    if fmt in ("JPEG", "WEBP"):
        save_kwargs["quality"] = 85
    if icc_profile and fmt in ("JPEG", "PNG", "WEBP"):
        save_kwargs["icc_profile"] = icc_profile
    if transparency is not None and fmt in ("PNG", "GIF") and img.mode == "P":
        save_kwargs["transparency"] = transparency
    img.save(buf, **save_kwargs)
    buf.seek(0)
    return InMemoryUploadedFile(
        file=buf,
        field_name=getattr(file, "field_name", None),
        name=f"image.{_WEB_FORMATS[fmt]}",
        content_type=Image.MIME[fmt],
        size=buf.getbuffer().nbytes,
        charset=None,
    )


def _reencode_animated(file, img, fmt: str):
    """Re-save every frame so embedded metadata (EXIF, XMP, comments) is dropped.

    The result carries the content type and extension of the real format: whatever the client
    declared for the upload is discarded, because it ends up on the stored object.
    """
    frames = [frame.copy() for frame in ImageSequence.Iterator(img)]
    for frame in frames:
        # Keep only what rendering needs; comments, EXIF, XMP and the like are dropped.
        frame.info = {
            k: v for k, v in frame.info.items() if k in ("transparency", "duration", "disposal")
        }
    buf = BytesIO()
    save_kwargs = {
        "format": fmt,
        "save_all": True,
        "append_images": frames[1:],
        "loop": img.info.get("loop", 0),
        "duration": img.info.get("duration", 100),
    }
    if fmt == "WEBP":
        save_kwargs["quality"] = 85
    frames[0].save(buf, **save_kwargs)
    buf.seek(0)
    return InMemoryUploadedFile(
        file=buf,
        field_name=getattr(file, "field_name", None),
        name=f"image.{_WEB_FORMATS[fmt]}",
        content_type=Image.MIME[fmt],
        size=buf.getbuffer().nbytes,
        charset=None,
    )
