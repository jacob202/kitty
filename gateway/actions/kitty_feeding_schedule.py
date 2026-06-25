"""
title: Kitty Feeding Schedule
author: kitty
version: 0.1
type: action
"""

from datetime import datetime


class Action:
    class Valves:
        pass

    class UserValves:
        pass

    def __init__(self):
        pass

    async def action(self, body: dict, __event_emitter__=None, __user__=None) -> dict:
        if __event_emitter__:
            await __event_emitter__({
                "type": "status",
                "data": {"description": "Calculating feeding schedule...", "done": False},
            })

        messages = body.get("messages", [])
        query = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                query = msg.get("content", "")
                break

        weights = _parse_weights(query)
        if not weights:
            result = (
                "**Feeding Schedule Calculator**\n\n"
                "Tell me each animal's current weight and species (dog/cat/other), "
                "e.g.: 'Dog 65 lbs, Cat 10 lbs'\n\n"
                "**Metabolic scaling formula:**\n"
                "`Resting Energy (kcal/day) = 70 × (weight_kg^0.75)`\n"
                "For dogs: RER × 1.6 (maintenance)\n"
                "For cats: RER × 1.4 (maintenance)"
            )
        else:
            lines = ["**Feeding Schedule**", ""]
            for name, species, weight_lb, weight_kg in weights:
                rer = 70 * (weight_kg ** 0.75)
                if species == "cat":
                    mer = rer * 1.4
                    factor = 1.4
                else:
                    mer = rer * 1.6
                    factor = 1.6
                lines.append(f"### {name}")
                lines.append(f"- Species: {species}")
                lines.append(f"- Weight: {weight_lb} lb ({weight_kg:.1f} kg)")
                lines.append(f"- RER: {rer:.0f} kcal/day")
                lines.append(f"- Maintenance ({factor:.1f}x): {mer:.0f} kcal/day")
                lines.append(f"- Per meal (2x/day): {mer/2:.0f} kcal")
                lines.append("")
            lines.append(f"*Calculated {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
            result = "\n".join(lines)

        if __event_emitter__:
            await __event_emitter__({
                "type": "status",
                "data": {"description": "Feeding schedule ready", "done": True},
            })
            await __event_emitter__({
                "type": "replace",
                "data": {"content": result},
            })

        return body


def _parse_weights(text: str) -> list[tuple[str, str, float, float]]:
    import re

    results = []
    pattern = r"(?P<name>\w+)\s+(?:(?P<species>dog|cat|puppy|kitten)\s+)?(?P<weight>[\d.]+)\s*(?:lb|lbs|kg|kgs)?"
    for match in re.finditer(pattern, text.lower()):
        name = match.group("name").capitalize()
        species_raw = match.group("species")
        species = "cat" if species_raw in ("cat", "kitten") else "dog"
        weight_val = float(match.group("weight"))
        if text.lower().count("kg") > 0 and "lb" not in text.lower():
            weight_kg = weight_val
            weight_lb = weight_val * 2.205
        else:
            weight_lb = weight_val
            weight_kg = weight_val / 2.205
        results.append((name, species, weight_lb, weight_kg))
    return results
