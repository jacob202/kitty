from gateway.domain_router import classify_domain

def test_blood_test_routes_health_not_code():
    assert classify_domain("I need a blood test") == "health"
    
def test_pain_in_python_script_routes_health():
    # 'pain' (3 points for health), 'python script' (2 points for code: python, script)
    assert classify_domain("I have pain while writing my python script") == "health"
    
def test_medication_routes_health():
    assert classify_domain("medication") == "health"
    
def test_car_noise_routes_repair():
    assert classify_domain("car noise") == "repair"

def test_python_code_routes_code():
    assert classify_domain("python code") == "code"

def test_health_wins_tie():
    # 'repair' (1 point), 'hurt' (1 point for health) -> tie, health wins
    assert classify_domain("repair hurt") == "health"
    
def test_general_routes_default():
    assert classify_domain("hello there") == "soul"
