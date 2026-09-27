import pytest

from core.contracts import Category
from core.sensing.categorize import categorize

from .conftest import synthetic_span as span


@pytest.mark.parametrize("process,title,expected", [
    ("winword.exe", "", Category.work), ("chrome.exe", "CAP3", Category.work),
    ("chrome.EXE", "YouTube", Category.distraction), ("DISCORD.exe", "", Category.distraction),
    ("notepad.exe", "youtube", Category.other), ("DiscordHelper.exe", "", Category.other),
    ("?", "", Category.other), ("__paused__", "cap3", Category.other),
])
def test_classification(block, settings, process, title, expected):
    assert categorize(span(0, 10, process, title), block, settings) == expected


def test_no_work_without_block(settings):
    assert categorize(span(0, 10), None, settings) == Category.other


def test_work_precedence_and_whitelist(block, settings):
    settings.whitelist_processes = ["chrome.EXE"]
    assert categorize(span(0, 10, "chrome.exe", "youtube"), block, settings) == Category.other
    assert categorize(span(0, 10, "chrome.exe", "youtube cap3"), block, settings) == Category.work
