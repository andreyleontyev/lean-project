from AlgorithmImports import *
from datetime import datetime
from BinanceFundingRateData import BinanceFundingRateData
from YahooHourlyCrypto import YahooHourlyCrypto

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

        # 1. Добавляем ваши кастомные данные
        # LEAN создаст инструмент с дефолтными настройками (LotSize=1, Market=Empty)
        self.symbol = self.AddData(YahooHourlyCrypto, "BTC", Resolution.Hour).Symbol
        
        # 2. Получаем доступ к объекту этого инструмента
        security = self.Securities[self.symbol]
        
        # --- НАСТРОЙКА 1: Дробные лоты (как мы обсуждали ранее) ---
        # Создаем свойства: Описание, Валюта, Множитель, Шаг цены, РАЗМЕР ЛОТА, Тикер
        # LotSize = 0.00001 (позволяет торговать дробным BTC)
        binance_like_props = SymbolProperties("BTC Yahoo", "USD", 1, 0.01, 0.00001, "BTC")
        security.SymbolProperties = binance_like_props
        security.FeeModel = PercentageFeeModel(0.001)  # 0.1% комиссия

        # ===== FUNDING DATA =====
        self.funding_symbol = self.AddData(BinanceFundingRateData,"BTC_FUNDING",Resolution.Hour).Symbol
        self.last_funding_rate = None

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
        # atr_sma обновляется вручную, не регистрируем через RegisterIndicator

        # ===== RISK =====
        self.risk_per_trade = 0.01
        self.atr_stop_mult = 2.5

        self.stop_ticket = None

        self.SetWarmUp(300)

    def OnData(self, data: Slice):

        if data.ContainsKey(self.funding_symbol):
            funding = data[self.funding_symbol].Value
            if funding != 0:
                self.last_funding_rate = funding
                self.last_funding_time = self.Time

        if self.last_funding_rate is None:
            return

        if self.IsWarmingUp:
            return

        if not data.ContainsKey(self.symbol):
            return

        # ===== CHECK INDICATORS READINESS =====
        if not (self.dc_entry.IsReady and self.dc_exit.IsReady and 
                self.ema200.IsReady and self.ema50.IsReady and 
                self.atr.IsReady):
            return

        price = data[self.symbol].Close

        # ===== VOLATILITY FILTER =====
        self.atr_sma.Update(self.Time, self.atr.Current.Value)
        if not self.atr_sma.IsReady:
            return

        # Код сравнивает текущую волатильность (atr.Current.Value) со средней исторической волатильностью (atr_sma.Current.Value).
        # Логика: Если текущая волатильность ниже или равна средней, код делает return (прекращает работу).
        if self.atr.Current.Value <= self.atr_sma.Current.Value:
            return

        invested = self.Portfolio[self.symbol].Invested

        # ===== FUNDING FILTER =====
        allow_long  = self.last_funding_rate <= 0.0001
        allow_short = self.last_funding_rate >= -0.0001

        # ===== LONG ENTRY =====
        if not invested and allow_long:
            # Проверяем, что UpperBand готов
            if (self.dc_entry.UpperBand.IsReady and 
                data[self.symbol].High > self.dc_entry.UpperBand.Previous.Value and
                price > self.ema200.Current.Value):
                qty = self.CalculatePositionSize()
                if qty > 0:
                    self.MarketOrder(self.symbol, qty)
                    stop_price = price - self.atr_stop_mult * self.atr.Current.Value
                    stop_price = round(stop_price, DonchianBTCWithFunding.BTC_PRICE_ROUND)
                    self.stop_ticket = self.StopMarketOrder(self.symbol, -qty, stop_price)

        # return is not need to place Stop
        if not invested:
            return

        holding = self.Portfolio[self.symbol]
        entry_price = holding.AveragePrice
        atr = self.atr.Current.Value

        r = (price - entry_price) / (self.atr_stop_mult * atr)

        # 1. Donchian hard exit
        if self.dc_exit.IsReady and price < self.dc_exit.LowerBand.Current.Value:
            if self.stop_ticket:
                self.stop_ticket.Cancel()
            self.Liquidate(self.symbol)
            self.stop_ticket = None
            return
        
        # 2. Breakeven
        if r > 1.0:
            self.UpdateStop(entry_price)

        # 3. EMA trailing (only improve)
        if r > 2.0 and self.ema50.IsReady:
            ema = self.ema50.Current.Value
            new_stop = max(entry_price, ema)
            self.UpdateStop(new_stop)    

        return

    def UpdateStop(self, new_price):
        if self.stop_ticket is None:
            return

        update = UpdateOrderFields()
        update.StopPrice = round(new_price, DonchianBTCWithFunding.BTC_PRICE_ROUND)
        self.stop_ticket.Update(update)

    def CalculatePositionSize(self):
        atr = self.atr.Current.Value
        risk = self.Portfolio.TotalPortfolioValue * self.risk_per_trade
        qty = risk / (atr * self.atr_stop_mult)
        return round(qty, 4)
