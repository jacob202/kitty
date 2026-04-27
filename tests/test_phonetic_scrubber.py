from src.voice.phonetic_scrubber import PhoneticScrubber, load_project_entities


def test_phonetic_scrubber_corrects_common_repair_voice_errors():
    result = PhoneticScrubber().scrub("suns you AU-7900 cappacitor replacement")

    assert result["was_modified"] is True
    assert "Sansui" in result["cleaned"]
    assert "capacitor" in result["cleaned"]


def test_load_project_entities_extracts_known_models_and_brands():
    entities = load_project_entities("Working on Sansui AU-7900 with TDA7294 and LM3886")

    assert "Sansui" in entities
    assert "AU-7900" in entities
    assert "TDA7294" in entities
    assert "LM3886" in entities
