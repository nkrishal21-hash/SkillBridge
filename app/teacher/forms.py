"""
app/teacher/forms.py — Teacher Profile Forms
WTForms-based form for teacher profile editing with availability multi-select and validation.
"""

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (
    StringField,
    TextAreaField,
    IntegerField,
    DecimalField,
    SelectMultipleField,
    URLField,
    SubmitField,
)
from wtforms.widgets import ListWidget, CheckboxInput
from wtforms.validators import (
    DataRequired,
    Optional,
    Length,
    NumberRange,
    URL,
)

DAYS_OF_WEEK = [
    ("Mon", "Monday"),
    ("Tue", "Tuesday"),
    ("Wed", "Wednesday"),
    ("Thu", "Thursday"),
    ("Fri", "Friday"),
    ("Sat", "Saturday"),
    ("Sun", "Sunday"),
]


class TeacherProfileForm(FlaskForm):
    """Form for teachers to edit their public mentor profile."""

    photo = FileField(
        "Profile Photo",
        validators=[
            Optional(),
            FileAllowed(["jpg", "jpeg", "png", "gif", "webp"], "Images only (JPG, PNG, GIF, WEBP)!"),
        ],
    )

    headline = StringField(
        "Professional Headline",
        validators=[
            DataRequired(message="Please provide a professional headline."),
            Length(max=200, message="Headline must be under 200 characters."),
        ],
        render_kw={"placeholder": "e.g. Senior Full-Stack Engineer & Python Mentor"},
    )

    bio = TextAreaField(
        "About Me / Bio",
        validators=[
            Optional(),
            Length(max=2000, message="Bio must be under 2000 characters."),
        ],
        render_kw={
            "rows": 5,
            "placeholder": "Share your background, teaching philosophy, and what learners can expect...",
        },
    )

    skills = StringField(
        "Skills & Subjects (comma-separated)",
        validators=[
            DataRequired(message="Please list at least one skill or subject."),
            Length(max=300, message="Skills string must be under 300 characters."),
        ],
        render_kw={"placeholder": "e.g. Python, Data Structures, Flask, Machine Learning"},
    )

    qualifications = TextAreaField(
        "Qualifications & Certifications",
        validators=[
            Optional(),
            Length(max=1000, message="Qualifications must be under 1000 characters."),
        ],
        render_kw={
            "rows": 3,
            "placeholder": "e.g. B.Sc. Computer Science, AWS Certified Solutions Architect",
        },
    )

    experience_years = IntegerField(
        "Years of Experience",
        validators=[
            Optional(),
            NumberRange(min=0, max=60, message="Experience must be between 0 and 60 years."),
        ],
        default=0,
        render_kw={"placeholder": "e.g. 5", "min": 0, "max": 60},
    )

    teaching_languages = StringField(
        "Teaching Languages",
        validators=[
            Optional(),
            Length(max=200, message="Languages must be under 200 characters."),
        ],
        render_kw={"placeholder": "e.g. English, Nepali, Hindi"},
    )

    hourly_rate = DecimalField(
        "Hourly Mentorship Rate (NPR)",
        places=2,
        validators=[
            DataRequired(message="Hourly rate is required."),
            NumberRange(min=0, message="Hourly rate must be 0 or greater."),
        ],
        render_kw={"placeholder": "e.g. 1000"},
    )

    availability = SelectMultipleField(
        "Weekly Availability (Days)",
        choices=DAYS_OF_WEEK,
        widget=ListWidget(prefix_label=False),
        option_widget=CheckboxInput(),
        validators=[Optional()],
    )

    linkedin_url = URLField(
        "LinkedIn Profile URL",
        validators=[
            Optional(),
            URL(message="Please enter a valid URL starting with http:// or https://"),
            Length(max=300),
        ],
        render_kw={"placeholder": "https://linkedin.com/in/username"},
    )

    website_url = URLField(
        "Personal Website / Portfolio",
        validators=[
            Optional(),
            URL(message="Please enter a valid URL starting with http:// or https://"),
            Length(max=300),
        ],
        render_kw={"placeholder": "https://yourportfolio.com"},
    )

    submit = SubmitField("Save Profile")
