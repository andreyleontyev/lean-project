from AlgorithmImports import *
from datetime import datetime
from BinanceFundingRateData import BinanceFundingRateData
from BinanceHourlyBTC import BinanceHourlyBTC
from collections import deque
import csv
import os

# --- КЛАСС КОМИССИИ ---
class PercentageFeeModel(FeeModel):
    def __init__(self, percent):
        self.percent = percent

    def GetOrderFee(self, parameters):
        # Считаем объем сделки: Цена * Количество
        val = parameters.Security.Price * abs(parameters.Order.Quantity) * self.percent
        # Возвращаем размер комиссии в валюте котировки (обычно USD)
        return OrderFee(CashAmount(val, parameters.Security.QuoteCurrency.Symbol))

class DonchianBTCWithFunding(QCAlgorithm):

    BTC_TICK_SIZE = 0.01
    BTC_PRICE_ROUND = 2

    def Initialize(self):
        self.SetStartDate(2024, 1, 1)
        self.SetEndDate(2026, 1, 1)
        self.SetCash(100000)

        self.last_funding_rate = 0.0
        self.last_funding_time = None

        self.funding_window = deque(maxlen=168)  # ~7 дней
        self.min_funding_samples = 30
        self.prev_quantity = 0

        self.trade_logs = []

        # 1. Добавляем ваши кастомные данные
        # LEAN создаст инструмент с дефолтными настройками (LotSize=1, Market=Empty)
        self.symbol = self.AddData(BinanceHourlyBTC, "BTC", Resolution.Hour).Symbol
        
        # 2. Получаем доступ к объекту этого инструмента
        security = self.Securities[self.symbol]
        
        # --- НАСТРОЙКА 1: Дробные лоты (как мы обсуждали ранее) ---
        # Создаем свойства: Описание, Валюта, Множитель, Шаг цены, РАЗМЕР ЛОТА, Тикер
        # LotSize = 0.00001 (позволяет торговать дробным BTC)
        binance_like_props = SymbolProperties("BTC Binance", "USD", 1, 0.01, 0.00001, "BTC")
        security.SymbolProperties = binance_like_props
        security.FeeModel = PercentageFeeModel(0.001)  # 0.1% комиссия

        # ===== FUNDING DATA =====
        self.funding_symbol = self.AddData(BinanceFundingRateData,"BTC_FUNDING",Resolution.Hour).Symbol
        self.last_funding_rate = None

        self.funding_buckets = [
            (-999, -1.5),
            (-1.5, -0.5),
            (-0.5, 0.5),
            (0.5, 1.5),
            (1.5, 999)
        ]

        # ===== INDICATORS =====
        self.dc_entry = DonchianChannel(20)
        self.dc_exit  = DonchianChannel(10)

        self.ema200 = self.EMA(self.symbol, 200, Resolution.Hour)
        self.ema50  = self.EMA(self.symbol, 50, Resolution.Hour)

        self.atr = self.ATR(self.symbol, 14, MovingAverageType.Simple, Resolution.Hour)
        self.atr_sma = SimpleMovingAverage(50)

        self.RegisterIndicator(self.symbol, self.dc_entry, Resolution.Hour)
        self.RegisterIndicator(self.symbol, self.dc_exit, Resolution.Hour)
        self.RegisterIndicator(self.symbol, self.atr, Resolution.Hour)

        # ===== RISK =====
        self.base_risk_per_trade = 0.01
        self.max_risk_per_trade = 0.02
        self.min_risk_per_trade = 0.003

        self.stop_ticket = None

        self.SetWarmUp(300)

    def OnData(self, data: Slice):
        self._update_funding_rate(data)
        
        if not self._should_process_data(data):
            return

        price = data[self.symbol].Close
        
        if not self._check_volatility_filter():
            return

        invested = self.Portfolio[self.symbol].Invested
        
        if not invested:
            self._try_long_entry(price, data)
            return

        self._manage_position(price)

    def _update_funding_rate(self, data: Slice):
        if data.ContainsKey(self.funding_symbol):
            funding = data[self.funding_symbol].Value
            if funding != 0:
                self.last_funding_rate = funding
                self.last_funding_time = self.Time
                self.funding_window.append(funding)

    def _should_process_data(self, data: Slice) -> bool:
        """Проверяет все условия для продолжения обработки данных"""
        if self.last_funding_rate is None:
            return False
        
        if self.IsWarmingUp:
            return False
        
        if not data.ContainsKey(self.symbol):
            return False
        
        if not (self.dc_entry.IsReady and self.dc_exit.IsReady and 
                self.ema200.IsReady and self.ema50.IsReady and 
                self.atr.IsReady):
            return False
        
        return True

    def _check_volatility_filter(self) -> bool:
        """Проверяет фильтр волатильности: торгуем только при высокой волатильности"""
        self.atr_sma.Update(self.Time, self.atr.Current.Value)
        
        if not self.atr_sma.IsReady:
            return False
        
        # Торгуем только если текущая волатильность выше средней
        return self.atr.Current.Value > self.atr_sma.Current.Value

    def _try_long_entry(self, price: float, data: Slice):
        z = self.FundingZScore()

        breakout = (
            self.dc_entry.UpperBand.IsReady and
            data[self.symbol].High > self.dc_entry.UpperBand.Previous.Value
        )

        trend_ok = price > self.ema200.Current.Value

        # Если рынок перегрет (crowding) — требуем усиленный сетап
        if z > 1.0:
            volatility_ok = self.atr.Current.Value > 1.2 * self.atr_sma.Current.Value
        else:
            volatility_ok = True

        if not (breakout and trend_ok and volatility_ok):
            return

        qty = self.CalculatePositionSize()
        if qty <= 0:
            return

        #======= LOGGING =======
        z = self.FundingZScore()

        self.current_trade = {
            "entry_time": self.Time,
            "entry_price": price,
            "funding": self.last_funding_rate,
            "funding_z": z,
            "bucket": self.FundingBucket(z)
        }

        #======= END LOGGING =======

        self.MarketOrder(self.symbol, qty)

        stop_price = price - self.DynamicATRStopMultiplier() * self.atr.Current.Value
        stop_price = round(stop_price, DonchianBTCWithFunding.BTC_PRICE_ROUND)
        self.stop_ticket = self.StopMarketOrder(self.symbol, -qty, stop_price)

    def _manage_position(self, price: float):
        """Управляет открытой позицией: выходы и обновление стоп-лосса"""
        holding = self.Portfolio[self.symbol]
        entry_price = holding.AveragePrice
        atr = self.atr.Current.Value
        
        # Вычисляем текущий R (отношение прибыли к риску)
        r = (price - entry_price) / (self.DynamicATRStopMultiplier() * atr)
        
        # 1. Donchian hard exit
        if self._check_donchian_exit(price):
            return
        
        # 2. Breakeven stop
        if r > 1.0:
            self.UpdateStop(entry_price)
        
        # 3. EMA trailing stop (только улучшаем)
        if r > 2.0 and self.ema50.IsReady:
            ema = self.ema50.Current.Value
            new_stop = max(entry_price, ema)
            self.UpdateStop(new_stop)

    def _check_donchian_exit(self, price):
        if self.dc_exit.IsReady and price < self.dc_exit.LowerBand.Current.Value:
            if self.stop_ticket:
                self.stop_ticket.Cancel()
            self.Liquidate(self.symbol)
            self.stop_ticket = None
            return True
        return False


    def UpdateStop(self, new_price):
        if self.stop_ticket is None:
            return

        update = UpdateOrderFields()
        update.StopPrice = round(new_price, DonchianBTCWithFunding.BTC_PRICE_ROUND)
        self.stop_ticket.Update(update)

    def CalculatePositionSize(self):
        atr = self.atr.Current.Value

        base_risk = self.Portfolio.TotalPortfolioValue * self.base_risk_per_trade
        adjusted_risk = base_risk * self.FundingRiskMultiplier()

        adjusted_risk = max(
            self.min_risk_per_trade * self.Portfolio.TotalPortfolioValue,
            min(adjusted_risk, self.max_risk_per_trade * self.Portfolio.TotalPortfolioValue)
        )

        qty = adjusted_risk / (atr * self.DynamicATRStopMultiplier())
        return round(qty, 4)


    def FundingZScore(self):
        if len(self.funding_window) < self.min_funding_samples:
            return 0.0

        mean = sum(self.funding_window) / len(self.funding_window)
        var = sum((x - mean) ** 2 for x in self.funding_window) / len(self.funding_window)
        std = var ** 0.5 if var > 1e-8 else 1e-8

        return (self.last_funding_rate - mean) / std

    def FundingRiskMultiplier(self):
        z = self.FundingZScore()

        if z < -1.0:
            return 1.5   # рынок платит за лонг
        elif z > 1.0:
            return 0.5   # crowding, режем риск
        return 1.0

    def DynamicATRStopMultiplier(self):
        z = self.FundingZScore()
        if z > 1.0:
            return 2.0   # tighter
        if z < -1.0:
            return 3.0   # даём тренду дышать
        return 2.5

    def FundingBucket(self, z):
        for low, high in self.funding_buckets:
            if low <= z < high:
                return f"{low}:{high}"
        return "unknown"

    def OnOrderEvent(self, orderEvent):
        if orderEvent.Status != OrderStatus.Filled:
            return

        holding = self.Portfolio[self.symbol]
        current_qty = holding.Quantity

        # === DETECT POSITION CLOSE ===
        if self.prev_quantity != 0 and current_qty == 0:
            if not hasattr(self, "current_trade") or self.current_trade is None:
                self.prev_quantity = current_qty
                return

            trade = self.current_trade
            exit_price = orderEvent.FillPrice

            trade["exit_time"] = self.Time
            trade["exit_price"] = exit_price

            pnl = exit_price - trade["entry_price"]
            trade["pnl"] = pnl

            risk = self.atr.Current.Value * self.DynamicATRStopMultiplier()
            trade["R"] = pnl / risk if risk > 0 else 0

            trade["holding_hours"] = (
                trade["exit_time"] - trade["entry_time"]
            ).total_seconds() / 3600

            self.trade_logs.append(trade)
            self.current_trade = None

            self.Debug(f"TRADE CLOSED | R={round(trade['R'],2)}")

        self.prev_quantity = current_qty



    def OnEndOfAlgorithm(self):

        if not self.trade_logs:
            self.Debug("No trades to export")
            return

        self.Debug(f"Total trades collected: {len(self.trade_logs)}")

        filename = "trade_log.csv"

        base_path = self.GetParameter("export_path")
        if not base_path:
            base_path = "/Lean/Data/exports"

        filepath = os.path.join(base_path, filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        fieldnames = [
            "entry_time",
            "exit_time",
            "entry_price",
            "exit_price",
            "pnl",
            "R",
            "holding_hours",
            "funding",
            "funding_z",
            "bucket"
        ]

        with open(filepath, mode="w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for trade in self.trade_logs:
                writer.writerow({
                    "entry_time": trade["entry_time"],
                    "exit_time": trade["exit_time"],
                    "entry_price": round(trade["entry_price"], 2),
                    "exit_price": round(trade["exit_price"], 2),
                    "pnl": round(trade["pnl"], 2),
                    "R": round(trade["R"], 2),
                    "holding_hours": round(trade["holding_hours"], 2),
                    "funding": trade["funding"],
                    "funding_z": round(trade["funding_z"], 2),
                    "bucket": trade["bucket"]
                })

        self.Debug(f"Exported {len(self.trade_logs)} trades to {filepath}")
