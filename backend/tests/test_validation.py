import os
import tempfile

import pytest

from app.services.file_validation import ValidationError, sniff_mime, validate_upload


@pytest.mark.parametrize(
    "data, expected",
    [
        (b"%PDF-1.7\n%...", "application/pdf"),
        (b"\xff\xd8\xff\xe0\x00\x10JFIF", "image/jpeg"),
        (b"\x89PNG\r\n\x1a\n" + b"\x00" * 32, "image/png"),
        (b"II*\x00" + b"\x00" * 32, "image/tiff"),
        (b"MM\x00*" + b"\x00" * 32, "image/tiff"),
        (b"Hello, world!", "text/plain"),
    ],
)
def test_sniff_mime(data, expected):
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(data)
        path = f.name
    try:
        assert sniff_mime(path) == expected
    finally:
        os.unlink(path)


def test_validate_upload_empty_file():
    with tempfile.NamedTemporaryFile(delete=False) as f:
        path = f.name
    try:
        with pytest.raises(ValidationError):
            validate_upload(path)
    finally:
        os.unlink(path)


def test_validate_upload_unsupported_binary():
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"\x00\x01\x02\x03some binary")
        path = f.name
    try:
        with pytest.raises(ValidationError):
            validate_upload(path)
    finally:
        os.unlink(path)
