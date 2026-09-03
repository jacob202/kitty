import warnings

from fastapi import FastAPI

from gateway.app import app
from gateway.routes.register import register_routes


def test_product_routes_are_mounted_on_the_gateway_app():
    paths = set(app.openapi()["paths"])

    assert {
        "/feedback",
        "/settings/personality",
        "/session/context",
        "/usage/summary",
        "/chronicle/tips",
    } <= paths


def test_registered_gateway_openapi_has_no_duplicate_operation_ids() -> None:
    candidate = FastAPI(title="registration-contract")
    register_routes(candidate)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        candidate.openapi()

    duplicates = [
        str(item.message)
        for item in caught
        if "Duplicate Operation ID" in str(item.message)
    ]
    assert duplicates == []
