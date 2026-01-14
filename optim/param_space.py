"""
Генератор пространства параметров с ограничениями.
Генерирует только допустимые комбинации параметров для оптимизации.
"""

from itertools import product


def generate_param_space():
    """
    Генерирует все допустимые комбинации параметров с учетом constraints.
    
    Yields:
        dict: Словарь с параметрами для одного прогона
    """
    # Диапазоны параметров
    atr_stop_negative_values = [3.0, 3.5, 4.0, 4.5]
    atr_stop_neutral_values = [2.0, 2.25, 2.5, 2.75, 3.0]
    atr_stop_positive_values = [1.5, 1.75, 2.0, 2.25]
    
    breakeven_r_values = [0.8, 1.0, 1.2, 1.4]
    trail_start_r_values = [1.8, 2.1, 2.4, 2.7]
    soft_exit_r_values = [3.0, 3.5, 4.0, 4.5]
    
    # Генерируем все комбинации
    for (
        atr_stop_negative,
        atr_stop_neutral,
        atr_stop_positive,
        breakeven_r,
        trail_start_r,
        soft_exit_r
    ) in product(
        atr_stop_negative_values,
        atr_stop_neutral_values,
        atr_stop_positive_values,
        breakeven_r_values,
        trail_start_r_values,
        soft_exit_r_values
    ):
        # Применяем constraints
        # 1. atr_stop_negative >= atr_stop_neutral >= atr_stop_positive
        if not (atr_stop_negative >= atr_stop_neutral >= atr_stop_positive):
            continue
        
        # 2. soft_exit_r > trail_start_r
        if not (soft_exit_r > trail_start_r):
            continue
        
        # Все constraints выполнены - возвращаем комбинацию
        yield {
            "atr_stop_negative": atr_stop_negative,
            "atr_stop_neutral": atr_stop_neutral,
            "atr_stop_positive": atr_stop_positive,
            "breakeven_r": breakeven_r,
            "trail_start_r": trail_start_r,
            "soft_exit_r": soft_exit_r,
        }
