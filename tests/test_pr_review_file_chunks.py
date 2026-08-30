from scripts import pr_review


def test_review_diff_keeps_complete_file_diffs_together(monkeypatch) -> None:
    file_a = "diff --git a/a.py b/a.py\n" + ("+a = 1\n" * 8)
    file_b = "diff --git a/b.py b/b.py\n" + ("+b = 2\n" * 8)
    assert len(file_a) < 100
    assert len(file_b) < 100
    assert len(file_a + file_b) > 100

    seen: list[str] = []
    monkeypatch.setattr(pr_review, "MAX_REVIEW_CHARS", 100)
    monkeypatch.setattr(
        pr_review,
        "_review_chunk",
        lambda chunk: seen.append(chunk) or pr_review.NO_FINDINGS,
    )

    assert pr_review.review_diff(file_a + file_b) == pr_review.NO_FINDINGS
    assert seen == [file_a, file_b]
    assert "".join(seen) == file_a + file_b


def test_review_diff_only_splits_a_file_when_that_file_exceeds_budget(monkeypatch) -> None:
    oversized = "diff --git a/large.py b/large.py\n" + ("+value = 1\n" * 20)
    tail = "diff --git a/tail.py b/tail.py\n+tail = True\n"

    seen: list[str] = []
    monkeypatch.setattr(pr_review, "MAX_REVIEW_CHARS", 80)
    monkeypatch.setattr(
        pr_review,
        "_review_chunk",
        lambda chunk: seen.append(chunk) or pr_review.NO_FINDINGS,
    )

    assert pr_review.review_diff(oversized + tail) == pr_review.NO_FINDINGS
    assert "".join(seen) == oversized + tail
    assert seen[-1] == tail
    assert all(len(chunk) <= 80 for chunk in seen)
