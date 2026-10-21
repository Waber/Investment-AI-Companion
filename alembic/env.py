from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.core.config import settings
from app.core.utc_datetime import UTCDateTime
from app.models.database_models import Base
from app.models.price_amount import PriceAmount

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
# A test passes its own connection and must not replace the logging
# setup pytest already installed. fileConfig would drop captured logs
# for every test that runs after the migration.
if (
    config.config_file_name is not None
    and config.attributes.get("connection") is None
):
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def render_item(type_, obj, autogen_context):
    """Teach autogenerate how to write custom column types.

    Without the ``UTCDateTime`` branch the generated file contains
    ``app.core.utc_datetime.UTCDateTime(timezone=True)``. Running
    that file raises ``NameError`` because the name ``app`` is not
    imported there. The short class name is valid once the import
    below is in the migration.

    ``PriceAmount`` would be written the same way, as
    ``app.models.price_amount.PriceAmount()``, and that name is not
    imported either. The column is ``NUMERIC(20, 8)`` in a migration.
    Alembic already imports ``sqlalchemy as sa``. Autogenerate would
    render NUMERIC on SQLite for a future table too. The live SQLite
    column is TEXT; a new migration still has to say so itself, the
    way revision ``0006`` does.
    """
    if type_ == "type" and isinstance(obj, UTCDateTime):
        autogen_context.imports.add(
            "from app.core.utc_datetime import UTCDateTime"
        )
        return "UTCDateTime(timezone=True)"
    if type_ == "type" and isinstance(obj, PriceAmount):
        return "sa.Numeric(20, 8)"
    return False


def get_url():
    """
    Get the database URL from our application settings.
    This allows us to use environment variables for database configuration.
    """
    return settings.DATABASE_URL


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_item=render_item,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    Tests pass an open connection on ``config.attributes["connection"]``
    so a revision can be applied to a temporary database. That path
    does not read ``settings.DATABASE_URL`` and does not open the
    application engine.
    """
    connection = config.attributes.get("connection")
    if connection is not None:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_item=render_item,
        )
        with context.begin_transaction():
            context.run_migrations()
        return

    # Override the sqlalchemy.url in alembic.ini with our dynamic URL
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_item=render_item,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
