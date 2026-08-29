"""Regression coverage for lightweight provider collection responses."""

from datetime import datetime, timezone

from app.models.provider import Provider as ProviderModel
from app.schemas.provider import ProviderListItem


def test_provider_list_item_omits_oversized_profile_image() -> None:
    provider = ProviderModel(
        id=1,
        tenant_id=1,
        name="Test Provider",
        created_at=datetime.now(timezone.utc),
        active=True,
        is_visible=True,
        capacity=1,
        ignore_company_hours=False,
        image="x" * (150 * 1024 + 1),
    )

    response = ProviderListItem.model_validate(provider).model_dump()

    assert provider.thumbnail is None
    assert response["thumbnail"] is None
    assert "image" not in response


def test_provider_list_item_keeps_small_thumbnail() -> None:
    thumbnail = "data:image/webp;base64,small"
    provider = ProviderModel(
        id=1,
        tenant_id=1,
        name="Test Provider",
        created_at=datetime.now(timezone.utc),
        active=True,
        is_visible=True,
        capacity=1,
        ignore_company_hours=False,
        image=thumbnail,
    )

    response = ProviderListItem.model_validate(provider).model_dump()

    assert response["thumbnail"] == thumbnail
