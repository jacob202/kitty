import sys
import os
from pathlib import Path
import logging

# Ensure project root is on path
_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(_root))

from src.core.specialist_framework import SpecialistRegistry, ingest_domain_documents

logging.basicConfig(level=logging.INFO)

def verify_isolation():
    print("\n=== Specialist KB Isolation Verification (FAST MODE) ===\n")
    
    # Create tiny unique snippets
    audio_snippet = "The Sansui AU-7900 amplifier uses Hitachi TO-3 metal can transistors for its output stage."
    code_snippet = "Kitty AI orchestrator uses a domain-aware LightRAG factory for specialized knowledge retrieval."
    
    # 1. Ingest sample snippets
    print("Step 1: Ingesting tiny sample snippets...")
    
    audio_dir = Path("data/staging/audio_fast")
    code_dir = Path("data/staging/code_fast")
    audio_dir.mkdir(parents=True, exist_ok=True)
    code_dir.mkdir(parents=True, exist_ok=True)
    
    (audio_dir / "audio.md").write_text(audio_snippet)
    (code_dir / "code.md").write_text(code_snippet)
    
    audio_results = ingest_domain_documents(watch_dir="data/staging/audio_fast", domain="audio")
    code_results = ingest_domain_documents(watch_dir="data/staging/code_fast", domain="code")
    
    print(f"   Audio ingestion: {audio_results}")
    print(f"   Code ingestion: {code_results}")

    # 2. Test Retrieval via Registry
    registry = SpecialistRegistry()
    alex = registry.get_specialist("Alex") # Audio
    devin = registry.get_specialist("Devin") # Code

    print("\nStep 2: Testing Alex (Audio Specialist) retrieval...")
    q1 = "What transistors does the AU-7900 use?"
    resp1 = alex.query(q1)
    
    print(f"   Query: {q1}")
    print(f"   Response Content: {resp1.content[:100]}...")
    has_sansui = "hitachi" in resp1.content.lower() or "to-3" in resp1.content.lower()
    has_kitty = "orchestrator" in resp1.content.lower()
    
    print(f"   Retrieval Success: {has_sansui}")
    print(f"   Isolation Success (No Kitty info): {not has_kitty}")

    print("\nStep 3: Testing Devin (Code Specialist) retrieval...")
    q2 = "What does the Kitty AI orchestrator use for knowledge retrieval?"
    resp2 = devin.query(q2)
    
    print(f"   Query: {q2}")
    print(f"   Response Content: {resp2.content[:100]}...")
    has_kitty_actual = "lightrag" in resp2.content.lower() or "factory" in resp2.content.lower()
    has_sansui_leak = "sansui" in resp2.content.lower()
    
    print(f"   Retrieval Success: {has_kitty_actual}")
    print(f"   Isolation Success (No Sansui info): {not has_sansui_leak}")

    # 4. Check Inventory
    inventory_path = Path("data/knowledge_bases/INVENTORY.md")
    print(f"\nStep 4: Checking inventory at {inventory_path}...")
    if inventory_path.exists():
        print("   Inventory exists ✅")
    else:
        print("   Inventory missing ❌")

    if has_sansui and not has_kitty and has_kitty_actual and not has_sansui_leak:
        print("\n✅ VERIFICATION PASSED: Specialist KB Training is active and isolated.")
    else:
        print("\n❌ VERIFICATION FAILED: Check retrieved content and isolation flags.")

if __name__ == "__main__":
    verify_isolation()
