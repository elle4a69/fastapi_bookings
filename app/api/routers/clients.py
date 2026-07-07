"""Client CRUD routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_db
from ...core.pagination import paginate_query, pagination_params
from ...models.client import Client as ClientModel
from ...schemas.client import (
    Client,
    ClientCreate,
    ClientListResponse,
    ClientResponse,
    ClientUpdate,
)


router = APIRouter()


@router.get("/clients", response_model=ClientListResponse, tags=["clients"])
def list_clients(
    params: dict = Depends(pagination_params),
    db: Session = Depends(get_db),
) -> dict:
    """Return a paginated list of clients."""
    query = db.query(ClientModel)
    items, meta = paginate_query(query, params["page"], params["page_size"])
    return {"ok": True, "data": items, "meta": meta}


@router.post("/clients", response_model=ClientResponse, tags=["clients"])
def create_client(
    client_in: ClientCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Create a new client."""
    client = ClientModel(**client_in.dict())
    db.add(client)
    db.commit()
    db.refresh(client)
    return {"ok": True, "data": client}


@router.get("/clients/{client_id}", response_model=ClientResponse, tags=["clients"])
def get_client(client_id: int, db: Session = Depends(get_db)) -> dict:
    """Retrieve a single client by ID."""
    client = db.query(ClientModel).filter(ClientModel.id == client_id).first()
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return {"ok": True, "data": client}


@router.put("/clients/{client_id}", response_model=ClientResponse, tags=["clients"])
def update_client(
    client_id: int,
    client_in: ClientUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Update an existing client."""
    client = db.query(ClientModel).filter(ClientModel.id == client_id).first()
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    for field, value in client_in.dict(exclude_unset=True).items():
        setattr(client, field, value)
    db.commit()
    db.refresh(client)
    return {"ok": True, "data": client}


@router.delete("/clients/{client_id}", response_model=ClientResponse, tags=["clients"])
def delete_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Delete a client."""
    client = db.query(ClientModel).filter(ClientModel.id == client_id).first()
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    db.delete(client)
    db.commit()
    return {"ok": True, "data": client}