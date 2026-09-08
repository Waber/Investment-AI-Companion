import os
import runpy
import shutil
from pathlib import Path


def test_env_example_startup_preserves_cors_origins(monkeypatch, tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    shutil.copyfile(project_root / ".env.example", tmp_path / ".env")
    monkeypatch.chdir(tmp_path)
    for name in list(os.environ):
        monkeypatch.delenv(name)

    # Execute a fresh module so cached settings cannot hide startup failures.
    config = runpy.run_path(str(project_root / "app/core/config.py"))

    origins = config["settings"].BACKEND_CORS_ORIGINS
    assert [str(origin) for origin in origins] == [
        "http://localhost:3000/",
        "http://127.0.0.1:3000/",
    ]
