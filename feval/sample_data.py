"""Demo SharePoint-style exports for local testing and app preview."""

from __future__ import annotations

import random
from typing import Sequence

import pandas as pd

from feval.models import QuestionBlock


LIKERT_LABELS = {
    1: "Strongly Disagree",
    2: "Disagree",
    3: "Neutral",
    4: "Agree",
    5: "Strongly Agree",
}


def make_demo_sharepoint_export(
    block: QuestionBlock,
    rows: int = 90,
    teachers: Sequence[str] = ("A. Santos", "B. Reyes", "C. Lim"),
    seed: int = 7,
) -> pd.DataFrame:
    """Create a synthetic export with realistic SharePoint/MS Forms-style headers."""

    random.seed(seed)
    teacher_quality = {teacher: random.uniform(3.2, 4.7) for teacher in teachers}
    records = []
    for index in range(rows):
        teacher = teachers[index % len(teachers)]
        engagement = min(5, max(1, round(random.gauss(3.9, 0.8))))
        record = {
            "ID": f"R-{index + 1:04d}",
            "Start time": "2026-06-01 08:00",
            "Completion time": "2026-06-01 08:08",
            "Email": f"student{index + 1:04d}@example.edu",
            "Teacher Name": teacher,
            "Section": f"{block.id.upper()}-{1 + index % 4}",
        }
        for item in block.faculty_items:
            latent = teacher_quality[teacher] + random.gauss(0, 0.65)
            score = min(5, max(1, round(latent)))
            record[item.text] = LIKERT_LABELS[int(score)]
        for item in block.self_eval_items:
            score = min(5, max(1, round(random.gauss(engagement, 0.6))))
            record[item.text] = LIKERT_LABELS[int(score)]
        for position, item in enumerate(block.open_ended_items):
            if position == 0:
                record[item.text] = random.choice(
                    [
                        "The teacher is clear, fair, and organized.",
                        "The lessons are engaging and helpful.",
                        "The teacher is patient and approachable.",
                    ]
                )
            elif position == 1:
                record[item.text] = random.choice(
                    [
                        "More examples during difficult topics would help.",
                        "Feedback could be more consistent.",
                        "Activities are useful but deadlines are sometimes tight.",
                    ]
                )
            else:
                record[item.text] = random.choice(
                    [
                        "Overall the class feels supportive.",
                        "I appreciate the prepared materials.",
                        "Some instructions are unclear, but the teacher responds to questions.",
                    ]
                )
        records.append(record)
    return pd.DataFrame(records)
