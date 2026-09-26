"""
S3 storage service.

Loads AWS/S3 configuration from the project's .env file.

Expected .env variables:

    S3_ENABLED=true
    S3_BUCKET_NAME=your-bucket-name
    S3_REGION=us-east-1
    AWS_ACCESS_KEY_ID=your-access-key
    AWS_SECRET_ACCESS_KEY=your-secret-key
    S3_FOLDER=simulations

Files are stored privately in S3.
Presigned URLs are generated for temporary access.
"""

import asyncio
import mimetypes
import os
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv

# ---------------------------------------------------------
# Load .env BEFORE reading environment variables
# ---------------------------------------------------------

load_dotenv()

import boto3
from botocore.exceptions import ClientError, BotoCoreError
from fastapi import UploadFile


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

S3_ENABLED = (
    os.getenv("S3_ENABLED", "true").strip().lower() == "true"
)

S3_BUCKET_NAME = (
    os.getenv("S3_BUCKET_NAME", "").strip()
)

S3_REGION = (
    os.getenv("S3_REGION", "us-east-1").strip()
)

S3_FOLDER = (
    os.getenv("S3_FOLDER", "").strip().strip("/")
)

AWS_ACCESS_KEY_ID = (
    os.getenv("AWS_ACCESS_KEY_ID") or None
)

AWS_SECRET_ACCESS_KEY = (
    os.getenv("AWS_SECRET_ACCESS_KEY") or None
)


# ---------------------------------------------------------
# S3 settings
# ---------------------------------------------------------

_PRESIGNED_URL_EXPIRY = 60 * 60  # 1 hour

MAX_FILE_SIZE_BYTES = int(
    os.getenv("S3_MAX_FILE_SIZE_MB", "150")
) * 1024 * 1024


# ---------------------------------------------------------
# Allowed file types
# ---------------------------------------------------------

# Document types - expanded to allow most common files
ALLOWED_DOCUMENT_TYPES = {
    # PDF
    "application/pdf": "pdf",
    
    # Images
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
    "image/bmp": "bmp",
    "image/svg+xml": "svg",
    "image/tiff": "tiff",
    "image/heic": "heic",
    "image/heif": "heif",
    
    # Documents
    "application/msword": "doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.ms-excel": "xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.ms-powerpoint": "ppt",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "application/rtf": "rtf",
    "application/vnd.oasis.opendocument.text": "odt",
    "application/vnd.oasis.opendocument.spreadsheet": "ods",
    "application/vnd.oasis.opendocument.presentation": "odp",
    
    # Text
    "text/plain": "txt",
    "text/csv": "csv",
    "text/html": "html",
    "text/xml": "xml",
    "text/markdown": "md",
    
    # Archives
    "application/zip": "zip",
    "application/x-zip-compressed": "zip",
    "application/x-rar-compressed": "rar",
    "application/x-7z-compressed": "7z",
    "application/gzip": "gz",
    "application/x-tar": "tar",
    "application/x-bzip2": "bz2",
    
    # Medical/Dental specific
    "application/dicom": "dcm",
    "application/octet-stream": "bin",
    
    # Audio/Video (if needed)
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "audio/mp4": "m4a",
    "audio/aac": "aac",
    "video/mp4": "mp4",
    "video/mpeg": "mpeg",
    "video/quicktime": "mov",
    "video/x-msvideo": "avi",
    "video/webm": "webm",
}

# Logo types - images only
ALLOWED_LOGO_TYPES = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/svg+xml": "svg",
    "image/gif": "gif",
    "image/bmp": "bmp",
}


# ---------------------------------------------------------
# Validate configuration
# ---------------------------------------------------------

def _validate_config() -> None:
    if not S3_ENABLED:
        raise RuntimeError(
            "S3 storage is disabled. "
            "Set S3_ENABLED=true in .env."
        )

    if not S3_BUCKET_NAME:
        raise RuntimeError(
            "S3_BUCKET_NAME is missing or empty in .env."
        )

    if not S3_REGION:
        raise RuntimeError(
            "S3_REGION is missing or empty in .env."
        )


# ---------------------------------------------------------
# Create S3 client
# ---------------------------------------------------------

def _client():
    _validate_config()

    # If explicit credentials exist, use them.
    # Otherwise boto3 will use its normal credential chain.
    kwargs = {
        "service_name": "s3",
        "region_name": S3_REGION,
    }

    if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
        kwargs["aws_access_key_id"] = AWS_ACCESS_KEY_ID
        kwargs["aws_secret_access_key"] = AWS_SECRET_ACCESS_KEY

    return boto3.client(**kwargs)


# ---------------------------------------------------------
# Build S3 object key
# ---------------------------------------------------------

def _build_key(
    prefix: str,
    original_filename: str,
    file_extension: str | None = None,
) -> str:
    if file_extension:
        extension = file_extension
        if not extension.startswith("."):
            extension = f".{extension}"
    else:
        extension = os.path.splitext(
            original_filename
        )[1].lower()

    unique_name = (
        f"{uuid.uuid4().hex}{extension}"
    )

    date_path = datetime.now(
        timezone.utc
    ).strftime("%Y/%m")

    parts = [
        S3_FOLDER,
        prefix.strip("/"),
        date_path,
        unique_name,
    ]

    return "/".join(
        part for part in parts if part
    )


# ---------------------------------------------------------
# Determine file extension from content type or filename
# ---------------------------------------------------------

def _get_file_extension(
    content_type: str | None,
    filename: str | None,
    allowed_types: dict[str, str] | None,
) -> str:
    """
    Determine the file extension based on content type or filename.
    
    If allowed_types is None, all file types are allowed.
    If content_type is not in allowed_types, fallback to filename extension.
    """
    
    # Try content type first
    if content_type and allowed_types and content_type in allowed_types:
        return allowed_types[content_type]
    
    # Try content type without allowed_types restriction
    if content_type and allowed_types is None:
        ext = mimetypes.guess_extension(content_type)
        if ext:
            return ext.lstrip('.')
    
    # Fallback to filename extension
    if filename:
        ext = os.path.splitext(filename)[1].lstrip('.').lower()
        if ext:
            return ext
    
    # Default
    return "bin"


# ---------------------------------------------------------
# Get file type category for display
# ---------------------------------------------------------

def get_file_type_category(
    content_type: str | None,
    filename: str | None,
) -> str:
    """
    Determine file type category for frontend display.
    Returns: 'image', 'pdf', 'doc', 'excel', 'archive', 'video', 'audio', or 'file'
    """
    
    ct = (content_type or "").lower()
    fn = (filename or "").lower()
    
    # Check by content type
    if ct.startswith("image/") or fn.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg', '.tiff', '.heic', '.heif')):
        return "image"
    elif ct == "application/pdf" or fn.endswith('.pdf'):
        return "pdf"
    elif ct in ["application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"] or fn.endswith(('.doc', '.docx', '.odt', '.rtf')):
        return "doc"
    elif ct in ["application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"] or fn.endswith(('.xls', '.xlsx', '.csv', '.ods')):
        return "excel"
    elif ct.startswith("application/") and any(x in ct for x in ["zip", "rar", "7z", "gzip", "tar", "bzip2"]) or fn.endswith(('.zip', '.rar', '.7z', '.gz', '.tar', '.bz2')):
        return "archive"
    elif ct.startswith("video/") or fn.endswith(('.mp4', '.mov', '.avi', '.webm', '.mpeg')):
        return "video"
    elif ct.startswith("audio/") or fn.endswith(('.mp3', '.wav', '.m4a', '.aac')):
        return "audio"
    elif ct.startswith("text/") or fn.endswith(('.txt', '.csv', '.html', '.xml', '.md')):
        return "text"
    else:
        return "file"


# ---------------------------------------------------------
# Upload file
# ---------------------------------------------------------

async def upload_file_to_s3(
    file: UploadFile,
    prefix: str,
    allowed_types: dict[str, str] | None = None,
) -> tuple[str, str, int]:
    """
    Upload an UploadFile to S3.

    Args:
        file: The uploaded file
        prefix: S3 folder prefix
        allowed_types: Dict mapping MIME types to extensions
                      If None, allows all file types

    Returns:
        (s3_key, content_type, file_size)
    """

    _validate_config()

    # -----------------------------------------------------
    # Determine content type
    # -----------------------------------------------------

    content_type = (
        file.content_type
        or mimetypes.guess_type(
            file.filename or ""
        )[0]
        or "application/octet-stream"
    )

    # -----------------------------------------------------
    # Validate filename
    # -----------------------------------------------------

    original_filename = (
        file.filename or "upload"
    )

    # -----------------------------------------------------
    # Validate file type (if restricted)
    # -----------------------------------------------------

    if allowed_types is not None and content_type not in allowed_types:
        # Check if filename extension is in allowed types
        filename_ext = os.path.splitext(original_filename)[1].lower().lstrip('.')
        allowed_extensions = set(allowed_types.values())
        
        if filename_ext not in allowed_extensions:
            raise ValueError(
                f"Unsupported file type '{content_type}' (extension: .{filename_ext}). "
                f"Allowed types: "
                f"{', '.join(sorted(allowed_types.keys()))}"
            )

    # -----------------------------------------------------
    # Read file
    # -----------------------------------------------------

    body = await file.read()

    size = len(body)

    if size == 0:
        raise ValueError(
            "Uploaded file is empty."
        )

    if size > MAX_FILE_SIZE_BYTES:
        raise ValueError(
            f"File exceeds the {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB size limit."
        )

    # -----------------------------------------------------
    # Determine file extension
    # -----------------------------------------------------

    file_extension = _get_file_extension(
        content_type=content_type,
        filename=original_filename,
        allowed_types=allowed_types,
    )

    # -----------------------------------------------------
    # Create S3 key
    # -----------------------------------------------------

    key = _build_key(
        prefix=prefix,
        original_filename=original_filename,
        file_extension=file_extension,
    )

    # -----------------------------------------------------
    # Upload
    # -----------------------------------------------------

    client = _client()

    try:
        # boto3 is synchronous -- put_object() blocks on the network round
        # trip to S3. Running it inline on the event loop would freeze the
        # ENTIRE server (every other user's request, not just uploads) for
        # as long as this upload takes. asyncio.to_thread runs it on a
        # worker thread instead, so concurrent users stay unblocked.
        await asyncio.to_thread(
            client.put_object,
            Bucket=S3_BUCKET_NAME,
            Key=key,
            Body=body,
            ContentType=content_type,
        )

    except (ClientError, BotoCoreError) as exc:
        raise RuntimeError(
            f"Failed to upload file to S3: {exc}"
        ) from exc

    return key, content_type, size


# ---------------------------------------------------------
# Delete file
# ---------------------------------------------------------

async def delete_file_from_s3(
    key: str | None,
) -> None:
    """
    Delete a file from S3.

    Missing keys are ignored.
    """

    if not key:
        return

    if not S3_ENABLED:
        return

    _validate_config()

    client = _client()

    try:
        # See upload_file_to_s3 -- boto3 calls are synchronous and must not
        # run inline on the event loop, or one user's delete stalls everyone
        # else's requests until the S3 round trip finishes.
        await asyncio.to_thread(
            client.delete_object,
            Bucket=S3_BUCKET_NAME,
            Key=key,
        )

    except (ClientError, BotoCoreError):
        # Do not block application requests because
        # an S3 cleanup operation failed.
        pass


async def download_file_bytes(key: str | None) -> bytes | None:
    """
    Fetch a private S3 object's raw bytes server-side.

    Used for building zip archives — browsers can't `fetch()` presigned
    S3 URLs cross-origin without the bucket having CORS configured for
    the app's origin, so bulk-download endpoints stream through here
    instead of handing the client a list of presigned URLs.
    """

    if not key or not S3_ENABLED:
        return None

    _validate_config()

    client = _client()

    try:
        # See upload_file_to_s3 -- offload the blocking network call so a
        # large "download all" zip doesn't freeze the server for other users
        # while it streams every file down from S3.
        response = await asyncio.to_thread(client.get_object, Bucket=S3_BUCKET_NAME, Key=key)
        return await asyncio.to_thread(response["Body"].read)

    except (ClientError, BotoCoreError) as e:
        # Silently returning None here used to mean a doctor's "download
        # all" zip would quietly come back with zero files inside and no
        # trace anywhere of why -- log which key/error so it's diagnosable.
        print(f"[S3] download_file_bytes failed for key={key!r}: {e}")
        return None


# ---------------------------------------------------------
# Presigned URL
# ---------------------------------------------------------

def get_presigned_url(
    key: str | None,
    *,
    download_filename: str | None = None,
) -> str | None:
    """
    Generate a temporary presigned URL for a private S3 object.

    download_filename, if given, forces the browser to save the file under
    that name via Content-Disposition -- the S3 object key is a random
    generated string (see generate_filename), not the file's original name,
    so without this the browser would offer that random string as the
    downloaded file's name instead of the one the user uploaded.
    """

    if not key:
        return None

    if not S3_ENABLED:
        return None

    _validate_config()

    client = _client()

    params = {"Bucket": S3_BUCKET_NAME, "Key": key}
    if download_filename:
        from urllib.parse import quote
        safe_name = download_filename.replace('"', "'")
        params["ResponseContentDisposition"] = (
            f"attachment; filename=\"{safe_name}\"; filename*=UTF-8''{quote(download_filename)}"
        )

    try:
        return client.generate_presigned_url(
            ClientMethod="get_object",
            Params=params,
            ExpiresIn=_PRESIGNED_URL_EXPIRY,
        )

    except (ClientError, BotoCoreError):
        return None


# ---------------------------------------------------------
# Startup/debug information
# ---------------------------------------------------------

def get_s3_status() -> dict[str, object]:
    """
    Safe configuration status for debugging.

    Does NOT expose AWS secret credentials.
    """

    return {
        "enabled": S3_ENABLED,
        "bucket_configured": bool(S3_BUCKET_NAME),
        "bucket_name": S3_BUCKET_NAME or None,
        "region": S3_REGION,
        "folder": S3_FOLDER or None,
        "access_key_configured": bool(AWS_ACCESS_KEY_ID),
        "secret_key_configured": bool(
            AWS_SECRET_ACCESS_KEY
        ),
    }