"""Targeted verification test suite for Task B1: Durable Media Backend.

Covers:
1. Safe file upload with validation (permitted MIME types, forbidden extensions, size checks)
2. Tenant-scoped media persistence and retrieval
3. Pagination and eligibility filtering
4. Strict multi-tenant isolation (Tenant B cannot read, patch, or delete Tenant A assets)
5. Public website eligibility gate (private media inaccessible at public delivery URL)
6. Assistant media context projection with absolute exclusion of clinical/booking notes
7. Soft deletion and cleanup
8. Authentication and authorization enforcement
"""

import io
import os
import shutil
import pytest
from datetime import datetime, timezone
from fastapi import status

from app.core.security import create_access_token
from app.models.tenant import Tenant
from app.models.user import User
from app.models.media import Media
from app.services.media_service import MediaService, get_media_base_dir


@pytest.fixture
def media_test_env(db_session):
    """Sets up two isolated test tenants with admin and provider accounts."""
    tenant_a = Tenant(
        name="Apex Aesthetics Clinic",
        subdomain="apex-clinic",
        email="contact@apexclinic.com.au",
        phone="+61 2 9000 1111",
        address="100 George St, Sydney NSW",
        created_at=datetime.now(timezone.utc),
    )
    tenant_b = Tenant(
        name="Harborview Dental Studio",
        subdomain="harborview-dental",
        email="info@harborviewdental.com.au",
        phone="+61 2 9000 2222",
        address="200 Pitt St, Sydney NSW",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add_all([tenant_a, tenant_b])
    db_session.commit()
    db_session.refresh(tenant_a)
    db_session.refresh(tenant_b)

    admin_a = User(
        tenant_id=tenant_a.id,
        login="admin_apex",
        password_hash="fake_hash",
        role="admin",
        created_at=datetime.now(timezone.utc),
    )
    admin_b = User(
        tenant_id=tenant_b.id,
        login="admin_harbor",
        password_hash="fake_hash",
        role="admin",
        created_at=datetime.now(timezone.utc),
    )
    client_user = User(
        tenant_id=tenant_a.id,
        login="regular_client",
        password_hash="fake_hash",
        role="client",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add_all([admin_a, admin_b, client_user])
    db_session.commit()
    db_session.refresh(admin_a)
    db_session.refresh(admin_b)
    db_session.refresh(client_user)

    headers_a = {
        "X-Tenant": tenant_a.subdomain,
        "X-Token": create_access_token({"sub": str(admin_a.id), "tenant_id": tenant_a.id}),
    }
    headers_b = {
        "X-Tenant": tenant_b.subdomain,
        "X-Token": create_access_token({"sub": str(admin_b.id), "tenant_id": tenant_b.id}),
    }
    headers_client = {
        "X-Tenant": tenant_a.subdomain,
        "X-Token": create_access_token({"sub": str(client_user.id), "tenant_id": tenant_a.id}),
    }

    yield {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "admin_a": admin_a,
        "admin_b": admin_b,
        "headers_a": headers_a,
        "headers_b": headers_b,
        "headers_client": headers_client,
    }

    # Teardown test uploads
    base_dir = get_media_base_dir()
    for tid in (tenant_a.id, tenant_b.id):
        tdir = os.path.join(base_dir, f"tenant_{tid}")
        if os.path.exists(tdir):
            shutil.rmtree(tdir, ignore_errors=True)


def test_media_upload_success(client, media_test_env):
    """Admin can upload an image file and receive durable persisted media metadata."""
    headers = media_test_env["headers_a"]
    file_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 200  # Synthetic JPEG content
    files = {
        "file": ("clinic_reception.jpg", io.BytesIO(file_bytes), "image/jpeg"),
    }
    data = {
        "title": "Main Reception Lounge",
        "description": "Welcoming front desk area",
        "is_public_website_eligible": "true",
        "notes": "Internal clinical note: camera 2 blindspot",
    }

    response = client.post("/api/admin/media/upload", headers=headers, files=files, data=data)
    assert response.status_code == status.HTTP_201_CREATED, response.text
    res_data = response.json()
    assert res_data["ok"] is True
    item = res_data["data"]

    assert item["id"] > 0
    assert item["tenant_id"] == media_test_env["tenant_a"].id
    assert "clinic_reception" in item["filename"]
    assert item["content_type"] == "image/jpeg"
    assert item["file_size"] == len(file_bytes)
    assert item["title"] == "Main Reception Lounge"
    assert item["description"] == "Welcoming front desk area"
    assert item["media_type"] == "image"
    assert item["is_public_website_eligible"] is True
    assert item["notes"] == "Internal clinical note: camera 2 blindspot"
    assert item["url"].startswith(f"/api/public/media/{media_test_env['tenant_a'].id}/")

    # Verify physical file existence in tenant-specific storage
    base_dir = get_media_base_dir()
    expected_path = os.path.join(base_dir, item["file_path"])
    assert os.path.exists(expected_path)
    with open(expected_path, "rb") as f:
        assert f.read() == file_bytes


def test_media_upload_validation_mime_and_extension(client, media_test_env):
    """Uploading forbidden file extensions or unsupported MIME types is rejected."""
    headers = media_test_env["headers_a"]

    # 1. Forbidden extension (.exe)
    malicious_files = {
        "file": ("malware.exe", io.BytesIO(b"MZ\x90\x00"), "application/octet-stream"),
    }
    resp1 = client.post("/api/admin/media/upload", headers=headers, files=malicious_files)
    assert resp1.status_code == status.HTTP_400_BAD_REQUEST

    # 2. Unsupported MIME type (text/html)
    html_files = {
        "file": ("exploit.html", io.BytesIO(b"<script>alert(1)</script>"), "text/html"),
    }
    resp2 = client.post("/api/admin/media/upload", headers=headers, files=html_files)
    assert resp2.status_code == status.HTTP_400_BAD_REQUEST


def test_media_listing_and_filtering(client, media_test_env):
    """Listing media returns tenant assets with optional public website eligibility filtering."""
    headers = media_test_env["headers_a"]

    # Upload two items: one eligible, one not eligible
    client.post(
        "/api/admin/media/upload",
        headers=headers,
        files={"file": ("photo1.png", io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50), "image/png")},
        data={"is_public_website_eligible": "true", "title": "Eligible Hero Photo"},
    )
    client.post(
        "/api/admin/media/upload",
        headers=headers,
        files={"file": ("photo2.png", io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50), "image/png")},
        data={"is_public_website_eligible": "false", "title": "Private Backoffice Photo"},
    )

    # 1. Unfiltered listing
    resp_all = client.get("/api/admin/media", headers=headers)
    assert resp_all.status_code == status.HTTP_200_OK
    assert resp_all.json()["total"] == 2

    # 2. Filter: eligible only
    resp_eligible = client.get("/api/admin/media?is_public_website_eligible=true", headers=headers)
    assert resp_eligible.status_code == status.HTTP_200_OK
    data_eligible = resp_eligible.json()["data"]
    assert len(data_eligible) == 1
    assert data_eligible[0]["title"] == "Eligible Hero Photo"

    # 3. Filter: ineligible only
    resp_ineligible = client.get("/api/admin/media?is_public_website_eligible=false", headers=headers)
    assert resp_ineligible.status_code == status.HTTP_200_OK
    data_ineligible = resp_ineligible.json()["data"]
    assert len(data_ineligible) == 1
    assert data_ineligible[0]["title"] == "Private Backoffice Photo"


def test_media_get_detail_and_patch_eligibility(client, media_test_env):
    """Admin can retrieve media detail and toggle website eligibility."""
    headers = media_test_env["headers_a"]

    upload_resp = client.post(
        "/api/admin/media/upload",
        headers=headers,
        files={"file": ("suite.webp", io.BytesIO(b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 40), "image/webp")},
        data={"is_public_website_eligible": "false", "title": "Consultation Suite"},
    )
    media_id = upload_resp.json()["data"]["id"]

    # Retrieve detail
    detail_resp = client.get(f"/api/admin/media/{media_id}", headers=headers)
    assert detail_resp.status_code == status.HTTP_200_OK
    assert detail_resp.json()["data"]["is_public_website_eligible"] is False

    # Patch eligibility to True
    patch_resp = client.patch(
        f"/api/admin/media/{media_id}/eligibility",
        headers=headers,
        json={"is_public_website_eligible": True},
    )
    assert patch_resp.status_code == status.HTTP_200_OK
    assert patch_resp.json()["data"]["is_public_website_eligible"] is True

    # Confirm updated state
    detail_resp2 = client.get(f"/api/admin/media/{media_id}", headers=headers)
    assert detail_resp2.json()["data"]["is_public_website_eligible"] is True


def test_media_deletion_and_disk_purge(client, media_test_env):
    """Deleting a media item removes the database record and cleans up the binary."""
    headers = media_test_env["headers_a"]

    upload_resp = client.post(
        "/api/admin/media/upload",
        headers=headers,
        files={"file": ("to_delete.png", io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 40), "image/png")},
    )
    media_item = upload_resp.json()["data"]
    media_id = media_item["id"]
    file_path = os.path.join(get_media_base_dir(), media_item["file_path"])
    assert os.path.exists(file_path)

    del_resp = client.delete(f"/api/admin/media/{media_id}", headers=headers)
    assert del_resp.status_code == status.HTTP_200_OK
    assert del_resp.json()["ok"] is True

    # Verify 404 on subsequent get
    assert client.get(f"/api/admin/media/{media_id}", headers=headers).status_code == status.HTTP_404_NOT_FOUND

    # Verify physical file is purged
    assert not os.path.exists(file_path)


def test_strict_multi_tenant_isolation(client, media_test_env):
    """Tenant B cannot access, modify, or delete Tenant A's media items."""
    headers_a = media_test_env["headers_a"]
    headers_b = media_test_env["headers_b"]

    upload_resp = client.post(
        "/api/admin/media/upload",
        headers=headers_a,
        files={"file": ("confidential_apex.jpg", io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 40), "image/jpeg")},
        data={"title": "Apex Confidential Treatment Photo"},
    )
    media_id = upload_resp.json()["data"]["id"]

    # Tenant B tries to get detail -> 404 Not Found
    resp_get = client.get(f"/api/admin/media/{media_id}", headers=headers_b)
    assert resp_get.status_code == status.HTTP_404_NOT_FOUND

    # Tenant B tries to patch eligibility -> 404 Not Found
    resp_patch = client.patch(
        f"/api/admin/media/{media_id}/eligibility",
        headers=headers_b,
        json={"is_public_website_eligible": True},
    )
    assert resp_patch.status_code == status.HTTP_404_NOT_FOUND

    # Tenant B tries to delete -> 404 Not Found
    resp_del = client.delete(f"/api/admin/media/{media_id}", headers=headers_b)
    assert resp_del.status_code == status.HTTP_404_NOT_FOUND

    # Tenant B tries to download file -> 404 Not Found
    resp_file = client.get(f"/api/admin/media/{media_id}/file", headers=headers_b)
    assert resp_file.status_code == status.HTTP_404_NOT_FOUND

    # Tenant B lists media -> 0 items
    list_b = client.get("/api/admin/media", headers=headers_b)
    assert list_b.status_code == status.HTTP_200_OK
    assert list_b.json()["total"] == 0


def test_public_website_eligibility_enforcement(client, media_test_env):
    """Unapproved media cannot be retrieved from public delivery endpoints."""
    headers = media_test_env["headers_a"]
    tenant_id = media_test_env["tenant_a"].id

    upload_resp = client.post(
        "/api/admin/media/upload",
        headers=headers,
        files={"file": ("clinical_progress.jpg", io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 40), "image/jpeg")},
        data={"is_public_website_eligible": "false"},
    )
    item = upload_resp.json()["data"]
    stored_filename = item["file_path"].split("/")[-1]

    # Attempt public delivery of private item -> 403 Forbidden
    pub_url = f"/api/public/media/{tenant_id}/{stored_filename}"
    resp_pub = client.get(pub_url)
    assert resp_pub.status_code == status.HTTP_403_FORBIDDEN

    # Approve item for public website
    client.patch(
        f"/api/admin/media/{item['id']}/eligibility",
        headers=headers,
        json={"is_public_website_eligible": True},
    )

    # Now public delivery succeeds with 200 OK
    resp_pub_approved = client.get(pub_url)
    assert resp_pub_approved.status_code == status.HTTP_200_OK
    assert resp_pub_approved.headers["content-type"].startswith("image/jpeg")


def test_exclusion_of_clinical_notes_from_assistant_media_context(db_session, media_test_env):
    """Clinical, booking notes, and private customer records are strictly excluded from assistant media context."""
    tenant = media_test_env["tenant_a"]

    # 1. Create ineligible media item with confidential medical note
    item_private = Media(
        tenant_id=tenant.id,
        filename="dermatology_preop.jpg",
        file_path="tenant_test/priv.jpg",
        url="/api/public/media/1/priv.jpg",
        content_type="image/jpeg",
        file_size=1024,
        title="Pre-Op Assessment",
        description="Clinical evaluation",
        notes="CONFIDENTIAL: Patient John Doe undergoing laser scar excision, patient ID #9942.",
        is_public_website_eligible=False,
        is_deleted=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    # 2. Create eligible media item with staff notes
    item_public = Media(
        tenant_id=tenant.id,
        filename="laser_room.jpg",
        file_path="tenant_test/pub.jpg",
        url="/api/public/media/1/pub.jpg",
        content_type="image/jpeg",
        file_size=2048,
        title="Laser Suite",
        description="Our state of the art laser therapy room",
        notes="INTERNAL STAFF NOTE: Door passcode is 4321. Booking schedule notes.",
        is_public_website_eligible=True,
        is_deleted=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add_all([item_private, item_public])
    db_session.commit()

    # Query assistant media context
    context = MediaService.get_assistant_media_context(db_session, tenant.id)

    # Ineligible item MUST NOT be present
    private_ids = [c["id"] for c in context if c["id"] == item_private.id]
    assert len(private_ids) == 0

    # Eligible item MUST be present
    public_items = [c for c in context if c["id"] == item_public.id]
    assert len(public_items) == 1
    projected = public_items[0]

    # Notes field MUST NOT be in the projected dictionary
    assert "notes" not in projected
    # Search all projected values for sensitive leakages
    projected_str = str(projected)
    assert "CONFIDENTIAL" not in projected_str
    assert "John Doe" not in projected_str
    assert "9942" not in projected_str
    assert "passcode" not in projected_str
    assert "4321" not in projected_str
    assert "Booking schedule" not in projected_str

    # Only safe fields allowed
    assert projected["title"] == "Laser Suite"
    assert projected["is_public_website_eligible"] is True


def test_media_unauthenticated_and_unauthorized_rejection(client, media_test_env):
    """Unauthenticated users or non-admin roles cannot access admin media endpoints."""
    # 1. Missing tenant context -> 400 Bad Request
    resp_no_tenant = client.get("/api/admin/media")
    assert resp_no_tenant.status_code == status.HTTP_400_BAD_REQUEST

    # 2. Missing auth token in tenant -> 401 Unauthorized
    resp_unauth = client.get(
        "/api/admin/media",
        headers={"X-Tenant": media_test_env["tenant_a"].subdomain},
    )
    assert resp_unauth.status_code == status.HTTP_401_UNAUTHORIZED

    # 3. Client role token -> 403 Forbidden
    resp_client = client.get("/api/admin/media", headers=media_test_env["headers_client"])
    assert resp_client.status_code == status.HTTP_403_FORBIDDEN

