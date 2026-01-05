from AlgorithmImports import *
from datetime import datetime
import os

# --- 2. КЛАСС ДАННЫХ ---
class BinanceHourlyBTC(PythonData):
    def GetSource(self, config, date, isLiveMode):
        source_path = os.path.join(Globals.DataFolder, "custom", "Binance", "BTCUSDT_Binance_1h.csv")
        return SubscriptionDataSource(source_path, SubscriptionTransportMedium.LocalFile)

    def Reader(self, config, line, date, isLiveMode):
        if not (line.strip() and line[0].isdigit()): return None
        data = BinanceHourlyBTC()
        data.Symbol = config.Symbol
        try:
            items = line.split(',')
            date_str = items[0][:19] 
            data.Time = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            data["Open"] = float(items[1])
            data["High"] = float(items[2])
            data["Low"] = float(items[3])
            data["Close"] = float(items[4])
            data.Value = float(items[4])

            # --- ХАК ДЛЯ ОБЪЕМА ---
            # Если объема нет или он 0, ставим искусственный объем.
            # Без этого ордера могут не исполняться!
            vol = 0
            if len(items) > 5 and items[5].strip():
                vol = float(items[5])
            
            data["Volume"] = vol if vol > 0 else 100000.0 


        except ValueError:
            return None
        return data
