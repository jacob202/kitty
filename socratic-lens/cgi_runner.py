"""
Context Grammar Induction (CGI) - Chain Runner
===============================================
Dynamically discovers what "context" and "transformation" mean
in any given dataset, then scans for transformative questions.

Core Principle:
  The right question transforms context.
  But what "context" means must be discovered, not assumed.
"""

import yaml
import json
import random
from pathlib import Path
from typing import Any
from string import Template


# =============================================================================
# CONFIGURATION
# =============================================================================

CHAINS_DIR = Path("chains")
CHAIN_ORDER = [
    "CGI-1-GRAMMAR",
    "CGI-2-POSITIVE", 
    "CGI-3-NEGATIVE",
    "CGI-4-LENS",
    "CGI-5-SCAN",
    "CGI-6-SOCRATIC"
]


# =============================================================================
# CHAIN LOADER
# =============================================================================

def load_chain(chain_id: str) -> dict:
    """Load a chain definition from YAML."""
    path = CHAINS_DIR / f"{chain_id}.yaml"
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_all_chains() -> dict[str, dict]:
    """Load all chain definitions."""
    return {cid: load_chain(cid) for cid in CHAIN_ORDER}


# =============================================================================
# SAMPLING
# =============================================================================

def stratified_sample(corpus: list[dict], n: int = 15) -> list[dict]:
    """
    Sample conversations from corpus.
    Tries to get diverse samples across the dataset.
    """
    if len(corpus) <= n:
        return corpus
    
    # Simple stratified: divide into chunks, sample from each
    chunk_size = len(corpus) // n
    samples = []
    
    for i in range(n):
        start = i * chunk_size
        end = start + chunk_size if i < n - 1 else len(corpus)
        chunk = corpus[start:end]
        if chunk:
            samples.append(random.choice(chunk))
    
    return samples


def format_samples_for_prompt(samples: list[dict]) -> str:
    """Format samples as readable text for prompt injection."""
    formatted = []
    
    for i, sample in enumerate(samples, 1):
        formatted.append(f"--- Conversation {i} ---")
        
        if isinstance(sample, dict):
            for turn in sample.get("turns", []):
                role = turn.get("role", "?")
                content = turn.get("content", "")
                formatted.append(f"[{role}]: {content}")
        elif isinstance(sample, str):
            formatted.append(sample)
        
        formatted.append("")
    
    return "\n".join(formatted)


# =============================================================================
# PROMPT RENDERING
# =============================================================================

def render_prompt(template: str, variables: dict[str, Any]) -> str:
    """
    Render prompt template with variables.
    Uses {{variable}} syntax.
    """
    result = template
    
    for key, value in variables.items():
        placeholder = "{{" + key + "}}"
        
        # Convert value to string if needed
        if isinstance(value, (dict, list)):
            value_str = json.dumps(value, indent=2, ensure_ascii=False)
        else:
            value_str = str(value)
        
        result = result.replace(placeholder, value_str)
    
    return result


# =============================================================================
# LLM INTERFACE (PLACEHOLDER)
# =============================================================================

def call_llm(prompt: str, output_schema: dict = None) -> dict | str:
    """
    Call LLM with prompt.
    
    Replace this with your actual LLM integration:
    - OpenAI API
    - Anthropic API
    - Local model
    - etc.
    """
    # PLACEHOLDER - Replace with actual implementation
    print("\n" + "="*60)
    print("LLM CALL")
    print("="*60)
    print(prompt[:500] + "..." if len(prompt) > 500 else prompt)
    print("="*60)
    
    # For testing: return empty structure matching schema
    if output_schema:
        return {"_placeholder": True, "schema": output_schema}
    return {"_placeholder": True}


# =============================================================================
# CHAIN EXECUTOR
# =============================================================================

class CGIRunner:
    """
    Runs the Context Grammar Induction chain.
    """
    
    def __init__(self, llm_fn=None):
        self.chains = load_all_chains()
        self.llm = llm_fn or call_llm
        self.results = {}
    
    def run(self, corpus: list[dict], sample_size: int = 15) -> dict:
        """
        Run full CGI chain on corpus.
        
        Returns:
            {
                "lens": {...},
                "candidates": [...],
                "reflection": "...",
                "all_outputs": {...}
            }
        """
        # Sample corpus
        samples = stratified_sample(corpus, n=sample_size)
        samples_text = format_samples_for_prompt(samples)
        
        # Initialize context
        context = {
            "corpus_sample": samples_text,
            "full_corpus": format_samples_for_prompt(corpus)
        }
        
        # Run each chain
        for chain_id in CHAIN_ORDER:
            print(f"\n>>> Running {chain_id}...")
            
            chain = self.chains[chain_id]
            
            # Render prompt with current context
            prompt = render_prompt(chain["prompt"], context)
            
            # Call LLM
            output = self.llm(prompt, chain.get("output_schema"))
            
            # Store result
            self.results[chain_id] = output
            
            # Add to context for next chain
            context[f"{chain_id}.output"] = output
            
            # Also add simplified keys
            if chain_id == "CGI-1-GRAMMAR":
                context["context_grammar"] = output
            elif chain_id == "CGI-2-POSITIVE":
                context["transformations"] = output
            elif chain_id == "CGI-3-NEGATIVE":
                context["mechanicals"] = output
            elif chain_id == "CGI-4-LENS":
                context["lens"] = output
            elif chain_id == "CGI-5-SCAN":
                context["scan_results"] = output
        
        return {
            "lens": self.results.get("CGI-4-LENS"),
            "candidates": self.results.get("CGI-5-SCAN"),
            "reflection": self.results.get("CGI-6-SOCRATIC"),
            "all_outputs": self.results
        }


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Example usage."""
    
    # Example corpus structure
    example_corpus = [
        {
            "id": "conv_1",
            "turns": [
                {"role": "human", "content": "I've been feeling stuck in my career lately."},
                {"role": "assistant", "content": "What does 'stuck' feel like for you?"},
                {"role": "human", "content": "Like I'm going through the motions but not growing."},
                {"role": "assistant", "content": "When did you last feel like you were growing?"},
                {"role": "human", "content": "Maybe three years ago, when I started this job."},
                {"role": "assistant", "content": "What was different then?"},
            ]
        },
        {
            "id": "conv_2", 
            "turns": [
                {"role": "human", "content": "Can you help me write an email?"},
                {"role": "assistant", "content": "Sure, what's the email about?"},
                {"role": "human", "content": "I need to ask my boss for a raise."},
                {"role": "assistant", "content": "What achievements would you highlight?"},
            ]
        },
        # Add more conversations...
    ]
    
    # Run CGI
    runner = CGIRunner()
    results = runner.run(example_corpus)
    
    print("\n" + "="*60)
    print("CGI COMPLETE")
    print("="*60)
    print(json.dumps(results, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()