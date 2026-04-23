#!/usr/bin/env python3
"""
Visual Diagram Generator - Creates ASCII diagrams and visual aids for repairs
"""


class VisualDiagramGenerator:
    """Generates visual diagrams for electronics repair"""

    def __init__(self):
        self.diagrams = {}
        self._init_common_diagrams()

    def _init_common_diagrams(self):
        """Initialize common repair diagrams"""

        self.diagrams["capacitor_check"] = """
    🔍 HOW TO CHECK FILTER CAPACITORS

    STEP 1: FIND THE CAPACITORS
    ┌─────────────────────────────────┐
    │     [  BIG CAN-SHAPED  ]       │ ← These are filter caps
    │     [   COMPONENTS    ]       │    Usually near power transformer
    │     [                 ]       │
    └─────────────────────────────────┘

    STEP 2: VISUAL INSPECTION
    GOOD CAP:        BAD CAP:
    ┌───────┐       ┌───────┐
    │ FLAT  │       │BULGING│ ← Rounded top = BAD
    │  TOP  │       │  TOP  │
    └───────┘       └───────┘

    STEP 3: TEST WITH MULTIMETER
    ┌─────────────┐
    │  MULTIMETER │
    │    ┌───┐    │
    │    │ Ω │    │ ← Set to OHMS (Ω)
    │    └───┘    │
    └──────┬──────┘
           │
    ┌──────┴──────┐
    │  RED PROBE  │──┬──→ Touch capacitor + terminal
    │ BLACK PROBE │──┴──→ Touch capacitor - terminal
    └─────────────┘

    READING:
    • Shows 0Ω = SHORTED (BAD)
    • Shows OL/∞ = OPEN (MAYBE OK, check capacitance)
    • Shows some resistance then climbs = GOOD

    💡 TIP: Discharge capacitor with screwdriver first!
        """

        self.diagrams["tube_test"] = """
    🔍 HOW TO TEST TUBES (12AX7, EL84, etc.)

    METHOD 1: TAP TEST (EASIEST)
    ┌───────────────────┐
    │   POWER OFF!      │
    │  ┌─────────────┐  │
    │  │    TUBE     │  │ ← GENTLY tap with pencil
    │  │   ┌───┐     │  │    while amp is on
    │  │   │GLASS│    │  │
    │  │   └───┘     │  │
    │  └─────────────┘  │
    └───────────────────┘

    LISTEN FOR:
    ✓ THUMP in speaker = Tube is OK
    ✗ RINGING/RATTling = Tube is MICROPHONIC (replace)

    ─────────────────────────────────────

    METHOD 2: SUBSTITUTION (BEST)

    1. Buy ONE new tube of same type
    2. Replace old tube with new one
    3. Does problem go away? → Old tube was bad
    4. Keep new tube as spare

    💡 TIP: Swap tubes one at a time to find the bad one!
        """

        self.diagrams["safety_discharge"] = """
    ⚠️  CRITICAL: DISCHARGE CAPACITORS BEFORE TOUCHING!

    WHY? Capacitors store 400-500 VOLTS even when unplugged!

    METHOD 1: DISCHARGE TOOL (SAFEST)

    MAKE ONE:
    ┌─────────────────────────────────┐
    │   Wire + 10kΩ resistor + clips  │
    │                                 │
    │   RED CLIP ──┬──[10kΩ]──┬── BLACK CLIP
    │              │          │
    │         (insulated)  (insulated)
    └─────────────────────────────────┘

    USE IT:
    1. RED clip → Capacitor + terminal (usually marked)
    2. BLACK clip → Capacitor - terminal (ground)
    3. Hold for 10 seconds
    4. Check voltage with multimeter (should be 0V)

    ─────────────────────────────────────

    METHOD 2: SCREWDRIVER (COMMON)

    ┌─────────────────────────────────┐
    │  INSULATED SCREWDRIVER          │
    │         │                       │
    │         ▼                       │
    │   ┌─────────┐                   │
    │   │  TIP    │──┬──→ Touch + terminal
    │   │ HANDLE  │  │
    │   │ (GRIP)  │  └──→ Touch - terminal
    │   └─────────┘      (spark is normal)
    └─────────────────────────────────┘

    ⚠️  WARNING:
    • Spark and pop is normal
    • Hold screwdriver by insulated handle
    • One hand behind back (safety)
    • Wear safety glasses
        """

        self.diagrams["power_supply_flow"] = """
    ⚡ POWER SUPPLY SIGNAL FLOW

    WALL OUTLET → TRANSFORMER → RECTIFIER → FILTER CAPS → TUBES

    ┌─────────┐    ┌──────────┐    ┌──────────┐
    │  WALL   │───▶│TRANSFORMER│───▶│ RECTIFIER │
    │ 120VAC  │    │  (BIG)    │    │  (DIODES) │
    └─────────┘    └──────────┘    └─────┬─────┘
                                         │
                                         ▼
    ┌────────────────────────────────────────────────┐
    │           FILTER CAPACITORS                     │
    │  ┌─────┐  ┌─────┐  ┌─────┐                     │
    │  │100µF│  │100µF│  │10µF │  (Smooth DC)       │
    │  │450V │  │450V │  │450V │                     │
    │  └──┬──┘  └──┬──┘  └──┬──┘                     │
    └─────┼────────┼────────┼────────────────────────┘
          │        │        │
          ▼        ▼        ▼
    ┌──────────────────────────────────────┐
    │          TUBE POWER                   │
    │  ┌─────────┐    ┌─────────┐          │
    │  │ 250V DC │───▶│  Preamp │          │
    │  └─────────┘    │  Tubes  │          │
    │                 └─────────┘          │
    │  ┌─────────┐    ┌─────────┐          │
    │  │ 400V DC │───▶│  Power  │          │
    │  └─────────┘    │  Tubes  │          │
    │                 └─────────┘          │
    │  ┌─────────┐                         │
    │  │ 6.3V AC │───▶│ Heaters │          │
    │  └─────────┘    └─────────┘          │
    └──────────────────────────────────────┘

    🔴 COMMON FAILURE POINTS:
    1. Filter caps dry out (most common)
    2. Rectifier tube/diodes fail
    3. Transformer windings open

    💡 TIP: Check voltage at each stage with multimeter!
        """

        self.diagrams["multimeter_basics"] = """
    📊 MULTIMETER BASIC FUNCTIONS

    ┌─────────────────────────────────┐
    │         MULTIMETER              │
    │  ┌─────────────────────────┐   │
    │  │        DISPLAY          │   │
    │  │        12.34            │   │
    │  └─────────────────────────┘   │
    │                                 │
    │  ┌─────┐ ┌─────┐ ┌─────┐      │
    │  │ V⎓  │ │ V∿  │ │  Ω  │      │
    │  │ DC  │ │ AC  │ │OHMS │      │
    │  └──┬──┘ └──┬──┘ └──┬──┘      │
    │     │       │       │         │
    │   VOLTAGE  VOLTAGE RESISTANCE │
    │   (BATTERY) (WALL) (CHECK IF  │
    │             (DANGER) BROKEN)  │
    └─────────────────────────────────┘

    WHEN TO USE EACH:

    DC VOLTAGE (V⎓):
    • Check power supply voltages
    • Check battery levels
    • Tube cathode voltages

    AC VOLTAGE (V∿):
    • Check wall outlet (DANGEROUS!)
    • Transformer secondary voltages
    • Heater voltage

    RESISTANCE (Ω):
    • Check if component is broken
    • Verify resistor values
    • Test continuity (beep mode)

    💡 TIP: Always start with HIGHEST voltage range!
        """

    def get_diagram(self, topic: str) -> str:
        """Get diagram by topic"""
        return self.diagrams.get(
            topic, "Diagram not found. Available: " + ", ".join(self.diagrams.keys())
        )

    def get_all_topics(self) -> list:
        """List all available diagram topics"""
        return list(self.diagrams.keys())

    def generate_custom_diagram(self, component: str, context: str) -> str:
        """Generate a custom diagram for specific component"""

        if "capacitor" in component.lower():
            return self.diagrams["capacitor_check"]
        elif "tube" in component.lower() or "valve" in component.lower():
            return self.diagrams["tube_test"]
        elif "power" in context.lower():
            return self.diagrams["power_supply_flow"]
        elif "safety" in context.lower():
            return self.diagrams["safety_discharge"]
        else:
            return self.diagrams["multimeter_basics"]

    def add_diagram_to_response(self, response: dict, diagram_topic: str) -> dict:
        """Add diagram to response"""
        if "visual_aids" not in response:
            response["visual_aids"] = []

        diagram = self.get_diagram(diagram_topic)
        response["visual_aids"].append({"topic": diagram_topic, "diagram": diagram})

        return response


if __name__ == "__main__":
    generator = VisualDiagramGenerator()

    print("VISUAL DIAGRAM GENERATOR")
    print("=" * 60)
    print(f"\nAvailable diagrams: {len(generator.get_all_topics())}")
    print(f"Topics: {', '.join(generator.get_all_topics())}")

    print("\n" + "=" * 60)
    print("SAMPLE: Capacitor Check Diagram")
    print("=" * 60)
    print(generator.get_diagram("capacitor_check"))
