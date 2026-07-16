---
name: meeting-minutes
description: Use when the user provides meeting notes, a transcript, or STT output and wants structured meeting minutes exported to Markdown and Word (.docx). Extracts 회의 주제/참석자/논의 내용/결정 사항/Action Items/다음 회의 일정.
---

# 회의록 자동 생성 Skill

텍스트 회의 내용을 구조화된 회의록(Markdown + Word .docx)으로 변환한다.
파이프라인은 4단계이며 각 단계의 계약은 `schema/minutes.schema.json`이다.

## 사전 준비

의존성 설치(최초 1회): `pip install -r requirements.txt`
출력 폴더 준비: `output/` 이 없으면 만든다 (`mkdir output`).

## 단계별 절차

### [1] 입력 정규화
사용자의 회의 원문(붙여넣은 텍스트 또는 .txt 경로)을 확보한다.
정규화가 필요하면 `scripts/normalize_input.py`의 `load_meeting_text(source)`를
사용하거나, 텍스트를 직접 다음 단계로 넘긴다.

### [2] 추출 (이 단계는 네가 직접 수행)
회의 원문을 읽고 `schema/minutes.schema.json`을 **정확히** 따르는
`minutes.json`을 작성한다. 규칙:
- 6개 항목을 모두 채운다: title, date, attendees, discussion, decisions, action_items, next_meeting.
- 원문에 없는 정보는 **지어내지 않는다**. 없으면 `null`(date/next_meeting/owner/due) 또는 빈 배열.
- `discussion`은 주제별로 `{topic, points}`로 묶는다.
- 결과를 `output/minutes.json`으로 저장한다.

검증: `render_markdown.py`/`render_docx.py`가 `load_minutes()`로 로드하며
자동으로 스키마 검증한다. 검증 실패(ValidationError) 시 `minutes.json`을
스키마에 맞게 수정한다.

### [3] Markdown 생성 및 사용자 검토
`python scripts/render_markdown.py output/minutes.json output/minutes.md`
생성된 Markdown을 사용자에게 보여주고 검토를 요청한다.
사용자가 수정을 요청하면 `minutes.json`을 고치고 이 단계를 반복한다.

### [4] docx 생성 (사용자 승인 후)
`python scripts/render_docx.py output/minutes.json output/minutes.docx`
최종 `.docx` 경로를 사용자에게 안내한다.

## 확장 (STT)
STT 입력은 현재 미지원. 추가 시 `scripts/normalize_input.py`의
`load_from_stt(audio_path)`만 구현하면 [2]~[4]는 수정 불필요.
