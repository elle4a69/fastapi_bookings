import pytest
from fastapi import status

def test_gate1_baseline_regression(client):
    """Gate 1 Baseline Regression Test."""
    response = client.get("/api/public/bootstrap")
    assert response.status_code in (status.HTTP_200_OK, status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN, status.HTTP_400_BAD_REQUEST)

def test_gate3_baseline_regression(client):
    """Gate 3 Baseline Regression Test."""
    response = client.get("/api/public/services")
    assert response.status_code in (status.HTTP_200_OK, status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN, status.HTTP_400_BAD_REQUEST)
