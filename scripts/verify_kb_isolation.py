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
    print("\n=== Specialist KB Isolation Verification ===\n")
    
    # 1. Ingest sample documents
    print("Step 1: Ingesting sample documents...")
    audio_results = ingest_domain_documents(watch_dir="data/staging/audio", domain="audio")
    code_results = ingest_domain_documents(watch_dir="data/staging/code", domain="code")
    
    print(f"   Audio ingestion: {audio_results}")
    print(f"   Code ingestion: {code_results}")

    # 2. Test Retrieval via Registry
    registry = SpecialistRegistry()
    alex = registry.get_specialist("Alex") # Audio
    devin = registry.get_specialist("Devin") # Code

    print("\nStep 2: Testing Alex (Audio Specialist) retrieval...")
    q1 = "What are the common service issues for the Sansui AU-7900?"
    resp1 = alex.query(q1)
    
    print(f"   Query: {q1}")
    has_sansui = "bias corrosion" in resp1.content.lower() or "potentiometers" in resp1.content.lower()
    has_kitty = "orchestration layer" in resp1.content.lower()
    
    print(f"   Retrieval Success: {has_sansui}")
    print(f"   Isolation Success (No Kitty info): {not has_kitty}")

    print("\nStep 3: Testing Devin (Code Specialist) retrieval...")
    q2 = "Explain the orchestration layer in Kitty AI."
    resp2 = devin.query(q2)
    
    print(f"   Query: {q2}")
    has_kitty_actual = "orchestrator" in resp2.content.lower() or "specialist" in resp2.content.lower()
    has_sansui_leak = "sansui" in resp2.content.lower()
    
    print(f"   Retrieval Success: {has_kitty_actual}")
    print(f"   Isolation Success (No Sansui info): {not has_sansui_leak}")

    # 4. Check Inventory
    inventory_path = Path("data/knowledge_bases/INVENTORY.md")
    print(f"\nStep 4: Checking inventory at {inventory_path}...")
    if inventory_path.exists():
        print("   Inventory exists ✅")
        # print(inventory_path.read_text())
    else:
        print("   Inventory missing ❌")

    if has_sansui and not has_kitty and has_kitty_actual and not has_sansui_leak:
        print("\n✅ VERIFICATION PASSED: Specialist KB Training is active and isolated.")
    else:
        print("\n❌ VERIFICATION FAILED: Check logs for details.")

if __name__ == "__main__":
    verify_isolation()
