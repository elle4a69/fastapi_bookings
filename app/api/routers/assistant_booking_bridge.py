"""Private booking-domain bridge for the single approved Assistant UI line."""
from fastapi import APIRouter, Depends, Header, Request, HTTPException, status
from sqlalchemy.orm import Session
from ...db.database import get_db
from ...schemas.assistant_booking_bridge import AvailabilityRequest, ProposalRequest, ConfirmRequest
from ...services import assistant_booking_bridge as bridge

router = APIRouter(prefix="/api/internal/assistant-booking-bridge", tags=["assistant-booking-bridge"])

async def _binding(request: Request, db: Session = Depends(get_db), key_id: str | None = Header(None, alias="X-Assistant-Bridge-Key-Id"), timestamp: str | None = Header(None, alias="X-Assistant-Bridge-Timestamp"), nonce: str | None = Header(None, alias="X-Assistant-Bridge-Nonce"), signature: str | None = Header(None, alias="X-Assistant-Bridge-Signature")):
    return bridge.authenticate(db, method=request.method, path=request.url.path, body=await request.body(), key_id=key_id, timestamp=timestamp, nonce=nonce, signature=signature)

@router.get("/catalog")
def catalog(binding=Depends(_binding), db: Session = Depends(get_db)):
    data = []
    from ...models import Service
    for service in db.query(Service).filter(Service.tenant_id == binding.tenant_id, Service.active.is_(True), Service.deleted_at.is_(None)).all():
        try:
            bridge._service(db, binding, service.id)
        except HTTPException as exc:
            if exc.status_code < 500:
                continue
            raise
        except Exception:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, {"code": "BRIDGE_UNAVAILABLE"})
        data.append({"id": service.id, "name": service.name, "duration_minutes": service.duration, "price": str(service.price) if service.price is not None else None})
    return {"ok": True, "data": {"services": data, "timezone": bridge.business_timezone(db, binding)}}

@router.post("/availability")
def get_availability(payload: AvailabilityRequest, binding=Depends(_binding), db: Session = Depends(get_db)):
    return {"ok": True, "data": bridge.availability(db, binding, payload.service_id, payload.start_time, payload.end_time)}

@router.post("/proposals")
def create_proposal(payload: ProposalRequest, binding=Depends(_binding), db: Session = Depends(get_db)):
    item = bridge.propose(db, binding, payload.service_id, payload.start_time)
    return {"ok": True, "data": {
        "proposal_id": item.id,
        "summary": bridge.proposal_summary(db, binding, item),
        "expires_at": item.expires_at,
        "status": "awaiting_customer_confirmation",
    }}

@router.post("/confirmations")
def confirm_booking(payload: ConfirmRequest, binding=Depends(_binding), db: Session = Depends(get_db)):
    booking = bridge.confirm(db, binding, payload.proposal_id, payload.request_id, payload.customer_name, payload.customer_phone, payload.customer_email)
    return {"ok": True, "data": {"booking_id": booking.id, "status": booking.status, "start_time": booking.start_time, "end_time": booking.end_time}}
