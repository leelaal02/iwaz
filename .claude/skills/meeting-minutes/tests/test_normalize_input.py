from pathlib import Path

import pytest

from normalize_input import load_meeting_text, resolve_input_path

SAMPLE_TXT = Path(__file__).resolve().parent.parent / "examples" / "sample_meeting.txt"


def test_load_from_string():
    result = load_meeting_text("회의 시작\n논의 내용")
    assert result == "회의 시작\n논의 내용"


def test_load_from_file():
    result = load_meeting_text(str(SAMPLE_TXT))
    assert "STT 연동" in result
    assert "김수민" in result


def test_trailing_whitespace_and_blank_lines_collapsed():
    result = load_meeting_text("첫 줄   \n\n\n\n둘째 줄  ")
    assert result == "첫 줄\n\n둘째 줄"


def test_empty_input_raises():
    with pytest.raises(ValueError):
        load_meeting_text("   \n\n  ")


# --- resolve_input_path: 파일 이름만으로 위치 탐색 ---

def test_resolve_finds_file_by_name_outside_cwd(tmp_path, monkeypatch):
    # 작업 폴더가 아닌 다른 폴더에 파일을 두고, 이름만으로 찾게 한다.
    other = tmp_path / "somewhere"
    other.mkdir()
    audio = other / "b.m4a"
    audio.write_bytes(b"fake")
    monkeypatch.setenv("MEETING_INPUT_DIRS", str(other))
    monkeypatch.chdir(tmp_path)  # cwd에는 파일이 없음
    resolved = resolve_input_path("b.m4a", must_exist=True)
    assert resolved is not None
    assert resolved.name == "b.m4a"
    assert resolved.read_bytes() == b"fake"


def test_resolve_prefers_exact_existing_path(tmp_path, monkeypatch):
    # 주어진 경로가 이미 존재하면 탐색 없이 그대로 반환.
    f = tmp_path / "given.txt"
    f.write_text("x", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert resolve_input_path("given.txt") == Path("given.txt")


def test_resolve_missing_must_exist_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("MEETING_INPUT_DIRS", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError) as exc:
        resolve_input_path("does_not_exist_12345.m4a", must_exist=True)
    # 오류 메시지에 검색 위치 안내가 포함
    assert "검색한 위치" in str(exc.value)


def test_resolve_missing_without_must_exist_returns_none(tmp_path, monkeypatch):
    monkeypatch.setenv("MEETING_INPUT_DIRS", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    assert resolve_input_path("nope_98765.m4a", must_exist=False) is None


def test_load_meeting_text_finds_txt_by_name(tmp_path, monkeypatch):
    # text 어댑터 경로: 작업 폴더 밖의 .txt를 이름만으로 읽어온다.
    other = tmp_path / "notes_dir"
    other.mkdir()
    (other / "note.txt").write_text("회의 내용\n결정 사항", encoding="utf-8")
    monkeypatch.setenv("MEETING_INPUT_DIRS", str(other))
    monkeypatch.chdir(tmp_path)
    assert load_meeting_text("note.txt") == "회의 내용\n결정 사항"


def test_load_meeting_text_literal_string_still_works(tmp_path, monkeypatch):
    # 파일로 해석되지 않는 문자열은 그대로 원문으로 취급(리터럴 폴백 유지).
    monkeypatch.setenv("MEETING_INPUT_DIRS", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    assert load_meeting_text("그냥 회의 원문 텍스트") == "그냥 회의 원문 텍스트"
