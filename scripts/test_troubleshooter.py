import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from gateway.troubleshooter import initiate_troubleshooting

def main():
    device = "Sansui AU-7900"
    symptom = "Left channel is distorted"
    
    print(f"--- SOCRATIC TROUBLESHOOTER ---")
    print(f"Device: {device}")
    print(f"Symptom: {symptom}\n")
    
    response = initiate_troubleshooting(device, symptom)
    print("Kitty's Response:")
    print(response)
    print("-------------------------------")

if __name__ == "__main__":
    main()
