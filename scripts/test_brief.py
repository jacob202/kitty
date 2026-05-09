import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gateway.brief import fetch_news, get_tasks_summary, generate_brief_text

def main():
    print("Gathering news...")
    headlines = fetch_news(limit_per_feed=2)
    
    print("Reading tasks...")
    task_summary = get_tasks_summary()
    
    print("\n--- GENERATED BRIEF ---\n")
    brief = generate_brief_text(headlines, task_summary)
    print(brief)
    print("\n-----------------------\n")

if __name__ == "__main__":
    main()
