"""
app/courses/utils.py — Course & Lesson Media Uploads & Quiz Utilities
Provides Cloudinary uploading with local disk fallback for course thumbnails,
lesson videos, and lesson PDFs, plus quiz data serialization helpers.
"""

import os
import json
import time
from werkzeug.utils import secure_filename
from flask import current_app, url_for, has_request_context
import cloudinary.uploader


def _is_cloudinary_configured() -> bool:
    """Check if valid Cloudinary credentials exist in current_app config."""
    cloud_name = current_app.config.get("CLOUDINARY_CLOUD_NAME")
    api_key = current_app.config.get("CLOUDINARY_API_KEY")
    api_secret = current_app.config.get("CLOUDINARY_API_SECRET")

    return bool(
        cloud_name
        and api_key
        and api_secret
        and "your-" not in str(cloud_name).lower()
    )


def upload_course_thumbnail(file_storage, teacher_id: int) -> str:
    """
    Upload course thumbnail to Cloudinary with fallback to local disk.
    Validates file extension and size.
    Returns the URL/path to the uploaded image.
    """
    if not file_storage or not file_storage.filename:
        raise ValueError("No thumbnail file selected.")

    filename = file_storage.filename
    allowed_exts = current_app.config.get(
        "ALLOWED_IMAGE_EXTENSIONS", {"jpg", "jpeg", "png", "gif", "webp"}
    )
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in allowed_exts and ext != "webp":
        raise ValueError(
            f"Unsupported thumbnail format '.{ext}'. Allowed: {', '.join(sorted(allowed_exts)).upper()}."
        )

    file_storage.seek(0, os.SEEK_END)
    file_size = file_storage.tell()
    file_storage.seek(0)

    max_size = current_app.config.get("MAX_IMAGE_SIZE", 16 * 1024 * 1024)
    if file_size > max_size:
        max_mb = max_size // (1024 * 1024)
        raise ValueError(f"Thumbnail exceeds the {max_mb}MB limit.")

    # 1. Attempt upload to Cloudinary
    if _is_cloudinary_configured():
        try:
            result = cloudinary.uploader.upload(
                file_storage,
                folder="skillbridge/course_thumbnails",
                public_id=f"course_thumb_teacher_{teacher_id}_{int(time.time())}",
                overwrite=True,
                resource_type="image",
                transformation=[
                    {"width": 800, "height": 450, "crop": "fill"},
                    {"quality": "auto", "fetch_format": "auto"},
                ],
            )
            secure_url = result.get("secure_url")
            if secure_url:
                return secure_url
        except Exception as exc:
            current_app.logger.warning(
                f"[Cloudinary] Course thumbnail upload failed: {exc}. Falling back to local disk."
            )

    # 2. Local fallback storage
    upload_dir = os.path.join(current_app.root_path, "static", "uploads", "course_thumbnails")
    os.makedirs(upload_dir, exist_ok=True)

    safe_name = secure_filename(f"thumb_teacher_{teacher_id}_{int(time.time())}.{ext}")
    destination = os.path.join(upload_dir, safe_name)
    file_storage.seek(0)
    file_storage.save(destination)

    if has_request_context():
        return url_for("static", filename=f"uploads/course_thumbnails/{safe_name}")
    return f"/static/uploads/course_thumbnails/{safe_name}"


def upload_lesson_video(file_storage, course_id: int) -> str:
    """
    Upload lesson video to Cloudinary with fallback to local disk.
    Validates against ALLOWED_VIDEO_EXTENSIONS and MAX_VIDEO_SIZE.
    Returns the URL/path to the video.
    """
    if not file_storage or not file_storage.filename:
        raise ValueError("No video file selected.")

    filename = file_storage.filename
    allowed_exts = current_app.config.get("ALLOWED_VIDEO_EXTENSIONS", {"mp4"})
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in allowed_exts:
        raise ValueError(
            f"Unsupported video format '.{ext}'. Allowed formats: {', '.join(sorted(allowed_exts)).upper()}."
        )

    file_storage.seek(0, os.SEEK_END)
    file_size = file_storage.tell()
    file_storage.seek(0)

    max_size = current_app.config.get("MAX_VIDEO_SIZE", 500 * 1024 * 1024)
    if file_size > max_size:
        max_mb = max_size // (1024 * 1024)
        raise ValueError(f"Video file exceeds the {max_mb}MB limit.")

    # 1. Attempt upload to Cloudinary
    if _is_cloudinary_configured():
        try:
            result = cloudinary.uploader.upload(
                file_storage,
                folder="skillbridge/lesson_videos",
                public_id=f"course_{course_id}_lesson_{int(time.time())}",
                overwrite=True,
                resource_type="video",
            )
            secure_url = result.get("secure_url")
            if secure_url:
                return secure_url
        except Exception as exc:
            current_app.logger.warning(
                f"[Cloudinary] Lesson video upload failed: {exc}. Falling back to local disk."
            )

    # 2. Local fallback storage
    upload_dir = os.path.join(current_app.root_path, "static", "uploads", "lesson_videos")
    os.makedirs(upload_dir, exist_ok=True)

    safe_name = secure_filename(f"course_{course_id}_vid_{int(time.time())}.{ext}")
    destination = os.path.join(upload_dir, safe_name)
    file_storage.seek(0)
    file_storage.save(destination)

    if has_request_context():
        return url_for("static", filename=f"uploads/lesson_videos/{safe_name}")
    return f"/static/uploads/lesson_videos/{safe_name}"


def upload_lesson_pdf(file_storage, course_id: int) -> str:
    """
    Upload lesson PDF document to Cloudinary with fallback to local disk.
    Validates against ALLOWED_DOC_EXTENSIONS.
    Returns the URL/path to the PDF.
    """
    if not file_storage or not file_storage.filename:
        raise ValueError("No PDF file selected.")

    filename = file_storage.filename
    allowed_exts = current_app.config.get("ALLOWED_DOC_EXTENSIONS", {"pdf"})
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in allowed_exts:
        raise ValueError(
            f"Unsupported document format '.{ext}'. Allowed: {', '.join(sorted(allowed_exts)).upper()}."
        )

    file_storage.seek(0, os.SEEK_END)
    file_size = file_storage.tell()
    file_storage.seek(0)

    # Max 50 MB for PDF
    max_size = 50 * 1024 * 1024
    if file_size > max_size:
        raise ValueError("PDF document exceeds the 50MB limit.")

    # 1. Attempt upload to Cloudinary
    if _is_cloudinary_configured():
        try:
            result = cloudinary.uploader.upload(
                file_storage,
                folder="skillbridge/lesson_pdfs",
                public_id=f"course_{course_id}_doc_{int(time.time())}",
                overwrite=True,
                resource_type="raw",
            )
            secure_url = result.get("secure_url")
            if secure_url:
                return secure_url
        except Exception as exc:
            current_app.logger.warning(
                f"[Cloudinary] Lesson PDF upload failed: {exc}. Falling back to local disk."
            )

    # 2. Local fallback storage
    upload_dir = os.path.join(current_app.root_path, "static", "uploads", "lesson_pdfs")
    os.makedirs(upload_dir, exist_ok=True)

    safe_name = secure_filename(f"course_{course_id}_doc_{int(time.time())}.{ext}")
    destination = os.path.join(upload_dir, safe_name)
    file_storage.seek(0)
    file_storage.save(destination)

    if has_request_context():
        return url_for("static", filename=f"uploads/lesson_pdfs/{safe_name}")
    return f"/static/uploads/lesson_pdfs/{safe_name}"


def parse_quiz_data(quiz_raw) -> list[dict]:
    """
    Safely parse quiz data from JSON string or list of dicts.
    Expected format: [{"question": "...", "options": ["A", "B", "C", "D"], "answer": 0}, ...]
    """
    if not quiz_raw:
        return []
    if isinstance(quiz_raw, list):
        return quiz_raw
    if isinstance(quiz_raw, str):
        try:
            data = json.loads(quiz_raw)
            if isinstance(data, list):
                return data
            return []
        except (json.JSONDecodeError, TypeError):
            return []
    return []


def format_quiz_data(questions: list[dict]) -> str:
    """Serialize a list of quiz question dicts to standard JSON string."""
    cleaned = []
    for q in questions:
        question_text = str(q.get("question", "")).strip()
        options = [str(opt).strip() for opt in q.get("options", []) if str(opt).strip()]
        answer = int(q.get("answer", 0))
        if question_text and len(options) >= 2:
            cleaned.append({
                "question": question_text,
                "options": options,
                "answer": answer if 0 <= answer < len(options) else 0,
            })
    return json.dumps(cleaned)
