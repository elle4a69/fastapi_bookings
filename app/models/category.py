"""Category model.

Categories provide a way to group services into logical collections.
They can be used to drive a category‑first booking flow or simply
organise services within the admin dashboard.  A service can belong
to zero or more categories via the association table defined in
``service_category``.
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from ..db.database import Base


class Category(Base):
    """Represents a group of related services.

    Attributes:
        id: Primary key.
        name: Human‑readable name.
        description: Optional description shown to clients.
        active: Whether the category is available in booking flows.
        created_at: Timestamp when the category was created.
    """

    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    services = relationship(
        "ServiceCategory",
        back_populates="category",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Category id={self.id} name={self.name}>"


class ServiceCategory(Base):
    """Association table linking services and categories.

    A service can belong to multiple categories and a category can contain
    multiple services.  This model implements the many‑to‑many
    relationship between :class:`Category` and :class:`Service`.
    """

    __tablename__ = "service_categories"

    id = Column(Integer, primary_key=True, index=True)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)

    # Relationships
    service = relationship("Service", back_populates="categories")
    category = relationship("Category", back_populates="services")

    def __repr__(self) -> str:
        return (
            f"<ServiceCategory service_id={self.service_id} category_id={self.category_id}>"
        )