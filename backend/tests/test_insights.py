from datetime import datetime, timezone
from decimal import Decimal

from app.services import budgets, insights


def _sub(cat, amount, cadence="monthly"):
    return insights.SubSpend(category=cat, amount=Decimal(amount), cadence=cadence)


def test_monthly_equivalent_cadences():
    assert insights.monthly_equivalent(Decimal("120"), "monthly") == Decimal("120")
    assert insights.monthly_equivalent(Decimal("1200"), "yearly") == Decimal("100")
    assert insights.monthly_equivalent(Decimal("12"), "weekly") == Decimal("52")


def test_spend_by_category_groups_and_shares():
    total, rows = insights.spend_by_category(
        [
            _sub("Streaming", "300"),
            _sub("Streaming", "100"),
            _sub("Music", "100"),
            _sub(None, "..." and "0"),  # uncategorized, zero
        ]
    )
    assert total == Decimal("500.00")
    # Sorted high to low; Streaming first.
    assert rows[0].category == "Streaming"
    assert rows[0].monthly == Decimal("400.00")
    assert abs(rows[0].share - 0.8) < 1e-6
    cats = {r.category for r in rows}
    assert "Uncategorized" in cats


def test_spend_by_category_empty():
    total, rows = insights.spend_by_category([])
    assert total == Decimal("0.00")
    assert rows == []


def test_yearly_contributes_monthly_share():
    total, rows = insights.spend_by_category([_sub("Cloud", "1200", "yearly")])
    assert total == Decimal("100.00")
    assert rows[0].monthly == Decimal("100.00")


def test_spend_by_month_buckets_and_limits():
    def dt(y, m, d):
        return datetime(y, m, d, tzinfo=timezone.utc)

    charges = [
        (dt(2026, 8, 5), Decimal("100")),
        (dt(2026, 8, 20), Decimal("50")),
        (dt(2026, 9, 1), Decimal("200")),
        (dt(2026, 10, 1), Decimal("300")),
    ]
    rows = insights.spend_by_month(charges)
    assert [(r.month, r.total) for r in rows] == [
        ("2026-08", Decimal("150.00")),
        ("2026-09", Decimal("200.00")),
        ("2026-10", Decimal("300.00")),
    ]
    assert len(insights.spend_by_month(charges, months=2)) == 2


def test_trend_pct():
    rows = [
        insights.MonthSpend("2026-09", Decimal("200")),
        insights.MonthSpend("2026-10", Decimal("300")),
    ]
    assert insights.trend_pct(rows) == 50.0
    assert insights.trend_pct(rows[:1]) is None
    assert (
        insights.trend_pct(
            [insights.MonthSpend("a", Decimal("0")), insights.MonthSpend("b", Decimal("5"))]
        )
        is None
    )


def test_budget_status():
    assert budgets.status_for(Decimal("50"), Decimal("100")) == "ok"
    assert budgets.status_for(Decimal("80"), Decimal("100")) == "near"
    assert budgets.status_for(Decimal("120"), Decimal("100")) == "over"
    assert budgets.status_for(Decimal("10"), Decimal("0")) == "ok"
