"""Domain router edge case tests — especially mixed health+code signals."""
from gateway.domain_router import classify_domain, get_specialist


def test_blood_test_routes_to_health_not_code():
    """'blood test' has health keywords (blood, test) and code keyword (test).
    Health wins because it scores higher overall."""
    assert classify_domain("I got my blood test results back") == "health"


def test_pain_with_code_context_routes_to_health():
    """'pain in Python script' — health keyword 'pain' has 3x multiplier (score=3),
    code gets 'Python' + 'script' (score=2). Health wins."""
    result = classify_domain("I'm having pain in my Python script")
    assert result == "health"


def test_pure_health_query():
    assert classify_domain("I have a headache and fever") == "health"


def test_pure_code_query():
    assert classify_domain("Debug this Python function") == "code"


def test_no_keywords_returns_soul():
    assert classify_domain("hey what's up") == "soul"


def test_strong_health_beats_weak_code():
    """Multiple health keywords vs one code keyword — health wins."""
    assert classify_domain("my pain medication dose makes me tired") == "health"


def test_get_specialist_reads_canonical_registry():
    specialist = get_specialist("repair")

    assert specialist["name"] == "audio_repair"
    assert specialist["collection_id"] == "ac05f7c1-f341-449c-b520-80882fda3a8e"

def test_health_keyword_does_not_match_med_substring_in_medium():
    assert classify_domain("Derive the wave equation in a homogeneous medium") != "health"


def test_ibuprofen_routes_to_health():
    assert classify_domain("Can I take ibuprofen?") == "health"


def test_drug_interaction_question_routes_to_health():
    """"warfarin with ginkgo" carries no symptom or body-part word, so it only
    routes to health via the medication vocabulary."""
    assert classify_domain("Can I take warfarin with ginkgo?") == "health"


def test_ordinary_taking_question_stays_out_of_health():
    """Adding medication vocabulary must not capture ordinary uses of 'take'."""
    assert classify_domain("Can I take my dog with me to the store?") != "health"
