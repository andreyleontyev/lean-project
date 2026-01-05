from AlgorithmImports import *
from datetime import datetime
from BinanceFundingRateData import BinanceFundingRateData
from BinanceHourlyBTC import BinanceHourlyBTC
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
        self.risk_per_trade = 0.01
        self.atr_stop_mult = 2.5

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
        """Обновляет funding rate из данных"""
        if data.ContainsKey(self.funding_symbol):
            funding = data[self.funding_symbol].Value
            if funding != 0:
                self.last_funding_rate = funding
                self.last_funding_time = self.Time

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
        """Пытается открыть длинную позицию при выполнении условий"""
        allow_long = self.last_funding_rate <= 0.0001
        
        if not allow_long:
            return
        
        if not (self.dc_entry.UpperBand.IsReady and 
                data[self.symbol].High > self.dc_entry.UpperBand.Previous.Value and
                price > self.ema200.Current.Value):
            return
        
        qty = self.CalculatePositionSize()
        if qty <= 0:
            return
        
        self.MarketOrder(self.symbol, qty)
        
        stop_price = price - self.atr_stop_mult * self.atr.Current.Value
        stop_price = round(stop_price, DonchianBTCWithFunding.BTC_PRICE_ROUND)
        self.stop_ticket = self.StopMarketOrder(self.symbol, -qty, stop_price)

    def _manage_position(self, price: float):
        """Управляет открытой позицией: выходы и обновление стоп-лосса"""
        holding = self.Portfolio[self.symbol]
        entry_price = holding.AveragePrice
        atr = self.atr.Current.Value
        
        # Вычисляем текущий R (отношение прибыли к риску)
        r = (price - entry_price) / (self.atr_stop_mult * atr)
        
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

    def _check_donchian_exit(self, price: float) -> bool:
        """Проверяет условие выхода по Donchian и выполняет его"""
        if not (self.dc_exit.IsReady and price < self.dc_exit.LowerBand.Current.Value):
            return False
        
        if self.stop_ticket:
            self.stop_ticket.Cancel()
        
        self.Liquidate(self.symbol)
        self.stop_ticket = None
        return True

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
