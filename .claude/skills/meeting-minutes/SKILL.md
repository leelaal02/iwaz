---
name: meeting-minutes
description: Use when the user provides meeting notes, a transcript, or STT output and wants structured meeting minutes exported to Markdown and Word (.docx). Extracts 회의 주제/참석자/논의 내용/결정 사항/Action Items/다음 회의 일정.
---

# 회의록 자동 생성 Skill

텍스트 회의 내용을 구조화된 회의록(Markdown + Word .docx)으로 변환한다.
파이프라인은 4단계이며 각 단계의 계약은 `schema/minutes.schema.json`이다.

## 경로 규칙 (중요)

아래 명령의 `scripts/`·`schema/`·`requirements*.txt`는 모두 **이 SKILL.md가 있는
스킬 디렉토리** 기준 경로다. 실행할 때는 스킬 디렉토리 기준 절대경로로 바꿔서 실행한다.
(이 저장소에서는 스킬 디렉토리가 `.claude/skills/meeting-minutes/` 이므로
예: `python .claude/skills/meeting-minutes/scripts/transcribe.py ...`)
반면 `output/`은 **사용자의 현재 작업 디렉토리** 기준이다 — 산출물은 사용자 프로젝트에 남긴다.

## 사전 준비

의존성 설치(최초 1회): `pip install -r requirements.txt`
(오디오 STT를 쓸 때만 추가로: `pip install -r requirements-stt.txt`)
출력 폴더 준비: `output/` 이 없으면 만든다 (`mkdir output`).

## 단계별 절차

### [1] 입력 확보 (텍스트 / 로컬 STT / 클라우드 STT)
사용자가 준 입력의 종류에 따라 소스를 고른다.

- **텍스트**(붙여넣은 내용 또는 `.txt` 경로): `--source text`
- **오디오 파일**: 로컬/클라우드 중 무엇을 쓸지 사용자에게 확인한다.
  - 로컬(오프라인, `pip install -r requirements-stt.txt` 필요): `--source whisper`
  - 클라우드(Groq, `GROQ_API_KEY` 필요): `--source groq`

정규화된 회의 텍스트를 얻는다:
`python scripts/transcribe.py --source <text|whisper|groq> <입력> > output/meeting.txt`

이 표준 출력(정규화된 회의 원문)을 [2] 추출 단계의 입력으로 사용한다.
STT 라이브러리 미설치나 `GROQ_API_KEY` 미설정 시, 명령이 안내 메시지와 함께
실패하므로 사용자에게 그대로 전달해 설치/설정을 요청한다.

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

## 확장 (입력 어댑터)
입력 방식 추가: `scripts/adapters/`에 `transcribe(source, **opts) -> str`를
구현한 모듈을 만들고 `scripts/adapters/__init__.py`의 `REGISTRY`에 한 줄 등록.
삭제: REGISTRY에서 한 줄 제거 + 모듈 삭제. [2]~[4] 단계는 수정 불필요.
