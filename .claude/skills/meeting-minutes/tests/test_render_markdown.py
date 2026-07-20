import json
from pathlib import Path

from render_markdown import render_markdown

SAMPLE = Path(__file__).resolve().parent.parent / "examples" / "sample_minutes.json"


def _sample():
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


def test_title_and_sections_present():
    md = render_markdown(_sample())
    assert md.startswith("# 2026 3분기 제품 로드맵 회의")
    for heading in ["## 참석자", "## 회의 목적", "## 논의 내용", "## 결정 사항",
                    "## Action Items", "## 다음 회의 일정", "## 기타·특이사항"]:
        assert heading in md


def test_section_order():
    md = render_markdown(_sample())
    # 회의 목적은 참석자와 논의 내용 사이, 기타·특이사항은 맨 끝(다음 회의 뒤)
    assert md.index("## 참석자") < md.index("## 회의 목적") < md.index("## 논의 내용")
    assert md.index("## 다음 회의 일정") < md.index("## 기타·특이사항")


def test_purpose_and_notes_content():
    md = render_markdown(_sample())
    assert "3분기 제품 로드맵과 STT 연동 범위 확정" in md   # purpose
    assert "- STT 엔진 후보 벤치마크는 다음 스프린트에 진행" in md  # notes 항목


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
    data["purpose"] = None
    data["notes"] = []
    md = render_markdown(data)
    assert "- (없음)" in md          # 빈 참석자/빈 notes
    assert "(미정)" in md            # next_meeting None
    # 회의 목적이 None이면 (없음)으로 렌더
    assert "## 회의 목적\n(없음)" in md
