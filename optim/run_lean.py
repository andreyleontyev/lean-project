"""
Запуск Lean CLI backtest с параметрами.
"""

import subprocess
import sys


def run_lean(run_id: str, params: dict) -> None:
    """
    Запускает lean backtest с заданными параметрами.
    
    Args:
        run_id: Идентификатор прогона для логирования
        params: Словарь параметров для передачи в lean backtest
    """
    print(f"[{run_id}] Запуск backtest с параметрами: {params}")
    
    # Базовая команда
    cmd = ["lean", "backtest", "DonchianWithFunding"]
    
    # Добавляем параметры в формате --parameter key value
    for key, value in params.items():
        cmd.extend(["--parameter", key, str(value)])
    
    try:
        # Запускаем backtest и ждем завершения
        result = subprocess.run(
            cmd,
            check=False,  # Не выбрасываем исключение при ошибке
            capture_output=False,  # Показываем вывод в реальном времени
            text=True
        )
        
        if result.returncode == 0:
            print(f"[{run_id}] Backtest завершен успешно")
        else:
            print(f"[{run_id}] Backtest завершился с кодом {result.returncode}")
            
    except Exception as e:
        print(f"[{run_id}] Ошибка при запуске backtest: {e}", file=sys.stderr)
