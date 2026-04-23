"""
Kitty Integration Layer
Connects Voice, Memory, and Tools into unified interface
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.memory.kitty_memory_enhanced import KittyMemoryEnhanced
from src.space_kitty.core_orchestrator import CoreOrchestrator
from src.tools.kitty_tools import KittyTools, ToolCallingLoop
from src.voice.kitty_ears import KittyEars
from src.voice.kitty_voice import KittyVoice
from src.voice.voice_session import VoiceSession


class SpaceKitty:
    """
    Main Space Kitty Interface
    Orchestrates voice, memory, and tools
    """

    def __init__(
        self, stt_model: str = "base", voice: str = "lessac", memory_dir: str = "./data/chroma"
    ):
        """Initialize Space Kitty with all components"""
        print("🐱✨ Initializing Space Kitty...")

        # Voice
        self.ears = KittyEars(model_size=stt_model)
        self.voice = KittyVoice(voice=voice)

        # Memory
        self.memory = KittyMemoryEnhanced(persist_dir=memory_dir)

        # Tools
        self.tools = KittyTools()
        self.tool_loop = ToolCallingLoop(tools=self.tools, process_callback=self._process_with_llm)

        # Core Orchestrator for task routing, personality, checkpointing
        self.orchestrator = CoreOrchestrator()

        # Session tracking
        self.session_count = 0

        print("✅ Space Kitty ready!")

    def chat(self, message: str, use_voice: bool = False) -> str:
        """
        Main chat interface.

        Flow: message → orchestrator (DomainRouter → Specialist → LLM + KB)
              → memory → optional voice → response

        Args:
            message: User message
            use_voice: If True, also speak the response

        Returns:
            Kitty's response
        """
        # Orchestrator handles: route → specialist → LLM → journal → honcho → checkpoint
        specialist_response = self.orchestrator.process(message)
        response = specialist_response.content

        # Store in memory
        try:
            self.memory.add_conversation(message, response)
        except Exception:
            pass

        # Speak if requested
        if use_voice and self.voice.is_available():
            self.voice.speak(response)

        return response

    def voice_chat(self):
        """Start voice chat session"""
        if not self.ears.is_available() and not self.voice.is_available():
            print("❌ Voice not available")
            return

        def process_with_memory(text):
            """Process voice input through chat"""
            return self.chat(text, use_voice=False)

        session = VoiceSession(
            stt_model="base", voice="lessac", process_callback=process_with_memory
        )

        session.start(continuous=True)

    def _generate_response(self, message: str, context: str) -> str:
        """Generate response using LLM (placeholder)"""
        # This would integrate with your actual LLM
        # For now, return contextual response
        if context:
            return f"[With memory] I understand you're asking about: {message}"
        else:
            return f"I received: {message}"

    def _process_with_llm(self, prompt: str) -> str:
        """Process through actual LLM (placeholder for integration)"""
        # This connects to your existing LLM infrastructure
        # For now, simple pattern matching
        if "time" in prompt.lower():
            return '<tool_call>{"name": "get_current_time", "arguments": {}}</tool_call>'
        return f"Processing: {prompt[:50]}..."

    def remember_fact(self, fact: str, category: str = "general"):
        """Store a fact about the user"""
        self.memory.add_user_fact(fact, category)
        print(f"💾 Remembered: {fact}")

    def ingest_document(self, file_path: str):
        """Ingest a document into memory"""
        self.memory.ingest_document(file_path)

    def get_stats(self):
        """Get system stats"""
        orch_status = self.orchestrator.get_status()
        return {
            "voice_available": self.ears.is_available() and self.voice.is_available(),
            "memory_stats": self.memory.get_stats(),
            "tools_available": len(self.tools.tools),
            "orchestrator": orch_status,
        }


# CLI Interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Space Kitty")
    parser.add_argument("--voice", action="store_true", help="Start in voice mode")
    parser.add_argument("--chat", action="store_true", help="Start chat mode")
    args = parser.parse_args()

    kitty = SpaceKitty()

    if args.voice:
        kitty.voice_chat()
    elif args.chat:
        print("\n🐱✨ Space Kitty Chat")
        print("Type 'exit' to quit\n")

        while True:
            user_input = input("You: ").strip()
            if user_input.lower() in ["exit", "quit"]:
                break

            response = kitty.chat(user_input)
            print(f"Kitty: {response}\n")
    else:
        print(kitty.get_stats())
