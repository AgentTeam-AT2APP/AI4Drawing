from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def _parse_env_line(line: str) -> Optional[tuple[str, str]]:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if "=" not in stripped:
        return None
    key, value = stripped.split("=", 1)
    key = key.strip()
    value = value.strip()
    if not key:
        return None
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"\"", "'"}:
        value = value[1:-1]
    return key, value


def load_env(env_path: Optional[Path] = None) -> Optional[Path]:
    """
    Load environment variables from frontend-workflow/.env if present.

    Existing environment variables are not overridden.
    """
    if env_path is None:
        project_root = Path(__file__).resolve().parent.parent
        env_path = project_root / "frontend-workflow" / ".env"

    if not env_path.exists():
        return None

    for line in env_path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_env_line(line)
        if not parsed:
            continue
        key, value = parsed
        os.environ.setdefault(key, value)

    return env_path
