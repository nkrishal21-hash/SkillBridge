"""
app/reviews/forms.py — Review & Rating Submission Forms
"""

from flask_wtf import FlaskForm
from wtforms import SelectField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Optional, Length


class ReviewForm(FlaskForm):
    """Form for learners to leave a 1-5 star rating and written review."""

    rating_value = SelectField(
        "Rating",
        choices=[
            (5, "⭐⭐⭐⭐⭐  (5 — Excellent)"),
            (4, "⭐⭐⭐⭐  (4 — Very Good)"),
            (3, "⭐⭐⭐  (3 — Good)"),
            (2, "⭐⭐  (2 — Fair)"),
            (1, "⭐  (1 — Poor)"),
        ],
        coerce=int,
        default=5,
        validators=[DataRequired(message="Please choose a star rating from 1 to 5.")],
    )

    review_text = TextAreaField(
        "Review & Feedback",
        validators=[
            Optional(),
            Length(max=2000, message="Review cannot exceed 2000 characters."),
        ],
        render_kw={
            "rows": 4,
            "placeholder": "Share what you learned, what you liked most, and constructive feedback for the mentor...",
        },
    )

    submit = SubmitField("Submit Review & Rating")
