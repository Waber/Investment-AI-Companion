import os
import runpy
from pathlib import Path


def test_env_example_startup_preserves_cors_origins(monkeypatch, tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    # The example may leave SECRET_KEY empty. Startup requires a real key,
    # so the copied file gets one before Settings() runs.
    lines = []
    replaced = False
    for line in (project_root / ".env.example").read_text().splitlines():
        if line.startswith("SECRET_KEY="):
            lines.append("SECRET_KEY=unit-test-secret-key-0123456789abcd")
            replaced = True
        else:
            lines.append(line)
    if not replaced:
        lines.append("SECRET_KEY=unit-test-secret-key-0123456789abcd")
    (tmp_path / ".env").write_text("\n".join(lines) + "\n")
    monkeypatch.chdir(tmp_path)
    for name in list(os.environ):
        monkeypatch.delenv(name)

    # Execute a fresh module so cached settings cannot hide startup failures.
    config = runpy.run_path(str(project_root / "app/core/config.py"))

    origins = config["settings"].cors_origins
    assert [str(origin) for origin in origins] == [
        "http://localhost:3000/",
        "http://127.0.0.1:3000/",
    ]
