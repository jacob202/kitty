from scripts import pr_review


def test_normalize_review_verdict_accepts_nonfinding_note_before_sentinel() -> None:
    verdict = (
        "The estimate and execution provider can differ if availability changes; "
        "this is inherent to the two-phase design and is omitted as a hard finding.\n\n"
        f"{pr_review.NO_FINDINGS}"
    )

    assert pr_review.normalize_review_verdict(verdict) == pr_review.NO_FINDINGS


def test_normalize_review_verdict_blocks_structured_finding_plus_sentinel() -> None:
    verdict = (
        "- File: gateway/example.py\n"
        "  Failure Mode: exact bad state is reported as success\n"
        "  Corrective Action: return the durable state instead\n\n"
        f"{pr_review.NO_FINDINGS}"
    )

    assert pr_review.normalize_review_verdict(verdict) == verdict


def test_normalize_review_verdict_leaves_actionable_verdict_without_sentinel_unchanged() -> None:
    verdict = (
        "- File: gateway/example.py\n"
        "  Failure Mode: exact bad state is reported as success\n"
        "  Corrective Action: return the durable state instead"
    )

    assert pr_review.normalize_review_verdict(verdict) == verdict
