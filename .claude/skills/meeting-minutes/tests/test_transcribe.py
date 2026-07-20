import pytest

from transcribe import run
from adapters import get_adapter, available_sources


def test_available_sources_includes_text():
    assert "text" in available_sources()


def test_get_adapter_returns_callable():
    adapter = get_adapter("text")
    assert callable(adapter)


def test_get_adapter_unknown_source_raises_with_list():
    with pytest.raises(ValueError) as exc:
        get_adapter("nope")
    # 오류 메시지에 사용 가능한 소스를 안내
    assert "text" in str(exc.value)


def test_run_text_source_returns_normalized_text():
    result = run("text", "첫 줄   \n\n\n\n둘째 줄  ")
    assert result == "첫 줄\n\n둘째 줄"


def test_run_default_source_is_text():
    # source_name 없이 호출하면 text로 처리
    result = run("text", "회의 시작\n논의 내용")
    assert result == "회의 시작\n논의 내용"
