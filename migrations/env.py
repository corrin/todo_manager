import logging
from logging.config import fileConfig
import os
import sys
from pathlib import Path

from alembic import context
from flask import current_app

# --- Setup Flask App ---
# Add project root to sys.path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import and create Flask app
from virtual_assistant import create_app

app = create_app()
app.app_context().push()

# Import all models for autogenerate support
from virtual_assistant.database.user import User
from virtual_assistant.database.calendar_account import CalendarAccount
from virtual_assistant.database.task import TaskAccount
from virtual_assistant.database.external_account import ExternalAccount
from virtual_assistant.database.database import db

# --- Alembic Config ---
config = context.config

# Setup Python logging
fileConfig(config.config_file_name)
logger = logging.getLogger('alembic.env')

# Pull SQLAlchemy engine URL from app config
def get_engine_url():
    return current_app.extensions['migrate'].db.engine.url.render_as_string(hide_password=False).replace('%', '%%')

config.set_main_option('sqlalchemy.url', get_engine_url())

target_db = db

# --- Migration Setup ---
def get_metadata():
    if hasattr(target_db, 'metadatas'):
        return target_db.metadatas[None]
    return target_db.metadata

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, target_metadata=get_metadata(), literal_binds=True
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    def process_revision_directives(context, revision, directives):
        if getattr(config.cmd_opts, 'autogenerate', False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                logger.info('No changes in schema detected.')

    conf_args = current_app.extensions['migrate'].configure_args
    if conf_args.get("process_revision_directives") is None:
        conf_args["process_revision_directives"] = process_revision_directives

    connectable = current_app.extensions['migrate'].db.engine

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=get_metadata(),
            **conf_args
        )

        with context.begin_transaction():
            context.run_migrations()

# --- Entry Point ---
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
