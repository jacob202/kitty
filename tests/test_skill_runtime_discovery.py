from src.tools.skill_commands import get_skill


def test_iterative_meta_optimization_skill_is_discoverable():
    skill = get_skill("iterative-self-review-meta-optimization")
    assert skill is not None
    assert "ITERATIVE SELF-REVIEW & META-OPTIMIZATION" in skill["content"]

