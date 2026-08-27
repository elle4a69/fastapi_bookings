from typing import Literal, Optional
from pydantic import BaseModel, HttpUrl, Field


class URLCreate(BaseModel):
    long_url: HttpUrl


class URLResponse(BaseModel):
    short_url: str
    long_url: HttpUrl
    created_at: Optional[int] = None

    @classmethod
    def from_raw(
        cls, short_url: str, long_url: HttpUrl | str, created_at: Optional[int] = None
    ):
        long_url_str = str(long_url) if isinstance(long_url, HttpUrl) else long_url
        return cls(short_url=short_url, long_url=long_url_str, created_at=created_at)


class URLInDB(URLResponse):
    id: str
    expires_at: Optional[int] = None
    access_count: int = Field(default=0, description="URL被访问的次数。")
    short_code: Optional[str] = None


class URLBatchItemResponse(BaseModel):
    index: int = Field(ge=0)
    long_url: HttpUrl
    status: Literal["success", "failed"]
    short_url: Optional[str] = None
    created_at: Optional[int] = None
    error_code: Optional[str] = None
    retryable: bool = False


class URLBatchResponse(BaseModel):
    results: list[URLBatchItemResponse]
    success_count: int = Field(ge=0)
    failure_count: int = Field(ge=0)
