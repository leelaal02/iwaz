"""클라우드 STT 어댑터: Groq Whisper API(whisper-large-v3)로 오디오 → 텍스트.

groq 라이브러리는 _client 안에서 lazy import한다.
"""
import os

from normalize_input import _normalize


def _client():
    """Groq 클라이언트 생성. 키 미설정/라이브러리 미설치를 명확히 안내."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY 환경변수가 설정되지 않았습니다. "
            "Groq 클라우드 STT를 쓰려면 API 키를 설정하세요."
        )
    try:
        from groq import Groq
    except ImportError as e:
        raise ImportError(
            "groq가 설치되지 않았습니다. "
            "pip install -r requirements-stt.txt 를 실행하세요."
        ) from e
    return Groq(api_key=api_key)


def transcribe(source: str, **opts) -> str:
    """오디오 파일 경로(source)를 Groq로 전사해 정규화된 텍스트로 반환.

    opts: model(기본 "whisper-large-v3"), language(기본 "ko").
    """
    client = _client()
    with open(source, "rb") as audio:
        result = client.audio.transcriptions.create(
            file=audio,
            model=opts.get("model", "whisper-large-v3"),
            language=opts.get("language", "ko"),
        )
    normalized = _normalize(result.text)
    if not normalized:
        raise ValueError("전사 결과가 비어 있습니다: 오디오에서 텍스트를 얻지 못했습니다.")
    return normalized
