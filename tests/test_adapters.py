import sys
from pathlib import Path

import pytest

from adapters.text import transcribe as text_transcribe
from adapters import whisper_local, groq_cloud

SAMPLE_TXT = Path(__file__).resolve().parent.parent / "examples" / "sample_meeting.txt"


def test_text_adapter_from_string():
    assert text_transcribe("첫 줄   \n\n\n\n둘째 줄  ") == "첫 줄\n\n둘째 줄"


def test_text_adapter_from_file():
    result = text_transcribe(str(SAMPLE_TXT))
    assert "STT 연동" in result
    assert "김수민" in result


class _FakeSegment:
    def __init__(self, text):
        self.text = text


class _FakeModel:
    def transcribe(self, path, **kwargs):
        # faster-whisper API: (segments, info) 반환. segments는 이터러블.
        return [_FakeSegment("첫 줄  "), _FakeSegment(" 둘째 줄")], None


def test_whisper_adapter_joins_and_normalizes(monkeypatch):
    monkeypatch.setattr(whisper_local, "_load_model", lambda **kw: _FakeModel())
    result = whisper_local.transcribe("dummy.wav")
    # 세그먼트 텍스트를 이어 붙이고 정규화(줄 끝 공백 제거)
    assert result == "첫 줄\n둘째 줄"


def test_whisper_adapter_missing_library(monkeypatch):
    # faster_whisper import 실패를 강제 → 친절한 설치 안내
    monkeypatch.setitem(sys.modules, "faster_whisper", None)
    with pytest.raises(ImportError) as exc:
        whisper_local._load_model()
    assert "requirements-stt.txt" in str(exc.value)


class _FakeTranscription:
    text = "첫 줄  \n\n\n둘째 줄  "


class _FakeAudio:
    class transcriptions:
        @staticmethod
        def create(**kwargs):
            return _FakeTranscription()


class _FakeGroqClient:
    audio = _FakeAudio()


def test_groq_adapter_normalizes(monkeypatch, tmp_path):
    audio = tmp_path / "a.m4a"
    audio.write_bytes(b"fake")
    monkeypatch.setattr(groq_cloud, "_client", lambda: _FakeGroqClient())
    result = groq_cloud.transcribe(str(audio))
    assert result == "첫 줄\n\n둘째 줄"


def test_groq_adapter_missing_api_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    # groq 라이브러리 존재 여부와 무관하게 키 미설정을 먼저 안내
    with pytest.raises(RuntimeError) as exc:
        groq_cloud._client()
    assert "GROQ_API_KEY" in str(exc.value)


def test_groq_adapter_missing_library(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "dummy")
    monkeypatch.setitem(sys.modules, "groq", None)
    with pytest.raises(ImportError) as exc:
        groq_cloud._client()
    assert "requirements-stt.txt" in str(exc.value)
