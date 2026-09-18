"""
app/reviews/__init__.py — Reviews & Ratings Blueprint
"""

from flask import Blueprint

reviews_bp = Blueprint("reviews", __name__)

from app.reviews import routes  # noqa: E402, F401
