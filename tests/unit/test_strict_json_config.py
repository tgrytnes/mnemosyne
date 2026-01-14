
from mnemosyne.llm.strict_json import StrictJsonConfig


def test_strict_json_defaults(monkeypatch):
    monkeypatch.delenv("STRICT_JSON_STEPS", raising=False)
    monkeypatch.delenv("ALLOW_JSON_FALLBACK", raising=False)

    config = StrictJsonConfig.from_env()

    assert config.steps == frozenset()
    assert config.allow_fallback is False
    assert config.is_strict("semantic_chunking") is False


def test_strict_json_parses_steps(monkeypatch):
    monkeypatch.setenv("STRICT_JSON_STEPS", "semantic_chunking, cluster_profiles")

    config = StrictJsonConfig.from_env()

    assert config.is_strict("semantic_chunking") is True
    assert config.is_strict("cluster_profiles") is True
    assert config.is_strict("contextual_headers") is False


def test_strict_json_all_steps(monkeypatch):
    monkeypatch.setenv("STRICT_JSON_STEPS", "ALL")

    config = StrictJsonConfig.from_env()

    assert config.is_strict("any_step") is True


def test_strict_json_fallback_toggle(monkeypatch):
    monkeypatch.setenv("ALLOW_JSON_FALLBACK", "true")

    config = StrictJsonConfig.from_env()

    assert config.allow_fallback is True
