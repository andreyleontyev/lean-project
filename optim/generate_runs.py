"""
Генератор списка прогонов с детерминированными run_id.
"""

from param_space import generate_param_space
import hashlib
import json


def generate_runs():
    """
    Генерирует список прогонов с детерминированными run_id.
    
    Returns:
        list: Список кортежей (run_id, params_dict)
    """
    runs = []
    
    # Сортируем параметры для детерминированности
    param_list = sorted(
        list(generate_param_space()),
        key=lambda p: (
            p["atr_stop_negative"],
            p["atr_stop_neutral"],
            p["atr_stop_positive"],
            p["breakeven_r"],
            p["trail_start_r"],
            p["soft_exit_r"],
        )
    )
    
    for idx, params in enumerate(param_list, start=1):
        # Создаем детерминированный run_id на основе параметров
        # Используем hash для компактности, но с индексом для уникальности
        params_str = json.dumps(params, sort_keys=True)
        params_hash = hashlib.md5(params_str.encode()).hexdigest()[:8]
        run_id = f"run_{params_hash}"
        
        runs.append((run_id, params))
    
    return runs
