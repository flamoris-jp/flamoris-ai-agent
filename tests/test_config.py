from pathlib import Path

import pytest

from flamoris_ai_agent import config


def test_home_must_be_absolute(monkeypatch):
    monkeypatch.setenv("FLAMORIS_AGENT_HOME", "relative")
    with pytest.raises(ValueError, match="absolute"):
        config.agent_home()


def test_context_does_not_depend_on_working_directory(monkeypatch, tmp_path):
    expected = config.load_agent_text("personality.md")
    monkeypatch.chdir(tmp_path)
    assert config.load_agent_text("personality.md") == expected


def test_configured_home_is_authoritative(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "AGENT_HOME", tmp_path)
    monkeypatch.setenv("FLAMORIS_AGENT_KEY", "custom")
    with pytest.raises(FileNotFoundError):
        config.load_agent_text("personality.md")
    path = tmp_path / "agents/custom/personality.md"
    path.parent.mkdir(parents=True)
    path.write_text("Custom identity", encoding="utf-8")
    assert config.load_agent_text("personality.md") == "Custom identity"


def test_context_paths_are_bounded(monkeypatch):
    monkeypatch.setenv("FLAMORIS_AGENT_KEY", "../other")
    with pytest.raises(ValueError):
        config.load_agent_text("personality.md")
    monkeypatch.setenv("FLAMORIS_AGENT_KEY", "umeko")
    with pytest.raises(ValueError):
        config.load_agent_text("../../.env")


def test_explicit_home(monkeypatch, tmp_path):
    monkeypatch.setenv("FLAMORIS_AGENT_HOME", str(tmp_path))
    assert config.agent_home() == Path(tmp_path)
