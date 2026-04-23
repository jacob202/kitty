#!/usr/bin/env python3
"""
Simulated User Personas for Testing
"""

import random

PERSONAS = [
    {
        "id": "beginner_hobbyist",
        "name": "Beginner Bob",
        "expertise_level": 1,
        "communication_style": "rambling_uncertain",
        "device": "mobile",
        "patience": "low",
        "queries": [
            "um so i have this amp and it makes noise and i dont know what to do?",
            "help me understand what this thing is",
            "is this capacitor thingy important?",
            "im new to this sorry if this is dumb but how do i test a tube",
            "my guitar amp buzzes when i turn it on... is that bad?",
        ],
    },
    {
        "id": "expert_technician",
        "name": "Expert Elena",
        "expertise_level": 9,
        "communication_style": "technical_precise",
        "device": "desktop",
        "patience": "high",
        "queries": [
            "TDA2030 thermal runaway analysis in bridge configuration",
            "Calculate required heatsink thermal resistance for 50W dissipation at 40C ambient",
            "Scope traces show 200kHz ringing on gate drive - suggest snubber values",
            "LM3886 vs TDA7294 THD comparison at 40W 8ohm",
        ],
    },
    {
        "id": "frustrated_stuck",
        "name": "Frustrated Fred",
        "expertise_level": 4,
        "communication_style": "frustrated_vague",
        "device": "tablet",
        "patience": "very_low",
        "queries": [
            "this doesnt work!!!!",
            "ugh why is this so hard",
            "help me before i throw this out the window",
            "ive been trying for hours and nothing works",
        ],
    },
    {
        "id": "mobile_only",
        "name": "Mobile Maria",
        "expertise_level": 3,
        "communication_style": "short_voice_like",
        "device": "mobile",
        "patience": "medium",
        "queries": [
            "quick question about this board i just uploaded",
            "what part is this? [photo]",
            "how do i test this",
            "is this normal?",
        ],
    },
    {
        "id": "visual_learner",
        "name": "Visual Vince",
        "expertise_level": 5,
        "communication_style": "visual_references",
        "device": "desktop",
        "patience": "medium",
        "queries": [
            "can you show me what that looks like?",
            "uploading photo - whats wrong with this circuit",
            "draw me a diagram of how this works",
            "color code the schematic by voltage levels",
        ],
    },
    {
        "id": "student",
        "name": "Student Sam",
        "expertise_level": 2,
        "communication_style": "curious_questions",
        "device": "laptop",
        "patience": "high",
        "queries": [
            "why does the capacitor go there?",
            "explain like I'm 5 how transistors work",
            "whats the difference between AC and DC coupling?",
            "can you recommend resources to learn more about op amps?",
        ],
    },
    {
        "id": "urgent",
        "name": "Urgent Ulrich",
        "expertise_level": 6,
        "communication_style": "urgent_direct",
        "device": "mobile",
        "patience": "none",
        "queries": [
            "EMERGENCY: amp died right before gig tonight",
            "QUICK: which capacitor do I replace???",
            "FASTEST way to test if power supply is dead",
            "help urgent limited time",
        ],
    },
    {
        "id": "budget_hacker",
        "name": "Budget Betty",
        "expertise_level": 7,
        "communication_style": "DIY_resourceful",
        "device": "desktop",
        "patience": "high",
        "queries": [
            "whats the cheapest way to build this?",
            "can I salvage parts from old electronics?",
            "alternative to expensive oscilloscope?",
            "where to buy components cheapest?",
        ],
    },
]


class PersonaEngine:
    """Generates realistic test queries from user personas"""

    def __init__(self):
        self.personas = PERSONAS

    def get_persona(self, persona_id: str) -> dict:
        """Get a specific persona"""
        for p in self.personas:
            if p["id"] == persona_id:
                return p
        return None

    def get_all_queries(self) -> list[dict]:
        """Get all queries from all personas"""
        all_queries = []
        for persona in self.personas:
            for query in persona["queries"]:
                all_queries.append(
                    {
                        "persona_id": persona["id"],
                        "persona_name": persona["name"],
                        "expertise_level": persona["expertise_level"],
                        "communication_style": persona["communication_style"],
                        "device": persona["device"],
                        "query": query,
                    }
                )
        return all_queries

    def get_random_query(self, expertise_range=None) -> dict:
        """Get a random query, optionally filtered by expertise"""
        queries = self.get_all_queries()

        if expertise_range:
            queries = [
                q
                for q in queries
                if expertise_range[0] <= q["expertise_level"] <= expertise_range[1]
            ]

        return random.choice(queries)

    def simulate_conversation(self, persona_id: str, turns: int = 3) -> list[dict]:
        """Simulate a multi-turn conversation"""
        persona = self.get_persona(persona_id)
        if not persona:
            return []

        conversation = []
        for i in range(min(turns, len(persona["queries"]))):
            conversation.append(
                {
                    "turn": i + 1,
                    "persona": persona["name"],
                    "query": persona["queries"][i],
                    "context": f"Simulating {persona['communication_style']} communication style",
                }
            )

        return conversation


if __name__ == "__main__":
    engine = PersonaEngine()

    print("PERSONA ENGINE TEST")
    print("=" * 60)

    print(f"\nTotal personas: {len(PERSONAS)}")
    print(f"Total queries: {len(engine.get_all_queries())}")

    print("\n--- Sample Queries ---")
    for _ in range(5):
        q = engine.get_random_query()
        print(f"\n[{q['persona_name']}] (expertise: {q['expertise_level']})")
        print(f"  Query: {q['query']}")
