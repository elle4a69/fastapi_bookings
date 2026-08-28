"""Service package CRUD routes."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_db, DatabaseId
from ...models.package import ServicePackage as PackageModel, PackageStep as StepModel
from ...schemas.package import (
    PackageCreate,
    PackageUpdate,
    PackageOut,
    PackageStepCreate,
    PackageStepUpdate,
    PackageStepOut,
)

router = APIRouter(prefix="/api/admin/packages", tags=["packages"])


@router.get("", response_model=List[PackageOut])
def list_packages(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> List[PackageOut]:
    packages = db.query(PackageModel).filter(PackageModel.tenant_id == current_user.tenant_id).all()
    return [PackageOut.model_validate(p) for p in packages]


@router.post("", response_model=PackageOut)
def create_package(
    package_in: PackageCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> PackageOut:
    package = PackageModel(**package_in.model_dump(), tenant_id=current_user.tenant_id)
    db.add(package)
    db.commit()
    db.refresh(package)
    return PackageOut.model_validate(package)


@router.get("/{package_id}", response_model=PackageOut)
def get_package(
    package_id: DatabaseId,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> PackageOut:
    package = db.query(PackageModel).filter(
        PackageModel.id == package_id,
        PackageModel.tenant_id == current_user.tenant_id
    ).first()
    if not package:
        raise HTTPException(status_code=404, detail="Package not found")
    return PackageOut.model_validate(package)


@router.put("/{package_id}", response_model=PackageOut)
def update_package(
    package_id: DatabaseId,
    package_in: PackageUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> PackageOut:
    package = db.query(PackageModel).filter(
        PackageModel.id == package_id,
        PackageModel.tenant_id == current_user.tenant_id
    ).first()
    if not package:
        raise HTTPException(status_code=404, detail="Package not found")
    for field, value in package_in.model_dump(exclude_unset=True).items():
        setattr(package, field, value)
    db.commit()
    db.refresh(package)
    return PackageOut.model_validate(package)


@router.delete("/{package_id}", response_model=PackageOut)
def delete_package(
    package_id: DatabaseId,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> PackageOut:
    package = db.query(PackageModel).filter(
        PackageModel.id == package_id,
        PackageModel.tenant_id == current_user.tenant_id
    ).first()
    if not package:
        raise HTTPException(status_code=404, detail="Package not found")
    db.delete(package)
    db.commit()
    return PackageOut.model_validate(package)


@router.post("/{package_id}/steps", response_model=PackageStepOut)
def add_package_step(
    package_id: DatabaseId,
    step_in: PackageStepCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> PackageStepOut:
    # Validate package existence
    package = db.query(PackageModel).filter(
        PackageModel.id == package_id,
        PackageModel.tenant_id == current_user.tenant_id
    ).first()
    if not package:
        raise HTTPException(status_code=404, detail="Package not found")
    step = StepModel(**step_in.model_dump())
    db.add(step)
    db.commit()
    db.refresh(step)
    return PackageStepOut.model_validate(step)


@router.put("/steps/{step_id}", response_model=PackageStepOut)
def update_package_step(
    step_id: DatabaseId,
    step_in: PackageStepUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> PackageStepOut:
    step = db.query(StepModel).filter(StepModel.id == step_id).first()
    if not step:
        raise HTTPException(status_code=404, detail="Package step not found")
    for field, value in step_in.model_dump(exclude_unset=True).items():
        setattr(step, field, value)
    db.commit()
    db.refresh(step)
    return PackageStepOut.model_validate(step)


@router.delete("/steps/{step_id}", response_model=PackageStepOut)
def delete_package_step(
    step_id: DatabaseId,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> PackageStepOut:
    step = db.query(StepModel).filter(StepModel.id == step_id).first()
    if not step:
        raise HTTPException(status_code=404, detail="Package step not found")
    db.delete(step)
    db.commit()
    return PackageStepOut.model_validate(step)