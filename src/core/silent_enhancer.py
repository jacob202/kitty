"""
Silent Prompt Enhancer - Transforms rambling input into SPEAR-structured prompts.
Runs locally with tiny model or rule-based fallback.
"""

import re


class SilentPromptEnhancer:
    """
    SPEAR Framework:
    S - System/Role
    P - Problem/Context
    E - Expectation/Goal
    A - Audience/Format
    R - Restrictions
    """

    def __init__(self, use_llm: bool = False, ollama_model: str = "phi3:mini"):
        self.use_llm = use_llm
        self.ollama_model = ollama_model
        self.ollama = None
        if use_llm:
            try:
                import ollama

                self.ollama = ollama
            except ImportError:
                print("Warning: ollama not installed. Falling back to rule-based.")
                self.use_llm = False

    def enhance(self, raw_input: str) -> str:
        if self.use_llm and self.ollama:
            return self._llm_enhance(raw_input)
        return self._rule_enhance(raw_input)

    def _rule_enhance(self, raw: str) -> str:
        raw_lower = raw.lower()

        role = "electronics repair assistant"
        if "schematic" in raw_lower or "diagram" in raw_lower:
            role = "schematic analysis expert"
        elif "solder" in raw_lower or "iron" in raw_lower:
            role = "soldering technician"

        problem = raw

        expectation = "provide step-by-step diagnostic instructions"
        if "identify" in raw_lower or "what is" in raw_lower:
            expectation = "identify the component and explain its function"
        elif "fix" in raw_lower or "repair" in raw_lower:
            expectation = "give a clear repair procedure with safety warnings"

        audience = "hobbyist electronics repairer"
        if "beginner" in raw_lower or "new" in raw_lower:
            audience = "complete beginner with no prior experience"
        elif "pro" in raw_lower or "experienced" in raw_lower:
            audience = "experienced technician"

        restrictions = (
            "do not assume tools beyond a multimeter and soldering iron. warn about high voltage."
        )
        if "no voltage" in raw_lower:
            restrictions = "assume the device is unplugged and capacitors discharged."

        enhanced = f"""System/Role: You are an expert {role}.
Problem: {problem}
Expectation: {expectation}
Audience: {audience}
Restrictions: {restrictions}

Provide your response concisely but thoroughly."""

        return enhanced

    def _llm_enhance(self, raw: str) -> str:
        system_prompt = """You are a prompt enhancer. Convert the user's rambling request into a structured SPEAR prompt:
- System/Role: define the AI's persona
- Problem: the user's situation
- Expectation: what output is needed
- Audience: who the answer is for
- Restrictions: what to avoid

Output only the SPEAR prompt, no extra commentary."""

        try:
            response = self.ollama.generate(
                model=self.ollama_model,
                prompt=f"User said: {raw}\n\nSPEAR prompt:",
                system=system_prompt,
            )
            return response["response"].strip()
        except Exception as e:
            print(f"LLM enhancement failed: {e}. Falling back to rule-based.")
            return self._rule_enhance(raw)

    def extract_spear_components(self, enhanced_prompt: str) -> dict[str, str]:
        components = {}
        patterns = {
            "role": r"System/Role:\s*(.*?)(?=\n\w+:|$)",
            "problem": r"Problem:\s*(.*?)(?=\n\w+:|$)",
            "expectation": r"Expectation:\s*(.*?)(?=\n\w+:|$)",
            "audience": r"Audience:\s*(.*?)(?=\n\w+:|$)",
            "restrictions": r"Restrictions:\s*(.*?)(?=\n\w+:|$)",
        }
        for key, pattern in patterns.items():
            match = re.search(pattern, enhanced_prompt, re.DOTALL | re.IGNORECASE)
            if match:
                components[key] = match.group(1).strip()
        return components


__all__ = ["SilentPromptEnhancer"]
