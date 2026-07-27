"""[4-공통] docx 저장 직전 후처리.

렌더러(무양식/템플릿)가 최종 저장하기 전에 공통으로 적용하는 마무리 작업.
현재는 표 행이 페이지 끝에서 자동으로 나뉘도록 보정한다.
"""
from docx.oxml.ns import qn


def _iter_all_tables(container):
    """문서/셀 안의 모든 표를 중첩표까지 재귀로 낸다.

    Document 본문과 `_Cell`은 모두 `.tables`를 가지므로 한 함수로 처리한다.
    """
    for table in container.tables:
        yield table
        for row in table.rows:
            for cell in row.cells:
                yield from _iter_all_tables(cell)


def allow_rows_to_break(doc) -> int:
    """모든 표 행이 페이지 끝에서 나뉠 수 있게 한다(w:cantSplit 제거).

    많은 회의록 양식 템플릿이 행 나눔 금지(`w:cantSplit`)를 걸어 두어, 한 칸에
    긴 내용(회의 내용·논의 등)을 채우면 페이지 경계에서 행이 안 쪼개져 통째로
    다음 장으로 밀리거나 넘친다. Word 기본값(행 나눔 허용)에 맞춰 `cantSplit`를
    없애 내용이 페이지를 자연스럽게 넘어가게 한다 — 사용자가 매번 워드에서
    "페이지 끝에서 행 나눔 허용"을 켜지 않아도 되도록.

    제거한 행 수를 반환한다(테스트·로깅용).
    """
    removed = 0
    for table in _iter_all_tables(doc):
        for row in table.rows:
            trPr = row._tr.find(qn("w:trPr"))
            if trPr is None:
                continue  # 속성 자체가 없으면 이미 나눔 허용(기본값)
            for cant_split in trPr.findall(qn("w:cantSplit")):
                trPr.remove(cant_split)
                removed += 1
    return removed
