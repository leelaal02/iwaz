"""[1] 입력 계층 CLI 디스패처.

사용자가 직접 실행하지 않는다. SKILL.md 지시에 따라 Claude가 [1] 단계에서
실행하는 헬퍼. 정규화된 회의 텍스트를 표준 출력으로 내보낸다.

사용:
    python scripts/transcribe.py --source text    회의.txt
    python scripts/transcribe.py --source whisper 회의.wav
    python scripts/transcribe.py --source groq    회의.m4a
"""
import argparse
import sys

from adapters import get_adapter, available_sources


def run(source_name: str, source: str, **opts) -> str:
    adapter = get_adapter(source_name)
    return adapter(source, **opts)


def main() -> None:
    parser = argparse.ArgumentParser(description="회의 입력 → 정규화된 회의 텍스트")
    parser.add_argument(
        "--source", default="text", choices=available_sources(),
        help="입력 어댑터 선택 (기본: text)",
    )
    parser.add_argument("input", help="텍스트 문자열, .txt 경로, 또는 오디오 파일 경로")
    args = parser.parse_args()
    sys.stdout.write(run(args.source, args.input))


if __name__ == "__main__":
    main()
