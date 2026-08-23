"""Cost-aware, next-bar backtest for FinApp's rule-based stock signals."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


BUY_SIGNALS = {"buy", "strong buy", "al", "güçlü al"}
SELL_SIGNALS = {"sell", "strong sell", "sat", "güçlü sat"}


def indicator_signal(row: pd.Series) -> str:
    """Mirror the existing RSI/MACD score without using future rows."""
    buy_score = 0
    sell_score = 0
    rsi = row.get("rsi_value")
    macd = row.get("macd_value")
    macd_signal = row.get("macd_signal")

    if pd.notna(rsi):
        if rsi < 30:
            buy_score += 2
        elif rsi < 40:
            buy_score += 1
        elif rsi > 70:
            sell_score += 2
        elif rsi > 60:
            sell_score += 1
    if pd.notna(macd) and pd.notna(macd_signal):
        if macd > macd_signal:
            buy_score += 1
        else:
            sell_score += 1

    if buy_score >= 2:
        return "Buy"
    if sell_score >= 2:
        return "Sell"
    return "Hold"


def normalize_signal(value: Any) -> str:
    normalized = str(value or "").strip().casefold()
    if normalized in BUY_SIGNALS:
        return "Buy"
    if normalized in SELL_SIGNALS:
        return "Sell"
    return "Hold"


def build_target_position(signals: pd.Series) -> pd.Series:
    state = 0.0
    targets: list[float] = []
    for signal in signals:
        normalized = normalize_signal(signal)
        if normalized == "Buy":
            state = 1.0
        elif normalized == "Sell":
            state = 0.0
        targets.append(state)
    return pd.Series(targets, index=signals.index, dtype=float)


def performance_metrics(
    returns: pd.Series,
    benchmark_returns: pd.Series,
    periods_per_year: int,
    annual_risk_free_rate: float,
) -> dict[str, float | int | None]:
    returns = returns.fillna(0.0).astype(float)
    benchmark_returns = benchmark_returns.fillna(0.0).astype(float)
    observations = len(returns)
    if observations == 0:
        return {"observations": 0}

    equity = (1.0 + returns).cumprod()
    running_peak = equity.cummax()
    drawdown = equity / running_peak - 1.0
    total_return = float(equity.iloc[-1] - 1.0)
    years = observations / periods_per_year
    annualized_return = (
        float((1.0 + total_return) ** (1.0 / years) - 1.0)
        if years > 0 and total_return > -1.0
        else None
    )
    annualized_volatility = (
        float(returns.std(ddof=1) * np.sqrt(periods_per_year)) if observations > 1 else None
    )
    periodic_risk_free = annual_risk_free_rate / periods_per_year
    excess = returns - periodic_risk_free
    excess_std = excess.std(ddof=1) if observations > 1 else 0.0
    sharpe = (
        float(excess.mean() / excess_std * np.sqrt(periods_per_year))
        if excess_std and np.isfinite(excess_std)
        else None
    )
    benchmark_total = float((1.0 + benchmark_returns).prod() - 1.0)
    return {
        "observations": observations,
        "total_return": total_return,
        "annualized_return": annualized_return,
        "annualized_volatility": annualized_volatility,
        "sharpe": sharpe,
        "max_drawdown": float(drawdown.min()),
        "benchmark_total_return": benchmark_total,
        "excess_total_return": total_return - benchmark_total,
    }


def trade_metrics(frame: pd.DataFrame) -> dict[str, float | int | None]:
    entries = frame.index[(frame["position"] == 1.0) & (frame["position"].shift(fill_value=0.0) == 0.0)]
    trade_returns: list[float] = []
    for entry in entries:
        later = frame.loc[entry:]
        exits = later.index[(later["position"] == 0.0) & (later["position"].shift(fill_value=1.0) == 1.0)]
        exit_index = exits[0] if len(exits) else frame.index[-1]
        trade_slice = frame.loc[entry:exit_index, "strategy_return"]
        trade_returns.append(float((1.0 + trade_slice).prod() - 1.0))
    wins = sum(value > 0 for value in trade_returns)
    return {
        "trade_count": len(trade_returns),
        "win_rate": wins / len(trade_returns) if trade_returns else None,
        "mean_trade_return": float(np.mean(trade_returns)) if trade_returns else None,
        "median_trade_return": float(np.median(trade_returns)) if trade_returns else None,
    }


def run_backtest(
    data: pd.DataFrame,
    *,
    commission_bps: float = 10.0,
    slippage_bps: float = 5.0,
    annual_risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
    evaluation_start: str | None = None,
    liquidate_at_end: bool = True,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if commission_bps < 0 or slippage_bps < 0:
        raise ValueError("Transaction costs and slippage cannot be negative")
    if periods_per_year < 1:
        raise ValueError("periods_per_year must be positive")

    required = {"date", "close_price"}
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    frame = data.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="raise")
    frame["close_price"] = pd.to_numeric(frame["close_price"], errors="raise")
    frame = frame.sort_values("date").drop_duplicates("date", keep="last").set_index("date")
    if len(frame) < 2:
        raise ValueError("At least two dated price observations are required")
    if (frame["close_price"] <= 0).any():
        raise ValueError("close_price must be positive")

    if "signal" in frame and frame["signal"].notna().any():
        frame["decision_signal"] = frame["signal"].map(normalize_signal)
        signal_source = "stored signal column"
    else:
        frame["decision_signal"] = frame.apply(indicator_signal, axis=1)
        signal_source = "RSI/MACD score reconstructed from same-row indicators"

    frame["target_position"] = build_target_position(frame["decision_signal"])
    frame["position"] = frame["target_position"].shift(1).fillna(0.0)
    frame["asset_return"] = frame["close_price"].pct_change().fillna(0.0)
    frame["turnover"] = frame["position"].diff().abs().fillna(frame["position"].abs())
    if liquidate_at_end and frame["position"].iloc[-1] != 0.0:
        frame.iloc[-1, frame.columns.get_loc("turnover")] += abs(frame["position"].iloc[-1])

    one_way_cost = (commission_bps + slippage_bps) / 10_000.0
    frame["cost"] = frame["turnover"] * one_way_cost
    frame["strategy_return"] = frame["position"] * frame["asset_return"] - frame["cost"]
    frame["equity"] = (1.0 + frame["strategy_return"]).cumprod()
    frame["drawdown"] = frame["equity"] / frame["equity"].cummax() - 1.0

    frame["benchmark_return"] = frame["asset_return"].copy()
    frame.iloc[0, frame.columns.get_loc("benchmark_return")] -= one_way_cost
    frame.iloc[-1, frame.columns.get_loc("benchmark_return")] -= one_way_cost

    summary: dict[str, Any] = {
        "assumptions": {
            "signal_source": signal_source,
            "execution": "signal observed at close t; target position applied to return t→t+1",
            "positioning": "long-or-cash, one unit notional, no leverage",
            "commission_bps_one_way": commission_bps,
            "slippage_bps_one_way": slippage_bps,
            "liquidate_at_end": liquidate_at_end,
            "price_basis": "close-to-close; dividends, taxes, borrow fees, FX, and corporate actions depend on source data",
        },
        "full_period": performance_metrics(
            frame["strategy_return"],
            frame["benchmark_return"],
            periods_per_year,
            annual_risk_free_rate,
        ),
        "trades": trade_metrics(frame),
    }

    if evaluation_start:
        boundary = pd.Timestamp(evaluation_start)
        development = frame.loc[frame.index < boundary]
        evaluation = frame.loc[frame.index >= boundary]
        if development.empty or evaluation.empty:
            raise ValueError("evaluation_start must leave observations on both sides of the boundary")
        summary["time_split"] = {
            "evaluation_start": boundary.date().isoformat(),
            "development": performance_metrics(
                development["strategy_return"],
                development["benchmark_return"],
                periods_per_year,
                annual_risk_free_rate,
            ),
            "evaluation": performance_metrics(
                evaluation["strategy_return"],
                evaluation["benchmark_return"],
                periods_per_year,
                annual_risk_free_rate,
            ),
        }
    return frame, summary


def load_database_rows(ticker: str, start: str | None, end: str | None) -> pd.DataFrame:
    from database import get_connection

    conditions = ["ticker = ?"]
    parameters: list[Any] = [ticker]
    if start:
        conditions.append("date >= ?")
        parameters.append(start)
    if end:
        conditions.append("date <= ?")
        parameters.append(end)
    query = f"""
        SELECT date, close_price, rsi_value, macd_value, macd_signal, signal
        FROM stocks
        WHERE {' AND '.join(conditions)}
        ORDER BY date ASC
    """
    connection = get_connection()
    try:
        return pd.read_sql_query(query, connection, params=parameters)
    finally:
        connection.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--ticker", help="Ticker stored in FinApp's SQLite database")
    source.add_argument("--csv", type=Path, help="CSV containing date, close_price, and optional indicators/signal")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--evaluation-start")
    parser.add_argument("--commission-bps", type=float, default=10.0)
    parser.add_argument("--slippage-bps", type=float, default=5.0)
    parser.add_argument("--annual-risk-free-rate", type=float, default=0.0)
    parser.add_argument("--periods-per-year", type=int, default=252)
    parser.add_argument("--leave-open", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=Path("backtest-results"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.csv:
        data = pd.read_csv(args.csv)
        source_name = args.csv.stem
    else:
        data = load_database_rows(args.ticker, args.start, args.end)
        source_name = args.ticker.replace("/", "_")
    frame, summary = run_backtest(
        data,
        commission_bps=args.commission_bps,
        slippage_bps=args.slippage_bps,
        annual_risk_free_rate=args.annual_risk_free_rate,
        periods_per_year=args.periods_per_year,
        evaluation_start=args.evaluation_start,
        liquidate_at_end=not args.leave_open,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    frame.reset_index().to_csv(args.output_dir / f"{source_name}-equity.csv", index=False)
    (args.output_dir / f"{source_name}-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

