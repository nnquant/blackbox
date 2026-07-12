from __future__ import annotations

import importlib

import pytest

from blackbox_common.performance import compute_performance_summary, performance_metadata


def test_return_mode_keeps_first_period_return() -> None:
    summary = compute_performance_summary(
        [{"series_values": 0.10}, {"series_values": 0.0}],
        mode="return",
        periods_per_year=2,
    )

    assert summary["annual_return"] == pytest.approx(10.0)
    assert summary["max_drawdown"] == pytest.approx(0.0)
    assert summary["periods_per_year"] == 2


def test_return_and_nav_modes_match_for_equivalent_curve() -> None:
    returns_summary = compute_performance_summary(
        [{"series_values": 0.10}, {"series_values": 0.0}],
        mode="return",
        periods_per_year=2,
    )
    nav_summary = compute_performance_summary(
        [{"series_values": 1.0}, {"series_values": 1.1}, {"series_values": 1.1}],
        mode="nav",
        periods_per_year=2,
    )

    for key in ["annual_return", "annual_volatility", "max_drawdown", "sharpe", "periods_per_year"]:
        assert nav_summary[key] == pytest.approx(returns_summary[key])


def test_total_loss_keeps_finite_return_and_drawdown() -> None:
    summary = compute_performance_summary(
        [{"series_values": -1.0}],
        mode="return",
        periods_per_year=252,
    )

    assert summary["annual_return"] == -100.0
    assert summary["max_drawdown"] == -100.0
    assert summary["calmar"] == pytest.approx(-1.0)


def test_zero_volatility_does_not_emit_infinite_ratios() -> None:
    summary = compute_performance_summary(
        [{"series_values": 0.01}, {"series_values": 0.01}],
        mode="return",
        periods_per_year=252,
    )

    assert summary["annual_volatility"] == 0.0
    assert "sharpe" not in summary
    assert "sortino" not in summary


def test_pnl_without_capital_only_emits_absolute_metrics() -> None:
    summary = compute_performance_summary(
        [{"series_values": 10.0}, {"series_values": -2.0}],
        mode="pnl",
        periods_per_year=252,
    )

    assert summary == {"total_pnl": 8.0, "annualized_pnl": 1008.0, "periods_per_year": 252}


def test_performance_metadata_records_calculation_contract() -> None:
    metadata = performance_metadata(mode="return", periods_per_year=252, risk_free_rate=0.02, mar=0.01)

    assert metadata == {
        "calculator_version": "performance-v1",
        "periods_per_year": 252,
        "annual_return_method": "compounded",
        "risk_free_rate": 0.02,
        "mar": 0.01,
        "percent_unit": "percentage_point",
        "source_mode": "return",
    }


def test_sdk_performance_helper_logs_canonical_summary(monkeypatch) -> None:
    logging_module = importlib.import_module("blackbox.logging")
    logged: dict[str, object] = {}

    def fake_log_summary(values):
        logged["summary"] = values
        return [{"key": key, "value": value} for key, value in values.items()]

    def fake_log_series(name, data, **kwargs):
        logged["series"] = {"name": name, "data": data, **kwargs}
        return {"id": "artifact_1", "name": name}

    monkeypatch.setattr(logging_module, "log_backtest_summary", fake_log_summary)
    monkeypatch.setattr(logging_module, "log_result_series", fake_log_series)

    result = logging_module.log_performance_result(
        [{"date": "2026-01-01", "series_values": 0.1}, {"date": "2026-01-02", "series_values": 0.0}],
        mode="return",
        metrics={"annual_return": 999.0, "turnover": 0.4},
        periods_per_year=2,
    )

    assert logged["summary"]["annual_return"] == pytest.approx(10.0)
    assert logged["summary"]["periods_per_year"] == 2
    assert logged["summary"]["turnover"] == 0.4
    assert logged["series"]["metadata"]["performance"]["periods_per_year"] == 2
    assert result["computed_metrics"]["annual_return"] == pytest.approx(10.0)
