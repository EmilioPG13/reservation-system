"""Write the OpenAPI schema to a file.

Run from backend/: `uv run python -m app.export_openapi ../frontend/openapi.json`.
The frontend generates its typed client from this file, so it needs neither a running API nor a
database.
"""

import json
import os
import sys
from pathlib import Path

# Settings requires a signing key at import time; exporting the schema signs nothing.
os.environ.setdefault("JWT_SECRET_KEY", "openapi-export-only")

from app.main import app  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("Usage: python -m app.export_openapi <output.json>", file=sys.stderr)
        return 2
    Path(args[0]).write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
