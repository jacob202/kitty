import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gateway.brief import fetch_news, get_tasks_summary, generate_brief

def main():
    print("Gathering data and synthesizing brief via LLM...")
    brief_data = generate_brief()
    
    print("\n--- GENERATED BRIEF (SOUL INJECTED) ---\n")
    print(brief_data["intention"])
    print("\n-----------------------\n")
    
    print("Metadata Check:")
    print(f"- Date: {brief_data['date']}")
    print(f"- Headlines found: {len(brief_data['headlines'])}")

if __name__ == "__main__":
    main()
