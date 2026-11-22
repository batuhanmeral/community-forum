"""Object storage: upload naming, storage settings validation, S3 options and the media migration."""

import io
import os
import uuid

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.core.management import CommandError, call_command
from PIL import Image

from apps.common.uploads import UuidUpload
from config.settings.storage import MEDIA_CACHE_CONTROL, build_media_storage, validate_http_url


def env(**values):
    return lambda key, default="": values.get(key, default)


# ── upload names ──────────────────────────────────────────────────────────────


def test_upload_names_are_random_and_ignore_the_client_filename():
    upload = UuidUpload("posts")
    name = upload(None, "../../etc/passwd.PNG")
    prefix, filename = name.split("/")
    assert prefix == "posts"
    stem, ext = os.path.splitext(filename)
    assert uuid.UUID(stem) and ext == ".png"
    assert ".." not in name and "passwd" not in name
    assert upload(None, "a.png") != upload(None, "a.png")


@pytest.mark.parametrize("filename", ["x.html", "x.svg", "x.php", "x", "x.png.exe", ".htaccess"])
def test_unknown_extensions_never_survive(filename):
    assert UuidUpload("avatars")(None, filename).endswith(".bin")


def test_upload_to_is_deconstructible_for_migrations():
    assert UuidUpload("posts").deconstruct()[2] == {} and UuidUpload("posts") == UuidUpload("posts")
    assert UuidUpload("posts") != UuidUpload("avatars")


def test_models_use_the_uuid_upload_names():
    from apps.communities.models import Community
    from apps.posts.models import Post
    from apps.users.models import User

    for model, field, prefix in (
        (User, "avatar", "avatars"),
        (Community, "avatar", "community_avatars"),
        (Post, "image", "posts"),
    ):
        upload_to = model._meta.get_field(field).upload_to
        assert isinstance(upload_to, UuidUpload) and upload_to.prefix == prefix


# ── metadata stripping ────────────────────────────────────────────────────────


def _jpeg_with_exif(size=(64, 48), orientation=1):
    exif = Image.Exif()
    exif[0x010F] = "SecretCam"  # Make
    exif[0x0112] = orientation
    buf = io.BytesIO()
    Image.new("RGB", size, "red").save(buf, format="JPEG", exif=exif.tobytes())
    buf.seek(0)
    return ContentFile(buf.read(), name="holiday.jpg")


@pytest.mark.parametrize("max_side", [32, 4000])  # resized and already-small paths
def test_exif_is_always_stripped(max_side):
    from apps.common.images import downscale_image

    source = _jpeg_with_exif()
    assert Image.open(io.BytesIO(source.read())).getexif().get(0x010F) == "SecretCam"
    source.seek(0)
    result = downscale_image(source, max_side)
    image = Image.open(result)
    assert not image.getexif() and "exif" not in image.info
    assert image.format == "JPEG"


def test_orientation_is_applied_before_the_tag_is_dropped():
    from apps.common.images import downscale_image

    result = downscale_image(_jpeg_with_exif(size=(64, 48), orientation=6), 4000)
    assert Image.open(result).size == (48, 64)  # rotated upright


def test_output_name_is_derived_from_the_real_format():
    from apps.common.images import downscale_image

    buf = io.BytesIO()
    Image.new("RGB", (10, 10), "blue").save(buf, format="PNG")
    sneaky = ContentFile(buf.getvalue(), name="evil.html")
    assert downscale_image(sneaky, 4000).name.endswith(".png")


def test_non_web_formats_become_png():
    from apps.common.images import downscale_image

    buf = io.BytesIO()
    Image.new("RGB", (10, 10), "blue").save(buf, format="BMP")
    result = downscale_image(ContentFile(buf.getvalue(), name="x.bmp"), 4000)
    assert Image.open(result).format == "PNG" and result.name.endswith(".png")


def _animated_gif(comment=b"gps:41.0,29.0"):
    frames = [Image.new("RGB", (8, 8), color).convert("P") for color in ("red", "blue")]
    buf = io.BytesIO()
    frames[0].save(
        buf,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=80,
        loop=0,
        comment=comment,
    )
    return buf.getvalue()


def test_animated_images_are_re_encoded_renamed_and_typed_from_content():
    from django.core.files.uploadedfile import SimpleUploadedFile

    from apps.common.images import downscale_image

    hostile = SimpleUploadedFile("evil.html", _animated_gif(), content_type="text/html")
    result = downscale_image(hostile, 4000)
    assert result.content_type == "image/gif" and result.name.endswith(".gif")
    data = result.read()
    assert b"gps:41.0,29.0" not in data
    image = Image.open(io.BytesIO(data))
    assert image.is_animated and image.n_frames == 2 and not image.info.get("comment")


# ── settings ──────────────────────────────────────────────────────────────────


def test_filesystem_is_the_default():
    assert build_media_storage(env()) == {"BACKEND": "django.core.files.storage.FileSystemStorage"}


def test_unknown_backend_is_rejected():
    with pytest.raises(ImproperlyConfigured):
        build_media_storage(env(STORAGE_BACKEND="gcs"))


def test_s3_needs_a_bucket():
    with pytest.raises(ImproperlyConfigured, match="S3_BUCKET"):
        build_media_storage(env(STORAGE_BACKEND="s3"))


def test_s3_options_from_the_environment():
    config = build_media_storage(
        env(
            STORAGE_BACKEND="s3",
            S3_BUCKET="nexus-media",
            S3_ENDPOINT_URL="https://abc.r2.cloudflarestorage.com",
            AWS_ACCESS_KEY_ID="AKIAFAKEFAKEFAKE",
            AWS_SECRET_ACCESS_KEY="fake-secret",
            AWS_S3_REGION_NAME="auto",
            MEDIA_BASE_URL="https://cdn.example.com/media/",
        )
    )
    options = config["OPTIONS"]
    assert config["BACKEND"] == "apps.common.storage.MediaS3Storage"
    assert options["bucket_name"] == "nexus-media"
    assert options["endpoint_url"] == "https://abc.r2.cloudflarestorage.com"
    assert (
        options["custom_domain"] == "cdn.example.com/media" and options["url_protocol"] == "https:"
    )
    assert options["object_parameters"] == {"CacheControl": MEDIA_CACHE_CONTROL}
    # Short on purpose: deleted media (account erasure, replaced avatars) must age out of CDN edges.
    assert "max-age=86400" in MEDIA_CACHE_CONTROL and "31536000" not in MEDIA_CACHE_CONTROL
    # Keys are never overwritten, URLs are plain public ones (no signed, expiring query strings).
    assert options["file_overwrite"] is False and options["querystring_auth"] is False
    assert options["default_acl"] is None


def test_s3_storage_builds_public_urls_without_the_network():
    from django.core.files.storage import storages  # noqa: F401

    from apps.common.storage import MediaS3Storage as S3Storage

    options = build_media_storage(
        env(STORAGE_BACKEND="s3", S3_BUCKET="b", MEDIA_BASE_URL="https://cdn.example.com/m")
    )["OPTIONS"]
    storage = S3Storage(**options)
    assert storage.url("posts/abc.png") == "https://cdn.example.com/m/posts/abc.png"


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://files.example.com",
        "gopher://x",
        "https://user:pw@s3.example.com",
        "http://169.254.169.254",  # cloud metadata
        "http://[fe80::1]",
        "http://0.0.0.0",
        "https://s3.example.com/?a=1",
        "https://s3.example.com/#frag",
        "https://",
        "metadata.google.internal",
        "http://metadata.google.internal",
        "",
    ],
)
def test_endpoint_urls_are_validated(url):
    with pytest.raises(ImproperlyConfigured):
        validate_http_url("S3_ENDPOINT_URL", url)


def test_local_and_private_endpoints_are_fine_for_development():
    assert validate_http_url("S3_ENDPOINT_URL", "http://localhost:8333/") == "http://localhost:8333"
    assert validate_http_url("S3_ENDPOINT_URL", "http://seaweedfs:8333") == "http://seaweedfs:8333"


def test_media_base_url_cannot_widen_the_csp():
    for bad in (
        "*",
        "https://*.example.com",
        "https://cdn.example.com;script-src *",
        "https://cdn.example.com\nscript-src *",
    ):
        with pytest.raises(ImproperlyConfigured):
            build_media_storage(env(STORAGE_BACKEND="s3", S3_BUCKET="b", MEDIA_BASE_URL=bad))


# ── migrate_media_to_s3 ───────────────────────────────────────────────────────


@pytest.fixture
def media(tmp_path, settings):
    source = tmp_path / "local"
    target = tmp_path / "remote"
    source.mkdir()
    target.mkdir()
    settings.MEDIA_ROOT = str(source)
    settings.STORAGES = {
        **settings.STORAGES,
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
            "OPTIONS": {"location": str(target)},
        },
    }
    return FileSystemStorage(location=str(source)), FileSystemStorage(location=str(target))


@pytest.fixture
def uploads(db, media):
    from apps.communities.models import Community
    from apps.posts.models import Post
    from apps.users.models import User

    local, _ = media
    user = User.objects.create_user(username="alice", email="a@example.test", password="x")
    community = Community.objects.create(slug="c", name="C", creator=user)
    local.save("avatars/a.png", ContentFile(b"avatar-bytes"))
    local.save("posts/p.jpg", ContentFile(b"post-bytes"))
    User.objects.filter(pk=user.pk).update(avatar="avatars/a.png")
    Post.objects.create(author=user, community=community, title="t", image="posts/p.jpg")
    return user


def run(*args, **kwargs):
    out = io.StringIO()
    call_command("migrate_media_to_s3", *args, stdout=out, **kwargs)
    return out.getvalue()


def test_copies_every_referenced_file_and_is_idempotent(media, uploads):
    _, remote = media
    first = run()
    assert remote.exists("avatars/a.png") and remote.exists("posts/p.jpg")
    assert remote.open("avatars/a.png").read() == b"avatar-bytes"
    assert "copied 2" in first
    second = run()
    assert "copied 0" in second and "already there 2" in second


def test_dry_run_changes_nothing(media, uploads):
    _, remote = media
    output = run(dry_run=True)
    assert "would copy 2" in output
    assert not remote.exists("avatars/a.png")


def test_size_mismatch_is_reported_and_never_overwritten(media, uploads):
    _, remote = media
    remote.save("avatars/a.png", ContentFile(b"different"))
    with pytest.raises(CommandError, match="1 problem"):
        run()
    assert remote.open("avatars/a.png").read() == b"different"
    assert remote.exists("posts/p.jpg")  # the healthy file was still copied


def test_missing_local_file_is_a_problem_not_a_crash(media, uploads):
    local, remote = media
    local.delete("posts/p.jpg")
    with pytest.raises(CommandError, match="1 problem"):
        run()
    assert remote.exists("avatars/a.png")


def test_path_traversal_names_are_refused(media, uploads, tmp_path):
    from apps.posts.models import Post

    secret = tmp_path / "secret.txt"
    secret.write_text("top secret")
    Post.objects.update(image="../secret.txt")
    with pytest.raises(CommandError, match="problem"):
        run()
    # Nothing was written outside the destination and the file outside MEDIA_ROOT was not read.
    assert sorted(p.name for p in tmp_path.iterdir()) == ["local", "remote", "secret.txt"]
    assert (tmp_path / "secret.txt").read_text() == "top secret"


def test_refuses_to_run_against_local_storage(db, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    settings.STORAGES = {
        **settings.STORAGES,
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    }
    with pytest.raises(CommandError, match="STORAGE_BACKEND"):
        run()


# ── S3 object parameters ──────────────────────────────────────────────────────


def test_s3_content_type_comes_only_from_the_key_extension():
    from django.core.files.base import ContentFile

    from apps.common.storage import MediaS3Storage

    storage = MediaS3Storage(bucket_name="b")
    hostile = ContentFile(b"<script>", name="x")
    hostile.content_type = "text/html"
    for key, expected in (
        ("posts/abc.png", "image/png"),
        ("posts/abc.jpg", "image/jpeg"),
        ("avatars/abc.gif", "image/gif"),
        ("posts/abc.webp", "image/webp"),
        ("posts/abc.bin", "application/octet-stream"),
        ("posts/abc.html", "application/octet-stream"),
    ):
        params = storage._get_write_parameters(key, hostile)
        assert params["ContentType"] == expected, key
    assert (
        storage._get_write_parameters("posts/a.bin", hostile)["ContentDisposition"] == "attachment"
    )
    assert "ContentDisposition" not in storage._get_write_parameters("posts/a.png", hostile)


def test_s3_objects_get_the_short_cache_control():
    from apps.common.storage import MediaS3Storage

    options = build_media_storage(env(STORAGE_BACKEND="s3", S3_BUCKET="b"))["OPTIONS"]
    storage = MediaS3Storage(**options)
    assert storage._get_write_parameters("posts/a.png")["CacheControl"] == MEDIA_CACHE_CONTROL


def test_prod_rejects_plain_http_media_urls():
    from config.settings.storage import require_https_media

    options = build_media_storage(
        env(STORAGE_BACKEND="s3", S3_BUCKET="b", MEDIA_BASE_URL="http://cdn.example.com")
    )
    with pytest.raises(ImproperlyConfigured, match="https"):
        require_https_media(options)
    require_https_media({"BACKEND": "django.core.files.storage.FileSystemStorage"})
    require_https_media(
        build_media_storage(
            env(STORAGE_BACKEND="s3", S3_BUCKET="b", MEDIA_BASE_URL="https://c.example.com")
        )
    )


# ── migrate command robustness ────────────────────────────────────────────────


def test_a_storage_error_on_one_file_does_not_stop_the_rest(media, uploads, monkeypatch):
    from botocore.exceptions import ClientError

    _, remote = media
    real_save = FileSystemStorage.save

    def flaky(self, name, content, *args, **kwargs):
        if name == "avatars/a.png":
            raise ClientError({"Error": {"Code": "SlowDown", "Message": "x"}}, "PutObject")
        return real_save(self, name, content, *args, **kwargs)

    monkeypatch.setattr(FileSystemStorage, "save", flaky)
    with pytest.raises(CommandError, match="1 problem"):
        run()
    assert remote.exists("posts/p.jpg")


def test_connection_errors_are_summarised_too(media, uploads, monkeypatch):
    from botocore.exceptions import EndpointConnectionError

    def down(self, name, content, *args, **kwargs):
        raise EndpointConnectionError(endpoint_url="http://s3.invalid")

    monkeypatch.setattr(FileSystemStorage, "save", down)
    with pytest.raises(CommandError, match="2 problem"):
        run()


def test_symlinks_inside_media_root_are_not_followed(media, uploads, tmp_path):
    from apps.posts.models import Post

    outside = tmp_path / "outside.txt"
    outside.write_text("private")
    (tmp_path / "local" / "posts" / "link.jpg").symlink_to(outside)
    Post.objects.update(image="posts/link.jpg")
    with pytest.raises(CommandError, match="problem"):
        run()
    _, remote = media
    assert not remote.exists("posts/link.jpg")
