import math

class ScoringStrategy:

    @staticmethod
    def clamp(x, lo, hi):
        return max(lo, min(hi, x))

    @staticmethod
    def score_strategy(stats: dict) -> float:

        # --- извлечение ---
        cagr = float(stats.get("cagr", 0))
        dd = abs(float(stats.get("max_drawdown_pct", 1)))
        sharpe = float(stats.get("sharpe", 0))
        calmar = float(stats.get("calmar", 0))
        pf = float(stats.get("profit_factor", 0))
        total_trades = int(stats.get("total_trades", 0))

        # кастомные (если считаешь сам)
        expectancy = float(stats.get("Expectancy", 0))
        avg_holding = float(stats.get("Average Holding Time", 0))  # часы

        # --- жёсткие отсечки ---
        if total_trades < 30:
            return -999

        if dd > 0.35:
            return -999

        # --- нормализация ---
        s_cagr = ScoringStrategy.clamp(cagr / 0.30, 0, 1.5)
        s_calmar = ScoringStrategy.clamp(calmar / 2.0, 0, 1.5)
        s_sharpe = ScoringStrategy.clamp(sharpe / 2.0, 0, 1.2)
        s_pf = ScoringStrategy.clamp((pf - 1) / 1.0, 0, 1.5)
        s_exp = ScoringStrategy.clamp(expectancy / 0.5, -1, 1.5)

        # --- штрафы ---
        p_dd = ScoringStrategy.clamp(dd / 0.25, 0, 2.0)
        p_holding = ScoringStrategy.clamp(avg_holding / 240, 0, 1.0)  # >10 дней — штраф

        # --- итог ---
        score = (
            2.0 * s_calmar +
            1.5 * s_cagr +
            1.2 * s_sharpe +
            1.0 * s_pf +
            1.5 * s_exp
            - 2.5 * p_dd
            - 0.5 * p_holding
        )

        return round(score, 3)