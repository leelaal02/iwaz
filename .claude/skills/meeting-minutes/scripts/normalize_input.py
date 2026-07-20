"""입력 계층: 회의 원문 텍스트를 정규화. STT 어댑터 자리 확보."""
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


# --- STT 확장 자리 (이번 범위에서 구현하지 않음) ---
# def load_from_stt(audio_path: str) -> str:
#     """STT 추가 시 이 함수만 구현하면 하위 단계([2]~[4]) 무수정."""
#     raise NotImplementedError("STT 입력은 아직 지원하지 않습니다.")
