from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from backend.database import Base

class Project(Base):
    __tablename__ = "projects"
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    repo_path = Column(String, nullable=False)
    default_branch = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    threads = relationship("Thread", back_populates="project", cascade="all, delete-orphan")

class Thread(Base):
    __tablename__ = "threads"
    
    id = Column(String, primary_key=True)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    status = Column(String, nullable=False, default="active")
    is_pinned = Column(Boolean, nullable=False, default=False)
    is_archived = Column(Boolean, nullable=False, default=False)
    
    project = relationship("Project", back_populates="threads")
    turns = relationship("Turn", back_populates="thread", cascade="all, delete-orphan")
    tool_approvals = relationship("ToolApproval", back_populates="thread", cascade="all, delete-orphan")
    subagents = relationship("SubAgent", back_populates="thread", cascade="all, delete-orphan")

class Turn(Base):
    __tablename__ = "turns"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    thread_id = Column(String, ForeignKey("threads.id", ondelete="CASCADE"), nullable=False)
    turn_number = Column(Integer, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
    prompt = Column(Text, nullable=True)
    
    __table_args__ = (UniqueConstraint('thread_id', 'turn_number'),)
    
    thread = relationship("Thread", back_populates="turns")
    items = relationship("Item", back_populates="turn", cascade="all, delete-orphan")

class Item(Base):
    __tablename__ = "items"
    
    id = Column(String, primary_key=True)
    turn_id = Column(Integer, ForeignKey("turns.id", ondelete="CASCADE"), nullable=False)
    item_type = Column(String, nullable=False)
    content = Column(JSON, nullable=False)
    sequence = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    turn = relationship("Turn", back_populates="items")

class ToolApproval(Base):
    __tablename__ = "tool_approvals"
    
    id = Column(String, primary_key=True)
    thread_id = Column(String, ForeignKey("threads.id", ondelete="CASCADE"), nullable=False)
    tool_call_id = Column(String, nullable=False)
    command = Column(Text, nullable=False)
    risk_level = Column(String, nullable=False)
    consequence = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="pending")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime, nullable=True)
    
    thread = relationship("Thread", back_populates="tool_approvals")

class SubAgent(Base):
    __tablename__ = "subagents"
    
    id = Column(String, primary_key=True)
    thread_id = Column(String, ForeignKey("threads.id", ondelete="CASCADE"), nullable=False)
    parent_thread_id = Column(String, nullable=True)
    name = Column(String, nullable=False)
    role = Column(String, nullable=False)
    status = Column(String, nullable=False)
    progress = Column(Integer, nullable=False, default=0)
    current_action = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    thread = relationship("Thread", back_populates="subagents")
