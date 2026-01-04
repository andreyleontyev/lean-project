from AlgorithmImports import *

class DonchianBTCTrend(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2021, 1, 1)
        self.SetEndDate(2025, 1, 1)
        self.SetCash(100000)

        # ===== ASSET =====
        self.symbol = self.AddCrypto("BTCUSDT", Resolution.Hour, Market.Binance).Symbol

        # ===== INDICATORS =====
        self.entry_period = 20
        self.exit_period = 10

        self.dc_entry = DonchianChannel(self.entry_period)
        self.dc_exit = DonchianChannel(self.exit_period)

        self.ema200 = self.EMA(self.symbol, 200, Resolution.Hour)
        self.ema50  = self.EMA(self.symbol, 50, Resolution.Hour)

        self.atr = self.ATR(self.symbol, 14, MovingAverageType.Simple, Resolution.Hour)
        self.atr_sma = SimpleMovingAverage(50)

        self.RegisterIndicator(self.symbol, self.dc_entry, Resolution.Hour)
        self.RegisterIndicator(self.symbol, self.dc_exit, Resolution.Hour)
        self.RegisterIndicator(self.symbol, self.atr, Resolution.Hour)
        self.RegisterIndicator(self.symbol, self.atr_sma, Resolution.Hour)

        # ===== RISK =====
        self.risk_per_trade = 0.01   # 1%
        self.atr_stop_mult = 2.5

        self.stop_ticket = None

        self.SetWarmUp(300)

    def OnData(self, data: Slice):

        if self.IsWarmingUp:
            return

        if not data.ContainsKey(self.symbol):
            return

        price = data[self.symbol].Close

        # ===== VOLATILITY FILTER =====
        self.atr_sma.Update(self.Time, self.atr.Current.Value)
        if not self.atr_sma.IsReady:
            return

        vol_ok = self.atr.Current.Value > self.atr_sma.Current.Value
        if not vol_ok:
            return

        invested = self.Portfolio[self.symbol].Invested

        # ===== LONG ENTRY =====
        if not invested:
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

            # R-multiple
            r = (price - entry_price) / (self.atr_stop_mult * atr)

            # Move stop to breakeven
            if r > 1.0 and self.stop_ticket is not None:
                new_stop = entry_price
                self.UpdateStop(new_stop)

            # Trail by EMA50
            if r > 2.0 and self.stop_ticket is not None:
                new_stop = self.ema50.Current.Value
                self.UpdateStop(new_stop)

            # Donchian exit
            if price < self.dc_exit.LowerBand.Current.Value:
                self.Liquidate(self.symbol)
                self.stop_ticket = None

    def UpdateStop(self, new_price):
        if self.stop_ticket is None:
            return

        update_fields = UpdateOrderFields()
        update_fields.StopPrice = round(new_price, 2)
        self.stop_ticket.Update(update_fields)

    def CalculatePositionSize(self):
        atr = self.atr.Current.Value
        risk_dollars = self.Portfolio.TotalPortfolioValue * self.risk_per_trade
        qty = risk_dollars / (atr * self.atr_stop_mult)
        return round(qty, 4)
