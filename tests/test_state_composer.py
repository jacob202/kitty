def test_state_composer_imports():
    from gateway import state_composer

    assert state_composer.SCHEMA_VERSION == 1
