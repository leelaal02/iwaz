import json
from pathlib import Path

from render_markdown import render_markdown

SAMPLE = Path(__file__).resolve().parent.parent / "examples" / "sample_minutes.json"


def _sample():
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


def test_title_and_sections_present():
    md = render_markdown(_sample())
    assert md.startswith("# 2026 3분기 제품 로드맵 회의")
    for heading in ["## 참석자", "## 논의 내용", "## 결정 사항",
                    "## Action Items", "## 다음 회의 일정"]:
        assert heading in md


def test_action_items_table():
    md = render_markdown(_sample())
    assert "| 할 일 | 담당자 | 기한 |" in md
    assert "| python-docx 렌더러 PoC 작성 | 이정우 | 2026-07-23 |" in md


def test_null_due_rendered_as_dash():
    md = render_markdown(_sample())
    assert "| 샘플 회의 원문 수집 | 박서연 | - |" in md


def test_empty_and_null_fields():
    data = _sample()
    data["attendees"] = []
    data["action_items"] = []
    data["next_meeting"] = None
    md = render_markdown(data)
    assert "- (없음)" in md          # 빈 참석자
    assert "(미정)" in md            # next_meeting None
