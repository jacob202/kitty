import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gateway.reset import generate_reset_prompt

def main():
    print("Generating character-driven Nightly Reset prompt...")
    prompt = generate_reset_prompt()
    
    print("\n--- NIGHTLY RESET PROMPT ---\n")
    print(prompt)
    print("\n----------------------------\n")

if __name__ == "__main__":
    main()
