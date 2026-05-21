from __future__ import annotations

from pathlib import Path

import blackbox as bb


def main() -> None:
    report = Path("example_report.html")
    report.write_text("<html><head><title>Example Report</title></head><body>ok</body></html>", encoding="utf-8")

    with bb.init(
        project="alpha-lab",
        research="csi500-reversal",
        branch="baseline-v1",
        name="lb20_hold5_fee10bp",
        config={"lookback": 20, "hold_days": 5, "fee_bps": 10},
        tags=["reversal", "baseline"],
    ):
        bb.log_event("stage_completed", stage="data_loaded", payload={"rows": 3200000})
        bb.log_factor_summary({"ic_mean": 0.034, "ic_ir": 0.61, "coverage": 0.94})
        bb.log_backtest_summary({"sharpe": 1.42, "max_drawdown": 0.09, "annual_return": 0.18})
        bb.log_artifact("post_cost_report", report, kind="report_html")
        bb.log_note("decision", "Keep baseline for comparison", "Baseline is usable for the next branch.")


if __name__ == "__main__":
    main()

