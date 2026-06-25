

def test_summarize_usage_groups_paid_and_recent_activity():
    from gateway.token_spend_report import summarize_usage

    entries = [
        {
            "date": "2026-05-11",
            "provider": "openrouter",
            "model": "deepseek/deepseek-v4-flash",
            "operation": "knowledge.librarian",
            "usage": {"prompt_tokens": 1800, "completion_tokens": 300, "total_tokens": 2100},
            "metadata": {"route": "openrouter_direct", "from_pool": False},
        },
        {
            "date": "2026-05-13",
            "provider": "openrouter",
            "model": "deepseek/deepseek-r1",
            "operation": "agent.99",
            "usage": {"prompt_tokens": 5000, "completion_tokens": 2000, "total_tokens": 7000},
            "metadata": {"route": "openrouter_direct", "from_pool": False},
        },
        {
            "date": "2026-05-13",
            "provider": "openrouter",
            "model": "qwen/qwen3-coder:free",
            "operation": "chat.completions.create",
            "usage": {},
            "metadata": {"route": "openrouter_direct", "from_pool": True},
        },
    ]

    report = summarize_usage(entries)

    assert report["totals"]["calls"] == 3
    assert report["totals"]["tokens"] == 9100
    assert report["paid"]["calls"] == 2
    assert report["paid"]["tokens"] == 9100
    assert report["estimated_cost"]["usd"] >= 0
    assert report["estimated_cost"]["cad"] >= report["estimated_cost"]["usd"]
    assert report["providers"][0]["provider"] == "openrouter"
    assert report["operations"][0]["operation"] == "agent.99"
    assert report["operations"][0]["tokens"] == 7000
    assert report["recent_dates"][0]["date"] == "2026-05-13"
    assert report["recent_dates"][0]["tokens"] == 7000
    assert report["routes"][0]["route"] == "openrouter_direct"


def test_format_report_mentions_librarian_and_agent_spend():
    from gateway.token_spend_report import format_report, summarize_usage

    entries = [
        {
            "date": "2026-05-11",
            "provider": "openrouter",
            "model": "deepseek/deepseek-v4-flash",
            "operation": "knowledge.librarian",
            "usage": {"prompt_tokens": 1800, "completion_tokens": 300, "total_tokens": 2100},
            "metadata": {"route": "openrouter_direct", "from_pool": False},
        },
        {
            "date": "2026-05-13",
            "provider": "openrouter",
            "model": "deepseek/deepseek-r1",
            "operation": "agent.99",
            "usage": {"prompt_tokens": 5000, "completion_tokens": 2000, "total_tokens": 7000},
            "metadata": {"route": "openrouter_direct", "from_pool": False},
        },
    ]

    text = format_report(summarize_usage(entries))

    assert "Paid traffic" in text
    assert "Providers" in text
    assert "Estimated spend" in text
    assert "CAD" in text
    assert "knowledge.librarian" in text
    assert "agent.99" in text
    assert "openrouter_direct" in text


def test_agentrouter_deepseek_pro_cost_and_credit_balance():
    from gateway.token_spend_report import summarize_usage

    report = summarize_usage(
        [
            {
                "date": "2026-05-18",
                "provider": "agentrouter",
                "model": "deepseek-v4-pro",
                "operation": "llm.call",
                "usage": {
                    "prompt_tokens": 1000,
                    "completion_tokens": 1000,
                    "cached_tokens": 500,
                    "total_tokens": 2000,
                },
                "metadata": {"route": "agentrouter_direct"},
            }
        ],
        credit_balance=150.0,
    )

    assert report["estimated_cost"]["usd"] > 0
    assert report["estimated_credits"]["balance"] == 150.0
    assert report["estimated_credits"]["remaining"] < 150.0


def test_filter_entries_by_provider_and_since():
    from gateway.token_spend_report import filter_entries

    entries = [
        {"date": "2026-05-17", "provider": "openrouter"},
        {"date": "2026-05-18", "provider": "agentrouter"},
    ]

    filtered = filter_entries(entries, since="2026-05-18", provider="agentrouter")

    assert filtered == [{"date": "2026-05-18", "provider": "agentrouter"}]
