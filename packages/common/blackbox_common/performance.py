from __future__ import annotations

import math
from typing import Any


PERFORMANCE_CALCULATOR_VERSION = "performance-v1"


def compute_performance_summary(
    rows: list[dict[str, Any]],
    *,
    mode: str,
    value_key: str = "series_values",
    periods_per_year: float = 252.0,
    risk_free_rate: float = 0.0,
    mar: float = 0.0,
    capital_base: float | None = None,
) -> dict[str, float]:
    """Compute canonical Blackbox strategy.summary metrics.

    Return, volatility, and drawdown values are returned in percentage points,
    matching the strategy.summary storage contract. Ratio metrics stay unitless.
    """

    normalized_mode = str(mode or "").strip().lower()
    if normalized_mode not in {"nav", "return", "pnl"}:
        raise ValueError("mode must be nav, return, or pnl")
    if not math.isfinite(periods_per_year) or periods_per_year <= 0:
        raise ValueError("periods_per_year must be a positive finite number")
    if not math.isfinite(risk_free_rate) or risk_free_rate <= -1:
        raise ValueError("risk_free_rate must be finite and greater than -1")
    if not math.isfinite(mar) or mar <= -1:
        raise ValueError("mar must be finite and greater than -1")

    values = [_finite_number(row.get(value_key), value_key) for row in rows]
    if not values:
        raise ValueError("performance rows must not be empty")

    if normalized_mode == "pnl" and capital_base is None:
        cumulative = _cumulative_sum(values)
        return {
            "total_pnl": cumulative[-1],
            "annualized_pnl": _mean(values) * periods_per_year,
            "periods_per_year": periods_per_year,
        }

    if normalized_mode == "pnl":
        if not math.isfinite(capital_base or math.nan) or float(capital_base) <= 0:
            raise ValueError("capital_base must be a positive finite number")
        returns = [value / float(capital_base) for value in values]
        nav = [1.0]
        cumulative_pnl = 0.0
        for value in values:
            cumulative_pnl += value
            level = 1.0 + cumulative_pnl / float(capital_base)
            if level < 0:
                raise ValueError("cumulative pnl falls below the supplied capital base")
            nav.append(level)
    elif normalized_mode == "return":
        if any(value < -1 for value in values):
            raise ValueError("period returns must be greater than or equal to -1")
        returns = values
        nav = [1.0]
        for value in returns:
            nav.append(nav[-1] * (1.0 + value))
    else:
        if len(values) < 2:
            raise ValueError("nav mode requires at least two levels")
        if any(value <= 0 for value in values):
            raise ValueError("nav levels must be positive")
        nav = values
        returns = [current / previous - 1.0 for previous, current in zip(nav, nav[1:])]

    if not returns:
        raise ValueError("performance curve must contain at least one return period")

    period_count = len(returns)
    growth = nav[-1] / nav[0]
    annual_return = -1.0 if growth == 0 else growth ** (periods_per_year / period_count) - 1.0
    max_drawdown = _max_drawdown(nav)
    summary: dict[str, float] = {
        "annual_return": annual_return * 100.0,
        "max_drawdown": max_drawdown * 100.0,
        "periods_per_year": periods_per_year,
    }

    deviation = _sample_standard_deviation(returns)
    if deviation is not None:
        annual_volatility = deviation * math.sqrt(periods_per_year)
        summary["annual_volatility"] = annual_volatility * 100.0
        if deviation > 0:
            risk_free_per_period = (1.0 + risk_free_rate) ** (1.0 / periods_per_year) - 1.0
            summary["sharpe"] = (_mean(returns) - risk_free_per_period) / deviation * math.sqrt(periods_per_year)

    mar_per_period = (1.0 + mar) ** (1.0 / periods_per_year) - 1.0
    downside_deviation = math.sqrt(_mean([min(0.0, value - mar_per_period) ** 2 for value in returns]))
    if downside_deviation > 0:
        summary["sortino"] = (_mean(returns) - mar_per_period) / downside_deviation * math.sqrt(periods_per_year)
    if max_drawdown < 0:
        summary["calmar"] = annual_return / abs(max_drawdown)
    return {key: value for key, value in summary.items() if math.isfinite(value)}


def performance_metadata(
    *,
    mode: str,
    periods_per_year: float,
    risk_free_rate: float = 0.0,
    mar: float = 0.0,
    capital_base: float | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "calculator_version": PERFORMANCE_CALCULATOR_VERSION,
        "periods_per_year": periods_per_year,
        "annual_return_method": "compounded",
        "risk_free_rate": risk_free_rate,
        "mar": mar,
        "percent_unit": "percentage_point",
        "source_mode": mode,
    }
    if capital_base is not None:
        metadata["capital_base"] = capital_base
    return metadata


def _finite_number(value: Any, key: str) -> float:
    if value is None or value == "" or isinstance(value, bool):
        raise ValueError(f"{key} contains a missing or non-numeric value")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} contains a missing or non-numeric value") from exc
    if not math.isfinite(number):
        raise ValueError(f"{key} contains a non-finite value")
    return number


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _sample_standard_deviation(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    average = _mean(values)
    return math.sqrt(sum((value - average) ** 2 for value in values) / (len(values) - 1))


def _cumulative_sum(values: list[float]) -> list[float]:
    total = 0.0
    result: list[float] = []
    for value in values:
        total += value
        result.append(total)
    return result


def _max_drawdown(nav: list[float]) -> float:
    peak = nav[0]
    maximum_drawdown = 0.0
    for value in nav:
        peak = max(peak, value)
        drawdown = value / peak - 1.0 if peak > 0 else -1.0
        maximum_drawdown = min(maximum_drawdown, drawdown)
    return maximum_drawdown
