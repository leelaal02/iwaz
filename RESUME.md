# 이어서 하기 (RESUME)

회의록 자동 생성 Skill 개발을 **일시 중단**하고 STT 테스트를 먼저 진행하기 위한 재개 메모.
(중단 시점: 2026-07-16)

## 현재 상태: 구현 완료, 브랜치 유지

- 브랜치: `feat/meeting-minutes-skill` (아직 `master`에 병합 안 함)
- 계획서 5개 태스크 **전부 구현·커밋 완료**, 테스트 **16/16 통과**
- 남은 마지막 절차: 브랜치 마무리(병합 or PR) — STT 작업 후 결정 예정

## 구현된 것

- `SKILL.md` — 4단계 오케스트레이션 지시문(진입점)
- `schema/minutes.schema.json` — 중간 계약(단일 진실 원천)
- `scripts/validate.py` — 스키마 검증·로드
- `scripts/normalize_input.py` — 입력 정규화 (+ `load_from_stt` 자리만 주석으로 확보)
- `scripts/render_markdown.py` — JSON → Markdown
- `scripts/render_docx.py` — JSON → Word(.docx)
- `examples/`, `tests/` (4개 테스트 파일, 16 케이스)

## 문서

- 설계(요구사항): `docs/superpowers/specs/2026-07-16-meeting-minutes-skill-design.md`
- 계획서: `docs/superpowers/plans/2026-07-16-meeting-minutes-skill.md`

## 재개 방법

```bash
cd C:/Users/user/Desktop/metting
git checkout feat/meeting-minutes-skill
pip install -r requirements.txt   # 새 환경일 때만
python -m pytest -q               # 16 passed 확인
```

## STT 연동 지점 (다음 작업과의 연결)

STT는 이 Skill의 **[1] 입력 계층**에만 붙는다. 다른 폴더에서 STT를 테스트해
오디오→텍스트 변환이 되면, 그 결과 텍스트를 그대로 `load_meeting_text()`에 넘기거나,
`scripts/normalize_input.py`의 `load_from_stt(audio_path)` 주석을 실제 구현으로
바꾸면 [2]~[4] 단계는 **수정 없이** 그대로 재사용된다.
STT가 뱉는 transcript 포맷(화자 라벨/타임스탬프 유무)을 확인해 두면 연동이 쉬워진다.
