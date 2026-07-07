"""Pagination utilities.

These helpers standardize pagination across the API. They can be used
both in route dependencies to expose ``page`` and ``page_size`` query
parameters and inside services to calculate offsets and totals.
"""

from typing import Any, Dict, Tuple

from fastapi import Query


def pagination_params(
    page: int = Query(1, ge=1, description="Page number (1‑indexed)"),
    page_size: int = Query(25, ge=1, le=100, description="Number of items per page"),
) -> Dict[str, int]:
    """Dependency returning pagination parameters as a dictionary.

    ``page`` and ``page_size`` are exposed as query parameters on list
    endpoints. The default page size is 25 and the maximum is 100.
    """
    return {"page": page, "page_size": page_size}


def paginate_query(query, page: int, page_size: int) -> Tuple[list[Any], Dict[str, int]]:
    """Paginate a SQLAlchemy query.

    :param query: An instance of ``sqlalchemy.orm.Query``.
    :param page: The 1‑indexed page number.
    :param page_size: The number of items per page.
    :return: A tuple ``(items, meta)`` where ``items`` is a list of
        results and ``meta`` is a dictionary containing ``page``,
        ``page_size`` and ``total``.
    """
    offset = (page - 1) * page_size
    total = query.count()
    items = query.offset(offset).limit(page_size).all()
    meta = {"page": page, "page_size": page_size, "total": total}
    return items, meta