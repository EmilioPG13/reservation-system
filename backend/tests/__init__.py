import os

# Runs before conftest imports app.core.config, which requires a signing key.
os.environ.setdefault("JWT_SECRET_KEY", "test-only-signing-key-not-used-anywhere-else")
