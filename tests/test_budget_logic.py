from pathlib import Path

from app.budget import TavilyBudgetGuard


def test_budget_reserve_for_critical(tmp_path: Path) -> None:
    budget = TavilyBudgetGuard(
        db_path=str(tmp_path / "budget.sqlite3"),
        daily_soft_cap_calls=8,
        monthly_cap_calls=150,
        reserve_percent_critical=25,
    )

    for _ in range(6):
        allowed, reason = budget.can_use(is_critical=False)
        assert allowed is True, reason
        budget.record_call(is_critical=False)

    allowed_non_critical, reason_non_critical = budget.can_use(is_critical=False)
    assert allowed_non_critical is False
    assert reason_non_critical == "reserved_for_critical"

    allowed_critical, reason_critical = budget.can_use(is_critical=True)
    assert allowed_critical is True
    assert reason_critical == "ok"


def test_budget_monthly_cap(tmp_path: Path) -> None:
    budget = TavilyBudgetGuard(
        db_path=str(tmp_path / "budget.sqlite3"),
        daily_soft_cap_calls=100,
        monthly_cap_calls=3,
        reserve_percent_critical=25,
    )

    for _ in range(3):
        budget.record_call(is_critical=True)

    allowed, reason = budget.can_use(is_critical=True)
    assert allowed is False
    assert reason == "monthly_cap_reached"
