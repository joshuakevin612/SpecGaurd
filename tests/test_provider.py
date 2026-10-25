"""Provider boundaries: never consume Nebius as an implicit fallback."""

from types import SimpleNamespace

import pytest
from openai import APIConnectionError

from specguard_ai import provider


def fake_client(monkeypatch, tmp_path, content='{"requirements": []}', finish_reason="stop"):
    captured = {}
    monkeypatch.setenv("SPECGUARD_PROVIDER", "nvidia")
    monkeypatch.setenv("NVIDIA_API_KEY", "test-nvidia-key")
    monkeypatch.setenv("NVIDIA_MODEL", "test-model")
    monkeypatch.setenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
    monkeypatch.setenv("NEBIUS_API_KEY", "reserved-nebius-key")
    monkeypatch.setenv("SPECGUARD_USAGE_FILE", str(tmp_path / "usage.jsonl"))

    class Client:
        def __init__(self, **kwargs):
            captured["client"] = kwargs
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def create(self, **kwargs):
            captured["request"] = kwargs
            return SimpleNamespace(
                usage=None,
                choices=[SimpleNamespace(finish_reason=finish_reason,
                                         message=SimpleNamespace(content=content))],
            )

    monkeypatch.setattr(provider, "OpenAI", Client)
    return captured


def test_nvidia_selection_never_uses_nebius_key(monkeypatch, tmp_path):
    captured = fake_client(monkeypatch, tmp_path)
    assert provider.request_json("parse_spec", {"spec": "hello"}) == {"requirements": []}
    assert captured["client"]["api_key"] == "test-nvidia-key"
    assert captured["client"]["max_retries"] == 0
    log = (tmp_path / "usage.jsonl").read_text("utf-8")
    assert '"provider": "nvidia"' in log
    assert "test-nvidia-key" not in log
    assert "reserved-nebius-key" not in log
    assert "hello" not in log


def test_lightning_uses_documented_json_settings(monkeypatch, tmp_path):
    captured = fake_client(monkeypatch, tmp_path)
    monkeypatch.setenv("NVIDIA_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b")
    provider.request_json("parse_spec", {"spec": "hello"})
    assert captured["request"]["response_format"] == {"type": "json_object"}
    assert captured["request"]["extra_body"]["chat_template_kwargs"]["enable_thinking"] is False


def test_code_model_override_stays_on_nvidia(monkeypatch, tmp_path):
    captured = fake_client(monkeypatch, tmp_path, content='{"tests": []}')
    monkeypatch.setenv("NVIDIA_CODE_MODEL", "nvidia/nemotron-3.5-super-vl-120b-a12b")
    provider.request_json("generate_tests", {"requirements": [{"id": "REQ-001"}], "code": ""})
    assert captured["request"]["model"] == "nvidia/nemotron-3.5-super-vl-120b-a12b"
    assert captured["request"]["response_format"]["type"] == "json_object"
    assert captured["client"]["api_key"] == "test-nvidia-key"
    assert captured["request"]["extra_body"]["chat_template_kwargs"]["enable_thinking"] is False


@pytest.mark.parametrize("content,reason,message", [
    ("not JSON", "stop", "valid JSON"),
    ('{"requirements": []}', "length", "incomplete"),
])
def test_invalid_or_truncated_response_is_an_error(monkeypatch, tmp_path, content, reason, message):
    fake_client(monkeypatch, tmp_path, content=content, finish_reason=reason)
    with pytest.raises(provider.ProviderError, match=message):
        provider.request_json("parse_spec", {"spec": "hello"})


def test_connection_failure_does_not_try_another_provider(monkeypatch, tmp_path):
    fake_client(monkeypatch, tmp_path)
    calls = []

    def fail(**kwargs):
        calls.append(kwargs["base_url"])
        raise APIConnectionError(request=SimpleNamespace())

    monkeypatch.setattr(provider, "OpenAI", fail)
    with pytest.raises(provider.ProviderError, match="no retry"):
        provider.request_json("parse_spec", {"spec": "hello"})
    assert calls == ["https://integrate.api.nvidia.com/v1"]
