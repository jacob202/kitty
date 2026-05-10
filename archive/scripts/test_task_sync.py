import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gateway.tasks import sync_next_action

def main():
    test_action = "Diagnose the protection circuit relay on the Sansui board (Page 12 of manual)."
    print(f"Attempting to sync test action: {test_action}")
    
    success = sync_next_action(test_action)
    if success:
        print("Success! Check TASKS.md to verify.")
    else:
        print("Failed to sync task.")

if __name__ == "__main__":
    main()
