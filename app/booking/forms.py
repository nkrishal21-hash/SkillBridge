"""
app/booking/forms.py — Mentorship Booking Forms
WTForms classes for scheduling 1-on-1 sessions and teacher approvals.
"""

from datetime import date
from flask_wtf import FlaskForm
from wtforms import (
    DateField,
    SelectField,
    StringField,
    TextAreaField,
    SubmitField,
)
from wtforms.validators import (
    DataRequired,
    Optional,
    Length,
    ValidationError,
)

# Standard half-hour time slots between 8:00 AM and 8:00 PM
TIME_SLOT_CHOICES = [
    ("08:00", "08:00 AM"),
    ("08:30", "08:30 AM"),
    ("09:00", "09:00 AM"),
    ("09:30", "09:30 AM"),
    ("10:00", "10:00 AM"),
    ("10:30", "10:30 AM"),
    ("11:00", "11:00 AM"),
    ("11:30", "11:30 AM"),
    ("12:00", "12:00 PM"),
    ("12:30", "12:30 PM"),
    ("13:00", "01:00 PM"),
    ("13:30", "01:30 PM"),
    ("14:00", "02:00 PM"),
    ("14:30", "02:30 PM"),
    ("15:00", "03:00 PM"),
    ("15:30", "03:30 PM"),
    ("16:00", "04:00 PM"),
    ("16:30", "04:30 PM"),
    ("17:00", "05:00 PM"),
    ("17:30", "05:30 PM"),
    ("18:00", "06:00 PM"),
    ("18:30", "06:30 PM"),
    ("19:00", "07:00 PM"),
    ("19:30", "07:30 PM"),
    ("20:00", "08:00 PM"),
]

DURATION_CHOICES = [
    (30, "30 minutes (Half session)"),
    (60, "60 minutes (1 hour)"),
    (90, "90 minutes (1.5 hours)"),
]


class BookingForm(FlaskForm):
    """Form for learners to request a 1-on-1 session with a mentor."""

    session_date = DateField(
        "Session Date",
        format="%Y-%m-%d",
        validators=[DataRequired(message="Please choose a session date.")],
        render_kw={"type": "date"},
    )

    start_time = SelectField(
        "Start Time",
        choices=TIME_SLOT_CHOICES,
        default="10:00",
        validators=[DataRequired(message="Please select a start time.")],
    )

    duration_minutes = SelectField(
        "Session Duration",
        choices=DURATION_CHOICES,
        coerce=int,
        default=60,
        validators=[DataRequired()],
    )

    topic = StringField(
        "Topic / Learning Goals",
        validators=[
            DataRequired(message="Please specify the topic or goal for this session."),
            Length(max=300, message="Topic must be under 300 characters."),
        ],
        render_kw={"placeholder": "e.g. Python AsyncIO Debugging & Code Review"},
    )

    learner_notes = TextAreaField(
        "Notes & Questions for Mentor",
        validators=[
            Optional(),
            Length(max=2000, message="Notes must be under 2000 characters."),
        ],
        render_kw={
            "rows": 4,
            "placeholder": "Provide context, repository links, or specific questions you would like to discuss...",
        },
    )

    submit = SubmitField("Request Mentorship Session")

    def validate_session_date(self, field):
        """Ensure booking session is not scheduled in the past."""
        if field.data and field.data < date.today():
            raise ValidationError("Session date cannot be in the past.")


class BookingResponseForm(FlaskForm):
    """Form for teachers to approve or reject a session request with optional notes."""

    teacher_response_note = TextAreaField(
        "Note to Learner",
        validators=[
            Optional(),
            Length(max=2000, message="Response note must be under 2000 characters."),
        ],
        render_kw={
            "rows": 3,
            "placeholder": "Optional note, meeting prep instructions, or explanation...",
        },
    )

    submit = SubmitField("Submit Response")
