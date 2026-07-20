from pathlib import Path

from adapters.text import transcribe as text_transcribe

SAMPLE_TXT = Path(__file__).resolve().parent.parent / "examples" / "sample_meeting.txt"


def test_text_adapter_from_string():
    assert text_transcribe("첫 줄   \n\n\n\n둘째 줄  ") == "첫 줄\n\n둘째 줄"


def test_text_adapter_from_file():
    result = text_transcribe(str(SAMPLE_TXT))
    assert "STT 연동" in result
    assert "김수민" in result
