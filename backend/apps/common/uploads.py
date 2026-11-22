import uuid

from django.utils.deconstruct import deconstructible

# Extensions a stored upload may carry; everything else is stored as .bin and never served as a
# document. Image uploads are re-encoded and renamed from their real format before they get here.
SAFE_EXTENSIONS = {"jpg", "png", "gif", "webp"}


@deconstructible
class UuidUpload:
    """`upload_to` that ignores the client's filename and stores `<prefix>/<random uuid>.<ext>`.

    Random keys cannot be guessed or collide, leak nothing about the uploader and, being unique,
    can be cached forever.
    """

    def __init__(self, prefix: str):
        self.prefix = prefix

    def __call__(self, instance, filename: str) -> str:
        _, dot, ext = filename.rpartition(".")
        ext = ext.lower() if dot and "/" not in ext and "\\" not in ext else ""
        if ext == "jpeg":
            ext = "jpg"
        if ext not in SAFE_EXTENSIONS:
            ext = "bin"
        return f"{self.prefix}/{uuid.uuid4().hex}.{ext}"

    def __eq__(self, other):
        return isinstance(other, UuidUpload) and other.prefix == self.prefix

    def __hash__(self):
        return hash(self.prefix)
