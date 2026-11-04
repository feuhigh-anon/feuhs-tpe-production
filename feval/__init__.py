"""Faculty evaluation aggregation toolkit."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from feval.questions import DEFAULT_QUESTION_BLOCKS, get_question_block

__all__ = ["DEFAULT_QUESTION_BLOCKS", "get_question_block"]


def __getattr__(name: str):
    if name in __all__:
        from feval import questions

        return getattr(questions, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
