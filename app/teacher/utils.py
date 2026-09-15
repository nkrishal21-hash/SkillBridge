"""
app/teacher/utils.py — Teacher Utilities
Helpers for profile photo uploading (Cloudinary with local dev fallback),
skills parsing, and weekly availability JSON conversion.
"""

import os
import json
import time
from werkzeug.utils import secure_filename
from flask import current_app, url_for, has_request_context
import cloudinary.uploader

DAYS_ORDER = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def parse_skills(skills_str: str | None) -> list[str]:
    """Parse comma-separated skills string into a clean, deduplicated list."""
    if not skills_str:
        return []
    seen = set()
    cleaned = []
    for item in skills_str.split(","):
        tag = item.strip()
        if tag and tag.lower() not in seen:
            seen.add(tag.lower())
            cleaned.append(tag)
    return cleaned


def availability_to_json(selected_days: list[str] | None) -> str:
    """
    Convert a list of selected day abbreviations into a standardized JSON string.
    Example: ["Mon", "Wed"] -> '{"Mon": true, "Tue": false, "Wed": true, ...}'
    """
    selected_set = set(selected_days or [])
    data = {day: day in selected_set for day in DAYS_ORDER}
    return json.dumps(data)


def availability_from_json(json_str: str | None) -> dict[str, bool]:
    """
    Deserialize availability JSON into a dictionary of {day: bool}.
    Falls back gracefully if string is empty or corrupted.
    """
    default_dict = {day: False for day in DAYS_ORDER}
    if not json_str:
        return default_dict
    try:
        parsed = json.loads(json_str)
        if isinstance(parsed, dict):
            # Ensure all days are represented
            return {day: bool(parsed.get(day, False)) for day in DAYS_ORDER}
        return default_dict
    except (json.JSONDecodeError, TypeError):
        return default_dict


def available_days_list(json_str: str | None) -> list[str]:
    """Return a list of day abbreviations where availability is True."""
    avail_map = availability_from_json(json_str)
    return [day for day in DAYS_ORDER if avail_map.get(day, False)]


def upload_profile_photo(file_storage, user_id: int) -> str:
    """
    Upload profile photo to Cloudinary with fallback to local disk storage.
    Validates file extension and size.
    Returns the URL/path to the uploaded image.
    Raises ValueError with user-facing message on invalid format/size.
    """
    if not file_storage or not file_storage.filename:
        raise ValueError("No file was selected for upload.")

    filename = file_storage.filename
    allowed_exts = current_app.config.get(
        "ALLOWED_IMAGE_EXTENSIONS", {"jpg", "jpeg", "png", "gif", "webp"}
    )
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in allowed_exts:
        raise ValueError(
            f"Unsupported file format '.{ext}'. Allowed formats: {', '.join(sorted(allowed_exts)).upper()}."
        )

    # Check file size (read length, then seek back)
    file_storage.seek(0, os.SEEK_END)
    file_size = file_storage.tell()
    file_storage.seek(0)

    max_size = current_app.config.get("MAX_IMAGE_SIZE", 16 * 1024 * 1024)
    if file_size > max_size:
        max_mb = max_size // (1024 * 1024)
        raise ValueError(f"File size exceeds the {max_mb}MB limit.")

    # 1. Attempt upload to Cloudinary if credentials are configured
    cloud_name = current_app.config.get("CLOUDINARY_CLOUD_NAME")
    api_key = current_app.config.get("CLOUDINARY_API_KEY")
    api_secret = current_app.config.get("CLOUDINARY_API_SECRET")

    is_cloudinary_configured = bool(
        cloud_name
        and api_key
        and api_secret
        and "your-" not in str(cloud_name).lower()
    )

    if is_cloudinary_configured:
        try:
            result = cloudinary.uploader.upload(
                file_storage,
                folder="skillbridge/profile_photos",
                public_id=f"user_{user_id}",
                overwrite=True,
                resource_type="image",
                transformation=[
                    {"width": 400, "height": 400, "crop": "fill", "gravity": "face"},
                    {"quality": "auto", "fetch_format": "auto"},
                ],
            )
            secure_url = result.get("secure_url")
            if secure_url:
                return secure_url
        except Exception as exc:
            current_app.logger.warning(
                f"[Cloudinary] Upload failed for user {user_id}: {exc}. Falling back to local disk storage."
            )

    # 2. Local fallback storage (development mode)
    upload_dir = os.path.join(current_app.root_path, "static", "uploads", "profile_photos")
    os.makedirs(upload_dir, exist_ok=True)

    safe_name = secure_filename(f"user_{user_id}_{int(time.time())}.{ext}")
    destination = os.path.join(upload_dir, safe_name)
    file_storage.seek(0)
    file_storage.save(destination)

    # Return local web-accessible URL
    if has_request_context():
        return url_for("static", filename=f"uploads/profile_photos/{safe_name}")
    return f"/static/uploads/profile_photos/{safe_name}"
