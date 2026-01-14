"""
Загрузка результатов из CSV файла.
"""

import pandas as pd
import os
import sys


def load_results() -> pd.DataFrame:
    """
    Загружает метрики из CSV файла.
    
    Returns:
        pd.DataFrame: DataFrame с метриками. Пустой DataFrame если файл не существует.
    """
    # Путь относительно корня проекта
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(project_root, "Data", "exports", "run_metrics.csv")
    
    if not os.path.exists(path):
        return pd.DataFrame()
    
    try:
        df = pd.read_csv(path)
        return df
    except Exception as e:
        print(f"Ошибка при загрузке CSV: {e}", file=sys.stderr)
        return pd.DataFrame()
