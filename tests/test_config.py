from pathlib import Path

import pytest

from flamoris_ai_agent import config


def create_agent(home, key="custom", manifest=None, files=None):
    directory = home / "agents" / key
    directory.mkdir(parents=True)
    (directory / "agent.toml").write_text(
        manifest or 'version = 1\n[[context]]\ntitle = "Identity"\nfile = "identity.md"\n',
        encoding="utf-8",
    )
    for filename, content in (files or {"identity.md": "Custom identity"}).items():
        (directory / filename).write_text(content, encoding="utf-8")
    return directory


def test_home_must_be_absolute(monkeypatch):
    monkeypatch.setenv("FLAMORIS_AGENT_HOME", "relative")
    with pytest.raises(ValueError, match="absolute"):
        config.agent_home()


def test_explicit_home(monkeypatch, tmp_path):
    monkeypatch.setenv("FLAMORIS_AGENT_HOME", str(tmp_path))
    assert config.agent_home() == Path(tmp_path)


def test_source_context_does_not_depend_on_working_directory(monkeypatch, tmp_path):
    monkeypatch.setenv("FLAMORIS_AGENT_KEY", "example-agent")
    assert config.agent_home() is not None
    expected = config.load_agent_context()
    monkeypatch.chdir(tmp_path)
    assert config.load_agent_context() == expected
    assert [entry["title"] for entry in expected] == ["Identity", "Support scope"]


def test_custom_minimal_agent_and_order(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "AGENT_HOME", tmp_path)
    monkeypatch.setenv("FLAMORIS_AGENT_KEY", "custom")
    create_agent(
        tmp_path,
        manifest='version = 1\n[[context]]\ntitle = "Advice"\nfile = "advice.md"\n'
        '[[context]]\ntitle = "Identity"\nfile = "identity.md"\n',
        files={"advice.md": "Be concise", "identity.md": "Support agent"},
    )
    assert [(x["title"], x["content"]) for x in config.load_agent_context()] == [
        ("Advice", "Be concise"),
        ("Identity", "Support agent"),
    ]


def test_explicit_home_does_not_fall_back(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "AGENT_HOME", tmp_path)
    monkeypatch.setenv("FLAMORIS_AGENT_KEY", "example-agent")
    with pytest.raises(config.AgentContextError, match="manifest.*agent.toml"):
        config.load_agent_context()


@pytest.mark.parametrize(
    "name",
    ["../secret.md", "/tmp/secret.md", "a/secret.md", "..\\secret.md", "../.env"],
)
def test_invalid_manifest_path_rejected(monkeypatch, tmp_path, name):
    monkeypatch.setattr(config, "AGENT_HOME", tmp_path)
    monkeypatch.setenv("FLAMORIS_AGENT_KEY", "custom")
    create_agent(
        tmp_path,
        manifest=f"version = 1\n[[context]]\ntitle = 'Identity'\nfile = '{name}'\n",
    )
    with pytest.raises(config.AgentContextError, match="Invalid or duplicate"):
        config.load_agent_context()


def test_symlink_escape_rejected(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "AGENT_HOME", tmp_path)
    monkeypatch.setenv("FLAMORIS_AGENT_KEY", "custom")
    directory = create_agent(tmp_path)
    (directory / "identity.md").unlink()
    secret = tmp_path / "secret.md"
    secret.write_text("outside", encoding="utf-8")
    (directory / "identity.md").symlink_to(secret)
    with pytest.raises(config.AgentContextError, match="escapes"):
        config.load_agent_context()


def test_manifest_symlink_escape_rejected(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "AGENT_HOME", tmp_path)
    monkeypatch.setenv("FLAMORIS_AGENT_KEY", "custom")
    directory = create_agent(tmp_path)
    (directory / "agent.toml").unlink()
    outside = tmp_path / "outside.toml"
    outside.write_text('version = 1\n[[context]]\ntitle = "X"\nfile = "identity.md"\n')
    (directory / "agent.toml").symlink_to(outside)
    with pytest.raises(config.AgentContextError, match="manifest escapes"):
        config.load_agent_context()


@pytest.mark.parametrize(
    "manifest,match",
    [
        ("version = 1\n", "requires version"),
        ('version = 2\n[[context]]\ntitle = "A"\nfile = "a.md"\n', "requires version"),
        (
            'version = 1\n[[context]]\ntitle = "A"\nfile = "a.md"\n'
            '[[context]]\ntitle = "A"\nfile = "b.md"\n',
            "duplicate",
        ),
    ],
)
def test_invalid_manifest(monkeypatch, tmp_path, manifest, match):
    monkeypatch.setattr(config, "AGENT_HOME", tmp_path)
    monkeypatch.setenv("FLAMORIS_AGENT_KEY", "custom")
    create_agent(tmp_path, manifest=manifest, files={"a.md": "A", "b.md": "B"})
    with pytest.raises(config.AgentContextError, match=match):
        config.load_agent_context()
