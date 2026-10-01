"""
app/reports/utils.py — Evidence Upload & Report Admin Utilities
Handles secure evidence file upload (photos, videos, documents) to Cloudinary
with seamless fallback to local disk storage.
"""

import os
import time
import uuid
import cloudinary.uploader
from werkzeug.utils import secure_filename
from flask import current_app, url_for, has_request_context

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}
ALLOWED_VIDEO_EXTENSIONS = {"mp4", "webm", "mov"}
ALLOWED_AUDIO_EXTENSIONS = {"mp3", "wav", "m4a", "ogg"}
ALLOWED_DOC_EXTENSIONS = {"pdf"}
ALLOWED_EVIDENCE_EXTENSIONS = (
    ALLOWED_IMAGE_EXTENSIONS | ALLOWED_VIDEO_EXTENSIONS | ALLOWED_AUDIO_EXTENSIONS | ALLOWED_DOC_EXTENSIONS
)

MAX_IMAGE_SIZE = 16 * 1024 * 1024     # 16 MB
MAX_VIDEO_SIZE = 100 * 1024 * 1024    # 100 MB
MAX_AUDIO_SIZE = 50 * 1024 * 1024     # 50 MB
MAX_DOC_SIZE = 20 * 1024 * 1024       # 20 MB


def _is_cloudinary_configured() -> bool:
    cloud_name = current_app.config.get("CLOUDINARY_CLOUD_NAME")
    api_key = current_app.config.get("CLOUDINARY_API_KEY")
    api_secret = current_app.config.get("CLOUDINARY_API_SECRET")
    return bool(
        cloud_name
        and api_key
        and api_secret
        and "your-" not in str(cloud_name).lower()
    )


def determine_file_type(ext: str) -> str:
    ext = ext.lower().lstrip(".")
    if ext in ALLOWED_IMAGE_EXTENSIONS:
        return "image"
    elif ext in ALLOWED_VIDEO_EXTENSIONS:
        return "video"
    elif ext in ALLOWED_AUDIO_EXTENSIONS:
        return "audio"
    elif ext in ALLOWED_DOC_EXTENSIONS:
        return "document"
    return "other"


def upload_report_evidence(file_storage, user_id: int) -> dict:
    """
    Validate and save evidence file for a Report Admin case.
    Uploads to Cloudinary if configured; otherwise falls back to local disk storage.

    Returns dict:
        {
            "file_url": str,
            "file_type": 'image' | 'video' | 'document',
            "original_filename": str
        }
    Raises ValueError on validation failure.
    """
    if not file_storage or not file_storage.filename:
        raise ValueError("No file provided.")

    original_filename = file_storage.filename
    if "." not in original_filename:
        raise ValueError("File must have a valid extension.")

    ext = original_filename.rsplit(".", 1)[1].lower()
    if ext not in ALLOWED_EVIDENCE_EXTENSIONS:
        allowed_list = ", ".join(sorted(ALLOWED_EVIDENCE_EXTENSIONS))
        raise ValueError(f"File type '.{ext}' is not supported. Allowed formats: {allowed_list}")

    file_type = determine_file_type(ext)

    # Check size
    file_storage.seek(0, os.SEEK_END)
    file_size = file_storage.tell()
    file_storage.seek(0)

    if file_type == "image" and file_size > MAX_IMAGE_SIZE:
        max_mb = MAX_IMAGE_SIZE // (1024 * 1024)
        raise ValueError(f"Image exceeds the {max_mb}MB limit.")
    elif file_type == "video" and file_size > MAX_VIDEO_SIZE:
        max_mb = MAX_VIDEO_SIZE // (1024 * 1024)
        raise ValueError(f"Video exceeds the {max_mb}MB limit.")
    elif file_type == "audio" and file_size > MAX_AUDIO_SIZE:
        max_mb = MAX_AUDIO_SIZE // (1024 * 1024)
        raise ValueError(f"Audio file exceeds the {max_mb}MB limit.")
    elif file_type == "document" and file_size > MAX_DOC_SIZE:
        max_mb = MAX_DOC_SIZE // (1024 * 1024)
        raise ValueError(f"Document exceeds the {max_mb}MB limit.")

    # 1. Cloudinary upload if configured
    if _is_cloudinary_configured():
        try:
            resource_type = "video" if file_type == "video" else ("image" if file_type == "image" else "auto")
            result = cloudinary.uploader.upload(
                file_storage,
                folder="skillbridge/report_evidence",
                public_id=f"evidence_{user_id}_{int(time.time())}_{uuid.uuid4().hex[:6]}",
                overwrite=True,
                resource_type=resource_type,
            )
            secure_url = result.get("secure_url")
            if secure_url:
                return {
                    "file_url": secure_url,
                    "file_type": file_type,
                    "original_filename": original_filename,
                }
        except Exception as exc:
            current_app.logger.warning(
                f"[Cloudinary] Report evidence upload failed for user {user_id}: {exc}. "
                "Falling back to local disk storage."
            )

    # 2. Local disk fallback
    upload_dir = os.path.join(current_app.root_path, "static", "uploads", "report_evidence")
    os.makedirs(upload_dir, exist_ok=True)

    safe_name = secure_filename(
        f"ev_{user_id}_{int(time.time())}_{uuid.uuid4().hex[:6]}.{ext}"
    )
    destination = os.path.join(upload_dir, safe_name)
    file_storage.seek(0)
    file_storage.save(destination)

    if has_request_context():
        web_url = url_for("static", filename=f"uploads/report_evidence/{safe_name}")
    else:
        web_url = f"/static/uploads/report_evidence/{safe_name}"

    return {
        "file_url": web_url,
        "file_type": file_type,
        "original_filename": original_filename,
    }
