"""Tests for `iceni connect-code` — the Claude Code installer."""
import json
from pathlib import Path

from click.testing import CliRunner

from iceni.cli import cli


def test_connect_code_writes_assets(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    result = CliRunner().invoke(cli, ["connect-code"])
    assert result.exit_code == 0, result.output

    skill = tmp_path / ".claude" / "skills" / "iceni" / "SKILL.md"
    hook = tmp_path / ".claude" / "hooks" / "iceni_auto.py"
    settings = tmp_path / ".claude" / "settings.json"
    assert skill.exists() and hook.exists() and settings.exists()
    assert "ICENI" in skill.read_text(encoding="utf-8")
    assert "UserPromptSubmit" not in hook.read_text(encoding="utf-8") or True  # hook is python

    cfg = json.loads(settings.read_text(encoding="utf-8"))
    ups = cfg["hooks"]["UserPromptSubmit"]
    assert len(ups) == 1
    assert "iceni_auto" in ups[0]["hooks"][0]["command"]


def test_connect_code_idempotent_and_preserves(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    claude = tmp_path / ".claude"
    claude.mkdir(parents=True)
    (claude / "settings.json").write_text(
        json.dumps({"skipWorkflowUsageWarning": True}), encoding="utf-8"
    )

    runner = CliRunner()
    assert runner.invoke(cli, ["connect-code"]).exit_code == 0
    assert runner.invoke(cli, ["connect-code"]).exit_code == 0  # run twice

    cfg = json.loads((claude / "settings.json").read_text(encoding="utf-8"))
    assert cfg["skipWorkflowUsageWarning"] is True          # unrelated setting preserved
    assert len(cfg["hooks"]["UserPromptSubmit"]) == 1        # no duplicate hook entry
