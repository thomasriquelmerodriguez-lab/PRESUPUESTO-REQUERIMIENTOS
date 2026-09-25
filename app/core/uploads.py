from __future__ import annotations

from pathlib import Path

from fastapi import UploadFile

from app.core.exceptions import AppError


async def read_upload_limited(
    upload: UploadFile,
    *,
    max_bytes: int,
    allowed_extensions: set[str],
) -> tuple[str, bytes]:
    """Read an upload with an explicit byte limit and a strict extension allowlist."""
    filename = Path(upload.filename or "archivo").name[:255]
    extension = Path(filename).suffix.lower()
    if extension not in allowed_extensions:
        allowed = ", ".join(sorted(allowed_extensions))
        raise AppError(
            f"Formato no permitido. Utilice uno de estos formatos: {allowed}.",
            415,
            "unsupported_file",
        )

    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise AppError(
                "El archivo supera el tamaño máximo permitido.",
                413,
                "file_too_large",
            )
        chunks.append(chunk)
    return filename, b"".join(chunks)
