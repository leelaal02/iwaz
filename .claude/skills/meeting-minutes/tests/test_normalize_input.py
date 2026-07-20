from pathlib import Path

import pytest

from normalize_input import load_meeting_text

SAMPLE_TXT = Path(__file__).resolve().parent.parent / "examples" / "sample_meeting.txt"


def test_load_from_string():
    result = load_meeting_text("회의 시작\n논의 내용")
    assert result == "회의 시작\n논의 내용"


def test_load_from_file():
    result = load_meeting_text(str(SAMPLE_TXT))
    assert "STT 연동" in result
    assert "김수민" in result


def test_trailing_whitespace_and_blank_lines_collapsed():
    result = load_meeting_text("첫 줄   \n\n\n\n둘째 줄  ")
    assert result == "첫 줄\n\n둘째 줄"


def test_empty_input_raises():
    with pytest.raises(ValueError):
        load_meeting_text("   \n\n  ")
