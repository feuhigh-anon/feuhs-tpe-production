"""Student-portal instruments transcribed from the September 2026 source tools.

The live portal loads the published Supabase versions. These local definitions
power the demo and document the intended target-specific layout.
"""
from __future__ import annotations

from feval.models import QuestionBlock, QuestionItem


def _items(prefix, rows, *, scale=5, response_type="likert_5"):
    return tuple(QuestionItem(
        id=f"{prefix}_{i:02d}", text=text, required=True,
        use_for_rci=False, response_type=response_type, rating_max=scale,
    ) for i, text in enumerate(rows, 1))


def _block(block_id, label, target_type, sections, scale=5):
    forms = tuple((title, _items(f"{block_id}_{key}", rows, scale=scale,
                response_type="text" if kind == "comments" else ("likert_4" if scale == 4 else "likert_5")), kind)
                  for key, title, rows, kind in sections)
    ratings = tuple(item for _, items, kind in forms if kind == "rating" for item in items)
    texts = tuple(item for _, items, kind in forms if kind == "comments" for item in items)
    return QuestionBlock(
        id=block_id, label=label, faculty_items=ratings, self_eval_items=(),
        open_ended_items=texts, target_type=target_type, form_sections=forms,
        rating_labels=tuple((i, label) for i, label in enumerate(
            ("Strongly Disagree", "Disagree", "Neutral", "Agree", "Strongly Agree") if scale == 5
            else ("Strongly Disagree", "Disagree", "Agree", "Strongly Agree"), 1)),
    )


SUBJECT_TEACHER = _block("subject_teacher", "Subject Teacher Evaluation", "subject_teacher", (
    ("practice", "A. Teaching Practice and Instructional Delivery", (
        "My teacher clearly explains lesson objectives, instructions, and content, connecting lessons to real-life situations or other subjects.",
        "My teacher uses different teaching strategies and activities that help me understand and learn the lesson.",
        "My teacher asks thought-provoking questions, values the questions we ask, and gives us chances to explain our own ideas, lead discussions, and come up with our own solutions.",
        "My teacher connects meaningfully the activities in Canvas/online tasks.",
        "My teacher communicates clearly (through language, tone, and gestures) in a way I can understand.",
        "My teacher provides learning materials that are useful, well-organized, and easy to access.",
        "My teacher gives assessments/activities that match what was taught and can be reasonably finished within the given time.",
        "My teacher gives timely and specific feedback on my work that helps me improve.",), "rating"),
    ("classroom", "B. Classroom Environment and Learning Experience", (
        "My teacher starts and ends class on time, comes prepared, and stays fully present and engaged throughout.",
        "My teacher checks attendance regularly and follows up when I am absent.",
        "My teacher treats all students fairly, with respect and care, and creates a safe space where I feel comfortable to participate, ask questions, and take risks.",
        "When there is misbehavior, my teacher handles it in a way that helps students reflect and improve, rather than just punish.",
        "My teacher adjusts lessons and activities to fit different students' needs, abilities, and backgrounds.",
        "My teacher connects our lessons to FEU's Vision, Mission, and Core Values (Fortitude, Excellence, Uprightness).",
        "I feel motivated to learn and participate because of how my teacher teaches and treats the class.",), "rating"),
    ("self", "Student Self-Evaluation", (
        "I always arrive on time and regularly for class.",
        "I actively participate in class discussions, asking questions and engaging with the material.",
        "I collaborate with classmates when working on class activities/subject requirements.",
        "I turn in my activities and assessments on time and in good quality.",
        "I exerted a lot of effort and dedication in studying for this class.",), "rating"),
    ("feedback", "Qualitative Feedback", (
        "What strategies and practices did you appreciate the most about your teacher?",
        "What constructive suggestions can you give to help your teacher handle students or teach better?",
        "Overall, how was your learning experience with your teacher?",), "comments"),
))


HOMEROOM_ADVISER = _block("homeroom_adviser", "Homeroom Adviser Evaluation", "homeroom_adviser", (
    ("fortitude", "A. Fortitude — Resilience — Showing Up", (
        "My HRA regularly checks student attendance and proactively follows up on absences.",
        "My HRA arrives prepared for homeroom sessions and begins and ends them on time.",
        "My HRA maintains an active and engaged presence throughout homeroom sessions."), "rating"),
    ("excellence", "B. Excellence — Curiosity — Asking Thoughtful Questions", (
        "My HRA intentionally incorporates and elaborates on thoughtful questions during homeroom sessions.",
        "My HRA ensures that multiple students are intentionally invited to explain, challenge, and refine ideas, making student thinking visible during classroom discussions.",
        "My HRA actively encourage students to ask questions. Recognize insightful inquiries, and reinforce questioning as a valued habit."), "rating"),
    ("uprightness", "C. Uprightness — Integrity — Owning Actions and Making Things Right", (
        "My HRA addresses student misbehavior fairly and promotes learning, reflection, and personal growth.",
        "My HRA consistently follows through on classroom expectations, agreements, and reminders.",
        "My HRA models accountability by acknowledging mistakes or areas for improvement and making appropriate adjustments."), "rating"),
    ("overall", "Overall Evaluation", (
        "Overall, my HRA effectively facilitates homeroom sessions and has been effective in guiding me academically and supporting my personal development.",), "rating"),
    ("feedback", "Qualitative Feedback", (
        "What are the most commendable characteristics of your homeroom adviser?",
        "What are the aspects of your homeroom adviser that need improvement?"), "comments"),
))


HOMEROOM_PROGRAM = _block("homeroom_program", "Homeroom Program Evaluation", "homeroom_program", (
    ("fortitude", "1. Fortitude — Resilience — Showing Up", (
        "The program helped me become more consistent in attending and actively participating in homeroom sessions.",
        "The program encouraged me to be present, engaged, and prepared during homeroom activities.",
        "The program helped me become more responsible in showing up and participating meaningfully in school activities."), "rating"),
    ("excellence", "2. Excellence — Curiosity — Asking Thoughtful Questions", (
        "The program encouraged me to ask meaningful and reflective questions during discussions.",
        "The program helped me become more confident in expressing my thoughts, analyzing perspectives, and evaluating ideas critically.",
        "The program helped me develop curiosity and deeper thinking about academic, personal, and social topics."), "rating"),
    ("uprightness", "3. Uprightness — Integrity — Owning Actions and Making Things Right", (
        "The program helped me become more accountable for my actions and decisions.",
        "The program helped me learn the importance of acknowledging mistakes and taking steps to correct them.",
        "The program provided opportunities for me to reflect on my actions and make better choices when faced with challenges."), "rating"),
    ("platform", "4. Shared Platform — HRA and Student-led Sessions", (
        "The Shared Platform helped make homeroom sessions more organized, purposeful, and responsive to student needs.",
        "The Shared Platform encouraged collaboration, active participation, and the sharing of ideas among classmates.",
        "The Shared Platform supported student reflection, feedback, and communication with the homeroom adviser."), "rating"),
    ("structure", "5. Program Structure and Implementation", (
        "The structure of the Be Brave Homeroom Program effectively integrated Showing Up, Asking Thoughtful Questions, and Owning Actions & Making Things Right.",
        "The homeroom sessions were well-organized, relevant, and engaging.",
        "The duration and pacing of the homeroom sessions were sufficient to support student formation and reflection."), "rating"),
    ("overall", "6. Overall Experience", (
        "Overall, the Be Brave Homeroom Program has significantly contributed to making the school a safe space for me, where I am able to consistently show up, ask thoughtful questions, and take ownership of my actions, while also helping me support others with resilience in adversity, a commitment to continuous growth, and the courage to do what is right even when it is difficult.",), "rating"),
    ("feedback", "Qualitative Feedback", (
        "What topics and activities do you like most about your homeroom?",
        "What topics and activities do you like least about your homeroom?",
        "Do you have any topic/activity suggestions that you want to include in future homeroom sessions?",
        "Additional Comments:"), "comments"),
), scale=4)


PORTAL_INSTRUMENTS = {
    "subject_teacher": SUBJECT_TEACHER,
    "homeroom_adviser": HOMEROOM_ADVISER,
    "homeroom_program": HOMEROOM_PROGRAM,
}
