import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gateway.researcher import deep_dive

def main():
    topic = "Sansui AU-7900 bias adjustment procedure"
    print(f"--- DEEP RESEARCH WRAPPER ---")
    print(f"Topic: {topic}\n")
    
    # We skip ingestion for the test to avoid cluttering the DB
    from gateway.researcher import DeepResearcher
    researcher = DeepResearcher()
    response = researcher.technical_deep_dive(topic, ingest=False)
    
    print("Kitty's Technical Brief:")
    print(response)
    print("-----------------------------")

if __name__ == "__main__":
    main()
