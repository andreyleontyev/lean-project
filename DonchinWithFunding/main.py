from AlgorithmImports import *
from datetime import datetime
from BinanceFundingRateData import BinanceFundingRateData

class DonchianBTCWithFunding(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2021, 1, 1)
        self.SetEndDate(2025, 1, 1)
        self.SetCash(100000)

        # ===== BTC =====
        self.symbol = self.AddCrypto("BTCUSDT", Resolution.Hour, Market.Binance).Symbol

        # ===== FUNDING DATA =====
        self.funding_symbol = self.AddData(
            BinanceFundingRateData,
            "BTC_FUNDING",
            Resolution.Hour
        ).Symbol

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
        self.RegisterIndicator(self.symbol, self.atr_sma, Resolution.Hour)

        # ===== RISK =====
        self.risk_per_trade = 0.01
        self.atr_stop_mult = 2.5

        self.stop_ticket = None

        self.SetWarmUp(300)

    def OnData(self, data: Slice):

        # ===== FUNDING UPDATE =====
        if data.ContainsKey(self.funding_symbol):
            self.last_funding_rate = data[self.funding_symbol].Value

        if self.IsWarmingUp:
            return

        if not data.ContainsKey(self.symbol):
            return

        if self.last_funding_rate is None:
            return  # funding ещё не пришёл

        price = data[self.symbol].Close

        # ===== VOLATILITY FILTER =====
        self.atr_sma.Update(self.Time, self.atr.Current.Value)
        if not self.atr_sma.IsReady:
            return

        if self.atr.Current.Value <= self.atr_sma.Current.Value:
            return

        invested = self.Portfolio[self.symbol].Invested

        # ===== FUNDING FILTER =====
        allow_long  = self.last_funding_rate <= 0.0001
        allow_short = self.last_funding_rate >= -0.0001

        # ===== LONG ENTRY =====
        if not invested and allow_long:
            if (
                price > self.dc_entry.UpperBand.Current.Value and
                price > self.ema200.Current.Value
            ):
                qty = self.CalculatePositionSize()
                self.MarketOrder(self.symbol, qty)

                stop_price = price - self.atr_stop_mult * self.atr.Current.Value
                self.stop_ticket = self.StopMarketOrder(self.symbol, -qty, stop_price)

        # ===== POSITION MANAGEMENT =====
        if invested:
            holding = self.Portfolio[self.symbol]
            entry_price = holding.AveragePrice
            atr = self.atr.Current.Value

            r = (price - entry_price) / (self.atr_stop_mult * atr)

            # Breakeven
            if r > 1.0:
                self.UpdateStop(entry_price)

            # Trail by EMA50
            if r > 2.0:
                self.UpdateStop(self.ema50.Current.Value)

            # Donchian exit
            if price < self.dc_exit.LowerBand.Current.Value:
                self.Liquidate(self.symbol)
                self.stop_ticket = None

    def UpdateStop(self, new_price):
        if self.stop_ticket is None:
            return

        update = UpdateOrderFields()
        update.StopPrice = round(new_price, 2)
        self.stop_ticket.Update(update)

    def CalculatePositionSize(self):
        atr = self.atr.Current.Value
        risk = self.Portfolio.TotalPortfolioValue * self.risk_per_trade
        qty = risk / (atr * self.atr_stop_mult)
        return round(qty, 4)
