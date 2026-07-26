from gateway.app import app


def test_product_routes_are_mounted_on_the_gateway_app():
    paths = set(app.openapi()["paths"])

    assert {
        "/feedback",
        "/settings/personality",
        "/session/context",
        "/usage/summary",
    } <= paths
