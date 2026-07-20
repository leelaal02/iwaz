# STT 입력 어댑터 3종 Implementation Plan (계획서)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 회의록 Skill의 [1] 입력 계층에 텍스트/로컬 STT(faster-whisper)/클라우드 STT(Groq) 세 어댑터를 플러그인 레지스트리로 추가하되, 하위 파이프라인([2]~[4])은 수정하지 않는다.

**Architecture:** `scripts/adapters/` 패키지에 어댑터별 모듈을 두고 모두 동일한 `transcribe(source, **opts) -> str` 인터페이스를 구현한다. `adapters/__init__.py`의 `ADAPTERS` 레지스트리가 이름→(모듈, 함수)를 매핑하고, `get_adapter(name)`이 **lazy import**로 어댑터를 로드한다. STT 라이브러리 import는 어댑터 함수 내부에서만 일어나 미설치 시에도 텍스트 경로가 동작한다. 새 진입점 `scripts/transcribe.py`가 `--source`로 어댑터를 골라 정규화 텍스트를 stdout에 출력한다.

**Tech Stack:** Python 3.9+, faster-whisper, groq, pytest(모킹).

## Global Constraints

- Python 3.9+ 사용 (타입 힌트, `pathlib`).
- 모든 어댑터 인터페이스는 `transcribe(source: str, **opts) -> str` — 반환은 항상 **정규화된 회의 텍스트**.
- 세 어댑터 모두 반환 전 `normalize_input.normalize_text()`를 적용해 하위 단계 소비 형태를 통일.
- STT 라이브러리(`faster_whisper`, `groq`)는 **어댑터 함수 내부에서 lazy import** — 모듈 top-level import 금지.
- STT 의존성은 `requirements-stt.txt`로 분리 (기존 `requirements.txt` 불변).
- 하위 단계 파일(`validate.py`, `render_markdown.py`, `render_docx.py`, `schema/`)은 **수정 금지**.
- 로컬 whisper 기본값: 모델 `medium`, `cpu_threads=4`, `language="ko"`.
- 클라우드 Groq 기본값: 모델 `whisper-large-v3`, `language="ko"`, 키는 `GROQ_API_KEY` 환경변수.
- 빈 변환 결과는 `ValueError` (기존 정규화 규칙과 동일).
- 모든 파일 입출력 인코딩 `utf-8`.
- `tests/conftest.py`가 `scripts/`를 `sys.path`에 추가하므로, 테스트·스크립트는 `normalize_input`, `adapters`를 top-level로 import 한다.

---

## File Structure

- Modify: `scripts/normalize_input.py` — `normalize_text(text)` public 함수 추가, `load_meeting_text`가 이를 재사용하도록 리팩터.
- Create: `scripts/adapters/__init__.py` — `ADAPTERS` 레지스트리, `get_adapter(name)`, `available_sources()`.
- Create: `scripts/adapters/text.py` — 텍스트 어댑터(기존 로직 위임).
- Create: `scripts/adapters/whisper_local.py` — faster-whisper 어댑터.
- Create: `scripts/adapters/groq_cloud.py` — Groq Whisper API 어댑터.
- Create: `scripts/transcribe.py` — CLI 디스패처.
- Create: `requirements-stt.txt` — STT 선택 의존성.
- Modify: `SKILL.md` — [1] 단계 지시문에 세 소스 사용법 반영.
- Test: `tests/test_adapters.py`, `tests/test_transcribe.py`.

---

## Task 1: 정규화 공용화 + 어댑터 패키지 + 텍스트 어댑터 + 레지스트리

**Files:**
- Modify: `scripts/normalize_input.py`
- Create: `scripts/adapters/__init__.py`
- Create: `scripts/adapters/text.py`
- Test: `tests/test_adapters.py`

**Interfaces:**
- Consumes: 기존 `normalize_input._normalize(text) -> str`, `load_meeting_text(source) -> str`.
- Produces:
  - `normalize_input.normalize_text(text: str) -> str` — 정규화 후 빈 결과면 `ValueError`.
  - `adapters.get_adapter(name: str) -> Callable[..., str]` — 미지원 이름이면 `ValueError`.
  - `adapters.available_sources() -> list[str]` — 등록된 소스 이름 목록.
  - `adapters.text.transcribe(source: str, **opts) -> str`.

- [ ] **Step 1: 정규화 공용 함수 테스트 작성 (실패 예상)**

`tests/test_adapters.py`:
```python
import pytest

from normalize_input import normalize_text


def test_normalize_text_collapses_and_strips():
    assert normalize_text("첫 줄   \n\n\n\n둘째 줄  ") == "첫 줄\n\n둘째 줄"


def test_normalize_text_empty_raises():
    with pytest.raises(ValueError):
        normalize_text("   \n\n  ")
```

- [ ] **Step 2: 테스트 실행하여 실패 확인**

Run: `python -m pytest tests/test_adapters.py -v`
Expected: FAIL — `ImportError: cannot import name 'normalize_text'`

- [ ] **Step 3: `normalize_input.py` 리팩터 — `normalize_text` 추가**

`scripts/normalize_input.py` 를 아래로 교체:
```python
"""입력 계층: 회의 원문 텍스트를 정규화. 어댑터 공용 정규화 제공."""
from pathlib import Path


def load_meeting_text(source: str) -> str:
    """텍스트 문자열 또는 .txt 파일 경로를 정규화된 회의 원문으로 변환.

    - source가 존재하는 파일 경로면 파일 내용을 읽음.
    - 그렇지 않으면 source 자체를 원문 텍스트로 간주.
    """
    candidate = Path(source)
    if candidate.exists() and candidate.is_file():
        text = candidate.read_text(encoding="utf-8")
    else:
        text = source
    return normalize_text(text)


def normalize_text(text: str) -> str:
    """원시 텍스트를 정규화. 빈 결과면 ValueError.

    어댑터(text/whisper/groq)가 반환 직전 공통으로 호출한다.
    """
    normalized = _normalize(text)
    if not normalized:
        raise ValueError("빈 입력입니다: 회의 원문 텍스트가 없습니다.")
    return normalized


def _normalize(text: str) -> str:
    """줄 끝 공백 제거, 연속 빈 줄을 하나로 축약, 앞뒤 공백 제거."""
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").split("\n")]
    result = []
    prev_blank = False
    for line in lines:
        blank = (line == "")
        if blank and prev_blank:
            continue
        result.append(line)
        prev_blank = blank
    return "\n".join(result).strip()
```

- [ ] **Step 4: 정규화 테스트 통과 확인**

Run: `python -m pytest tests/test_adapters.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: 기존 정규화 회귀 테스트 확인**

Run: `python -m pytest tests/test_normalize_input.py -v`
Expected: PASS (기존 4개 그대로 — `load_meeting_text` 동작 불변)

- [ ] **Step 6: 어댑터 패키지 + 텍스트 어댑터 테스트 작성 (실패 예상)**

`tests/test_adapters.py` 하단에 추가:
```python
from adapters import get_adapter, available_sources
from adapters.text import transcribe as text_transcribe


def test_text_adapter_from_string():
    assert text_transcribe("회의 시작\n논의 내용") == "회의 시작\n논의 내용"


def test_text_adapter_normalizes():
    assert text_transcribe("첫 줄   \n\n\n\n둘째 줄") == "첫 줄\n\n둘째 줄"


def test_get_adapter_text_returns_callable():
    fn = get_adapter("text")
    assert fn("안녕\n회의") == "안녕\n회의"


def test_get_adapter_unknown_raises():
    with pytest.raises(ValueError):
        get_adapter("nope")


def test_text_is_available():
    assert "text" in available_sources()
```

- [ ] **Step 7: 테스트 실행하여 실패 확인**

Run: `python -m pytest tests/test_adapters.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'adapters'`

- [ ] **Step 8: 어댑터 레지스트리 구현**

`scripts/adapters/__init__.py`:
```python
"""입력 어댑터 레지스트리. 이름 → (모듈, 함수)를 lazy import로 매핑.

새 입력 방식 추가: ADAPTERS에 한 줄 등록 + 어댑터 모듈 추가.
제거: 해당 줄 삭제 + 모듈 삭제. 하위 단계는 영향 없음.
"""
import importlib
from typing import Callable

# name -> (module path, function name)
ADAPTERS = {
    "text": ("adapters.text", "transcribe"),
}


def available_sources() -> list:
    """등록된 소스 이름 목록."""
    return list(ADAPTERS.keys())


def get_adapter(name: str) -> Callable[..., str]:
    """이름에 해당하는 transcribe 함수를 lazy import로 반환.

    미지원 이름이면 ValueError(사용 가능한 목록 포함).
    STT 어댑터의 무거운 라이브러리는 함수 호출 시점까지 로드되지 않는다.
    """
    if name not in ADAPTERS:
        raise ValueError(
            f"알 수 없는 입력 소스: {name!r}. "
            f"사용 가능: {', '.join(available_sources())}"
        )
    module_path, func_name = ADAPTERS[name]
    module = importlib.import_module(module_path)
    return getattr(module, func_name)
```

`scripts/adapters/text.py`:
```python
"""텍스트 어댑터: 붙여넣은 문자열 또는 .txt 경로 → 정규화 회의 텍스트."""
from normalize_input import load_meeting_text


def transcribe(source: str, **opts) -> str:
    """source(문자열 또는 .txt 경로)를 정규화된 회의 원문으로 반환."""
    return load_meeting_text(source)
```

- [ ] **Step 9: 테스트 통과 확인**

Run: `python -m pytest tests/test_adapters.py -v`
Expected: PASS (7 passed)

- [ ] **Step 10: 커밋**

```bash
git add scripts/normalize_input.py scripts/adapters/__init__.py scripts/adapters/text.py tests/test_adapters.py
git commit -m "feat: 어댑터 레지스트리 + 텍스트 어댑터, 정규화 공용화"
```

---

## Task 2: 로컬 STT 어댑터 (faster-whisper)

**Files:**
- Create: `scripts/adapters/whisper_local.py`
- Modify: `scripts/adapters/__init__.py` (레지스트리 한 줄 추가)
- Test: `tests/test_adapters.py`

**Interfaces:**
- Consumes: `normalize_input.normalize_text(text) -> str`, `adapters.get_adapter`.
- Produces: `adapters.whisper_local.transcribe(source: str, **opts) -> str`.
  - `opts`: `model_size="medium"`, `cpu_threads=4`, `language="ko"`.
  - `source`: 오디오 파일 경로. 없으면 `FileNotFoundError`. `faster_whisper` 미설치면 `RuntimeError`.

- [ ] **Step 1: whisper 어댑터 테스트 작성 (실패 예상)**

`tests/test_adapters.py` 하단에 추가:
```python
import sys
import types


def _fake_faster_whisper(segment_texts):
    """faster_whisper 모듈을 흉내내는 가짜. WhisperModel.transcribe가
    (.text 속성을 가진 세그먼트 iterable, info)를 반환하도록 구성."""
    module = types.ModuleType("faster_whisper")

    class FakeSegment:
        def __init__(self, text):
            self.text = text

    class FakeModel:
        def __init__(self, *args, **kwargs):
            self.init_kwargs = kwargs

        def transcribe(self, path, **kwargs):
            segs = [FakeSegment(t) for t in segment_texts]
            return segs, {"language": kwargs.get("language")}

    module.WhisperModel = FakeModel
    return module


def test_whisper_transcribes_and_normalizes(tmp_path, monkeypatch):
    monkeypatch.setitem(
        sys.modules, "faster_whisper",
        _fake_faster_whisper(["안녕하세요  ", "회의를 시작합니다"]),
    )
    from adapters.whisper_local import transcribe
    audio = tmp_path / "meeting.wav"
    audio.write_bytes(b"fake audio")
    result = transcribe(str(audio))
    assert result == "안녕하세요 회의를 시작합니다"


def test_whisper_missing_file_raises(monkeypatch):
    monkeypatch.setitem(sys.modules, "faster_whisper", _fake_faster_whisper(["x"]))
    from adapters.whisper_local import transcribe
    with pytest.raises(FileNotFoundError):
        transcribe("존재하지_않는_파일.wav")


def test_whisper_not_installed_raises(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "faster_whisper", None)  # import 시 ImportError 유발
    import importlib
    import adapters.whisper_local as wl
    importlib.reload(wl)
    audio = tmp_path / "meeting.wav"
    audio.write_bytes(b"fake audio")
    with pytest.raises(RuntimeError, match="requirements-stt.txt"):
        wl.transcribe(str(audio))


def test_whisper_registered():
    assert "whisper" in available_sources()
    assert callable(get_adapter("whisper"))
```

- [ ] **Step 2: 테스트 실행하여 실패 확인**

Run: `python -m pytest tests/test_adapters.py -k whisper -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'adapters.whisper_local'`

- [ ] **Step 3: whisper 어댑터 구현**

`scripts/adapters/whisper_local.py`:
```python
"""로컬 STT 어댑터: faster-whisper로 오디오 → 정규화 회의 텍스트.

faster_whisper는 함수 내부에서 lazy import (미설치 시에도 텍스트 경로 동작).
"""
from pathlib import Path

from normalize_input import normalize_text


def transcribe(source: str, **opts) -> str:
    """오디오 파일(source)을 faster-whisper로 전사 → 정규화 텍스트.

    opts: model_size='medium', cpu_threads=4, language='ko'.
    """
    audio_path = Path(source)
    if not audio_path.is_file():
        raise FileNotFoundError(f"오디오 파일을 찾을 수 없습니다: {source}")

    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise RuntimeError(
            "faster-whisper가 설치되지 않았습니다. "
            "`pip install -r requirements-stt.txt` 를 실행하세요."
        ) from e

    model_size = opts.get("model_size", "medium")
    cpu_threads = opts.get("cpu_threads", 4)
    language = opts.get("language", "ko")

    model = WhisperModel(
        model_size, device="cpu", compute_type="int8", cpu_threads=cpu_threads
    )
    segments, _info = model.transcribe(str(audio_path), language=language)
    raw = " ".join(seg.text.strip() for seg in segments)
    return normalize_text(raw)
```

`scripts/adapters/__init__.py` 의 `ADAPTERS`에 한 줄 추가:
```python
ADAPTERS = {
    "text": ("adapters.text", "transcribe"),
    "whisper": ("adapters.whisper_local", "transcribe"),
}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_adapters.py -k whisper -v`
Expected: PASS (4 passed)

- [ ] **Step 5: 커밋**

```bash
git add scripts/adapters/whisper_local.py scripts/adapters/__init__.py tests/test_adapters.py
git commit -m "feat: 로컬 STT 어댑터(faster-whisper)"
```

---

## Task 3: 클라우드 STT 어댑터 (Groq Whisper API)

**Files:**
- Create: `scripts/adapters/groq_cloud.py`
- Modify: `scripts/adapters/__init__.py` (레지스트리 한 줄 추가)
- Test: `tests/test_adapters.py`

**Interfaces:**
- Consumes: `normalize_input.normalize_text(text) -> str`, `adapters.get_adapter`.
- Produces: `adapters.groq_cloud.transcribe(source: str, **opts) -> str`.
  - `opts`: `model="whisper-large-v3"`, `language="ko"`.
  - `source`: 오디오 파일 경로. 없으면 `FileNotFoundError`. `GROQ_API_KEY` 미설정이면 `RuntimeError`. `groq` 미설치면 `RuntimeError`.

- [ ] **Step 1: groq 어댑터 테스트 작성 (실패 예상)**

`tests/test_adapters.py` 하단에 추가:
```python
def _fake_groq(transcript_text):
    """groq 모듈을 흉내내는 가짜. Groq().audio.transcriptions.create(...).text 반환."""
    module = types.ModuleType("groq")

    class FakeResp:
        def __init__(self, text):
            self.text = text

    class FakeTranscriptions:
        def create(self, **kwargs):
            return FakeResp(transcript_text)

    class FakeAudio:
        transcriptions = FakeTranscriptions()

    class FakeGroq:
        def __init__(self, *args, **kwargs):
            self.audio = FakeAudio()

    module.Groq = FakeGroq
    return module


def test_groq_transcribes_and_normalizes(tmp_path, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setitem(sys.modules, "groq", _fake_groq("안녕하세요   회의 시작"))
    from adapters.groq_cloud import transcribe
    audio = tmp_path / "meeting.m4a"
    audio.write_bytes(b"fake audio")
    assert transcribe(str(audio)) == "안녕하세요 회의 시작"


def test_groq_missing_key_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setitem(sys.modules, "groq", _fake_groq("x"))
    from adapters.groq_cloud import transcribe
    audio = tmp_path / "meeting.m4a"
    audio.write_bytes(b"fake audio")
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        transcribe(str(audio))


def test_groq_missing_file_raises(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setitem(sys.modules, "groq", _fake_groq("x"))
    from adapters.groq_cloud import transcribe
    with pytest.raises(FileNotFoundError):
        transcribe("존재하지_않는_파일.m4a")


def test_groq_not_installed_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setitem(sys.modules, "groq", None)  # import 시 ImportError 유발
    import importlib
    import adapters.groq_cloud as gc
    importlib.reload(gc)
    audio = tmp_path / "meeting.m4a"
    audio.write_bytes(b"fake audio")
    with pytest.raises(RuntimeError, match="requirements-stt.txt"):
        gc.transcribe(str(audio))


def test_groq_registered():
    assert "groq" in available_sources()
    assert callable(get_adapter("groq"))
```

- [ ] **Step 2: 테스트 실행하여 실패 확인**

Run: `python -m pytest tests/test_adapters.py -k groq -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'adapters.groq_cloud'`

- [ ] **Step 3: groq 어댑터 구현**

`scripts/adapters/groq_cloud.py`:
```python
"""클라우드 STT 어댑터: Groq Whisper API로 오디오 → 정규화 회의 텍스트.

groq는 함수 내부에서 lazy import. 인증은 GROQ_API_KEY 환경변수.
"""
import os
from pathlib import Path

from normalize_input import normalize_text


def transcribe(source: str, **opts) -> str:
    """오디오 파일(source)을 Groq Whisper API로 전사 → 정규화 텍스트.

    opts: model='whisper-large-v3', language='ko'.
    """
    audio_path = Path(source)
    if not audio_path.is_file():
        raise FileNotFoundError(f"오디오 파일을 찾을 수 없습니다: {source}")

    if not os.environ.get("GROQ_API_KEY"):
        raise RuntimeError(
            "GROQ_API_KEY 환경변수가 설정되지 않았습니다. "
            "Groq 콘솔에서 발급한 키를 환경변수로 지정하세요."
        )

    try:
        from groq import Groq
    except ImportError as e:
        raise RuntimeError(
            "groq 패키지가 설치되지 않았습니다. "
            "`pip install -r requirements-stt.txt` 를 실행하세요."
        ) from e

    model = opts.get("model", "whisper-large-v3")
    language = opts.get("language", "ko")

    client = Groq()
    with open(audio_path, "rb") as f:
        resp = client.audio.transcriptions.create(
            file=(audio_path.name, f.read()),
            model=model,
            language=language,
        )
    return normalize_text(resp.text)
```

`scripts/adapters/__init__.py` 의 `ADAPTERS`에 한 줄 추가:
```python
ADAPTERS = {
    "text": ("adapters.text", "transcribe"),
    "whisper": ("adapters.whisper_local", "transcribe"),
    "groq": ("adapters.groq_cloud", "transcribe"),
}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_adapters.py -k groq -v`
Expected: PASS (5 passed)

- [ ] **Step 5: 전체 어댑터 테스트 확인**

Run: `python -m pytest tests/test_adapters.py -v`
Expected: PASS (16 passed)

- [ ] **Step 6: 커밋**

```bash
git add scripts/adapters/groq_cloud.py scripts/adapters/__init__.py tests/test_adapters.py
git commit -m "feat: 클라우드 STT 어댑터(Groq Whisper API)"
```

---

## Task 4: CLI 디스패처 (transcribe.py)

**Files:**
- Create: `scripts/transcribe.py`
- Test: `tests/test_transcribe.py`

**Interfaces:**
- Consumes: `adapters.get_adapter(name)`, `adapters.available_sources()`.
- Produces: `transcribe.run(source_name: str, input_arg: str, **opts) -> str` (어댑터 호출 결과), CLI `python scripts/transcribe.py --source <name> <입력>` → 정규화 텍스트를 stdout 출력.

- [ ] **Step 1: 디스패처 테스트 작성 (실패 예상)**

`tests/test_transcribe.py`:
```python
import subprocess
import sys
from pathlib import Path

import pytest

from transcribe import run

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_TXT = ROOT / "examples" / "sample_meeting.txt"


def test_run_text_source_from_string():
    assert run("text", "회의 시작\n논의") == "회의 시작\n논의"


def test_run_text_source_from_file():
    result = run("text", str(SAMPLE_TXT))
    assert "STT 연동" in result


def test_run_unknown_source_raises():
    with pytest.raises(ValueError):
        run("nope", "x")


def test_cli_text_source_stdout():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "transcribe.py"),
         "--source", "text", "회의 시작\n논의 내용"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode == 0
    assert "회의 시작" in proc.stdout


def test_cli_unknown_source_errors():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "transcribe.py"),
         "--source", "nope", "x"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode != 0
```

- [ ] **Step 2: 테스트 실행하여 실패 확인**

Run: `python -m pytest tests/test_transcribe.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'transcribe'`

- [ ] **Step 3: 디스패처 구현**

`scripts/transcribe.py`:
```python
"""[1] 입력 계층 CLI 디스패처: --source로 어댑터를 골라 정규화 텍스트 출력.

사용:
    python scripts/transcribe.py --source text    회의.txt
    python scripts/transcribe.py --source whisper 회의.wav
    python scripts/transcribe.py --source groq    회의.m4a
결과(정규화된 회의 텍스트)를 표준 출력으로 내보내며, 이를 [2] 추출 단계로 넘긴다.
"""
import argparse
import sys

from adapters import available_sources, get_adapter


def run(source_name: str, input_arg: str, **opts) -> str:
    """source_name 어댑터로 input_arg를 정규화 회의 텍스트로 변환."""
    adapter = get_adapter(source_name)
    return adapter(input_arg, **opts)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="회의 입력을 정규화된 회의 텍스트로 변환한다."
    )
    parser.add_argument(
        "--source", default="text", choices=available_sources(),
        help="입력 소스 어댑터 (기본: text)",
    )
    parser.add_argument(
        "input", help="텍스트/.txt 경로(text) 또는 오디오 파일 경로(whisper/groq)",
    )
    args = parser.parse_args()

    try:
        text = run(args.source, args.input)
    except (ValueError, FileNotFoundError, RuntimeError) as e:
        print(f"오류: {e}", file=sys.stderr)
        sys.exit(1)

    sys.stdout.write(text + "\n")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_transcribe.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: 커밋**

```bash
git add scripts/transcribe.py tests/test_transcribe.py
git commit -m "feat: 입력 계층 CLI 디스패처(transcribe.py)"
```

---

## Task 5: 선택 의존성 파일 + SKILL.md 업데이트 + 최종 검증

**Files:**
- Create: `requirements-stt.txt`
- Modify: `SKILL.md`

**Interfaces:**
- Consumes: 위 모든 어댑터·디스패처.
- Produces: 없음(문서·의존성). 전체 테스트로 회귀 검증.

- [ ] **Step 1: STT 선택 의존성 파일 작성**

`requirements-stt.txt`:
```
# 선택 설치: STT(음성→텍스트) 입력을 쓸 때만 필요.
# 텍스트 입력만 쓰면 기존 requirements.txt만으로 충분하다.
faster-whisper>=1.0.0
groq>=0.11.0
```

- [ ] **Step 2: SKILL.md 의 [1] 단계 지시문 교체**

`SKILL.md` 에서 `### [1] 입력 정규화` 섹션 본문을 아래로 교체:
```markdown
### [1] 입력 (텍스트 / 로컬 STT / 클라우드 STT)
사용자 입력 소스에 따라 어댑터를 골라 정규화된 회의 텍스트를 얻는다.

- 텍스트(붙여넣기 또는 .txt):
  `python scripts/transcribe.py --source text <회의.txt 또는 텍스트>`
- 로컬 STT(faster-whisper, 오프라인):
  `python scripts/transcribe.py --source whisper <회의.wav>`
- 클라우드 STT(Groq Whisper API, GROQ_API_KEY 필요):
  `python scripts/transcribe.py --source groq <회의.m4a>`

STT를 쓰려면 최초 1회 `pip install -r requirements-stt.txt`.
출력(표준 출력의 정규화 텍스트)을 [2] 추출 단계의 입력으로 사용한다.
```

그리고 `SKILL.md` 하단 `## 확장 (STT)` 섹션을 아래로 교체:
```markdown
## 확장 (입력 어댑터 추가/삭제)
입력 방식은 `scripts/adapters/` 플러그인이다. 추가하려면 어댑터 모듈
(`transcribe(source, **opts) -> str`)을 만들고 `scripts/adapters/__init__.py`
의 `ADAPTERS`에 한 줄 등록한다. 삭제는 그 줄과 모듈을 지우면 된다.
[2]~[4] 단계는 어떤 경우에도 수정하지 않는다.
```

- [ ] **Step 3: 텍스트 경로 엔드투엔드 수동 검증**

Run: `python scripts/transcribe.py --source text examples/sample_meeting.txt`
Expected: 정규화된 회의 텍스트가 표준 출력에 나오고 "STT 연동" 문구가 포함됨.

- [ ] **Step 4: 미지원 소스 오류 확인**

Run: `python scripts/transcribe.py --source clova examples/sample_meeting.txt`
Expected: argparse가 `--source` 유효값 아님으로 비정상 종료(exit code ≠ 0).

- [ ] **Step 5: 전체 테스트 실행**

Run: `python -m pytest -v`
Expected: 전체 PASS (기존 16 + 신규 test_adapters 16 + test_transcribe 5 = 37).

- [ ] **Step 6: 커밋**

```bash
git add requirements-stt.txt SKILL.md
git commit -m "feat: STT 선택 의존성 및 SKILL.md 입력 계층 지시문 갱신"
```

---

## Self-Review 결과

- **Spec coverage:** 설계 §3 아키텍처(레지스트리+lazy import) → Task 1. §4 공통 인터페이스 → Task 1~3 전부 `transcribe(source, **opts)->str`. §5 디렉터리 → 전 태스크. §6 CLI → Task 4. §7.1 text → Task 1, §7.2 whisper(medium/cpu_threads=4) → Task 2, §7.3 groq(whisper-large-v3/GROQ_API_KEY) → Task 3. §8 에러 처리(미설치/키없음/파일없음/빈결과/미지원 소스) → Task 2·3·4 테스트. §9 테스트 전략(모킹) → Task 2·3. 의존성 분리 → Task 5. 누락 없음.
- **Placeholder scan:** "TBD/TODO/적절히" 없음. 모든 코드 스텝에 실제 코드 포함.
- **Type consistency:** `normalize_text(str)->str`, `load_meeting_text(str)->str`, `transcribe(str, **opts)->str`(세 어댑터 동일), `get_adapter(str)->Callable`, `available_sources()->list`, `run(str, str, **opts)->str` — 태스크 간 명칭/시그니처 일치 확인.
- **참고:** lazy import 테스트(`test_*_not_installed_raises`)는 `sys.modules[...] = None` 후 `importlib.reload`로 미설치를 시뮬레이션한다. 실제 환경에 STT 패키지가 설치돼 있어도 이 방식으로 결정적으로 검증된다.
