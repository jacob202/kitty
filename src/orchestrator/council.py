"""LLM Council — multi-model ranking + Chairman synthesis for COUNCIL_HEAVY queries.

This module implements a multi-model council system where:
1. Multiple models provide answers to queries
2. Models rank each other's responses
3. A chairman synthesizes responses into a coherent answer
4. Confidence scores are calculated based on consensus
5. Agreement/disagreement points are identified
"""

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

OLLAMA_BASE = "http://localhost:11434"

AnswerDict = dict[str, str]
RankedAnswer = dict[str, Any]  # Contains model, answer, score, role


def _ollama_chat(model: str, prompt: str, timeout: int = 60) -> str:
    """Send a prompt to Ollama and get the response."""
    try:
        r = requests.post(
            f"{OLLAMA_BASE}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=timeout,
        )
        return r.json().get("response", "")
    except Exception as e:
        logger.error(f"Ollama {model} error: {e}")
        return ""


class Council:
    """
    Multi-model council for synthesizing responses from multiple AI models.

    The council process:
    1. Collect answers from all configured models
    2. Have models rank each other's answers
    3. Identify points of agreement and disagreement
    4. Synthesize into a coherent response with confidence scoring
    5. Cite which models contributed to each insight
    """

    def __init__(
        self,
        models: list[str] | None = None,
        chairman_model: str = "dolphin-llama3",
        expert_panel_mode: bool = False,
    ):
        self.models = models if models is not None else ["llama3.2:3b", "dolphin-llama3"]
        self.chairman = chairman_model
        self.expert_panel_mode = expert_panel_mode
        self.expert_roles = {}

    def set_expert_roles(self, roles: dict[str, dict[str, str]]):
        """
        Configure expert roles for expert panel mode.

        Args:
            roles: Dict mapping model names to role definitions
                   e.g., {"llama3.2:3b": {"role": "electronics_expert", "prompt": "You are..."}}
        """
        self.expert_roles = roles

    def _get_answers(self, query: str) -> list[AnswerDict]:
        """Query all models and collect their answers."""
        answers = []
        for model in self.models:
            # Add expert role context if in expert panel mode
            prompt = query
            if self.expert_panel_mode and model in self.expert_roles:
                role_info = self.expert_roles[model]
                role_name = role_info.get("role", "expert")
                prompt = f"[{role_name.upper()} PERSPECTIVE]\n\n{query}"

            resp = _ollama_chat(model, prompt)
            if resp:
                answers.append(
                    {
                        "model": model,
                        "answer": resp,
                        "role": self.expert_roles.get(model, {}).get("role", "general"),
                    }
                )
        return answers

    def _rank(self, answers: list[AnswerDict], query: str) -> list[RankedAnswer]:
        """Each model anonymously ranks the other answers."""
        ranked = []
        for i, ans in enumerate(answers):
            others = [a["answer"] for j, a in enumerate(answers) if j != i]
            if not others:
                ranked.append({**ans, "score": 1.0})
                continue
            prompt = (
                f"Rate this answer to '{query}' on accuracy/completeness (0-10):\n\n"
                f"{others[0]}\n\nRespond with only a number 0-10."
            )
            score_str = _ollama_chat(self.models[i % len(self.models)], prompt, timeout=30)
            try:
                score = float(score_str.strip().split()[0])
            except (ValueError, IndexError):
                score = 5.0
            ranked.append({**ans, "score": score})
        return sorted(ranked, key=lambda x: x["score"], reverse=True)

    def _identify_agreement_disagreement(self, answers: list[RankedAnswer]) -> dict[str, list[str]]:
        """
        Identify points of agreement and disagreement between model answers.

        Returns:
            Dict with 'agreements' and 'disagreements' keys containing lists of points
        """
        if len(answers) < 2:
            return {"agreements": [], "disagreements": []}

        # Create prompt for finding agreement/disagreement
        answers_text = "\n\n".join(f"[{a['model']}]: {a['answer']}" for a in answers)

        prompt = f"""Analyze these model responses and identify:
1. KEY POINTS OF AGREEMENT - facts or conclusions all models agree on
2. KEY POINTS OF DISAGREEMENT - facts or conclusions where models differ

Format your response as:
AGREEMENTS:
- [point 1]
- [point 2]
etc.

DISAGREEMENTS:
- [point 1]
- [point 2]
etc.

If there are no agreements or disagreements, write "None" under that heading.

RESPONSES:
{answers_text[:4000]}
"""
        try:
            result = _ollama_chat(self.chairman, prompt, timeout=60)

            # Parse the result
            agreements = []
            disagreements = []
            current_section = None

            for line in result.split("\n"):
                line = line.strip()
                if "AGREEMENT" in line.upper():
                    current_section = "agreements"
                elif "DISAGREEMENT" in line.upper():
                    current_section = "disagreements"
                elif line.startswith("-") or line.startswith("•"):
                    point = line.lstrip("-• ").strip()
                    if point.lower() != "none" and point:
                        if current_section == "agreements":
                            agreements.append(point)
                        elif current_section == "disagreements":
                            disagreements.append(point)

            return {
                "agreements": agreements[:5],  # Limit to top 5
                "disagreements": disagreements[:5],
            }
        except Exception as e:
            logger.warning(f"Failed to identify agreement/disagreement: {e}")
            return {"agreements": [], "disagreements": []}

    def _calculate_confidence(self, answers: list[AnswerDict], ranked: list[RankedAnswer]) -> float:
        """
        Calculate confidence score based on consensus level.

        Returns:
            Confidence score from 0.0 to 1.0
        """
        if not answers:
            return 0.0

        if len(answers) == 1:
            return 0.7  # Single model has moderate confidence

        # Calculate agreement score
        avg_score = sum(a["score"] for a in ranked) / len(ranked)
        max(a["score"] for a in ranked) if ranked else 1.0

        # Check for consensus (high agreement between scores)
        score_variance = sum((a["score"] - avg_score) ** 2 for a in ranked) / len(ranked)
        consensus_factor = 1.0 - min(score_variance / 25, 1.0)  # Normalize variance

        # Higher confidence when:
        # - Average scores are high
        # - Score variance is low (models agree)
        # - Multiple models provided answers
        base_confidence = avg_score / 10.0
        confidence = base_confidence * 0.4 + consensus_factor * 0.4 + 0.2

        return min(max(confidence, 0.0), 1.0)

    def _synthesize(self, query: str, ranked: list[RankedAnswer]) -> dict[str, Any]:
        """
        Synthesize responses into a coherent answer with confidence scoring.

        Returns:
            Dict containing:
            - synthesis: The synthesized response
            - confidence: Confidence score (0.0-1.0)
            - agreements: Points of agreement
            - disagreements: Points of disagreement
            - contributors: Which models contributed to each part
        """
        top = ranked[:3]  # Use top 3 for synthesis
        answers = ranked

        # Identify agreement/disagreement
        analysis = self._identify_agreement_disagreement(answers)

        # Calculate confidence
        confidence = self._calculate_confidence(answers, ranked)

        # Build synthesis prompt
        context_parts = []
        for i, a in enumerate(top):
            model_name = a.get("role", a["model"])
            context_parts.append(f"[{model_name} (score: {a['score']:.1f})]:\n{a['answer']}")
        context = "\n\n".join(context_parts)

        # Build synthesis with citations
        synthesis_prompt = f"""You are the Council Chairman. Synthesize the following expert responses into a single, coherent answer.

Query: {query}

EXPERT RESPONSES:
{context}

INSTRUCTIONS:
1. Create a flowing, natural-language response (not a list)
2. Identify what the experts AGREE on - state these confidently
3. Address DISAGREEMENTS by presenting multiple viewpoints fairly
4. Where experts disagree, note which approach might be better and why
5. Include a brief confidence assessment at the end
6. Do not just concatenate - create a unified synthesis

AGREEMENTS (use these as foundation):
{chr(10).join(f"- {a}" for a in analysis["agreements"]) if analysis["agreements"] else "None identified"}

DISAGREEMENTS (address these):
{chr(10).join(f"- {d}" for d in analysis["disagreements"]) if analysis["disagreements"] else "None identified"}

Write the synthesis now:"""

        synthesis = _ollama_chat(self.chairman, synthesis_prompt, timeout=120)

        # Generate confidence reasoning
        confidence_reasoning = self._generate_confidence_reasoning(
            confidence, len(answers), analysis
        )

        # Build contributor attribution
        contributors = {}
        for a in answers:
            model = a.get("role", a["model"])
            if model not in contributors:
                contributors[model] = {"answers": 0, "avg_score": 0, "contributions": []}
            contributors[model]["answers"] += 1
            contributors[model]["avg_score"] = (
                contributors[model]["avg_score"] * (contributors[model]["answers"] - 1) + a["score"]
            ) / contributors[model]["answers"]

        return {
            "synthesis": synthesis,
            "confidence": confidence,
            "confidence_reasoning": confidence_reasoning,
            "agreements": analysis["agreements"],
            "disagreements": analysis["disagreements"],
            "contributors": contributors,
            "total_models": len(answers),
        }

    def _generate_confidence_reasoning(
        self, confidence: float, num_models: int, analysis: dict
    ) -> str:
        """Generate natural language explanation of confidence score."""
        parts = []

        if confidence >= 0.8:
            parts.append("high consensus among experts")
        elif confidence >= 0.6:
            parts.append("moderate consensus among experts")
        else:
            parts.append("significant disagreement or uncertainty")

        if num_models == 1:
            parts.append("only one model provided an answer")
        elif num_models == 2:
            parts.append("two models participated")
        else:
            parts.append(f"{num_models} models participated")

        if len(analysis["agreements"]) > 2:
            parts.append("multiple points of agreement identified")
        elif len(analysis["disagreements"]) > 2:
            parts.append("several points of disagreement noted")

        return f"Confidence is {confidence:.0%} based on {' and '.join(parts)}."

    def run(self, query: str, include_analysis: bool = False) -> str | dict[str, Any]:
        """
        Run the full council process: get answers, rank, synthesize.

        Args:
            query: The question to ask the council
            include_analysis: If True, return detailed analysis dict; if False, return just synthesis string

        Returns:
            Either synthesis string or full analysis dict depending on include_analysis
        """
        answers = self._get_answers(query)
        if not answers:
            return "Council unavailable — all models offline."

        if len(answers) == 1:
            result = answers[0]["answer"]
            if include_analysis:
                return {
                    "synthesis": result,
                    "confidence": 0.7,
                    "confidence_reasoning": "Single model response with moderate confidence.",
                    "agreements": [],
                    "disagreements": [],
                    "contributors": {
                        answers[0].get("role", answers[0]["model"]): {
                            "answers": 1,
                            "avg_score": 1.0,
                        }
                    },
                    "total_models": 1,
                }
            return result

        ranked = self._rank(answers, query)
        synthesis_result = self._synthesize(query, ranked)

        if include_analysis:
            return synthesis_result

        # Format as natural response with confidence
        confidence_pct = int(synthesis_result["confidence"] * 100)
        response = synthesis_result["synthesis"]

        # Add confidence note
        response += f"\n\n*[Council confidence: {confidence_pct}% based on {synthesis_result['total_models']} experts]*"

        # Add brief disagreement note if significant
        if synthesis_result["disagreements"] and synthesis_result["confidence"] < 0.7:
            response += "\n\n*Note: Experts disagreed on some points; the synthesis presents multiple viewpoints.*"

        return response

    def run_debate(self, query: str, rounds: int = 2) -> dict[str, Any]:
        """
        Run a multi-round debate where models challenge each other.

        Args:
            query: The debate topic
            rounds: Number of debate rounds (default 2)

        Returns:
            Dict with debate history and final synthesis
        """
        debate_history = []
        current_answers = self._get_answers(query)

        for round_num in range(rounds):
            # Rank current answers
            ranked = self._rank(current_answers, query)

            # Store round results
            debate_history.append(
                {
                    "round": round_num + 1,
                    "answers": ranked,
                }
            )

            # Generate challenges for next round
            if round_num < rounds - 1:
                challenges = []
                for ans in ranked:
                    challenge_prompt = f"""Critique this answer to: {query}

ANSWER:
{ans["answer"]}

Identify the 2-3 weakest points or potential inaccuracies. Be specific and constructive.
Respond concisely."""

                    challenge = _ollama_chat(ans["model"], challenge_prompt, timeout=45)
                    challenges.append(
                        {
                            "model": ans["model"],
                            "challenge": challenge,
                        }
                    )

                # Models respond to challenges
                updated_answers = []
                for ans in current_answers:
                    # Find challenges to this model
                    relevant_challenges = [
                        c["challenge"] for c in challenges if c["model"] != ans["model"]
                    ]

                    if relevant_challenges:
                        defense_prompt = f"""Original question: {query}

Your answer:
{ans["answer"]}

Critiques from other experts:
{chr(10).join(f"- {c}" for c in relevant_challenges)}

Address these critiques. Defend your answer where valid, acknowledge weaknesses,
and revise your answer if the critiques are valid. Be concise."""

                        response = _ollama_chat(ans["model"], defense_prompt, timeout=60)
                        updated_answers.append(
                            {
                                **ans,
                                "answer": response,
                                "responded_to_challenges": True,
                            }
                        )
                    else:
                        updated_answers.append(ans)

                current_answers = updated_answers

        # Final synthesis from debate
        final_ranked = self._rank(current_answers, query)
        synthesis = self._synthesize(query, final_ranked)

        return {
            "debate_history": debate_history,
            "final_answers": final_ranked,
            **synthesis,
        }
