"""
app/reports/forms.py — Report Admin Forms & Reason Definitions
"""

from flask_wtf import FlaskForm
from wtforms import SelectField, TextAreaField, SubmitField, RadioField
from wtforms.validators import DataRequired, Optional, Length

LEARNER_REPORT_REASONS = [
    ("late", "⏰ Teacher Came Late / Tardy"),
    ("no_show", "🚫 Teacher Did Not Attend / No Show"),
    ("misbehavior", "⚠️ Teacher Misbehavior / Disrespectful Conduct"),
    ("inappropriate_behavior", "🚫 Inappropriate Behavior While Teaching"),
    ("session_not_properly_taught", "📉 Session Not Properly Taught"),
    ("teacher_marked_completed_without_teaching", "❌ Marked Completed Without Teaching"),
    ("false_or_misleading_information", "🤥 False or Misleading Information"),
    ("session_issue", "🛠️ Session Quality / Platform Issue"),
    ("other", "📝 Other Session Issue"),
]

TEACHER_REPORT_REASONS = [
    ("no_show", "🚫 Student Did Not Attend / Absent"),
    ("misbehavior", "⚠️ Student Misbehavior / Disrespectful Conduct"),
    ("inappropriate_behavior", "🚫 Inappropriate Behavior"),
    ("false_or_misleading_information", "🤥 False Accusation / Misleading Information"),
    ("other", "📝 Other Session Issue"),
]

ALL_REPORT_REASONS = [
    ("late", "⏰ Late Arrival / Tardy"),
    ("no_show", "🚫 No Show / Absent"),
    ("misbehavior", "⚠️ Misbehavior / Unprofessional Conduct"),
    ("inappropriate_behavior", "🚫 Inappropriate Behavior While Teaching"),
    ("session_not_properly_taught", "📉 Session Not Properly Taught"),
    ("teacher_marked_completed_without_teaching", "❌ Marked Completed Without Teaching"),
    ("false_or_misleading_information", "🤥 False or Misleading Information"),
    ("session_issue", "🛠️ Session Issue"),
    ("other", "📝 Other Issue"),
]

REPORT_REASON_DICT = dict(ALL_REPORT_REASONS)
# Extra label aliases for compatibility
REPORT_REASON_DICT.update({
    "cancelled_by_teacher": "Cancelled by Teacher",
    "cancelled_by_student": "Cancelled by Student",
    "session_not_held": "Session Not Held",
    "teacher_marked_complete_without_teaching": "Marked Complete Without Teaching",
})

EVIDENCE_REQUIRED_REASONS = {
    "late",
    "no_show",
    "misbehavior",
    "inappropriate_behavior",
    "session_not_properly_taught",
    "teacher_marked_completed_without_teaching",
    "false_or_misleading_information",
}


class ReportForm(FlaskForm):
    """
    Unified Report Admin form for learners and teachers.
    Learners can optionally select request_refund='yes'.
    Teachers will have request_refund suppressed/ignored.
    """

    reason = SelectField(
        "Reason for Report",
        choices=ALL_REPORT_REASONS,
        validators=[DataRequired(message="Please select a reason for the report.")],
    )

    description = TextAreaField(
        "Details & Description",
        validators=[
            Optional(),
            Length(max=3000, message="Description cannot exceed 3000 characters."),
        ],
        render_kw={
            "rows": 4,
            "placeholder": "Provide relevant context, timestamps, or details about the issue...",
        },
    )

    request_refund = RadioField(
        "Do you want to request a refund?",
        choices=[("no", "No, report only"), ("yes", "Yes, request a refund")],
        default="no",
        validators=[Optional()],
    )

    submit = SubmitField("Submit Report to Admin")


class ReportResponseForm(FlaskForm):
    """
    Form for a reported teacher or learner to submit a formal response
    and explanation to an active Report Admin case.
    """

    explanation = TextAreaField(
        "Your Explanation & Response",
        validators=[
            DataRequired(message="Please provide an explanation or response to the report."),
            Length(max=3000, message="Response cannot exceed 3000 characters."),
        ],
        render_kw={
            "rows": 4,
            "placeholder": "Explain your perspective, clarify any misunderstandings, or refute false claims...",
        },
    )

    submit = SubmitField("Submit Response to Admin")
