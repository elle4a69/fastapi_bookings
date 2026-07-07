"""Product model.

Products are tangible items that can be sold in conjunction with
services.  For example, a massage therapist might sell bottles of
oil as a product.  Products can be tied to services to indicate
recommended upsells.  The relationship between services and
products is defined in the ``ServiceProduct`` association table.
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from ..db.database import Base


class Product(Base):
    """Represents a sellable product.

    Attributes:
        id: Primary key.
        name: Human‑readable product name.
        description: Optional description of the product.
        price: Sale price of the product.
        sku: Stock keeping unit or unique code.
        active: Whether the product is available for sale.
        created_at: Timestamp when the product was created.
    """

    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    price = Column(Float, nullable=False)
    sku = Column(String, nullable=True, unique=True)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    services = relationship(
        "ServiceProduct",
        back_populates="product",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Product id={self.id} name={self.name}>"


class ServiceProduct(Base):
    """Association table linking services and products.

    This table allows a service to recommend or include additional
    products.  For example, a hairdresser service might suggest a
    shampoo product that can be purchased with the booking.
    """

    __tablename__ = "service_products"

    id = Column(Integer, primary_key=True, index=True)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)

    # Relationships
    service = relationship("Service", back_populates="products")
    product = relationship("Product", back_populates="services")

    def __repr__(self) -> str:
        return (
            f"<ServiceProduct service_id={self.service_id} product_id={self.product_id}>"
        )