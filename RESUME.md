# 이어서 하기 (RESUME)

회의록 자동 생성 Skill 상태 메모. (최종 갱신: 2026-07-20)

## 현재 상태: 파이프라인 + STT 입력 어댑터 3종 구현 완료

- 브랜치: `feat/meeting-minutes-skill` (아직 `master`에 병합 안 함 — 사용자가 브랜치 유지 선택)
- 테스트 **28/28 통과**
- 스킬은 `/meeting-minutes` 로 호출 가능하도록 **`.claude/skills/meeting-minutes/`** 로 이동(자기완결 스킬)

## 스킬 구조 (`.claude/skills/meeting-minutes/`)

- `SKILL.md` — 4단계 오케스트레이션 지시문(진입점). 경로 규칙: `scripts/`·`schema/`·
  `requirements*.txt`는 스킬 디렉토리 기준, `output/`은 사용자 작업 디렉토리 기준.
- `schema/minutes.schema.json` — 중간 계약(단일 진실 원천)
- `scripts/validate.py` — 스키마 검증·로드
- `scripts/normalize_input.py` — 텍스트 정규화(`_normalize` 공용 함수 포함)
- `scripts/transcribe.py` — [1] 입력 계층 CLI 디스패처(`--source text|whisper|groq`)
- `scripts/adapters/` — 입력 어댑터 플러그인
  - `__init__.py` — `REGISTRY`(한 줄 등록/삭제로 어댑터 추가·제거)
  - `text.py` — 텍스트(기존 normalize_input 위임)
  - `whisper_local.py` — 로컬 STT(faster-whisper, `WhisperModel("medium", cpu_threads=4)`, ko)
  - `groq_cloud.py` — 클라우드 STT(Groq `whisper-large-v3`, `GROQ_API_KEY`)
- `scripts/render_markdown.py` — [3] JSON → Markdown
- `scripts/render_docx.py` — [4] JSON → Word(.docx)
- `examples/`, `tests/`(6개 테스트 파일, 28 케이스), `requirements.txt`, `requirements-stt.txt`

산출물(`output/`)과 개발 문서(`docs/`, `CLAUDE.md`, 이 파일)는 저장소 루트에 유지.

## 문서

- 파이프라인 설계: `docs/superpowers/specs/2026-07-16-meeting-minutes-skill-design.md`
- STT 어댑터 설계: `docs/superpowers/specs/2026-07-20-stt-input-adapters-design.md`
- STT 어댑터 계획: `docs/superpowers/plans/2026-07-20-stt-input-adapters.md`

## 재개 방법

```bash
cd C:/Users/user/Desktop/metting
git checkout feat/meeting-minutes-skill
pip install -r .claude/skills/meeting-minutes/requirements.txt        # 기본
pip install -r .claude/skills/meeting-minutes/requirements-stt.txt    # STT 쓸 때만
python -m pytest .claude/skills/meeting-minutes/tests -q              # 28 passed 확인
```

## 남은 일 / 참고

- STT 실제 사용: `requirements-stt.txt` 설치 필요, Groq는 `GROQ_API_KEY` 환경변수 필요.
  미설치/미설정 시 안내 메시지와 함께 실패하도록 처리됨.
- 화자 분리(diarization)는 미지원(두 STT 모두 Whisper 기반). 필요 시 어댑터 확장.
- 사용자 방침: 텍스트/로컬/클라우드 셋 다 만들어 두고, 나중에 불필요한 어댑터는
  `REGISTRY` 한 줄 + 모듈 파일 삭제로 제거([2]~[4] 무수정).
- 마지막 남은 선택: 브랜치 마무리(병합 or PR) — 추후 결정.
