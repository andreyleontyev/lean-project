import yfinance as yf
import pandas as pd
import os
from datetime import datetime, timedelta

# Настройки
ticker = "BTC-USD"
end_date = datetime.now()
start_date = end_date - timedelta(days=730) 

print(f"Скачиваем {ticker} (1h) с Yahoo Finance...")

df = yf.download(ticker, start=start_date, end=end_date, interval="1h")

# Убираем мультииндекс
if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)

# Сбрасываем индекс, чтобы Date/Datetime стала колонкой
df.reset_index(inplace=True)

# Заменяем volume
if 'Volume' in df.columns:
    df.loc[df['Volume'] == 0, 'Volume'] = 100000

# ==========================================
# УПРАВЛЕНИЕ ПОРЯДКОМ КОЛОНОК
# ==========================================

# 1. Определяем желаемый порядок.
# Примечание: yfinance для часовиков обычно называет колонку времени "Datetime".
# "Adj Close" мы исключаем, так как он часто не нужен для бектестов.
desired_columns = ['Datetime', 'Open', 'High', 'Low', 'Close', 'Volume']

# 2. (Опционально) Если вы хотите переименовать 'Datetime' просто в 'Date':
df.rename(columns={'Datetime': 'Date'}, inplace=True)
# Если переименовали, то и в списке выше поменяйте 'Datetime' на 'Date':
desired_columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']

# 3. Применяем сортировку и фильтрацию
# Этот код выберет только перечисленные колонки в указанном порядке.
# Если какой-то колонки нет в данных (чтобы скрипт не упал), добавим проверку:
final_cols = [c for c in desired_columns if c in df.columns]
df = df[final_cols]

# ==========================================

os.makedirs("Data/custom", exist_ok=True)
output_path = "Data/custom/btc_1h.csv"

# Сохраняем. header=False часто нужен для Lean Custom Data, 
# но если вам нужен заголовок, оставьте header=True (по умолчанию).
df.to_csv(output_path, index=False) 

print(f"Файл сохранен: {output_path}")
print("Порядок колонок:")
print(df.columns.tolist())
print(df.head(1))