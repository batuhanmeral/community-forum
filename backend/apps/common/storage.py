from storages.backends.s3 import S3Storage

# The only types media is ever served as. Derived from the key we generated (UuidUpload), never
# from what the client declared, so an upload cannot make the CDN serve HTML or script.
_CONTENT_TYPES = {
    "jpg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
}


class MediaS3Storage(S3Storage):
    def get_object_parameters(self, name):
        params = super().get_object_parameters(name)
        extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        content_type = _CONTENT_TYPES.get(extension)
        params["ContentType"] = content_type or "application/octet-stream"
        if content_type is None:
            params["ContentDisposition"] = "attachment"
        return params
