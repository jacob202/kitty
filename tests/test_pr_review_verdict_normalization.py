from scripts import pr_review, pr_review_gate


HEAD = "a" * 40


def _comment(review: str) -> dict:
    return {
        "user": {"login": pr_review_gate.AGENT_ACTOR},
        "body": (
            f"{pr_review.COMMENT_MARKER}\n## Agent PR Review\n\n"
            f"{review}\n\n_Reviewed commit `{HEAD}`._"
        ),
    }


def test_gate_accepts_nonfinding_note_before_sentinel() -> None:
    review = (
        "The estimate and execution provider can differ if availability changes; "
        "this is inherent to the two-phase design and is omitted as a hard finding.\n\n"
        f"{pr_review.NO_FINDINGS}"
    )

    assert pr_review_gate.agent_review_approved(_comment(review), HEAD)
    assert not pr_review_gate.agent_review_blocked(_comment(review), HEAD)


def test_gate_blocks_structured_finding_plus_sentinel() -> None:
    review = (
        "- File: gateway/example.py\n"
        "  Failure Mode: exact bad state is reported as success\n"
        "  Corrective Action: return the durable state instead\n\n"
        f"{pr_review.NO_FINDINGS}"
    )

    assert not pr_review_gate.agent_review_approved(_comment(review), HEAD)
    assert pr_review_gate.agent_review_blocked(_comment(review), HEAD)


def test_gate_blocks_actionable_verdict_without_sentinel() -> None:
    review = (
        "- File: gateway/example.py\n"
        "  Failure Mode: exact bad state is reported as success\n"
        "  Corrective Action: return the durable state instead"
    )

    assert not pr_review_gate.agent_review_approved(_comment(review), HEAD)
    assert pr_review_gate.agent_review_blocked(_comment(review), HEAD)
