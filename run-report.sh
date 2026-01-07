# 1. Запускаем бэктест и запоминаем результат
lean backtest "DonchianWithFunding"

# 2. Находим последний созданный JSON файл бэктеста (рекурсивно в подпапках)
# Исключаем summary и order-events файлы, берем только основной файл бэктеста
LATEST_BACKTEST_FILE=$(find DonchianWithFunding/backtests -name "*.json" -type f ! -name "*-summary.json" ! -name "*-order-events.json" ! -name "data-monitor-report-*.json" -exec stat -f "%m %N" {} \; 2>/dev/null | sort -n | tail -1 | cut -d' ' -f2-)

# Проверяем, что файл найден
if [ -z "$LATEST_BACKTEST_FILE" ] || [ ! -f "$LATEST_BACKTEST_FILE" ]; then
    echo "Ошибка: не удалось найти файл бэктеста"
    exit 1
fi

# 3. Запускаем генерацию отчета, указывая путь к файлу через опцию --backtest-results
lean report --overwrite --backtest-results "$LATEST_BACKTEST_FILE"