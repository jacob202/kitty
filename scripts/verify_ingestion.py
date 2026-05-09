import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gateway.knowledge import search_knowledge

def verify_latest(source_name: str):
    """
    Search for the source name and print a sample chunk to verify quality.
    """
    print(f"\n--- QUALITY VERIFICATION: {source_name} ---")
    
    # Use search to find chunks from this specific source
    # We search for the source name itself as the query
    results = search_knowledge(source_name, limit=2)
    
    # Filter for exact source match
    source_results = [r for r in results if r["source"] == source_name]
    
    if not source_results:
        print(f"FAILED: Could not find any chunks for source '{source_name}' in the database.")
        return False

    sample = source_results[0]
    print(f"Metadata: Type={sample['doc_type']}, Score={sample['score']:.4f}")
    print(f"Sample Text (First 300 chars):")
    print(f"\"\"\"{sample['text'][:300]}...\"\"\"")
    print("-" * 40 + "\n")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/verify_ingestion.py <source_name>")
        sys.exit(1)
    verify_latest(sys.argv[1])
