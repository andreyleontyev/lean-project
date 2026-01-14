"""
Фильтрация и ранжирование результатов оптимизации.
"""

import pandas as pd


def filter_and_rank(df: pd.DataFrame) -> pd.DataFrame:
    """
    Применяет hard-фильтры и использует score из run_metrics.csv для сортировки.
    
    Args:
        df: DataFrame с результатами backtest (должен содержать колонку score)
        
    Returns:
        pd.DataFrame: Отфильтрованный и отсортированный DataFrame с колонкой score
    """
    if df.empty:
        return df
    
    # Проверка наличия колонки score
    if "score" not in df.columns:
        raise ValueError("DataFrame должен содержать колонку 'score' из run_metrics.csv")
    
    # Hard-фильтры
    filtered = df[
        (df["total_trades"] >= 80) &
        (df["profit_factor"] >= 1.2) &
        (df["avg_R"] > 0)
    ].copy()
    
    if filtered.empty:
        return filtered
    
    # Сортировка по score DESC (score уже вычислен при прогоне стратегии)
    filtered = filtered.sort_values("score", ascending=False)
    
    return filtered
