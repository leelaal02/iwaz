# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Status

회의록 자동 생성 Skill이 구현되어 있습니다 — `.claude/skills/meeting-minutes/`에 자기완결 스킬로 존재하며 `/meeting-minutes`로 호출합니다. 아래는 확정된 **목표·설계 방향·규칙**이며, 코드를 변경할 때 이 방향을 벗어나지 않도록 합니다.

## Goal

Harness Engineering을 적용한 **회의록 자동 생성 Skill**. 텍스트 또는 STT(Speech-to-Text)로 변환된 회의 내용을 입력받아 구조화된 회의록을 생성하고 Word(.docx)로 출력합니다.

## Pipeline (핵심 아키텍처)

처리 흐름은 단방향 파이프라인이며 각 단계가 독립 모듈이어야 합니다. 한 단계의 출력이 다음 단계의 입력이 되므로, 단계 사이의 데이터 계약(중간 구조체)을 명시적으로 유지하세요.

```
입력(텍스트 | STT 결과)
   → 분석/추출 (회의 제목, 회의 일시, 참석자, 회의 목적, 회의 내용, 결정 사항, 실행 항목, 다음 회의, 기타·특이사항)
   → Markdown 회의록 생성
   → Word(.docx) 출력
```

- **입력 계층**: 텍스트 / 로컬 STT(faster-whisper) / 클라우드 STT(Groq)를 플러그인 어댑터로 지원(`scripts/adapters/`, `REGISTRY`). 공통 인터페이스 `transcribe(source, **opts) -> str`로 정규화 텍스트를 반환하므로, 새 입력 방식을 추가/삭제해도 하위 단계(분석/생성/출력)는 수정 불필요.
- **분석/추출 계층**: 반드시 위 9개 항목(회의 제목 / 회의 일시 / 참석자 / 회의 목적 / 회의 내용 / 결정 사항 / 실행 항목 / 다음 회의 / 기타·특이사항)을 추출. 이 항목 목록이 회의록 스키마(`schema/minutes.schema.json`)의 단일 기준(source of truth)이며, Markdown·docx 양쪽 렌더러가 동일 스키마를 소비.
- **Markdown 생성 계층**: 최종 산출물의 중간 표현. **먼저 Markdown으로 생성**한 뒤 이를 기반으로 docx를 만든다 — Markdown을 건너뛰고 곧바로 docx를 만들지 말 것.
- **출력 계층**: Markdown → Word(.docx) 변환. 다른 출력 포맷을 추가하더라도 분석/추출 계층은 재사용되어야 함.

## Design Rules (하드 제약)

- **Harness Engineering 기반**으로 구현.
- 유지보수·확장성을 위해 **모듈화** — 입력/분석/생성/출력을 서로 분리하고 인터페이스로만 결합.
- 추후 기능(특히 STT)을 쉽게 추가할 수 있는 구조 유지. 새 기능 추가가 기존 단계의 수정으로 이어지면 설계가 잘못된 것.
- 추출 항목 9종과 "Markdown 우선 → docx 변환" 순서는 임의로 바꾸지 말 것. 변경이 필요하면 먼저 사용자에게 확인.

## Commands

스택: Python 3.9+, python-docx, jsonschema, pytest, faster-whisper·groq(STT 선택). 스킬은 `.claude/skills/meeting-minutes/`에 자기완결로 존재.

- 필요 패키지 설치: `pip install -r .claude/skills/meeting-minutes/requirements.txt` (오디오 STT는 `requirements-stt.txt` 추가)
- 테스트: `python -m pytest .claude/skills/meeting-minutes/tests -q`
- 파이프라인은 `/meeting-minutes` 호출 시 Claude가 SKILL.md 지시대로 헬퍼를 실행:
  - [1] `python .claude/skills/meeting-minutes/scripts/transcribe.py --source <text|whisper|groq> <입력> > output/meeting.txt`
  - [3] `python .claude/skills/meeting-minutes/scripts/render_markdown.py output/minutes.json output/minutes.md`
  - [4] `python .claude/skills/meeting-minutes/scripts/render_docx.py output/minutes.json output/minutes.docx`

산출물은 사용자 작업 디렉토리의 `output/`에 생성.
