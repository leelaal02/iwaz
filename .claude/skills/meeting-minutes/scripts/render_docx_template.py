"""[4-대체] 템플릿 렌더러: .docx 양식 + minutes.json → 표시자 치환 docx."""
import sys

from normalize_input import resolve_input_path
from validate import load_minutes


def build_context(data: dict) -> dict:
    """minutes.json(dict) → docxtpl 렌더 컨텍스트.

    null 스칼라는 빈 문자열로, action_items의 owner/due null은 "-"로 정규화한다.
    """
    return {
        "title": data["title"],
        "date": data.get("date") or "",
        "purpose": data.get("purpose") or "",
        "next_meeting": data.get("next_meeting") or "",
        "attendees": data["attendees"],
        "attendees_joined": ", ".join(data["attendees"]),
        "discussion": data["discussion"],
        "decisions": data["decisions"],
        "action_items": [
            {"task": a["task"], "owner": a["owner"] or "-", "due": a["due"] or "-"}
            for a in data["action_items"]
        ],
        "notes": data["notes"],
    }


def _load_docxtemplate():
    try:
        from docxtpl import DocxTemplate
    except ImportError as e:
        raise ImportError(
            "docxtpl가 설치되어 있지 않습니다. "
            "'pip install -r requirements.txt'로 설치하세요."
        ) from e
    return DocxTemplate


def render_template(template_path: str, data: dict, out_path: str) -> None:
    """.docx 템플릿의 표시자를 minutes 데이터로 치환해 out_path에 저장한다."""
    resolved = resolve_input_path(template_path, must_exist=True)
    if resolved.suffix.lower() != ".docx":
        raise ValueError(
            f"템플릿은 .docx여야 합니다: {resolved.name}. "
            "hwp/pdf 양식이면 한글/워드에서 .docx로 저장해 다시 주세요."
        )
    DocxTemplate = _load_docxtemplate()
    from jinja2 import TemplateError
    tpl = DocxTemplate(str(resolved))
    try:
        # autoescape=True: 값에 든 XML 특수문자(&, <, >)를 이스케이프해 보존한다.
        # (기본값 False면 "R&D"·"<A>" 같은 값이 렌더 시 잘리거나 사라진다.)
        tpl.render(build_context(data), autoescape=True)
    except TemplateError as e:
        raise ValueError(
            f"템플릿의 표시자 문법에 오류가 있습니다: {e}. "
            "{{ }}·{% %}·{%tr %}·{%p %} 토큰을 치트시트와 비교해 확인하세요."
        ) from e
    # 양식 표의 행 나눔 금지를 풀어 긴 내용이 페이지를 자연스럽게 넘어가게 한다.
    from docx_postprocess import allow_rows_to_break
    allow_rows_to_break(tpl.docx)
    tpl.save(out_path)


def main() -> None:
    template_path, json_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    data = load_minutes(json_path)
    render_template(template_path, data, out_path)
    print(f"템플릿 docx 생성 완료: {out_path}")


if __name__ == "__main__":
    main()
