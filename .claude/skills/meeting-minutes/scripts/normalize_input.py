"""입력 계층: 회의 원문 텍스트를 정규화 + 입력 파일 위치 탐색.

`resolve_input_path`는 모든 입력 어댑터(text/whisper/groq 및 앞으로 추가될 것)가
공통으로 호출하는 파일 탐색 헬퍼다. 작업 폴더에 없더라도 파일 이름만으로
공통 위치를 찾아준다. 어댑터는 이 헬퍼만 쓰면 되므로 탐색 로직이 한 곳에 모인다.
"""
import os
import sys
from pathlib import Path

# 파일 이름만 주어졌을 때 재귀 탐색을 건너뛸 잡음 디렉토리(속도·안전).
_SKIP_DIRS = {
    "node_modules", "__pycache__", ".venv", "venv", "env",
    ".pytest_cache", "AppData", "$Recycle.Bin",
    "System Volume Information", "Windows", "Program Files",
    "Program Files (x86)",
}
# 재귀 탐색 최대 깊이(루트 기준). 홈 등 큰 트리에서 과도한 탐색 방지.
_MAX_DEPTH = 6


def _search_roots() -> list:
    """파일 이름 탐색에 쓸 루트 목록(우선순위 순, 존재하는 것만, 중복 제거).

    MEETING_INPUT_DIRS(os.pathsep 구분)로 앞쪽에 루트를 추가할 수 있다.
    기본: 현재 작업 폴더 → 바탕화면 → 다운로드 → 문서 → 홈.
    """
    roots = []
    env = os.environ.get("MEETING_INPUT_DIRS")
    if env:
        roots += [Path(p) for p in env.split(os.pathsep) if p.strip()]
    home = Path.home()
    roots += [Path.cwd(), home / "Desktop", home / "Downloads",
              home / "Documents", home]
    seen, uniq = set(), []
    for r in roots:
        try:
            key = r.resolve()
        except OSError:
            key = r
        if key not in seen and r.is_dir():
            seen.add(key)
            uniq.append(r)
    return uniq


def _find_under(root: Path, name: str) -> Path:
    """root 아래를 재귀 탐색해 파일명이 일치하는 첫 파일 경로를 반환(없으면 None)."""
    root = Path(root)
    root_depth = len(root.parts)
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            depth = len(Path(dirpath).parts) - root_depth
            if depth >= _MAX_DEPTH:
                dirnames[:] = []
            else:
                # 잡음·숨김 디렉토리 가지치기(탐색 속도 확보)
                dirnames[:] = [d for d in dirnames
                               if d not in _SKIP_DIRS and not d.startswith(".")]
            if name in filenames:
                return Path(dirpath) / name
    except (OSError, PermissionError):
        return None
    return None


def resolve_input_path(source: str, *, must_exist: bool = False):
    """입력 경로 문자열을 실제 파일 경로로 해석.

    1. source가 그대로 존재하는 파일이면 그 경로를 반환(cwd 기준 상대경로 포함).
    2. 아니고 절대경로면 탐색하지 않음(경로가 명시된 것이므로).
    3. 파일 이름/상대경로면 공통 루트들을 재귀 탐색해 첫 일치를 반환.
    4. 못 찾으면 must_exist=True면 FileNotFoundError, 아니면 None.

    작업 폴더 밖에서 찾았을 때는 어느 경로를 썼는지 stderr로 알린다(투명성).
    """
    candidate = Path(source)
    if candidate.exists() and candidate.is_file():
        return candidate
    if candidate.is_absolute():
        if must_exist:
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {source}")
        return None
    name = candidate.name
    for root in _search_roots():
        match = _find_under(root, name)
        if match is not None:
            print(f"[transcribe] 입력 파일을 찾았습니다: {match}", file=sys.stderr)
            return match
    if must_exist:
        locations = ", ".join(str(r) for r in _search_roots())
        raise FileNotFoundError(
            f"'{source}' 파일을 찾지 못했습니다. 검색한 위치: {locations}. "
            "정확한 경로를 지정하거나 MEETING_INPUT_DIRS 환경변수로 폴더를 추가하세요."
        )
    return None


def load_meeting_text(source: str) -> str:
    """텍스트 문자열 또는 .txt 파일 경로를 정규화된 회의 원문으로 변환.

    - source가 (작업 폴더 밖이라도) 파일로 해석되면 파일 내용을 읽음.
    - 그렇지 않으면 source 자체를 원문 텍스트로 간주.
    """
    resolved = resolve_input_path(source, must_exist=False)
    if resolved is not None:
        text = resolved.read_text(encoding="utf-8")
    else:
        text = source
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


