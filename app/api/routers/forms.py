"""Form schema endpoints.

These endpoints provide JSON schemas describing the forms used in the
admin and public UIs.  A front‑end can request these schemas to
generate dynamic forms that match the backend validation rules.
Schematizing forms allows changes to be rolled out centrally without
hard‑coding field definitions in the front‑end.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from fastapi import APIRouter

class FormFieldSchema(BaseModel):
    name: str
    type: str
    label: str
    required: Optional[bool] = None
    default: Optional[Any] = None
    items: Optional[Dict[str, Any]] = None


class FormSchemaResponse(BaseModel):
    fields: List[FormFieldSchema]


router = APIRouter(prefix="/api/forms", tags=["forms"])


@router.get("/service", response_model=FormSchemaResponse)
def get_service_form() -> Dict[str, Any]:
    """Return the form schema for creating/updating a service."""
    schema = {
        "fields": [
            {"name": "name", "type": "string", "label": "Service Name", "required": True},
            {"name": "description", "type": "text", "label": "Description"},
            {"name": "duration", "type": "number", "label": "Duration (minutes)", "required": True},
            {"name": "price", "type": "number", "label": "Price"},
            {"name": "active", "type": "boolean", "label": "Active", "default": True},
        ]
    }
    return schema


@router.get("/provider", response_model=FormSchemaResponse)
def get_provider_form() -> Dict[str, Any]:
    """Return the form schema for creating/updating a provider."""
    schema = {
        "fields": [
            {"name": "name", "type": "string", "label": "Provider Name", "required": True},
            {"name": "email", "type": "string", "label": "Email"},
            {"name": "phone", "type": "string", "label": "Phone"},
            {"name": "active", "type": "boolean", "label": "Active", "default": True},
        ]
    }
    return schema


@router.get("/booking", response_model=FormSchemaResponse)
def get_booking_form() -> Dict[str, Any]:
    """Return the form schema for creating a booking."""
    schema = {
        "fields": [
            {"name": "client_id", "type": "number", "label": "Client", "required": False},
            {"name": "service_id", "type": "number", "label": "Service", "required": True},
            {"name": "provider_id", "type": "number", "label": "Provider"},
            {"name": "location_id", "type": "number", "label": "Location"},
            {"name": "start_time", "type": "datetime", "label": "Start Time", "required": True},
            {"name": "end_time", "type": "datetime", "label": "End Time", "required": True},
            {"name": "add_on_ids", "type": "array", "items": {"type": "number"}, "label": "Add‑Ons"},
            {"name": "product_ids", "type": "array", "items": {"type": "number"}, "label": "Products"},
            {"name": "notes", "type": "text", "label": "Notes"},
        ]
    }
    return schema