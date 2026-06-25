"""
title: Kitty Audio Measurement
author: kitty
version: 0.1
type: action
"""

import math
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
                "data": {"description": "Opening audio measurement tools...", "done": False},
            })

        messages = body.get("messages", [])
        query = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                query = msg.get("content", "")
                break

        result = _render_audio_tools(query)

        if __event_emitter__:
            await __event_emitter__({
                "type": "status",
                "data": {"description": "Audio tools ready", "done": True},
            })
            await __event_emitter__({
                "type": "replace",
                "data": {"content": result},
            })

        return body


def _render_audio_tools(query: str) -> str:
    import re

    lines = ["**Audio Measurement Tools**", ""]
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # dB ↔ Voltage conversion
    db_match = re.search(r"(\d+\.?\d*)\s*dB", query)
    if db_match:
        db_val = float(db_match.group(1))
        ratio = 10 ** (db_val / 20)
        lines.append("### dB to Voltage Ratio")
        lines.append(f"  {db_val:+.1f} dB  →  ×{ratio:.4f} (voltage)")
        lines.append(f"  {db_val:+.1f} dB  →  ×{ratio**2:.4f} (power)")
        lines.append("")

    volt_match = re.search(r"(\d+\.?\d*)\s*V", query)
    if volt_match:
        v_val = float(volt_match.group(1))
        db = 20 * math.log10(v_val)
        lines.append("### Voltage to dB")
        lines.append(f"  {v_val} V  →  {db:+.1f} dB")
        lines.append("")

    # Voltage divider
    divider_match = re.search(
        r"(\d+\.?\d*)\s*[kKMG]?\s*Ω.*?(\d+\.?\d*)\s*[kKMG]?\s*Ω",
        query,
    )
    if divider_match:
        r1_str = divider_match.group(1)
        r2_str = divider_match.group(2)
        r1 = _parse_resistor(r1_str)
        r2 = _parse_resistor(r2_str)
        atten = 20 * math.log10(r2 / (r1 + r2))
        lines.append("### Voltage Divider (Attenuation)")
        lines.append(f"  R₁ = {_fmt_resistor(r1)}, R₂ = {_fmt_resistor(r2)}")
        lines.append(f"  Vout/Vin = {r2/(r1+r2):.4f}  ({atten:+.1f} dB)")
        lines.append("")

    # RC filter cutoff
    rc_match = re.search(r"(\d+\.?\d*)\s*[nµup]?F.*?(\d+\.?\d*)\s*[kKMG]?\s*Ω", query)
    if not rc_match:
        rc_match = re.search(r"(\d+\.?\d*)\s*[kKMG]?\s*Ω.*?(\d+\.?\d*)\s*[nµup]?F", query)
    if rc_match:
        cap_str, res_str = rc_match.groups()
        cap = _parse_cap(cap_str)
        res = _parse_resistor(res_str)
        fc = 1 / (2 * math.pi * res * cap)
        lines.append("### RC Filter Cutoff")
        lines.append(f"  R = {_fmt_resistor(res)}, C = {_fmt_cap(cap)}")
        lines.append(f"  f_c = {fc:.1f} Hz")
        lines.append(f"  f_c = {fc/1000:.2f} kHz")
        lines.append("")

    if not any(m in query.lower() for m in ("db", "v ", "volt", "divider", "filter")):
        lines.append("**Quick conversions:**")
        lines.append("")
        lines.append("| dB | Voltage Ratio | Power Ratio |")
        lines.append("|---|---|---|")
        for db_val in (-20, -12, -6, -3, 0, 3, 6, 12, 20):
            vr = 10 ** (db_val / 20)
            pr = 10 ** (db_val / 10)
            lines.append(f"| {db_val:+.0f} dB | ×{vr:.3f} | ×{pr:.3f} |")
        lines.append("")
        lines.append("**Example queries:** `-6 dB`, `0.775 V`, `47k Ω 100 nF`, `10k 5k divider`")
        lines.append("")

    lines.append(f"*{now}*")
    return "\n".join(lines)


def _parse_resistor(s: str) -> float:
    s = s.strip().lower().replace(" ", "")
    if "m" in s and "meg" not in s and "m" in s:
        return float(s.replace("m", "")) / 1000
    if "k" in s:
        return float(s.replace("k", "")) * 1000
    if "meg" in s or "m" in s:
        return float(s.replace("meg", "").replace("m", "")) * 1_000_000
    if "g" in s:
        return float(s.replace("g", "")) * 1_000_000_000
    return float(s)


def _parse_cap(s: str) -> float:
    s = s.strip().lower().replace(" ", "")
    if "nf" in s or "n" in s:
        return float(s.replace("nf", "").replace("n", "")) * 1e-9
    if "µf" in s or "uf" in s or "μf" in s:
        return float(s.replace("µf", "").replace("uf", "").replace("μf", "")) * 1e-6
    if "pf" in s or "p" in s:
        return float(s.replace("pf", "").replace("p", "")) * 1e-12
    return float(s)


def _fmt_resistor(r: float) -> str:
    if r >= 1_000_000:
        return f"{r/1_000_000:.1f} MΩ"
    if r >= 1000:
        return f"{r/1000:.1f} kΩ"
    return f"{r:.1f} Ω"


def _fmt_cap(c: float) -> str:
    if c >= 1e-3:
        return f"{c*1000:.0f} mF"
    if c >= 1e-6:
        return f"{c*1_000_000:.0f} µF"
    if c >= 1e-9:
        return f"{c*1_000_000_000:.0f} nF"
    return f"{c*1_000_000_000_000:.0f} pF"
