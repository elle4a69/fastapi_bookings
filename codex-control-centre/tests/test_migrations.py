import os
import pytest
import tempfile
from alembic import command
from alembic.config import Config
from backend.config import settings

@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    # Override settings for the duration of the test
    original_url = settings.database_url
    settings.database_url = f"sqlite:///{path}"
    
    yield path
    
    settings.database_url = original_url
    try:
        os.remove(path)
    except PermissionError:
        pass

def test_migrations_up_down_up(temp_db):
    alembic_cfg = Config("alembic.ini")
    
    # Set the sqlalchemy.url in the alembic config programmatically
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
    
    # Upgrade to head
    command.upgrade(alembic_cfg, "head")
    
    # Downgrade to base
    command.downgrade(alembic_cfg, "base")
    
    # Upgrade back to head
    command.upgrade(alembic_cfg, "head")
