"""Make research roots owner-scoped without coupling to application Alembic."""

VERSION = "0001"


def upgrade(connection, rebuild) -> None:
    """Run the durable owner-scoping rebuild supplied by the migration runner."""
    rebuild(connection)
