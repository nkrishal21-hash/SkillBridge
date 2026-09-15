"""
app/courses/forms.py — Course and Lesson Management Forms
WTForms classes for creating and editing courses, lessons, and quizzes.
"""

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (
    Form,
    StringField,
    TextAreaField,
    SelectField,
    DecimalField,
    IntegerField,
    BooleanField,
    FieldList,
    FormField,
    SubmitField,
)
from wtforms.validators import (
    DataRequired,
    Optional,
    Length,
    NumberRange,
)

COURSE_CATEGORIES = [
    ("Programming", "Programming & Software"),
    ("Web Development", "Web Development"),
    ("Data Science", "Data Science & AI"),
    ("Design", "UI/UX & Graphic Design"),
    ("Business", "Business & Entrepreneurship"),
    ("Languages", "Languages & Communication"),
    ("Other", "Other Skills"),
]

COURSE_LEVELS = [
    ("beginner", "Beginner"),
    ("intermediate", "Intermediate"),
    ("advanced", "Advanced"),
]

CONTENT_TYPES = [
    ("video", "Video Lesson (MP4)"),
    ("pdf", "PDF Notes / Reading Material"),
    ("text", "Text Article / Guide"),
    ("quiz", "Interactive Quiz"),
]


class CourseForm(FlaskForm):
    """Form for teachers to create and edit courses."""

    title = StringField(
        "Course Title",
        validators=[
            DataRequired(message="Please provide a course title."),
            Length(max=200, message="Title must be under 200 characters."),
        ],
        render_kw={"placeholder": "e.g. Complete Python Masterclass: From Zero to Hero"},
    )

    category = SelectField(
        "Category",
        choices=COURSE_CATEGORIES,
        validators=[DataRequired(message="Please select a category.")],
    )

    level = SelectField(
        "Skill Level",
        choices=COURSE_LEVELS,
        default="beginner",
        validators=[DataRequired()],
    )

    language = StringField(
        "Language of Instruction",
        default="English",
        validators=[
            DataRequired(),
            Length(max=50),
        ],
        render_kw={"placeholder": "e.g. English, Nepali"},
    )

    price = DecimalField(
        "Course Price (NPR)",
        places=2,
        default=0.00,
        validators=[
            NumberRange(min=0, message="Price cannot be negative."),
        ],
        render_kw={"placeholder": "0.00 (Enter 0 for Free course)"},
    )

    thumbnail = FileField(
        "Course Thumbnail (16:9 recommended)",
        validators=[
            Optional(),
            FileAllowed(["jpg", "jpeg", "png", "webp", "gif"], "Images only (JPG, PNG, WEBP, GIF)!"),
        ],
    )

    description = TextAreaField(
        "Course Overview / Description",
        validators=[
            Optional(),
            Length(max=3000, message="Description must be under 3000 characters."),
        ],
        render_kw={
            "rows": 6,
            "placeholder": "Describe what learners will learn, prerequisites, and course outcomes...",
        },
    )

    submit = SubmitField("Save Course")


class QuizQuestionForm(Form):
    """Sub-form for a single multiple-choice question in a quiz."""

    question = StringField(
        "Question",
        validators=[DataRequired(message="Question prompt is required.")],
        render_kw={"placeholder": "e.g. What is the output of print(2 ** 3) in Python?"},
    )

    option_1 = StringField(
        "Option 1",
        validators=[DataRequired(message="Option 1 is required.")],
        render_kw={"placeholder": "Option A"},
    )

    option_2 = StringField(
        "Option 2",
        validators=[DataRequired(message="Option 2 is required.")],
        render_kw={"placeholder": "Option B"},
    )

    option_3 = StringField(
        "Option 3",
        validators=[Optional()],
        render_kw={"placeholder": "Option C (optional)"},
    )

    option_4 = StringField(
        "Option 4",
        validators=[Optional()],
        render_kw={"placeholder": "Option D (optional)"},
    )

    answer = SelectField(
        "Correct Option",
        choices=[(0, "Option 1"), (1, "Option 2"), (2, "Option 3"), (3, "Option 4")],
        coerce=int,
        default=0,
        validators=[NumberRange(min=0, max=3)],
    )


class LessonForm(FlaskForm):
    """Form for teachers to add or edit a lesson in a course."""

    title = StringField(
        "Lesson Title",
        validators=[
            DataRequired(message="Please provide a lesson title."),
            Length(max=200, message="Title must be under 200 characters."),
        ],
        render_kw={"placeholder": "e.g. Introduction to Variables and Data Types"},
    )

    order = IntegerField(
        "Lesson Sequence / Order",
        default=1,
        validators=[
            DataRequired(),
            NumberRange(min=1, message="Sequence order must be at least 1."),
        ],
        render_kw={"min": 1},
    )

    content_type = SelectField(
        "Lesson Type",
        choices=CONTENT_TYPES,
        default="video",
        validators=[DataRequired()],
    )

    duration_minutes = IntegerField(
        "Estimated Duration (Minutes)",
        validators=[
            Optional(),
            NumberRange(min=1, max=600, message="Duration must be between 1 and 600 minutes."),
        ],
        render_kw={"placeholder": "e.g. 15", "min": 1},
    )

    is_preview = BooleanField(
        "Allow Free Preview (learners can view this lesson before enrolling)"
    )

    description = TextAreaField(
        "Lesson Summary / Notes",
        validators=[
            Optional(),
            Length(max=2000, message="Description must be under 2000 characters."),
        ],
        render_kw={
            "rows": 3,
            "placeholder": "Brief summary of what this lesson covers...",
        },
    )

    # Content-specific fields
    video_file = FileField(
        "Upload Video (MP4, up to 500MB)",
        validators=[
            Optional(),
            FileAllowed(["mp4"], "MP4 videos only!"),
        ],
    )

    pdf_file = FileField(
        "Upload PDF Notes / Handout (up to 50MB)",
        validators=[
            Optional(),
            FileAllowed(["pdf"], "PDF documents only!"),
        ],
    )

    text_content = TextAreaField(
        "Article / Text Content",
        validators=[
            Optional(),
            Length(max=20000, message="Content must be under 20,000 characters."),
        ],
        render_kw={
            "rows": 10,
            "placeholder": "Write or paste your lesson content, code snippets, or lecture notes...",
        },
    )

    quiz_pass_score = IntegerField(
        "Quiz Passing Score (%)",
        default=60,
        validators=[
            Optional(),
            NumberRange(min=1, max=100, message="Passing score must be between 1 and 100%."),
        ],
        render_kw={"min": 1, "max": 100, "placeholder": "60"},
    )

    quiz_questions = FieldList(FormField(QuizQuestionForm), min_entries=0)

    submit = SubmitField("Save Lesson")
