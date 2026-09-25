from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import uuid
from backend.database import get_db
from backend.models.codex import Thread, Project
from backend.config import settings
from backend.services import governance_service

router = APIRouter(prefix="/codex/threads", tags=["threads"])

class ThreadCreate(BaseModel):
    project_id: str
    title: str

class ThreadUpdate(BaseModel):
    title: Optional[str] = None
    is_pinned: Optional[bool] = None
    is_archived: Optional[bool] = None
    status: Optional[str] = None

class ThreadResponse(BaseModel):
    id: str
    project_id: str
    title: str
    status: str
    is_pinned: bool
    is_archived: bool

    model_config = {"from_attributes": True}

@router.post("", response_model=ThreadResponse)
def create_thread(thread: ThreadCreate, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == thread.project_id).first()
    if not project:
        existing_default = db.query(Project).first()
        if existing_default and (thread.project_id in ["default", "proj_default", ""] or not thread.project_id):
            project = existing_default
            actual_project_id = project.id
        else:
            project = Project(
                id=thread.project_id,
                name="Default Project",
                repo_path=str(settings.repo_root),
                default_branch="main"
            )
            db.add(project)
            db.flush()
            actual_project_id = project.id
    else:
        actual_project_id = project.id

    new_thread = Thread(
        id=str(uuid.uuid4()),
        project_id=actual_project_id,
        title=thread.title
    )
    db.add(new_thread)
    db.commit()
    db.refresh(new_thread)
    return new_thread

@router.get("", response_model=List[ThreadResponse])
def list_threads(db: Session = Depends(get_db)):
    return db.query(Thread).all()

@router.get("/{thread_id}", response_model=ThreadResponse)
def get_thread(thread_id: str, db: Session = Depends(get_db)):
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return thread

@router.patch("/{thread_id}", response_model=ThreadResponse)
def update_thread(thread_id: str, updates: ThreadUpdate, db: Session = Depends(get_db)):
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    update_data = updates.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(thread, key, value)
        
    db.commit()
    db.refresh(thread)

    if thread.status in ["stopped", "cancelled", "archived", "completed"] or thread.is_archived:
        governance_service.cancel_pending_approvals_for_thread(thread_id, db=db, reason=f"Thread transitioned to {thread.status}")

    return thread

@router.delete("/{thread_id}")
def delete_thread(thread_id: str, db: Session = Depends(get_db)):
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    governance_service.cancel_pending_approvals_for_thread(thread_id, db=db, reason="Thread deleted")
    db.delete(thread)
    db.commit()
    return {"message": "Thread deleted"}
