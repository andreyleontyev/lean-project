from AlgorithmImports import *
from datetime import datetime
import os

# --- 1. ВСПОМОГАТЕЛЬНЫЙ КЛАСС КОМИССИИ ---
# Добавляем этот класс, чтобы считать комиссию в процентах
class PercentageFeeModel(FeeModel):
    def __init__(self, percent):
        self.percent = percent

    def GetOrderFee(self, parameters):
        # Считаем объем сделки: Цена * Количество
        val = parameters.Security.Price * abs(parameters.Order.Quantity) * self.percent
        # Возвращаем размер комиссии в валюте котировки (обычно USD)
        return OrderFee(CashAmount(val, parameters.Security.QuoteCurrency.Symbol))

# --- 2. КЛАСС ДАННЫХ ---
class YahooHourlyCrypto(PythonData):
    def GetSource(self, config, date, isLiveMode):
        source_path = os.path.join(Globals.DataFolder, "custom", "btc_1h.csv")
        return SubscriptionDataSource(source_path, SubscriptionTransportMedium.LocalFile)

    def Reader(self, config, line, date, isLiveMode):
        if not (line.strip() and line[0].isdigit()): return None
        data = YahooHourlyCrypto()
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

# --- 3. СТРАТЕГИЯ ---
class RealisticBitcoinStrategy(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2025, 1, 1) 
        self.SetEndDate(2026, 1, 1)
        self.SetCash(100000)

        self.symbol = self.AddData(YahooHourlyCrypto, "BTC", Resolution.Hour).Symbol

        # === ИСПРАВЛЕНИЕ ОШИБКИ ЗДЕСЬ ===
        # Используем наш кастомный класс PercentageFeeModel.
        # 0.001 = 0.1% комиссии
        self.Securities[self.symbol].FeeModel = PercentageFeeModel(0.001)
        
        # Индикаторы
        self.fast_ema = self.EMA(self.symbol, 9, Resolution.Hour)
        self.slow_ema = self.EMA(self.symbol, 21, Resolution.Hour)
        self.SetWarmUp(21)

        # Риск-менеджмент
        self.stop_loss_pct = 0.03
        self.trailing_stop_pct = 0.05
        
        self.highest_price = 0
        self.entry_price = 0

        # Метрики
        self.trade_count = 0
        self.wins = 0
        self.losses = 0
        self.realized_pnl = 0.0
        
        # Создаем график для визуализации
        chart = Chart("Trade Plot")
        chart.AddSeries(Series("Price", SeriesType.Line, 0))
        chart.AddSeries(Series("Fast EMA", SeriesType.Line, 0))
        chart.AddSeries(Series("Slow EMA", SeriesType.Line, 0))
        chart.AddSeries(Series("Buy", SeriesType.Scatter, 0))
        chart.AddSeries(Series("Sell", SeriesType.Scatter, 0))
        self.AddChart(chart)

    def OnData(self, data):
        if not data.ContainsKey(self.symbol) or self.IsWarmingUp:
            return
        
        price = data[self.symbol].Close
        
        # === ВИЗУАЛИЗАЦИЯ ===
        # Рисуем цену
        self.Plot("Trade Plot", "Price", price)
        
        # Рисуем индикаторы (чтобы видеть пересечения)
        self.Plot("Trade Plot", "Fast EMA", self.fast_ema.Current.Value)
        self.Plot("Trade Plot", "Slow EMA", self.slow_ema.Current.Value)
        
        if self.Portfolio.Invested:
            if price > self.highest_price:
                self.highest_price = price

            stop_price = self.entry_price * (1 - self.stop_loss_pct)
            trailing_price = self.highest_price * (1 - self.trailing_stop_pct)
            signal_sell = self.fast_ema.Current.Value < self.slow_ema.Current.Value

            reason = ""
            if price < stop_price: reason = "Stop Loss"
            elif price < trailing_price: reason = "Trailing Stop"
            elif signal_sell: reason = "EMA Cross"

            if reason != "":
                self.Liquidate(self.symbol)
                # Отмечаем точку продажи на графике
                self.Plot("Trade Plot", "Sell", price)
                # Вывод сообщения для отладки
                pnl = self.Portfolio[self.symbol].UnrealizedProfit
                self.Debug(f"SELL ({reason}) Price:{price:.2f} PnL:{pnl:.2f}")

        else:
            if self.fast_ema.Current.Value > self.slow_ema.Current.Value:
                self.SetHoldings(self.symbol, 0.95)
                self.entry_price = price
                self.highest_price = price
                # Отмечаем точку покупки на графике
                self.Plot("Trade Plot", "Buy", price)
                self.Debug(f"BUY at {price}")

    def OnOrderEvent(self, orderEvent):
        if orderEvent.Status == OrderStatus.Filled:
            order = self.Transactions.GetOrderById(orderEvent.OrderId)
            if order.Direction == OrderDirection.Sell:
                self.trade_count += 1
                profit = self.Portfolio[self.symbol].LastTradeProfit
                self.realized_pnl += profit
                if profit > 0: self.wins += 1
                else: self.losses += 1

    def OnEndOfAlgorithm(self):
        self.Log(f"\n--- Strategy Report ---")
        self.Log(f"Total Trades: {self.trade_count}")
        win_rate = (self.wins / self.trade_count * 100) if self.trade_count > 0 else 0
        self.Log(f"Win Rate: {win_rate:.2f}%")
        self.Log(f"Realized PnL: ${self.realized_pnl:.2f}")
        self.Log(f"Final Equity: ${self.Portfolio.TotalPortfolioValue:.2f}")