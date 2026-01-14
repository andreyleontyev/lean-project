#!/usr/bin/env python3
"""
Главный entrypoint для запуска оптимизатора.
"""

import sys
import os

# Добавляем текущую директорию в путь для импортов
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_runs import generate_runs
from run_lean import run_lean
from collect_results import load_results
from rank_results import filter_and_rank
import pandas as pd


def main():
    """Главная функция оптимизатора."""
    print("=" * 80)
    print("Lean Optimizer Runner")
    print("=" * 80)
    
    # 1. Генерируем прогоны
    print("\n[1/5] Генерация прогонов...")
    runs = generate_runs()
    total_runs = len(runs)
    print(f"Сгенерировано {total_runs} прогонов")
    
    # 2. Запускаем backtest для каждого прогона
    print(f"\n[2/5] Запуск {total_runs} backtest'ов...")
    for idx, (run_id, params) in enumerate(runs, start=1):
        print(f"\nПрогон {idx}/{total_runs}")
        run_lean(run_id, params)
    
    # 3. Загружаем результаты
    print("\n[3/5] Загрузка результатов...")
    df = load_results()
    if df.empty:
        print("Внимание: CSV файл пуст или не существует")
        return
    
    print(f"Загружено {len(df)} записей")
    
    # 4. Фильтруем и ранжируем
    print("\n[4/5] Фильтрация и ранжирование...")
    ranked = filter_and_rank(df)
    
    if ranked.empty:
        print("Внимание: после фильтрации не осталось результатов")
        return
    
    print(f"После фильтрации: {len(ranked)} результатов")
    
    # 5. Выводим TOP-10 в stdout
    print("\n[5/5] TOP-10 результатов:")
    print("=" * 80)
    
    top10 = ranked.head(10)
    
    # Выбираем ключевые колонки для вывода
    display_cols = [
        "score",
        "calmar",
        "expectancy",
        "avg_R",
        "median_R",
        "profit_factor",
        "max_drawdown_pct",
        "total_trades",
        "atr_stop_neutral",
        "trail_start_r",
        "breakeven_r"
    ]
    
    # Оставляем только существующие колонки
    available_cols = [col for col in display_cols if col in top10.columns]
    display_df = top10[available_cols]
    
    # Настраиваем формат вывода
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)
    pd.set_option('display.max_colwidth', None)
    
    print(display_df.to_string(index=False))
    print("=" * 80)
    
    # 6. Сохраняем TOP-20 в CSV
    output_path = os.path.join(os.path.dirname(__file__), "top_configs.csv")
    top20 = ranked.head(20)
    top20.to_csv(output_path, index=False)
    print(f"\nTOP-20 конфигураций сохранены в: {output_path}")
    
    print("\nОптимизация завершена!")


if __name__ == "__main__":
    main()
