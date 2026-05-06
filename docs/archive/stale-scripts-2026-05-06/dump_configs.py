import json
import os
import sys

sys.path.insert(0, os.path.abspath('.'))
from src.core.domain_router import DOMAIN_CONFIG, DomainRouter
from src.core.physical_reality_router import HARDWARE_TRIGGER_WORDS

os.makedirs("config", exist_ok=True)

with open("config/hardware_triggers.json", "w") as f:
    json.dump(HARDWARE_TRIGGER_WORDS, f, indent=4)

router = DomainRouter()
domain_patterns = {k.value: v for k, v in router.domain_patterns.items()}

domain_config = {
    "DOMAIN_CONFIG": DOMAIN_CONFIG,
    "domain_patterns": domain_patterns
}

with open("config/domain_config.json", "w") as f:
    json.dump(domain_config, f, indent=4)
