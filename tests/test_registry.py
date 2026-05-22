from gateway.registry import get_collection_id, list_specialists


def test_registry_contains_required_specialists():
    specialists = list_specialists()

    assert "electronics" in specialists
    assert "audio_repair" in specialists
    assert "sask_watchdog" in specialists


def test_get_collection_id_returns_known_mapping():
    assert get_collection_id("electronics") == "4dd4a44d-6ec1-4378-8126-06cae382d0c2"


def test_get_collection_id_raises_for_unknown_specialist():
    try:
        get_collection_id("not_real")
    except KeyError as exc:
        assert "not_real" in str(exc)
    else:
        raise AssertionError("Expected KeyError for unknown specialist")
