"""[4-보강] 매핑 적용: 양식 복사본에 검증된 docxtpl 토큰 블록을 삽입.

자동 매핑 경로의 ③단계. Claude가 만든 mapping.json대로 표의 지정 칸에
**검증된 토큰 텍스트만** 넣는다(Claude는 토큰 문법을 짜지 않는다 → 문법 오류 차단).
삽입 후에는 기존 render_docx_template.py가 무수정으로 값을 채운다.

원본 양식은 절대 수정하지 않는다 — 호출자가 준 복사본 경로(out_path)에만 저장.
"""
import json
import sys
from pathlib import Path

from normalize_input import resolve_input_path

# --- 토큰 블록 라이브러리 (설계 §4.3) ---------------------------------------
# 스칼라 field의 값 토큰(inline·block 공통). render_docx_template.build_context 어휘와 일치.
_SCALAR_TOKEN = {
    "title": "{{ title }}",
    "date": "{{ date }}",
    "attendees": "{{ attendees_joined }}",
    "purpose": "{{ purpose }}",
    "next_meeting": "{{ next_meeting }}",
}

# 목록형 field의 block 본문(문단 라인 목록). {%p%}는 문단 단위 반복 태그.
_LIST_BLOCK = {
    "discussion": [
        "{%p for d in discussion %}",
        "[{{ d.topic }}]",
        "{%p for p in d.points %}",
        " - {{ p }}",
        "{%p endfor %}",
        "{%p endfor %}",
    ],
    "decisions": [
        "{%p for x in decisions %}",
        " - {{ x }}",
        "{%p endfor %}",
    ],
    "action_items": [
        "{%p for a in action_items %}",
        " - {{ a.task }} (담당: {{ a.owner }} / 기한: {{ a.due }})",
        "{%p endfor %}",
    ],
    "notes": [
        "{%p for n in notes %}",
        " - {{ n }}",
        "{%p endfor %}",
    ],
}

# 한 칸에 여러 field가 들어갈 때 구분용 섹션 라벨(block 복수 field에서만 붙임).
_SECTION_LABEL = {
    "title": "[제목]",
    "date": "[일시]",
    "attendees": "[참석자]",
    "purpose": "[회의 목적]",
    "next_meeting": "[다음 회의]",
    "discussion": "[논의 내용]",
    "decisions": "[결정 사항]",
    "action_items": "[실행 항목]",
    "notes": "[기타·특이사항]",
}

ALLOWED_FIELDS = set(_SECTION_LABEL)  # 고정 9항목 어휘


def _validate_fields(fields) -> None:
    if not fields:
        raise ValueError("fill의 'fields'가 비어 있습니다.")
    for f in fields:
        if f not in ALLOWED_FIELDS:
            raise ValueError(
                f"알 수 없는 field '{f}'. 허용 어휘: "
                + ", ".join(sorted(ALLOWED_FIELDS))
            )


def inline_tokens(fields) -> str:
    """inline mode: 스칼라 field의 값 토큰을 공백으로 이어 한 줄로."""
    _validate_fields(fields)
    parts = []
    for f in fields:
        if f not in _SCALAR_TOKEN:
            raise ValueError(
                f"'{f}'는 목록형이라 inline 모드로 넣을 수 없습니다. block 모드를 쓰세요."
            )
        parts.append(_SCALAR_TOKEN[f])
    return " ".join(parts)


def block_lines(fields) -> list:
    """block mode: field 순서대로 토큰 문단 라인 목록을 만든다.

    field가 하나면 섹션 라벨 생략, 둘 이상이면 각 field에 섹션 라벨 줄을 붙인다.
    """
    _validate_fields(fields)
    single = len(fields) == 1
    lines = []
    for f in fields:
        if f in _SCALAR_TOKEN:  # 스칼라·title·date는 값 토큰 한 줄
            token = _SCALAR_TOKEN[f]
            lines.append(token if single else f"{_SECTION_LABEL[f]} {token}")
        else:  # 목록형: 반복 블록
            if not single:
                lines.append(_SECTION_LABEL[f])
            lines.extend(_LIST_BLOCK[f])
    return lines


# --- docx 조작 --------------------------------------------------------------
def _clear_runs(paragraph) -> None:
    for run in list(paragraph.runs):
        run._element.getparent().remove(run._element)


def _append_inline(paragraph, fields) -> None:
    """paragraph 끝에 inline 토큰을 덧붙인다(라벨 텍스트 보존)."""
    tokens = inline_tokens(fields)
    sep = " " if paragraph.text.strip() else ""  # 라벨이 있으면 한 칸 띄움
    paragraph.add_run(sep + tokens)


def _insert_paragraph_after(paragraph, text: str):
    """본문에서 paragraph 바로 뒤에 새 문단을 만들어 반환한다.

    python-docx에 공개 API가 없어 XML(addnext)로 삽입한다. 표 셀이 아니라
    문단 기반 양식의 block 채움에서 여러 문단을 순서대로 끼워 넣을 때 쓴다.
    """
    from docx.oxml import OxmlElement
    from docx.text.paragraph import Paragraph

    new_p = OxmlElement("w:p")
    paragraph._p.addnext(new_p)
    new_para = Paragraph(new_p, paragraph._parent)
    if text:
        new_para.add_run(text)
    return new_para


def _apply_inline(cell, fields) -> None:
    _append_inline(cell.paragraphs[0], fields)


def _apply_block(cell, fields) -> None:
    """표 셀에 block 토큰을 삽입한다.

    라벨이 있는 칸("결정 사항:" 등)은 지우지 않고 그 뒤에 블록을 새 문단으로
    넣는다(inline과 동일한 라벨 보존 규칙). 빈 칸이면 첫 라인을 기존 첫 문단에
    넣어 셀 서식을 유지한다.
    """
    lines = block_lines(fields)
    p0 = cell.paragraphs[0]
    if p0.text.strip():  # 라벨 보존: 기존 텍스트 유지, 블록은 전부 뒤에
        for line in lines:
            cell.add_paragraph(line)
    else:  # 빈 칸: 첫 라인은 기존 첫 문단에(서식 유지), 나머지는 뒤에
        _clear_runs(p0)
        p0.add_run(lines[0])
        for line in lines[1:]:
            cell.add_paragraph(line)


def _apply_block_paragraph(paragraph, fields) -> None:
    """문단 기반 양식에 block 토큰을 삽입한다.

    라벨이 있는 문단("ㅇ 논의내용" 등)은 지우지 않고 그 뒤에 블록을 새 문단으로
    넣는다. 빈 문단이면 첫 라인을 그 문단에 넣고 나머지를 뒤에 삽입한다.
    """
    lines = block_lines(fields)
    if paragraph.text.strip():  # 라벨 보존: 기존 문단 유지, 블록은 전부 뒤에
        prev = paragraph
        for line in lines:
            prev = _insert_paragraph_after(prev, line)
    else:  # 빈 문단: 첫 라인은 그 문단에, 나머지는 뒤에
        _clear_runs(paragraph)
        paragraph.add_run(lines[0])
        prev = paragraph
        for line in lines[1:]:
            prev = _insert_paragraph_after(prev, line)


def _require(entry: dict, key: str, where: str):
    """매핑 항목에서 필수 키를 꺼낸다. 없으면 원시 KeyError 대신 안내 메시지."""
    if key not in entry:
        raise ValueError(
            f"매핑 항목({where})에 필수 키 '{key}'가 없습니다. "
            "각 fills 항목은 row·col·mode·fields를, paragraphs 항목은 para·mode·fields를 가져야 합니다."
        )
    return entry[key]


def _apply_table_fills(doc, mapping) -> None:
    """표 셀 채움(`fills`). 표가 없으면 fills가 있을 때만 오류."""
    fills = mapping.get("fills", [])
    if not fills:
        return
    ti = mapping.get("table", 0)
    if ti < 0 or ti >= len(doc.tables):
        raise IndexError(
            f"표 인덱스 {ti}가 범위를 벗어났습니다(문서의 표는 {len(doc.tables)}개)."
        )
    table = doc.tables[ti]
    n_rows = len(table.rows)
    for fill in fills:
        r = _require(fill, "row", "fills")
        c = _require(fill, "col", "fills")
        mode = _require(fill, "mode", "fills")
        fields = _require(fill, "fields", "fills")
        if r < 0 or r >= n_rows:
            raise IndexError(
                f"행 {r}이(가) 표 범위를 벗어났습니다(표 {ti}의 행은 {n_rows}개)."
            )
        row_cells = table.rows[r].cells
        if c < 0 or c >= len(row_cells):
            raise IndexError(
                f"열 {c}이(가) 표 범위를 벗어났습니다(행 {r}의 열은 {len(row_cells)}개)."
            )
        cell = row_cells[c]
        if mode == "inline":
            _apply_inline(cell, fields)
        elif mode == "block":
            _apply_block(cell, fields)
        else:
            raise ValueError(f"알 수 없는 mode '{mode}' (inline|block 중 하나).")


def _apply_paragraph_fills(doc, mapping) -> None:
    """문단 채움(`paragraphs`). 인덱스를 먼저 스냅샷해 삽입에 따른 인덱스 밀림을 피한다."""
    para_fills = mapping.get("paragraphs", [])
    if not para_fills:
        return
    paras = doc.paragraphs
    n = len(paras)
    # block 삽입이 뒤 인덱스를 밀기 전에 대상 문단 객체를 먼저 확보한다.
    targets = []
    for pf in para_fills:
        idx = _require(pf, "para", "paragraphs")
        if idx < 0 or idx >= n:
            raise IndexError(
                f"문단 인덱스 {idx}가 범위를 벗어났습니다(본문 문단은 {n}개)."
            )
        targets.append((paras[idx], pf))
    for paragraph, pf in targets:
        mode = _require(pf, "mode", "paragraphs")
        fields = _require(pf, "fields", "paragraphs")
        if mode == "inline":
            _append_inline(paragraph, fields)
        elif mode == "block":
            _apply_block_paragraph(paragraph, fields)
        else:
            raise ValueError(f"알 수 없는 mode '{mode}' (inline|block 중 하나).")


def apply_mapping(template_path: str, mapping: dict, out_path: str) -> None:
    """mapping대로 양식 복사본에 토큰을 삽입해 out_path에 저장한다.

    `fills`(표 셀)와 `paragraphs`(본문 문단) 둘 다, 또는 한쪽만 있어도 된다.
    """
    from docx import Document

    resolved = resolve_input_path(template_path, must_exist=True)
    doc = Document(str(resolved))
    _apply_table_fills(doc, mapping)
    _apply_paragraph_fills(doc, mapping)
    doc.save(out_path)


def main() -> None:
    template_path, mapping_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    mapping = json.loads(Path(mapping_path).read_text(encoding="utf-8"))
    apply_mapping(template_path, mapping, out_path)
    print(f"토큰 삽입 완료(토큰화 양식): {out_path}")


if __name__ == "__main__":
    main()
