"""
app/reports/forms.py — Incident Reporting Forms
"""

from flask_wtf import FlaskForm
from wtforms import SelectField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Optional, Length


class ReportForm(FlaskForm):
    """Form for reporting attendance or behavioral issues in a booked session."""

    reason = SelectField(
        "Reason for Report",
        choices=[
            ("late", "⏰ Late Arrival / Tardy"),
            ("no_show", "🚫 No Show / Absent"),
            ("misbehavior", "⚠️ Misbehavior / Unprofessional Conduct"),
            ("other", "📝 Other Issue"),
        ],
        validators=[DataRequired(message="Please select a reason for the report.")],
    )

    description = TextAreaField(
        "Details & Description",
        validators=[
            Optional(),
            Length(max=2000, message="Description cannot exceed 2000 characters."),
        ],
        render_kw={
            "rows": 4,
            "placeholder": "Provide relevant context, timestamps, or details about the issue...",
        },
    )

    submit = SubmitField("Submit Report")
