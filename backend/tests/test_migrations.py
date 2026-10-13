from alembic import command
from alembic.config import Config


def test_models_match_migrations(alembic_config: Config, migrated_schema: None) -> None:
    """Fails if a model changed without a matching migration."""
    command.check(alembic_config)
