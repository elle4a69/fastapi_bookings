import sys
from os.path import abspath, dirname
from logging.config import fileConfig

from sqlalchemy import engine_from_config, inspect, pool
from alembic import context
from alembic.script import ScriptDirectory

# Ensure the root project directory is in sys.path
sys.path.insert(0, abspath(dirname(dirname(__file__))))

# Import application settings and models metadata
from app.core.config import settings
from app.db.database import Base
import app.models  # imports all models to populate Base.metadata

# Set up Alembic Config object
config = context.config

# Dynamically set the database connection URL from Settings
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Expose models metadata for autogenerate migrations
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        # This repository adopted Alembic after its original tables already
        # existed, so the oldest revision is a legacy delta rather than a true
        # create-from-zero migration.  Bootstrap a genuinely empty database
        # from the authoritative current metadata and stamp it at head.  All
        # existing databases continue through the normal revision chain.
        destination = getattr(getattr(config, "cmd_opts", None), "revision", None)
        user_tables = set(inspect(connection).get_table_names()) - {"alembic_version"}
        if destination == "head" and not user_tables:
            script = ScriptDirectory.from_config(config)
            with context.begin_transaction():
                target_metadata.create_all(bind=connection)
                context.get_context().stamp(script, script.get_current_head())
            connection.commit()
            return

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
