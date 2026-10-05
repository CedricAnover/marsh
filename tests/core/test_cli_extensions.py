import json
from types import SimpleNamespace

from importlib import metadata

from marsh.cli import EXIT_INCOMPATIBLE, EXIT_SUCCESS, main
from marsh.extensions import discover_extensions


def _entry(name, value, contract, package="demo-ext"):
    dist = SimpleNamespace(
        name=package,
        version="1.0",
        metadata={"Marsh-Extension-Contract": str(contract)},
    )
    return SimpleNamespace(name=name, value=value, dist=dist)


def test_cli_inspect_is_read_only_and_deterministic(tmp_path, capsys):
    workflow = {
        "id": "demo",
        "tasks": [
            {
                "id": "b",
                "operation": {
                    "type": "process",
                    "executable": "python",
                    "arguments": ["-c", "print('b')"],
                },
                "dependencies": ["a"],
            },
            {
                "id": "a",
                "operation": {
                    "type": "process",
                    "executable": "python",
                    "arguments": ["-c", "print('a')"],
                },
            },
        ],
    }
    path = tmp_path / "workflow.json"
    path.write_text(json.dumps(workflow), encoding="utf-8")

    assert main(["inspect", str(path), "--json"]) == EXIT_SUCCESS
    first = capsys.readouterr().out
    assert main(["inspect", str(path), "--json"]) == EXIT_SUCCESS
    second = capsys.readouterr().out

    assert first == second
    payload = json.loads(first)
    assert payload["plan"]["order"] == ["a", "b"]
    assert payload["execution"]["performed"] is False


def test_discovery_is_sorted_and_does_not_load(monkeypatch):
    entries = [_entry("z", "demo:z", 1), _entry("a", "demo:a", 1)]
    monkeypatch.setattr(metadata, "entry_points", lambda: entries)

    assert [item.name for item in discover_extensions()] == ["a", "z"]


def test_discovery_rejects_incompatible_contract(monkeypatch, capsys):
    entries = [_entry("old", "old:plugin", 99, "old-ext")]
    monkeypatch.setattr(metadata, "entry_points", lambda: entries)

    assert discover_extensions()[0].status == "unsupported"
    assert main(["plugins", "list"]) == EXIT_INCOMPATIBLE
    assert "old:plugin" in capsys.readouterr().out


def test_secret_safe_cli_error(tmp_path, capsys):
    path = tmp_path / "bad.json"
    path.write_text('{"token":"super-secret",', encoding="utf-8")
    assert main(["inspect", str(path)]) != EXIT_SUCCESS
    assert "super-secret" not in capsys.readouterr().err


def test_redaction_masks_nested_credentials_and_authorization():
    from marsh.diagnostics import redact

    value = {
        "outer": {"password": "secret-value", "safe": "keep"},
        "authorization": "Bearer abc123",
        "items": [{"api_key": "another-secret"}],
    }

    safe = redact(value)
    assert safe["outer"]["password"] == "[REDACTED]"
    assert safe["outer"]["safe"] == "keep"
    assert safe["authorization"] == "[REDACTED]"
    assert safe["items"][0]["api_key"] == "[REDACTED]"
