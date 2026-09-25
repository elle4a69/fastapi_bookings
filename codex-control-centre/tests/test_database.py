import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from backend.database import Base, set_sqlite_pragma
from backend.models.codex import Project, Thread, Turn, Item

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    # Enable foreign keys for the in-memory SQLite database
    from sqlalchemy import event
    event.listen(engine, "connect", set_sqlite_pragma)
    
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_foreign_key_enforcement(db_session):
    # Try inserting a thread without a project
    thread = Thread(id="th_1", project_id="nonexistent_project", title="Test Thread")
    db_session.add(thread)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

def test_cascade_deletion(db_session):
    # Create project, thread, turn, and item
    project = Project(id="pr_1", name="Test Project", repo_path="/repo", default_branch="main")
    db_session.add(project)
    db_session.commit()
    
    thread = Thread(id="th_1", project_id="pr_1", title="Test Thread")
    db_session.add(thread)
    db_session.commit()
    
    turn = Turn(thread_id="th_1", turn_number=1, status="completed")
    db_session.add(turn)
    db_session.commit()
    
    item = Item(id="it_1", turn_id=turn.id, item_type="message", content={}, sequence=1)
    db_session.add(item)
    db_session.commit()
    
    # Delete the thread and expect turns and items to be deleted
    db_session.delete(thread)
    db_session.commit()
    
    assert db_session.query(Turn).count() == 0
    assert db_session.query(Item).count() == 0

def test_unique_turn_number(db_session):
    project = Project(id="pr_1", name="Test Project", repo_path="/repo", default_branch="main")
    db_session.add(project)
    
    thread = Thread(id="th_1", project_id="pr_1", title="Test Thread")
    db_session.add(thread)
    db_session.commit()
    
    turn1 = Turn(thread_id="th_1", turn_number=1, status="completed")
    db_session.add(turn1)
    db_session.commit()
    
    turn2 = Turn(thread_id="th_1", turn_number=1, status="pending")
    db_session.add(turn2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
