import pytest
from app.services.url_service import URLShortener
from app.core.config import settings


@pytest.fixture(scope="module", autouse=True)
def shortener():
    return URLShortener()


def test_encode(shortener):
    assert shortener.encode(1) == "1"
    assert shortener.encode(62) == "10"
    unique_id = 123456789
    encoded_id = shortener.encode(unique_id)
    assert isinstance(encoded_id, str)
    assert encoded_id.lower() == '8M0kX'.lower()


def test_add_url(shortener):
    long_url = "https://example.com"
    short_url = shortener.add_url(long_url)
    assert short_url.startswith(f"{settings.short_base_url.rstrip('/')}/")
    assert shortener.add_url(long_url) == short_url


def test_get_long_url(shortener):
    long_url = "https://example.com"
    short_url = shortener.add_url(long_url)
    assert shortener.get_long_url(short_url) == long_url
    assert shortener.get_long_url(f"{settings.short_base_url.rstrip('/')}/nonexistent") is None


def test_add_urls_concurrently(shortener):
    urls = ["https://example1.com", "https://example2.com"]
    short_urls = shortener.add_urls_concurrently(urls, max_workers=2)
    assert len(short_urls) == len(urls)
    for short_url in short_urls:
        assert short_url.startswith(f"{settings.short_base_url.rstrip('/')}/")
    assert len(set(short_urls)) == len(urls)


def test_encode_negative(shortener):
    with pytest.raises(ValueError):
        shortener.encode(-1)


def test_encode_zero(shortener):
    with pytest.raises(ValueError):
        shortener.encode(0)


def test_add_url_empty_string(shortener):
    with pytest.raises(ValueError):
        shortener.add_url("")


def test_get_long_url_invalid_format(shortener):
    assert shortener.get_long_url("http://invalid.url") is None


def test_add_urls_empty_list(shortener):
    assert shortener.add_urls([]) == []
    assert shortener.add_urls_concurrently([], max_workers=2) == []


def test_add_urls_concurrently_large_number_of_urls(shortener):
    urls = ["https://example.com"] * 10000
    short_urls = shortener.add_urls_concurrently(urls, max_workers=10)
    assert len(short_urls) == len(urls)
    unique_short_urls = set(short_urls)
    assert len(unique_short_urls) == 1


def test_get_long_url_does_not_cache_missing_entries(monkeypatch):
    shortener = URLShortener()
    base_url = settings.short_base_url.rstrip("/")
    short_code = "fixedcode"
    short_url = f"{base_url}/{short_code}"

    monkeypatch.setattr(shortener, "generate_short_code", lambda: short_code)

    assert shortener.get_long_url(short_url) is None

    long_url = "https://example.com/after-cache"
    shortener.add_url(long_url)

    assert shortener.get_long_url(short_url) == long_url
