"""Default SHS and JHS question blocks."""

from __future__ import annotations

from typing import Dict, Iterable, Optional

from feval.models import QuestionBlock, QuestionItem


def _question_items(
    prefix: str,
    group: str,
    texts: Iterable[str],
    *,
    required: bool = True,
    rci_start: Optional[int] = None,
) -> tuple[QuestionItem, ...]:
    items = []
    for index, text in enumerate(texts, start=1):
        items.append(
            QuestionItem(
                id=f"{prefix}_{group}_{index:02d}",
                text=text,
                aliases=(
                    f"{prefix} {group} {index}",
                    f"{prefix}-{group}-{index}",
                    f"{group} {index}",
                    f"Question {index}",
                    f"{prefix}_{group}_{index:02d}",
                ),
                required=required,
                use_for_rci=rci_start is None or index >= rci_start,
            )
        )
    return tuple(items)


SHS_FACULTY_TEXTS = (
    "My teacher starts and ends the class on time.",
    "My teacher explains the objectives and instructions of our lessons clearly.",
    "My teacher is very good at handling the students and managing the class.",
    "My teacher provides different strategies to help us learn the lesson.",
    "My teacher assigns assessments in advance that can be accomplished within the allotted time.",
    "My teacher returns graded assessments regularly.",
    "My teacher provides learning materials that are readily available or easily accessible.",
    "My teacher is available for consultations.",
    "My teacher replies to posts and messages during asynchronous sessions.",
    "My teacher provides help for students who are having difficulties or are advanced in the lesson or activity.",
)

JHS_FACULTY_TEXTS = (
    "My teacher starts and ends the class on time.",
    "My teacher tells us what we're going to do in class and explains it so we can understand.",
    "My teacher is really good at making sure the class behaves well and listens.",
    "My teacher teaches us different ways to learn new things.",
    "My teacher gives us activities to do that we can finish during class.",
    "My teacher regularly returns our graded tests and activities.",
    "My teacher gives us things to use for learning that are easy to get or understand.",
    "My teacher is there to talk to if we need help.",
    "My teacher writes back to us when we write or message them during online lessons.",
    "My teacher helps students who are having problems with the lesson or students who want to learn more.",
)

SHS_SELF_TEXTS = (
    "I feel respected and appreciated as a student in class.",
    "I felt my teacher is genuinely interested in my academic growth and success.",
    "I find it easy and comfortable to ask questions and seek help when needed.",
    "I am challenged by the subject and teacher in a way that promotes my learning and growth.",
    "I feel that the teacher encourages active participation and class engagement.",
    "I improved my understanding and performance through my teacher's constructive feedback.",
    "I am motivated to learn and excel in this class because of the teacher's teaching style.",
    "I felt my sharing of ideas and perspectives were valued in class.",
    "I developed a deeper understanding and appreciation of the subject taught by my teacher.",
    "I feel that this class has positively contributed to my overall learning experience at FEU High School.",
    "I always arrive on time and regularly for class.",
    "I actively participate in class discussions, asking questions and engaging with the material.",
    "I collaborate with classmates when working on class activities or subject requirements.",
    "I turn in my homework and assignments on time and in good quality.",
    "I exerted a lot of effort and dedication in studying for this class.",
)

JHS_SELF_TEXTS = (
    "I feel happy and safe when I'm in my teacher's class.",
    "I think my teacher really cares about how I do in school and wants me to do well.",
    "I can ask questions and get help easily, and it's not scary.",
    "I have to work hard in this class, but it helps me get better at things.",
    "My teacher likes it when we talk and do things in class.",
    "I get better at my assignments and tests when my teacher tells me how to do better.",
    "I want to learn and do my best because of my teacher.",
    "My teacher is happy when I share my ideas in class.",
    "I know more about the subject because of what my teacher teaches us.",
    "My teacher's class is fun, and it helps me learn a lot at FEU High School.",
    "I arrive on time for class every day.",
    "I actively participate in discussions and ask questions in class to learn more.",
    "I work with my classmates in class when we do projects together.",
    "I finish all my homework and give it to the teacher on time.",
    "I worked really hard when I was studying for this class.",
)

SHS_OPEN_TEXTS = (
    "What strategies and practices did you appreciate the most about your teacher?",
    "What are some constructive suggestions you can give to help them handle students or teach better?",
    "Overall how was your learning experience with your teacher?",
)

JHS_OPEN_TEXTS = (
    "What did you like the most about your teacher's way of teaching?",
    "How do you think your teacher can be better at helping students like you?",
    "Overall, how was your learning experience with your teacher?",
)

SHS_FACULTY_ITEMS = _question_items("SHS", "TP", SHS_FACULTY_TEXTS)
JHS_FACULTY_ITEMS = _question_items("JHS", "TP", JHS_FACULTY_TEXTS)
SHS_SELF_ITEMS = _question_items("SHS", "SELF", SHS_SELF_TEXTS, rci_start=11)
JHS_SELF_ITEMS = _question_items("JHS", "SELF", JHS_SELF_TEXTS, rci_start=11)
SHS_OPEN_ITEMS = _question_items("SHS", "OPEN", SHS_OPEN_TEXTS, required=False, rci_start=999)
JHS_OPEN_ITEMS = _question_items("JHS", "OPEN", JHS_OPEN_TEXTS, required=False, rci_start=999)

DEFAULT_QUESTION_BLOCKS: Dict[str, QuestionBlock] = {
    "shs": QuestionBlock(
        id="shs",
        label="Senior High School",
        faculty_items=SHS_FACULTY_ITEMS,
        self_eval_items=SHS_SELF_ITEMS,
        open_ended_items=SHS_OPEN_ITEMS,
    ),
    "jhs": QuestionBlock(
        id="jhs",
        label="Junior High School",
        faculty_items=JHS_FACULTY_ITEMS,
        self_eval_items=JHS_SELF_ITEMS,
        open_ended_items=JHS_OPEN_ITEMS,
    ),
}


def get_question_block(block_id: str) -> QuestionBlock:
    try:
        return DEFAULT_QUESTION_BLOCKS[block_id.lower()]
    except KeyError as exc:
        valid = ", ".join(sorted(DEFAULT_QUESTION_BLOCKS))
        raise ValueError(f"Unknown question block {block_id!r}. Valid blocks: {valid}") from exc
