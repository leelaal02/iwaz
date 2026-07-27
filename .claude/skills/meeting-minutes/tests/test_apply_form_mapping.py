"""apply_form_mapping.py 테스트: 토큰 블록 라이브러리 + 삽입 + 엔드투엔드."""
import json
from pathlib import Path

import pytest
from docx import Document

from apply_form_mapping import apply_mapping, block_lines, inline_tokens

SAMPLE = Path(__file__).resolve().parent.parent / "examples" / "sample_minutes.json"


def _sample():
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


def _make_form(path, rows=4, cols=2):
    """빈 표 서식(라벨 칸 포함)을 만든다."""
    doc = Document()
    table = doc.add_table(rows=rows, cols=cols)
    table.cell(1, 0).text = "제 목 :"
    table.cell(2, 0).text = "일 시 :"
    doc.save(str(path))


def _cell_texts(out_path, table=0, row=0, col=0):
    t = Document(str(out_path)).tables[table]
    return [p.text for p in t.rows[row].cells[col].paragraphs]


# --- 토큰 블록 라이브러리 단위 테스트 ---------------------------------------
def test_inline_tokens_join():
    assert inline_tokens(["title"]) == "{{ title }}"
    assert inline_tokens(["date"]) == "{{ date }}"
    assert inline_tokens(["attendees"]) == "{{ attendees_joined }}"


def test_inline_rejects_list_field():
    with pytest.raises(ValueError, match="목록형"):
        inline_tokens(["discussion"])


def test_block_single_field_no_section_label():
    lines = block_lines(["decisions"])
    assert lines == ["{%p for x in decisions %}", " - {{ x }}", "{%p endfor %}"]
    assert not any(line.startswith("[결정 사항]") for line in lines)


def test_block_single_scalar_is_value_token():
    assert block_lines(["purpose"]) == ["{{ purpose }}"]


def test_block_multi_field_adds_section_labels():
    lines = block_lines(["purpose", "next_meeting"])
    assert lines == ["[회의 목적] {{ purpose }}", "[다음 회의] {{ next_meeting }}"]


def test_block_multi_list_field_prepends_label_line():
    lines = block_lines(["decisions", "notes"])
    assert lines[0] == "[결정 사항]"
    assert "{%p for x in decisions %}" in lines
    assert "[기타·특이사항]" in lines


def test_unknown_field_raises():
    with pytest.raises(ValueError, match="알 수 없는 field"):
        block_lines(["bogus"])


# --- 삽입 테스트 -------------------------------------------------------------
def test_inline_appends_after_label(tmp_path):
    tpl = tmp_path / "form.docx"
    out = tmp_path / "out.docx"
    _make_form(tpl)
    apply_mapping(str(tpl), {"table": 0, "fills": [
        {"row": 1, "col": 0, "mode": "inline", "fields": ["title"]},
    ]}, str(out))
    text = _cell_texts(out, row=1, col=0)[0]
    assert "제 목 :" in text          # 라벨 보존
    assert "{{ title }}" in text      # 토큰이 라벨 뒤에


def test_block_single_fills_cell(tmp_path):
    tpl = tmp_path / "form.docx"
    out = tmp_path / "out.docx"
    _make_form(tpl)
    apply_mapping(str(tpl), {"table": 0, "fills": [
        {"row": 3, "col": 0, "mode": "block", "fields": ["decisions"]},
    ]}, str(out))
    lines = _cell_texts(out, row=3, col=0)
    assert "{%p for x in decisions %}" in lines
    assert " - {{ x }}" in lines


def test_block_multi_keeps_order_and_labels(tmp_path):
    tpl = tmp_path / "form.docx"
    out = tmp_path / "out.docx"
    _make_form(tpl)
    apply_mapping(str(tpl), {"table": 0, "fills": [
        {"row": 3, "col": 0, "mode": "block", "fields": ["purpose", "next_meeting"]},
    ]}, str(out))
    lines = _cell_texts(out, row=3, col=0)
    assert lines[0] == "[회의 목적] {{ purpose }}"
    assert lines[1] == "[다음 회의] {{ next_meeting }}"


def test_block_preserves_labeled_cell(tmp_path):
    """라벨 칸("제 목 :")에 block을 넣어도 라벨을 지우지 않고 그 뒤에 블록을 붙인다."""
    tpl = tmp_path / "form.docx"
    out = tmp_path / "out.docx"
    _make_form(tpl)  # cell(1,0) == "제 목 :"
    apply_mapping(str(tpl), {"table": 0, "fills": [
        {"row": 1, "col": 0, "mode": "block", "fields": ["decisions"]},
    ]}, str(out))
    lines = _cell_texts(out, row=1, col=0)
    assert lines[0] == "제 목 :"                       # 라벨 보존(첫 문단 유지)
    assert "{%p for x in decisions %}" in lines        # 블록은 라벨 뒤에
    assert lines.index("{%p for x in decisions %}") > 0


def test_out_of_range_row_raises(tmp_path):
    tpl = tmp_path / "form.docx"
    _make_form(tpl, rows=4)
    with pytest.raises(IndexError, match="행"):
        apply_mapping(str(tpl), {"table": 0, "fills": [
            {"row": 99, "col": 0, "mode": "inline", "fields": ["title"]},
        ]}, str(tmp_path / "out.docx"))


def test_out_of_range_table_raises(tmp_path):
    tpl = tmp_path / "form.docx"
    _make_form(tpl)
    with pytest.raises(IndexError, match="표 인덱스"):
        apply_mapping(str(tpl), {"table": 5, "fills": [
            {"row": 0, "col": 0, "mode": "inline", "fields": ["title"]},
        ]}, str(tmp_path / "out.docx"))


def test_missing_fill_key_raises_friendly_error(tmp_path):
    # mode 키가 빠진 fills 항목 → 원시 KeyError 대신 안내 메시지(ValueError)
    tpl = tmp_path / "form.docx"
    _make_form(tpl)
    with pytest.raises(ValueError, match="필수 키 'mode'"):
        apply_mapping(str(tpl), {"table": 0, "fills": [
            {"row": 1, "col": 0, "fields": ["title"]},
        ]}, str(tmp_path / "out.docx"))


def test_missing_paragraph_key_raises_friendly_error(tmp_path):
    tpl = tmp_path / "pform.docx"
    _make_para_form(tpl)
    with pytest.raises(ValueError, match="필수 키 'fields'"):
        apply_mapping(str(tpl), {"paragraphs": [
            {"para": 1, "mode": "inline"},
        ]}, str(tmp_path / "out.docx"))


def test_unknown_field_in_apply_raises(tmp_path):
    tpl = tmp_path / "form.docx"
    _make_form(tpl)
    with pytest.raises(ValueError, match="알 수 없는 field"):
        apply_mapping(str(tpl), {"table": 0, "fills": [
            {"row": 3, "col": 0, "mode": "block", "fields": ["nope"]},
        ]}, str(tmp_path / "out.docx"))


# --- 문단 기반 양식 삽입 -----------------------------------------------------
def _make_para_form(path):
    """개요/참석자/회의내용 문단 양식(표 없음)을 만든다."""
    doc = Document()
    doc.add_paragraph("개요")          # 0
    doc.add_paragraph("ㅇ (목적)")     # 1
    doc.add_paragraph("ㅇ (일시)")     # 2
    doc.add_paragraph("회의내용")      # 3
    doc.add_paragraph("ㅇ")            # 4
    doc.add_paragraph("ㅇ")            # 5
    doc.save(str(path))


def _para_texts(out_path):
    return [p.text for p in Document(str(out_path)).paragraphs]


def test_paragraph_inline_appends_after_label(tmp_path):
    tpl = tmp_path / "pform.docx"
    out = tmp_path / "out.docx"
    _make_para_form(tpl)
    apply_mapping(str(tpl), {"paragraphs": [
        {"para": 1, "mode": "inline", "fields": ["purpose"]},
        {"para": 2, "mode": "inline", "fields": ["date"]},
    ]}, str(out))
    texts = _para_texts(out)
    assert "ㅇ (목적) {{ purpose }}" in texts
    assert "ㅇ (일시) {{ date }}" in texts


def test_paragraph_block_inserts_following_paragraphs(tmp_path):
    tpl = tmp_path / "pform.docx"
    out = tmp_path / "out.docx"
    _make_para_form(tpl)
    apply_mapping(str(tpl), {"paragraphs": [
        {"para": 4, "mode": "block", "fields": ["decisions"]},
    ]}, str(out))
    texts = _para_texts(out)
    # block 첫 라인은 대상 문단에, 나머지는 바로 뒤 문단으로
    assert "{%p for x in decisions %}" in texts
    assert " - {{ x }}" in texts
    assert "{%p endfor %}" in texts
    # 회의내용 헤딩은 보존되고, 뒤의 다른 ㅇ 문단도 남아 있다
    assert "회의내용" in texts


def test_paragraph_block_multi_field_labels(tmp_path):
    tpl = tmp_path / "pform.docx"
    out = tmp_path / "out.docx"
    _make_para_form(tpl)
    apply_mapping(str(tpl), {"paragraphs": [
        {"para": 4, "mode": "block", "fields": ["decisions", "notes"]},
    ]}, str(out))
    texts = _para_texts(out)
    assert "[결정 사항]" in texts
    assert "[기타·특이사항]" in texts


def test_block_preserves_labeled_paragraph(tmp_path):
    """라벨 문단에 block을 넣어도 라벨을 지우지 않고 바로 뒤에 블록을 삽입한다."""
    doc = Document()
    doc.add_paragraph("ㅇ 결정사항")   # 0: 라벨 문단
    doc.add_paragraph("뒤 문단")        # 1: 이후 문단 보존 확인용
    tpl = tmp_path / "pform.docx"
    doc.save(str(tpl))
    out = tmp_path / "out.docx"
    apply_mapping(str(tpl), {"paragraphs": [
        {"para": 0, "mode": "block", "fields": ["decisions"]},
    ]}, str(out))
    texts = _para_texts(out)
    assert texts[0] == "ㅇ 결정사항"                    # 라벨 보존(그 자리 유지)
    assert texts[1] == "{%p for x in decisions %}"      # 블록이 라벨 바로 뒤
    assert "뒤 문단" in texts                           # 이후 문단도 보존


def test_paragraph_out_of_range_raises(tmp_path):
    tpl = tmp_path / "pform.docx"
    _make_para_form(tpl)
    with pytest.raises(IndexError, match="문단 인덱스"):
        apply_mapping(str(tpl), {"paragraphs": [
            {"para": 999, "mode": "inline", "fields": ["purpose"]},
        ]}, str(tmp_path / "out.docx"))


def test_mixed_table_and_paragraph_fills(tmp_path):
    """표 셀(title) + 문단(purpose)을 한 번에 채운다."""
    doc = Document()
    doc.add_table(rows=1, cols=1).cell(0, 0).text = "회의록"
    doc.add_paragraph("ㅇ (목적)")  # 문단 index 0 (표 안 문단은 제외되므로)
    tpl = tmp_path / "mixed.docx"
    doc.save(str(tpl))
    out = tmp_path / "out.docx"
    apply_mapping(str(tpl), {
        "table": 0,
        "fills": [{"row": 0, "col": 0, "mode": "inline", "fields": ["title"]}],
        "paragraphs": [{"para": 0, "mode": "inline", "fields": ["purpose"]}],
    }, str(out))
    doc_out = Document(str(out))
    assert "회의록 {{ title }}" in doc_out.tables[0].rows[0].cells[0].text
    assert "ㅇ (목적) {{ purpose }}" in [p.text for p in doc_out.paragraphs]


def test_paragraph_block_end_to_end(tmp_path):
    """문단 block 삽입 → render_docx_template로 실제 값이 채워지는지."""
    from render_docx_template import render_template

    tpl = tmp_path / "pform.docx"
    tokenized = tmp_path / "pform_tokenized.docx"
    final = tmp_path / "final.docx"
    _make_para_form(tpl)
    apply_mapping(str(tpl), {"paragraphs": [
        {"para": 1, "mode": "inline", "fields": ["purpose"]},
        {"para": 4, "mode": "block", "fields": ["decisions"]},
        {"para": 5, "mode": "block", "fields": ["action_items"]},
    ]}, str(tokenized))
    render_template(str(tokenized), _sample(), str(final))
    all_text = "\n".join(_para_texts(final))
    assert "docx 변환은 python-docx로 진행" in all_text     # decisions
    assert "python-docx 렌더러 PoC 작성" in all_text         # action_items


# --- 엔드투엔드: apply → render_docx_template ---------------------------------
def test_end_to_end_fills_values(tmp_path):
    from render_docx_template import render_template

    tpl = tmp_path / "form.docx"
    tokenized = tmp_path / "form_tokenized.docx"
    final = tmp_path / "final.docx"
    _make_form(tpl, rows=5)
    apply_mapping(str(tpl), {"table": 0, "fills": [
        {"row": 1, "col": 0, "mode": "inline", "fields": ["title"]},
        {"row": 2, "col": 0, "mode": "inline", "fields": ["date"]},
        {"row": 3, "col": 0, "mode": "block", "fields": ["decisions"]},
        {"row": 4, "col": 0, "mode": "block", "fields": ["action_items"]},
    ]}, str(tokenized))
    render_template(str(tokenized), _sample(), str(final))

    table = Document(str(final)).tables[0]
    all_text = "\n".join(
        p.text for row in table.rows for cell in row.cells for p in cell.paragraphs
    )
    assert "2026 3분기 제품 로드맵 회의" in all_text     # title inline
    assert "2026-07-16 14:00" in all_text               # date inline
    assert "docx 변환은 python-docx로 진행" in all_text  # decisions 반복
    assert "python-docx 렌더러 PoC 작성" in all_text     # action_items 반복


def test_end_to_end_empty_list_leaves_blank(tmp_path):
    from render_docx_template import render_template

    data = _sample()
    data["notes"] = []
    tpl = tmp_path / "form.docx"
    tokenized = tmp_path / "form_tokenized.docx"
    final = tmp_path / "final.docx"
    _make_form(tpl, rows=4)
    apply_mapping(str(tpl), {"table": 0, "fills": [
        {"row": 3, "col": 0, "mode": "block", "fields": ["notes"]},
    ]}, str(tokenized))
    render_template(str(tokenized), data, str(final))

    lines = _cell_texts(final, row=3, col=0)
    # notes가 비면 반복 문단이 생성되지 않아 " - ..." 라인이 없다
    assert not any(line.strip().startswith("-") for line in lines)
