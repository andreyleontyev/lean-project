import requests
from datetime import datetime, timezone
import time
import csv

def fetch_binance_ohlcv(symbol, interval, start_ts, end_ts):
    url = "https://api.binance.com/api/v3/klines"
    all_data = []

    while True:
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": start_ts,
            "endTime": end_ts,
            "limit": 1000
        }
        response = requests.get(url, params=params)
        data = response.json()

        if not data:
            break

        all_data.extend(data)
        last_time = data[-1][0]
        start_ts = last_time + 1

        if len(data) < 1000:
            break

        time.sleep(0.2)

    return all_data

def save_to_csv(data, filename):
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Date', 'Open', 'High', 'Low', 'Close', 'Volume'])
        for row in data:
            # Дата в формате YYYY-MM-DD HH:MM:SS+00:00
            dt = datetime.fromtimestamp(row[0]/1000, tz=timezone.utc)
            dt_str = dt.strftime("%Y-%m-%d %H:%M:%S+00:00")
            writer.writerow([
                dt_str,
                row[1],
                row[2],
                row[3],
                row[4],
                row[5]
            ])

if __name__ == "__main__":
    symbol = "BTCUSDT"
    interval = "1h"

    start = int(datetime(2020, 1, 1, 15, 0, tzinfo=timezone.utc).timestamp() * 1000)
    end = int(datetime(2026, 1, 1, 19, 0, tzinfo=timezone.utc).timestamp() * 1000)

    ohlcv_data = fetch_binance_ohlcv(symbol, interval, start, end)
    save_to_csv(ohlcv_data, "BTCUSDT_Binance_1h.csv")
    print(f"Сохранено {len(ohlcv_data)} свечей в BTCUSDT_1h.csv")
