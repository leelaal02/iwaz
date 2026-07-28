---
name: meeting-minutes
description: Use when the user wants structured meeting minutes (회의록) from meeting notes, a transcript, STT output, or an audio recording (녹취·녹음 파일) — exported to Markdown and Word (.docx). Also use when they want the minutes filled into their own .docx form/template (회의록 양식·템플릿 채우기). Extracts 9 fixed items: 제목/일시/참석자/회의 목적/논의 내용/결정 사항/실행 항목(Action Items)/다음 회의/기타·특이사항. Trigger this whenever someone turns meeting content, recordings, or transcripts into minutes — even if they phrase it as "문서로 정리해줘" and don't say "회의록" explicitly. Do NOT use for plain audio transcription without structuring, planning a meeting agenda in advance, scheduling meetings on a calendar, or translating an existing 회의록 — those are different tasks.
---

# 회의록 자동 생성 Skill

텍스트·STT·오디오(녹취) 회의 내용을 구조화된 회의록(Markdown + Word .docx)으로 변환한다.
사용자가 준 .docx 양식(표·문단)이 있으면 그 양식에 맞춰 채운다.
파이프라인은 4단계이며 각 단계의 계약은 `schema/minutes.schema.json`이다.

## 경로 규칙 (중요)

아래 명령의 `scripts/`·`schema/`·`requirements*.txt`는 모두 **이 SKILL.md가 있는
스킬 디렉토리** 기준 경로다. 실행할 때는 스킬 디렉토리 기준 절대경로로 바꿔서 실행한다.
(이 저장소에서는 스킬 디렉토리가 `.claude/skills/meeting-minutes/` 이므로
예: `python .claude/skills/meeting-minutes/scripts/transcribe.py ...`)
반면 `output/`은 **사용자의 현재 작업 디렉토리** 기준이다 — 산출물은 사용자 프로젝트에 남긴다.

## 산출물 위치 규칙 (중요)

**최종 docx만 `output/`에, 나머지 중간 파일은 전부 `output/.work/`에 둔다.** 아래 단계별
명령은 이미 이 규칙대로 경로를 적어 두었으니 그대로 실행하면 된다(머릿속에서 경로를 바꿀 필요 없음).

- **최종본:** `output/회의록_<제목>_<생성일 YYYY-MM-DD>.docx` — 사용자에게 전달하는 결과물.
  이름은 손으로 짓지 말고 [4]에서 `output_naming.py`로 구한다(제목은 앞부분 몇 단어만
  공백 그대로·금지문자 제거해 간결하게, 날짜는 회의 일시가 아니라 **파일을 만든 날**).
- **중간 파일(`output/.work/`):** STT 원문(`meeting.txt`), 추출 데이터(`minutes.json`),
  검토용 Markdown(`minutes.md`), 양식 구조 JSON, 매핑(`mapping.json`), 토큰화 중간
  docx(`*_tokenized.docx`) 등. `minutes.md`도 여기 두되 내용은 [3]에서 사용자에게 보여준다.

`output/` 전체가 `.gitignore` 대상이라 `.work/`도 자동 제외된다. 중간 파일은 다음번 수정 때
재사용할 수 있게 지우지 말고 남겨 둔다.

## 사전 준비

필요 패키지 설치(최초 1회): `pip install -r requirements.txt`
(오디오 STT를 쓸 때만 추가로: `pip install -r requirements-stt.txt`)
출력 폴더 준비: `output/`와 중간 파일용 `output/.work/`가 없으면 만든다
(`mkdir -p output/.work`).

## 단계별 절차

### [1] 입력 확보 (텍스트 / 로컬 STT / 클라우드 STT)
사용자가 준 입력의 종류에 따라 소스를 고른다.

- **텍스트**(붙여넣은 내용 또는 `.txt` 경로): `--source text`
- **오디오 파일**: 로컬/클라우드 중 무엇을 쓸지 사용자에게 확인한다.
  - 로컬(오프라인, `pip install -r requirements-stt.txt` 필요): `--source whisper`
  - 클라우드(Groq, `GROQ_API_KEY` 필요): `--source groq`
    - 키는 작업 디렉토리의 `.env`에 `GROQ_API_KEY=...`로 두면 `transcribe.py`가
      자동 로드한다(`.env`는 .gitignore 대상). 실제 환경변수가 있으면 그쪽이 우선.

정규화된 회의 텍스트를 얻는다:
`python scripts/transcribe.py --source <text|whisper|groq> <입력> > output/.work/meeting.txt`

(먼저 `output/.work/`가 없으면 만든다.) 이 표준 출력(정규화된 회의 원문)을 [2] 추출 단계의 입력으로 사용한다.
STT 라이브러리 미설치나 `GROQ_API_KEY` 미설정 시, 명령이 안내 메시지와 함께
실패하므로 사용자에게 그대로 전달해 설치/설정을 요청한다.

**입력 파일 위치 자동 탐색**: `<입력>`이 작업 폴더에 없더라도 **파일 이름만** 주면
공통 위치(작업 폴더 → 바탕화면 → 다운로드 → 문서 → 홈)를 재귀 탐색해 찾는다
(text/whisper/groq 모두 공통 헬퍼 `resolve_input_path` 사용). 추가 폴더가 필요하면
`MEETING_INPUT_DIRS`(os.pathsep 구분) 환경변수로 앞쪽에 넣을 수 있다. 못 찾으면
검색한 위치를 안내하며 실패하므로, 정확한 경로를 받거나 폴더를 추가한다.

### [2] 추출 (이 단계는 네가 직접 수행)
회의 원문을 읽고 `schema/minutes.schema.json`을 **정확히** 따르는
`minutes.json`을 작성한다. 규칙:
- 9개 항목을 모두 채운다: title, date, attendees, purpose, discussion, decisions, action_items, next_meeting, notes.
- 원문에 없는 정보는 **지어내지 않는다**. 없으면 `null`(date/purpose/next_meeting/owner/due) 또는 빈 배열(attendees/decisions/action_items/notes).
- `discussion`은 주제별로 `{topic, points}`로 묶는다.
- `purpose`는 이 회의를 왜 하는지(회의 목적) 한두 문장으로. `notes`는 어느 항목에도 안 들어가는 기타·특이사항을 배열로.
- 결과를 `output/.work/minutes.json`으로 저장한다.

검증: `render_markdown.py`/`render_docx.py`가 `load_minutes()`로 로드하며
자동으로 스키마 검증한다. 검증 실패(ValidationError) 시 `minutes.json`을
스키마에 맞게 수정한다.

### [3] Markdown 생성 및 사용자 검토
`python scripts/render_markdown.py output/.work/minutes.json output/.work/minutes.md`
생성된 Markdown을 사용자에게 보여주고 검토를 요청한다.
사용자가 수정을 요청하면 `minutes.json`을 고치고 이 단계를 반복한다.

### [4] docx 생성 (사용자 승인 후)
**먼저 최종 파일명을 구한다:** `python scripts/output_naming.py output/.work/minutes.json .docx [양식.docx]`
→ 출력된 이름을 최종 경로 `output/<그 이름>`으로 쓴다. 아래 명령의 `output/<최종.docx>`가
바로 이 경로이며, 나머지 중간 파일은 모두 `output/.work/`에 둔다.
- **양식을 쓸 때는 세 번째 인자로 양식 경로를 넘긴다** — 양식명이 파일명 맨 앞에 붙어
  (예: `누리미디어_회의록_주간보고 검토_2026-07-22.docx`, `KISA_회의록_...`) **같은 회의를
  여러 양식에 채워도 파일이 서로 겹쳐 덮이지 않는다.**
- 양식이 없으면 세 번째 인자를 생략한다(예: `회의록_3분기 로드맵_2026-07-22.docx`).

사용자가 **회의록 양식(.docx 템플릿)**을 제공했는지에 따라 렌더러를 고른다.

- **양식 없음(기본):**
  `python scripts/render_docx.py output/.work/minutes.json output/<최종.docx>`
- **양식 있음(.docx 템플릿):** 먼저 구조를 확인해 분기한다.
  `python scripts/inspect_template.py <template.docx>` → 구조 JSON(`has_tokens`, `tables`[칸 라벨·좌표·`is_empty`·`merged`], `paragraphs`[문단 index·텍스트·`is_empty`]).
  - **토큰 있음(`has_tokens: true`):** 그대로
    `python scripts/render_docx_template.py <template.docx> output/.work/minutes.json output/<최종.docx>`
  - **토큰 없음(`has_tokens: false`) → 자동 매핑 (표·문단 양식 모두 지원):**
    1. 구조 JSON을 읽고 9항목을 알맞은 칸/문단에 배치한 매핑을 `output/.work/mapping.json`으로 작성한다(아래 "자동 매핑 규칙"). 표 서식이면 `fills`로 표 칸에, 문단 서식이면 `paragraphs`로 본문 문단에 매핑한다. 표와 문단이 섞인 양식이면 둘 다 쓴다.
    2. `python scripts/apply_form_mapping.py <template.docx> output/.work/mapping.json output/.work/<양식>_tokenized.docx`
    3. `python scripts/render_docx_template.py output/.work/<양식>_tokenized.docx output/.work/minutes.json output/<최종.docx>`
    4. **매핑 요약을 사용자에게 텍스트로 보고**한다 — 어느 칸/문단에 무엇을 넣었는지, 데이터 없이 비워둔 곳, 전용 자리가 없어 다른 곳에 함께 넣은 항목.
  - 템플릿 파일은 이름만 줘도 공통 위치를 탐색한다(`resolve_input_path` 사용).
  - 사용자가 **hwp/pdf 양식**을 주면, 한글/워드에서 **.docx로 저장(다른 이름으로 저장 → Word)**해 달라고 요청한다. 렌더러는 .docx만 받는다.
  - 표시자 문법 오류·.docx 아님·파일 없음 시 명확한 오류가 나므로 그대로 사용자에게 전달한다.

최종 `.docx` 경로를 사용자에게 안내한다.

#### 자동 매핑 규칙 (토큰 없는 표·문단 양식)
`mapping.json`은 표 칸 채움 `fills`와 본문 문단 채움 `paragraphs`를 가진다. 표 양식이면 `fills`만, 문단 양식이면 `paragraphs`만, 섞인 양식이면 둘 다 쓴다.

```json
{
  "table": 0,
  "fills":      [ {"row": 1, "col": 0, "mode": "inline", "fields": ["title"]} ],
  "paragraphs": [ {"para": 4, "mode": "block",  "fields": ["decisions"]} ]
}
```

- `fills`는 표 칸을 `{"row", "col", "mode", "fields"}`로, `paragraphs`는 본문 문단을 `{"para", "mode", "fields"}`로 지정한다. `para`는 inspect의 `paragraphs[].index`(= `doc.paragraphs` 위치)와 일치.
- `fields`는 고정 9항목 어휘만: `title, date, attendees, purpose, discussion, decisions, action_items, next_meeting, notes`.
- `mode`:
  - `inline` — 라벨 칸/문단("제목: __", "ㅇ (목적)")이나 값 전용 빈 자리. 스칼라(`title/date/attendees/purpose/next_meeting`)만 가능하며 라벨 뒤에 토큰이 붙어 라벨 서식이 보존된다. 데이터가 없으면 그 자리에 빨간 "입력필요"가 자동으로 들어간다(값이 있으면 값).
  - `block` — 목록형(`discussion/decisions/action_items/notes`)이나 한 자리에 여러 항목을 넣을 때. 스크립트가 검증된 토큰 블록·섹션 라벨을 자동 생성한다. 대상 자리에 **라벨 텍스트가 있으면 지우지 않고**(inline과 동일) 블록을 그 **바로 뒤에 새 문단으로** 넣고, 빈 자리면 첫 줄을 그 자리에 넣어 서식을 유지한다(뒤 문단 밀림은 스크립트가 자동 처리). → 라벨 칸에 목록을 매핑해도 라벨이 보존된다. 논의 소제목은 "1. 주제"처럼 **자동 넘버링+굵게**로 렌더된다.
  - `todo` — **양식에만 있고 대응 데이터가 없는 값 칸/컬럼**(작성자·회의장소·장소·미결사항·다음회의·첨부 등)에 빨간 굵은 "입력필요"를 넣는다. `fields` 불필요. **음성(minutes.json)에 없는 값 슬롯에만** 쓴다(값이 있으면 `inline`/`block`으로 채움).
  - `literal` — 9항목 밖이지만 **원문(transcript)에 값이 있는** 양식 전용 칸(예: 원문에 언급된 장소)에 그 값을 평문으로 넣는다. `fields` 대신 `"text": "..."`.
- `row_repeats` — **리스트형 자리가 담당/기한 등 컬럼으로 나뉜 "행 반복 표"**면 이것으로 각 컬럼에 펼친다. `mapping.json` 최상위 키 `row_repeats`에 `{"row": 데이터행, "field": "action_items", "cols": {"task":0,"owner":4,"due":3}}`를 넣으면 그 표에 `{%tr%}` 3행 구조가 주입돼 항목마다 한 행씩 채워진다(gridSpan 병합 유지, 값 없는 컬럼은 "입력필요"). 표가 아니라 단일 칸·문단이면 `row_repeats` 대신 `block`을 쓴다(예: 담당·기한을 텍스트 "(담당:… / 기한:…)"로).
- **채우는 순서 — 라벨 칸 먼저, 빈 칸은 그다음**: 양식에 이미 글자(라벨)가 있는 칸부터 채운다. 라벨이 가리키는 항목(예: "제목:"→title, "일시:"→date, "참가자"→attendees, "장소:"→해당 데이터 없으면 빈칸)을 그 칸에 `inline`으로 넣는다. 그다음, 아무 글자도 없는 빈 칸/넓은 영역("회의 내용"·"향후 일정"·"비고" 등)에 목록형·전용 라벨이 없는 항목을 `block`으로 배치한다.
- **중복 금지 — 한 항목은 한 곳에만**: 이미 어느 칸/블록에 넣은 내용을 다른 칸이나 블록에 **반복해 넣지 않는다.** 같은 라벨이 여러 곳에 있으면(예: "제목:" 칸이 2개) 같은 값을 둘 다에 복사하지 말고 **각 칸에 서로 다른 알맞은 항목**을 배치한다(예: 위쪽 "제목:"→회의 제목(title), 회의내용 바로 위의 "제목:"→회의 목적/안건(purpose)). 한 칸에 purpose를 넣었으면 "회의 내용" 블록에서는 purpose를 빼서 중복을 없앤다. 마땅한 별도 항목이 없으면 그 라벨 칸은 빈칸으로 둔다.
- **데이터 보존 우선**: 비어 있지 않은 9항목은 모두 어느 fill/paragraph엔가 (중복 없이) **한 번씩** 포함시킨다. 전용 자리가 없는 항목은 가장 어울리는 곳에 `block`으로 함께 넣는다(버리지 않는다).
- **빈 값 슬롯은 "입력필요"로 — 음성에 없는 것만**: 양식이 값을 기대하는 칸/컬럼인데 대응 9항목 데이터가 없으면 `todo`를 매핑해 빨간 "입력필요"를 넣는다(작성자·회의장소·장소·미결사항·첨부·다음회의 등). 단 **9항목에 값이 있으면 절대 "입력필요"로 덮지 않는다** — 스크립트가 값 유무로 자동 처리하므로, `inline`/`block`에 매핑하면 값이 있을 땐 값, 없을 땐 "입력필요"가 들어간다. 원문에 값이 있는 양식 전용 칸은 `todo` 대신 `literal`로 그 값을 채운다.
- 토큰 문법은 스크립트가 만든다 — `mapping.json`에는 토큰을 직접 쓰지 말고 field 이름(또는 `todo`/`literal`/`row_repeats` 지정)만 넣는다.

#### 양식 템플릿 표시자 (스마트 토큰)
사용자 양식에 아래 토큰을 넣으면 해당 자리에 회의록 내용이 채워진다.
복사해 쓸 예시는 `templates/example-template.docx` (재생성:
`python scripts/make_example_template.py`).

| 토큰 | 채워지는 값 |
|---|---|
| `{{ title }}` | 회의 제목 |
| `{{ date }}` | 회의 일시 (없으면 빈칸) |
| `{{ purpose }}` | 회의 목적 |
| `{{ next_meeting }}` | 다음 회의 (없으면 빈칸) |
| `{{ attendees_joined }}` | 참석자 한 줄 결합 "홍길동, 김철수" |
| `{% for a in attendees %}{{ a }}{% endfor %}` | 참석자 목록 반복 |
| `{% for d in discussion %}{{ d.topic }} … {% for p in d.points %}{{ p }}{% endfor %}{% endfor %}` | 논의 주제·포인트 반복 |
| `{% for x in decisions %}{{ x }}{% endfor %}` | 결정 사항 반복 |
| 실행 항목 표 — 아래 "표 행 반복" 참고 (`action_items` 사용) | 실행 항목 표 — 행 자동 반복 |
| `{% for n in notes %}{{ n }}{% endfor %}` | 기타·특이사항 반복 |

**표 행 반복(`{%tr%}`)은 3행 구조로 넣는다** — 한 행에 for와 endfor를 함께 넣으면
동작하지 않는다. 표에 다음 3개 행을 만들고, `{%tr%}`가 든 for·endfor 행은
렌더 시 삭제되며 그 사이 데이터 행이 항목 수만큼 반복된다:

| 할 일 | 담당자 | 기한 |
|---|---|---|
| `{%tr for a in action_items %}` | (빈칸) | (빈칸) |
| `{{ a.task }}` | `{{ a.owner }}` | `{{ a.due }}` |
| `{%tr endfor %}` | (빈칸) | (빈칸) |

문단 단위로 반복시키려면 `{% %}` 대신 `{%p %}`를 쓴다.
없는 값은 빈칸(스칼라)·행 미생성(목록)으로 처리되어 양식이 깔끔하게 유지된다.
복사해 쓸 예시는 `templates/example-template.docx`.

## 확장 (입력 어댑터)
입력 방식 추가: `scripts/adapters/`에 `transcribe(source, **opts) -> str`를
구현한 모듈을 만들고 `scripts/adapters/__init__.py`의 `REGISTRY`에 한 줄 등록.
삭제: REGISTRY에서 한 줄 제거 + 모듈 삭제. [2]~[4] 단계는 수정 불필요.
