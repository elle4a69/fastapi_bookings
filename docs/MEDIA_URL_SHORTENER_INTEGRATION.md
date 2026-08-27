# Media & Album URL Shortener Integration Specification

> **Target Audience:** Backend Developers & AI Coding Agents working on the Media & Booking Modules.  
> **Purpose:** Technical specification and drop-in implementation guide for generating dynamic short links for individual media objects (photos, videos, files) and collections (albums, folders, directories).

---

## 1. System Overview & Architecture

The system uses a dedicated **URL Shortener Microservice** (located in `shortURLs/`, running on FastAPI + MongoDB) to produce Base62 short links.

```mermaid
flowchart TD
    subgraph Client ["Client / Frontend"]
        User["User / Admin"]
    end

    subgraph BookingApp ["FastAPI Booking & Media App"]
        MediaSvc["Media & Album Service"]
        DB[(PostgreSQL / App DB)]
    end

    subgraph ShortenerSvc ["URL Shortener Service (Port 8002)"]
        ShortAPI["FastAPI Shortener API"]
        MongoDB[(MongoDB - short_code store)]
    end

    User -->|1. Upload File / Create Album| MediaSvc
    MediaSvc -->|2. Generate Public/Cloud Long URL| MediaSvc
    MediaSvc -->|3. POST /api/v1/shorten/ (or batch)| ShortAPI
    ShortAPI -->|4. Store mapping & return short_url| MongoDB
    ShortAPI -->|5. Return short_url| MediaSvc
    MediaSvc -->|6. Save item + short_url| DB
    MediaSvc -->|7. Return Media/Album with short_url| User
    User -->|8. Copy & Share short_url| Recipient["External User / Visitor"]
    Recipient -->|9. GET short_url| ShortAPI
    ShortAPI -->|10. 307 Redirect to Long URL| Recipient
```

### Key Capabilities Required
1. **Individual Media Items:** Every photo, video, or document uploaded receives its own unique short link (e.g. `https://s.booking.com/aB3x9`).
2. **Albums & Directories:** Every album, gallery, or folder receives its own unique short link that points to the album's public gallery view.
3. **Bulk / Batch Operations:** When an album with multiple files is uploaded or imported, links are generated concurrently using the batch endpoint in a single HTTP request.
4. **Resilience / Graceful Degradation:** If the shortener service is temporarily unavailable, media upload/creation should **not** fail; the system logs a warning, falls back to the long URL, or enqueues a background task to populate the short link.

---

## 2. Service Endpoints & API Contract

The shortener service runs on `http://localhost:8002` (configurable via environment variables).

### 2.1 Single Short URL Creation
* **Endpoint:** `POST /api/v1/shorten/`
* **Request Header:** `Content-Type: application/json`
* **Request Body:**
```json
{
  "long_url": "https://media.booking.com/tenants/t-123/albums/wedding-2026/photo-001.jpg"
}
```
* **Response:** `200 OK`
```json
{
  "long_url": "https://media.booking.com/tenants/t-123/albums/wedding-2026/photo-001.jpg",
  "short_url": "http://short.url/xY7zK1",
  "created_at": 1770599999
}
```

---

### 2.2 Concurrent Batch Short URL Creation (For Albums & Bulk Uploads)
* **Endpoint:** `POST /api/v1/shorten/batch/concurrent/`
* **Request Header:** `Content-Type: application/json`
* **Request Body:**
```json
[
  { "long_url": "https://media.booking.com/tenants/t-123/albums/summer-promo/video-intro.mp4" },
  { "long_url": "https://media.booking.com/tenants/t-123/albums/summer-promo/banner.png" },
  { "long_url": "https://media.booking.com/tenants/t-123/albums/summer-promo/catalog.pdf" }
]
```
* **Response:** `200 OK` (or `207 Multi-Status` if partial failure)
```json
{
  "results": [
    {
      "index": 0,
      "long_url": "https://media.booking.com/tenants/t-123/albums/summer-promo/video-intro.mp4",
      "status": "success",
      "short_url": "http://short.url/9bX8q",
      "created_at": 1770599999,
      "error_code": null,
      "retryable": false
    },
    {
      "index": 1,
      "long_url": "https://media.booking.com/tenants/t-123/albums/summer-promo/banner.png",
      "status": "success",
      "short_url": "http://short.url/2kL1m",
      "created_at": 1770599999,
      "error_code": null,
      "retryable": false
    },
    {
      "index": 2,
      "long_url": "https://media.booking.com/tenants/t-123/albums/summer-promo/catalog.pdf",
      "status": "success",
      "short_url": "http://short.url/3jN9p",
      "created_at": 1770599999,
      "error_code": null,
      "retryable": false
    }
  ],
  "success_count": 3,
  "failure_count": 0
}
```

---

### 2.3 URL Redirection (Resolution)
* **Endpoint:** `GET /api/v1/{short_code}` or `GET /api/v1/{short_url_path}`
* **Response:** `307 Temporary Redirect` to the target `long_url` (also automatically increments access statistics).

---

### 2.4 Delete Short URL (Optional Cleanup on Media Deletion)
* **Endpoint:** `DELETE /api/v1/urls/delete/{short_url_path}`
* **Response:** `200 OK` `{"detail": "URL deleted successfully."}`

---

## 3. Database Schema Changes for Media & Album Models

Agents/Developers should ensure that the media models store the short URL and its code:

### 3.1 Media Asset Model (e.g. `MediaItem` or `MediaObject`)
```python
# In app/models/media.py (SQLAlchemy example)
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, func

class MediaItem(Base):
    __tablename__ = "media_items"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, index=True, nullable=False)
    album_id = Column(Integer, ForeignKey("media_albums.id"), nullable=True, index=True)
    
    file_name = Column(String(255), nullable=False)
    media_type = Column(String(50), nullable=False) # 'image', 'video', 'document'
    long_url = Column(String(2048), nullable=False)  # S3/Cloud/Local storage URL
    
    # URL Shortener fields:
    short_url = Column(String(255), nullable=True)   # e.g., "http://short.url/xY7zK1"
    short_code = Column(String(64), nullable=True, index=True) # e.g., "xY7zK1"
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

### 3.2 Media Album / Directory Model (e.g. `MediaAlbum`)
```python
# In app/models/media.py
class MediaAlbum(Base):
    __tablename__ = "media_albums"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=True)
    
    # Target public view URL (e.g., https://booking.domain.com/gallery/album-uuid)
    long_url = Column(String(2048), nullable=False)
    
    # URL Shortener fields:
    short_url = Column(String(255), nullable=True)
    short_code = Column(String(64), nullable=True, index=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

---

## 4. Drop-in Python Client: `URLShortenerClient`

Create or place this client in `app/services/url_shortener_client.py` inside the booking application:

```python
"""
URL Shortener Async Client for Media & Booking System.
"""
import logging
from typing import List, Optional, Dict, Any
import httpx

logger = logging.getLogger(__name__)

class URLShortenerClient:
    def __init__(self, base_api_url: str = "http://localhost:8002"):
        self.base_api_url = base_api_url.rstrip("/")
        self.timeout = httpx.Timeout(5.0, connect=2.0)

    async def shorten(self, long_url: str) -> Optional[str]:
        """
        Creates a single short URL. Returns the short_url string or None on failure.
        """
        endpoint = f"{self.base_api_url}/api/v1/shorten/"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(endpoint, json={"long_url": str(long_url)})
                resp.raise_for_status()
                data = resp.json()
                return data.get("short_url")
        except Exception as exc:
            logger.warning(
                "url_shortener_single_failed",
                extra={"long_url": long_url, "error": str(exc)}
            )
            return None

    async def shorten_batch(self, long_urls: List[str]) -> List[Optional[str]]:
        """
        Shortens a list of URLs concurrently in a single batch request.
        Returns a list of short_urls matching the index of input URLs (None if item failed).
        """
        if not long_urls:
            return []

        endpoint = f"{self.base_api_url}/api/v1/shorten/batch/concurrent/"
        payload = [{"long_url": str(u)} for u in long_urls]

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(endpoint, json=payload)
                if resp.status_code not in (200, 207):
                    resp.raise_for_status()
                
                data = resp.json()
                results = data.get("results", [])
                
                # Maintain exact positional mapping
                short_urls: List[Optional[str]] = [None] * len(long_urls)
                for item in results:
                    idx = item.get("index")
                    if idx is not None and 0 <= idx < len(short_urls):
                        if item.get("status") == "success":
                            short_urls[idx] = item.get("short_url")
                return short_urls
        except Exception as exc:
            logger.warning(
                "url_shortener_batch_failed",
                extra={"count": len(long_urls), "error": str(exc)}
            )
            return [None] * len(long_urls)

    async def delete(self, short_url_or_code: str) -> bool:
        """
        Deletes a short URL mapping.
        """
        endpoint = f"{self.base_api_url}/api/v1/urls/delete/{short_url_or_code}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.delete(endpoint)
                return resp.status_code == 200
        except Exception as exc:
            logger.warning("url_shortener_delete_failed", extra={"target": short_url_or_code, "error": str(exc)})
            return False
```

---

## 5. Usage Recipes for Media & Album Services

### Recipe A: Generating a Short Link for an Uploaded Media Item
```python
async def handle_media_upload(file, tenant_id: str, album_id: Optional[int] = None):
    # 1. Store the file to S3 / Cloud / Local storage
    long_url = await storage_service.save(file, tenant_id)

    # 2. Dynamically obtain short link
    short_client = URLShortenerClient(settings.URL_SHORTENER_API_URL)
    short_url = await short_client.shorten(long_url)

    # 3. Save to database
    media_item = MediaItem(
        tenant_id=tenant_id,
        album_id=album_id,
        file_name=file.filename,
        media_type=detect_type(file),
        long_url=long_url,
        short_url=short_url,
        short_code=short_url.split("/")[-1] if short_url else None
    )
    db.add(media_item)
    await db.commit()
    await db.refresh(media_item)
    return media_item
```

### Recipe B: Creating an Album with a Short Link
```python
async def create_album(name: str, description: str, tenant_id: str):
    # 1. Build public frontend album view URL
    album_slug = slugify(f"{tenant_id}-{name}")
    album_public_url = f"{settings.FRONTEND_PUBLIC_URL}/albums/{album_slug}"

    # 2. Generate short URL for the album
    short_client = URLShortenerClient(settings.URL_SHORTENER_API_URL)
    short_url = await short_client.shorten(album_public_url)

    # 3. Persist album
    album = MediaAlbum(
        tenant_id=tenant_id,
        name=name,
        description=description,
        long_url=album_public_url,
        short_url=short_url,
        short_code=short_url.split("/")[-1] if short_url else None
    )
    db.add(album)
    await db.commit()
    return album
```

### Recipe C: Batch Uploading Files into an Album
```python
async def batch_upload_to_album(album_id: int, files: list, tenant_id: str):
    # 1. Save all files to storage and collect long URLs
    long_urls = [await storage_service.save(f, tenant_id) for f in files]

    # 2. Request short URLs concurrently in ONE batch request
    short_client = URLShortenerClient(settings.URL_SHORTENER_API_URL)
    short_urls = await short_client.shorten_batch(long_urls)

    # 3. Bulk insert media items
    items = []
    for file, long_url, short_url in zip(files, long_urls, short_urls):
        items.append(MediaItem(
            tenant_id=tenant_id,
            album_id=album_id,
            file_name=file.filename,
            media_type=detect_type(file),
            long_url=long_url,
            short_url=short_url,
            short_code=short_url.split("/")[-1] if short_url else None
        ))
    db.add_all(items)
    await db.commit()
    return items
```

---

## 6. Environment Variables Checklist

Ensure these variables are set in the `.env` file of both services:

### For the Main Booking / Media Application:
```env
# URL Shortener Microservice API endpoint (internal network or localhost)
URL_SHORTENER_API_URL=http://localhost:8002

# Public Domain of Frontend Gallery / Album Views
FRONTEND_PUBLIC_URL=https://booking.example.com
```

### For the URL Shortener Microservice (`shortURLs/src/.env`):
```env
# Public domain used when creating short URLs (returned in short_url field)
SHORT_BASE_URL=https://s.booking.example.com

# Service limits
MAX_BATCH_SIZE=100
BATCH_MAX_CONCURRENCY=10
```

---

## 7. Frontend Integration Note for Copy-to-Clipboard

In the Media Library and Album views, render a **"Copy Link"** action button:
* If `item.short_url` is present, copy `item.short_url` directly to the clipboard.
* If `item.short_url` is null (e.g. legacy item or temporary network error), fallback to copying `item.long_url`.
