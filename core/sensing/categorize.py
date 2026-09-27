"""Pure, local classification. Work matchers take precedence over distractions."""
from __future__ import annotations

from core.contracts import ActivitySpan, Block, Category, Settings


def categorize(span: ActivitySpan, block: Block | None, settings: Settings) -> Category:
    if span.process == "__paused__":
        return Category.other
    if block is not None and any(
        matcher.pattern.casefold() in getattr(span, matcher.field).casefold()
        for matcher in block.work_matchers
    ):
        return Category.work
    process = span.process.casefold()
    if process in {p.casefold() for p in settings.whitelist_processes}:
        return Category.other
    if process in {p.casefold() for p in settings.distraction_processes}:
        return Category.distraction
    if process in {p.casefold() for p in settings.browser_processes} and any(
        pattern.casefold() in span.title.casefold()
        for pattern in settings.distraction_title_patterns if pattern
    ):
        return Category.distraction
    return Category.other
