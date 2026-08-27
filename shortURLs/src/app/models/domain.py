from typing import Optional
from pydantic import BaseModel, HttpUrl, ConfigDict


class URLModel(BaseModel):
    id: Optional[str] = None
    long_url: HttpUrl
    short_url: Optional[str] = None
    short_code: Optional[str] = None
    created_at: Optional[int] = None
    expires_at: Optional[int] = None
    access_count: int = 0
    # user_id: Optional[int] = None

    model_config = ConfigDict(
        json_encoders={
            HttpUrl: lambda v: str(v),
        }
    )
