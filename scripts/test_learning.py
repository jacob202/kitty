import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from gateway.learning import generate_micro_lesson

def main():
    topic = "Voltage dividers and bias circuits"
    
    print(f"--- TEXTBOOK LESSON PLANNER ---")
    print(f"Topic: {topic}\n")
    
    response = generate_micro_lesson(topic)
    print("Kitty's Micro-Lesson:")
    print(response)
    print("-------------------------------")

if __name__ == "__main__":
    main()
