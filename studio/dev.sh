#!/usr/bin/env bash
# 一条命令拉起 Postgres、Redis、API、worker 和前端。
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
  python3 - <<'PY'
import base64
import os
import secrets
from pathlib import Path

example = Path(".env.example").read_text(encoding="utf-8")
secret = secrets.token_urlsafe(32)
fernet = base64.urlsafe_b64encode(os.urandom(32)).decode()
text = example.replace("STUDIO_SECRET_KEY=dev-only-change-me", f"STUDIO_SECRET_KEY={secret}", 1)
text = text.replace("STUDIO_FERNET_KEY=", f"STUDIO_FERNET_KEY={fernet}", 1)
Path(".env").write_text(text, encoding="utf-8")
print("wrote studio/.env")
PY
fi

docker compose up --build "$@"
