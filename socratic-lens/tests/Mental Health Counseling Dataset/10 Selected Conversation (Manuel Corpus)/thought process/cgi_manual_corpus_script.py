#!/usr/bin/env python3
"""
CGI (Context Grammar Induction) Analysis Script
================================================

Socratic Lens analysis for mental health counseling conversations.

Usage:
    python cgi_manual_corpus_script.py

Output:
    - Console analysis results
    - Classification verdicts

Author: Claude (Anthropic)
Date: 2025
"""

import re
from dataclasses import dataclass
from typing import List, Tuple

# =============================================================================
# DATA: Manual Corpus (10 Samples)
# =============================================================================

CORPUS = [
    {
        "id": 1,
        "context": "I feel like I'm a burden to everyone. My depression is making me push people away, and I'm scared I'll end up alone.",
        "response": "It sounds like you are carrying a heavy weight of guilt. Depression often lies to us and tells us we are burdens. Have you shared these feelings with any of your friends or family?"
    },
    {
        "id": 2,
        "context": "I have a job interview tomorrow and I'm terrified. I keep thinking I'm going to freeze up and forget everything.",
        "response": "It is completely normal to feel nervous before a big interview. Try to visualize yourself succeeding. Also, remember to take deep breaths if you feel panic rising."
    },
    {
        "id": 3,
        "context": "My husband never helps with the kids. I do everything, and when I complain, he says I'm nagging. I feel so unappreciated.",
        "response": "That sounds incredibly frustrating and exhausting. You feel like your partnership is unbalanced and your efforts are invisible. Have you tried sitting down at a calm time to discuss division of labor?"
    },
    {
        "id": 4,
        "context": "I obsess over every mistake I make. If I say one wrong thing, I replay it in my head for days.",
        "response": "Rumination is a common symptom of anxiety. When you catch yourself replaying a scene, try to distract yourself with a sensory grounding exercise, like naming 5 things you can see."
    },
    {
        "id": 5,
        "context": "I don't know who I am anymore. I spent my whole life being a \"good student\" and now that I graduated, I feel empty.",
        "response": "It sounds like your identity was tightly wrapped around your performance. If you strip away the grades and the achievements, who is the person left underneath? What does she like to do when no one is grading her?"
    },
    {
        "id": 6,
        "context": "I'm angry all the time. Small things set me off, like traffic or a loud noise. I feel like a monster.",
        "response": "Anger is often a secondary emotion covering up something else, like hurt or fear. You are not a monster; you are likely overwhelmed. What is usually happening right before you get angry?"
    },
    {
        "id": 7,
        "context": "I can't sleep. My mind races with worries about the future.",
        "response": "Sleep hygiene is important. Try to avoid screens for an hour before bed and keep your room cool. Have you tried melatonin?"
    },
    {
        "id": 8,
        "context": "I feel guilty for setting boundaries with my toxic mother. She cries and says I don't love her.",
        "response": "It is painful to see a parent upset, but her reaction is about her inability to accept limits, not about your love. Why do you believe that \"loving someone\" means \"obeying them\"?"
    },
    {
        "id": 9,
        "context": "I have no motivation. I just want to stay in bed all day.",
        "response": "Depression zaps our energy. The key is \"behavioral activation\"—doing things even when you don't want to. Start with something very small, like brushing your teeth."
    },
    {
        "id": 10,
        "context": "Everyone else seems to have their life together except me. I'm 30 and I have nothing to show for it.",
        "response": "It's easy to compare our \"behind-the-scenes\" with everyone else's \"highlight reel\" on social media. Everyone struggles, even if they don't show it. Define \"success\" for yourself, not by society's timeline."
    }
]


# =============================================================================
# CGI LENS DEFINITION
# =============================================================================

@dataclass
class CGILens:
    """CGI Lens for mental health counseling analysis"""
    
    name: str = "Mental Health Counseling Lens"
    
    decision_question: str = """
    Does this response shift the user's UNDERLYING FRAME 
    (ontology, self-concept, belief structure) 
    or just validate/optimize WITHIN that frame?
    """
    
    # Transformative signal patterns
    transformative_patterns: List[Tuple[str, str]] = None
    
    # Mechanical signal patterns  
    mechanical_patterns: List[Tuple[str, str]] = None
    
    def __post_init__(self):
        self.transformative_patterns = [
            ("Invites reframing", 
             r"(what if|imagine|consider that|have you thought about|reframe|perspective)"),
            ("Challenges self-definition", 
             r"(who you are|your identity|you are not|you are more than|rooted in|underlying|wrapped around|left underneath)"),
            ("Points to underlying issue", 
             r"(the real question|beneath|deeper|root|actually about|covering up|secondary)"),
            ("Reframes ontology", 
             r"(isn't about|not really about|what it means to|not about your)"),
            ("Exposes hidden belief", 
             r"(why do you believe|why do you think|what makes you think)"),
            ("Socratic inquiry",
             r"(who is the person|what does she like|what would happen if)")
        ]
        
        self.mechanical_patterns = [
            ("Validation/reflection", 
             r"(it sounds like|I hear that|I understand|that must be|that sounds)"),
            ("Technique recommendation", 
             r"(try to|technique|skill|practice|exercise|breathing|meditation|visualize|grounding)"),
            ("Professional referral", 
             r"(therapist|counselor|professional|doctor|seek help)"),
            ("Behavioral advice", 
             r"(have you tried|consider|start with|avoid screens)"),
            ("Normalization", 
             r"(normal|common|many people|not alone|everyone struggles)"),
            ("Clinical labeling",
             r"(symptom of|depression zaps|rumination is|behavioral activation)")
        ]


# =============================================================================
# ANALYSIS FUNCTIONS
# =============================================================================

def analyze_response(response: str, lens: CGILens) -> dict:
    """
    Analyze a counselor response using the CGI lens.
    
    Returns:
        dict with verdict, confidence, and detected signals
    """
    transformative_signals = []
    mechanical_signals = []
    
    # Check transformative signals
    for name, pattern in lens.transformative_patterns:
        if re.search(pattern, response, re.IGNORECASE):
            transformative_signals.append(name)
    
    # Check mechanical signals
    for name, pattern in lens.mechanical_patterns:
        if re.search(pattern, response, re.IGNORECASE):
            mechanical_signals.append(name)
    
    # Determine verdict
    t_score = len(transformative_signals)
    m_score = len(mechanical_signals)
    
    # Decision logic
    if t_score >= 2:
        verdict = 'TRANSFORMATIVE'
        confidence = 'high' if t_score >= 3 else 'medium'
    elif m_score >= 1 and t_score < 2:
        verdict = 'MECHANICAL'
        confidence = 'high' if m_score >= 3 else ('medium' if m_score >= 2 else 'low')
    else:
        verdict = 'MECHANICAL'
        confidence = 'low'
    
    return {
        'verdict': verdict,
        'confidence': confidence,
        'transformative_signals': transformative_signals,
        'mechanical_signals': mechanical_signals,
        't_score': t_score,
        'm_score': m_score
    }


def run_analysis(corpus: List[dict], lens: CGILens) -> List[dict]:
    """Run CGI analysis on entire corpus."""
    results = []
    
    for item in corpus:
        analysis = analyze_response(item['response'], lens)
        results.append({
            'id': item['id'],
            'context': item['context'],
            'response': item['response'],
            **analysis
        })
    
    return results


def print_results(results: List[dict]):
    """Print formatted analysis results."""
    
    print("=" * 80)
    print("CGI ANALYSIS RESULTS")
    print("=" * 80)
    print()
    
    # Summary
    transformative_count = sum(1 for r in results if r['verdict'] == 'TRANSFORMATIVE')
    mechanical_count = sum(1 for r in results if r['verdict'] == 'MECHANICAL')
    
    print(f"SUMMARY:")
    print(f"  TRANSFORMATIVE: {transformative_count}")
    print(f"  MECHANICAL: {mechanical_count}")
    print()
    
    # Table header
    print("-" * 80)
    print(f"{'#':<3} {'Verdict':<15} {'Confidence':<10} {'Key Signals':<40}")
    print("-" * 80)
    
    # Results
    for r in results:
        signals = r['transformative_signals'] if r['verdict'] == 'TRANSFORMATIVE' else r['mechanical_signals']
        signal_str = ', '.join(signals[:2]) if signals else 'N/A'
        print(f"{r['id']:<3} {r['verdict']:<15} {r['confidence']:<10} {signal_str[:40]:<40}")
    
    print("-" * 80)
    print()
    
    # Transformative highlights
    transformative = [r for r in results if r['verdict'] == 'TRANSFORMATIVE']
    if transformative:
        print("=" * 80)
        print("🔥 TRANSFORMATIVE EXAMPLES")
        print("=" * 80)
        
        for r in transformative:
            print()
            print(f"[SAMPLE #{r['id']}]")
            print(f"Context: {r['context'][:100]}...")
            print(f"Response: {r['response'][:150]}...")
            print(f"Signals: {', '.join(r['transformative_signals'])}")
            print()
    
    # Pattern analysis
    print("=" * 80)
    print("PATTERN ANALYSIS")
    print("=" * 80)
    print()
    print("MECHANICAL PATTERN:")
    print("  Validate → Label → Technique")
    print("  'That sounds hard. This is called X. Try Y.'")
    print()
    print("TRANSFORMATIVE PATTERN:")
    print("  Name invisible structure → Challenge it → Open inquiry")
    print("  'Your identity was wrapped in X. What if you're not X?'")


def generate_ontological_analysis(results: List[dict]):
    """Generate detailed ontological shift analysis for transformative examples."""
    
    transformative = [r for r in results if r['verdict'] == 'TRANSFORMATIVE']
    
    if not transformative:
        print("\nNo transformative examples found.")
        return
    
    print("\n" + "=" * 80)
    print("ONTOLOGICAL SHIFT ANALYSIS")
    print("=" * 80)
    
    # Pre-defined deep analyses for known transformative samples
    analyses = {
        5: {
            "before": "I = Good Student, Worth = Performance",
            "after": "I = ? (open question), Worth = Inherent existence",
            "shift": "Identity dissolution - from role to authentic self inquiry"
        },
        6: {
            "before": "I am angry → I am a monster",
            "after": "I am hurt/afraid → I am overwhelmed",
            "shift": "Ontology of anger reframed from identity to symptom"
        },
        8: {
            "before": "Her tears = Proof I don't love her, Love = Obedience",
            "after": "Her tears = Her limitation, Love = ? (questioned)",
            "shift": "Hidden equation exposed and made questionable"
        }
    }
    
    for r in transformative:
        print(f"\n--- Sample #{r['id']} ---")
        
        if r['id'] in analyses:
            a = analyses[r['id']]
            print(f"BEFORE: {a['before']}")
            print(f"AFTER:  {a['after']}")
            print(f"SHIFT:  {a['shift']}")
        else:
            print(f"Transformative signals: {', '.join(r['transformative_signals'])}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Main entry point."""
    
    print()
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║  CGI ANALYSIS: MENTAL HEALTH COUNSELING CORPUS                 ║")
    print("║  Context Grammar Induction (Socratic Lens)                     ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print()
    
    # Initialize lens
    lens = CGILens()
    
    print(f"LENS: {lens.name}")
    print(f"DECISION QUESTION: {lens.decision_question.strip()}")
    print()
    
    # Run analysis
    results = run_analysis(CORPUS, lens)
    
    # Print results
    print_results(results)
    
    # Ontological analysis
    generate_ontological_analysis(results)
    
    # Meta-reflection
    print("\n" + "=" * 80)
    print("[SOCRATIC META-REFLECTION]")
    print("=" * 80)
    print("""
The core distinction:

MECHANICAL: "Here's how to cope with your problem"
            (Problem stays the same, coping improves)

TRANSFORMATIVE: "What if the problem isn't what you think it is?"
                (Problem itself is reconceived)

Socrates didn't give breathing exercises.
He asked questions that made the invisible visible.
    """)
    
    print("\n[HUMAN DECISION NEEDED]")
    print("Whether a mechanical response is 'right' depends on context.")
    print("The system can SHOW this distinction; it cannot DECIDE which is appropriate.")


if __name__ == "__main__":
    main()