from AlgorithmImports import *
from datetime import datetime
from BinanceFundingRateData import BinanceFundingRateData
from BinanceHourlyBTC import BinanceHourlyBTC
from ScoringStrategy import ScoringStrategy
from TradeLogger import TradeLogger
from collections import deque
from TradeContext import TradeContext
import statistics
import csv
import os
import hashlib
import json
from PercentageFeeModel import PercentageFeeModel

class DonchianBTCWithFunding(QCAlgorithm):

    STRATEGY_NAME = "BTC_Trend_Funding"
    STRATEGY_VERSION = "0.0.1"

    BTC_TICK_SIZE = 0.01
    BTC_PRICE_ROUND = 2

    def Initialize(self):
        self.SetStartDate(2024, 1, 1)
        self.SetEndDate(2026, 1, 1)
        self.SetCash(100000)

        # ===== OPTIMIZATION PARAMETERS =====

        # --- Donchian ---
        self.dc_entry_len = int(self.GetParameter("dc_entry_len") or 20)
        self.dc_exit_len  = int(self.GetParameter("dc_exit_len") or 10)

        # --- ATR / Stops ---
        self.atr_period = int(self.GetParameter("atr_period") or 14)

        self.atr_stop_negative = float(self.GetParameter("atr_stop_negative") or 3.0)
        self.atr_stop_neutral  = float(self.GetParameter("atr_stop_neutral")  or 2.5)
        self.atr_stop_positive = float(self.GetParameter("atr_stop_positive") or 2.0)

        # --- Risk multipliers ---
        self.risk_boost_negative = float(self.GetParameter("risk_boost_negative") or 1.5)
        self.risk_neutral        = float(self.GetParameter("risk_neutral") or 1.0)
        self.risk_cut_positive   = float(self.GetParameter("risk_cut_positive") or 0.5)

        # --- Breakeven ---
        self.breakeven_r = float(self.GetParameter("breakeven_r") or 1.0)
        self.breakeven_atr_frac = float(self.GetParameter("breakeven_atr_frac") or 0.75)

        # --- Trailing / exits ---
        self.trail_start_r = float(self.GetParameter("trail_start_r") or 2.0)
        self.soft_exit_r   = float(self.GetParameter("soft_exit_r") or 3.0)

        # ===== END OPTIMIZATION PARAMETERS =====

        version_hash = hashlib.md5(
            json.dumps(dict(self.GetParameters()), sort_keys=True).encode()).hexdigest()[:8]

        self.strategy_version = f"{self.STRATEGY_VERSION}-{version_hash}"
        self.SetRuntimeStatistic("strategy_version", self.strategy_version)


        self.trade_context = None

        self.run_r = []

        self.last_funding_rate = 0.0
        self.last_funding_time = None

        self.funding_window = deque(maxlen=168)  # ~7 дней

        self.min_funding_samples = 30
        self.prev_quantity = 0

        # ===== TRADE LOGGER =====
        export_path = self.GetParameter("export_path")
        if not export_path:
            export_path = "/Lean/Data/exports"
        self.trade_logger = TradeLogger(export_path=export_path)

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
        security.SetLeverage(1.5)

        # ===== FUNDING DATA =====
        self.funding_symbol = self.AddData(BinanceFundingRateData,"BTC_FUNDING",Resolution.Hour).Symbol
        self.last_funding_rate = None

        self.funding_buckets = [
            (-5.0, -2.0),    # экстремально дешёвый лонг
            (-2.0, -1.0),    # выгодный лонг
            (-1.0, 1.0),     # нейтраль
            (1.0, 2.0),      # crowding
            (2.0, 5.0)       # перегрев
        ]

        # ===== INDICATORS =====
        self.dc_entry = DonchianChannel(self.dc_entry_len)
        self.dc_exit  = DonchianChannel(self.dc_exit_len)

        self.ema200 = self.EMA(self.symbol, 200, Resolution.Hour)
        self.ema50  = self.EMA(self.symbol, 50, Resolution.Hour)
        self.atr = self.ATR(self.symbol, self.atr_period, type=MovingAverageType.Simple, resolution=Resolution.Hour)

        self.atr_sma = SimpleMovingAverage(50)

        self.RegisterIndicator(self.symbol, self.dc_entry, Resolution.Hour)
        self.RegisterIndicator(self.symbol, self.dc_exit, Resolution.Hour)
        self.RegisterIndicator(self.symbol, self.atr, Resolution.Hour)

        # ===== RISK =====
        self.base_risk_per_trade = 0.01
        self.max_risk_per_trade = 0.02
        self.min_risk_per_trade = 0.003

        # ===== POSITION MANAGER =====
        self.position_manager = PositionManager(
            price_round=DonchianBTCWithFunding.BTC_PRICE_ROUND,
            atr_stop_negative=self.atr_stop_negative,
            atr_stop_neutral=self.atr_stop_neutral,
            atr_stop_positive=self.atr_stop_positive,
            risk_boost_negative=self.risk_boost_negative,
            risk_neutral=self.risk_neutral,
            risk_cut_positive=self.risk_cut_positive
        )

        self.SetWarmUp(300)

    def OnData(self, data: Slice):
        self._update_funding_rate(data)
        
        if not self._should_process_data(data):
            return

        close_price = data[self.symbol].Close
        
        if not self._check_volatility_filter():
            return

        invested = self.Portfolio[self.symbol].Invested
        
        if not invested:
            self._try_long_entry(close_price, data)
            return

        self._manage_position(close_price)

    def _update_funding_rate(self, data: Slice):
        if data.ContainsKey(self.funding_symbol):
            funding = data[self.funding_symbol].Value
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

    def _calculate_entry_features(self, price, funding_z, atr):
        dt = self.Time
        weekday = dt.weekday()
        hour = dt.hour
        return {
            "entry_weekday": weekday,
            "is_weekend": int(weekday >= 5),
            "entry_hour": hour,
            "hour_bucket_4h": hour // 4,
            "session": self.GetSession(hour),
            "funding_sign": -1 if funding_z < -0.2 else (1 if funding_z > 0.2 else 0),
            "funding_extreme": int(abs(funding_z) > 1.5),
            "atr_pct": atr / price,
            "ema_distance_pct": (price - self.ema200.Current.Value) / price,
            "volatility_regime": self.GetVolatilityRegime(atr, self.atr_sma.Current.Value),
            "funding": self.last_funding_rate,
            "bucket": self.FundingBucket(funding_z)
        }

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

        qty = self.position_manager.calculate_position_size(
            atr_value=self.atr.Current.Value,
            portfolio_value=self.Portfolio.TotalPortfolioValue,
            price=price,
            funding_z=z,
            base_risk_per_trade=self.base_risk_per_trade,
            min_risk_per_trade=self.min_risk_per_trade,
            max_risk_per_trade=self.max_risk_per_trade
        )
        if qty <= 0:
            return

        funding_z = z
        atr_at_entry = self.atr.Current.Value
        stop_multiplier = self.position_manager.get_atr_stop_multiplier(funding_z)
        risk_multiplier = self.position_manager.get_risk_multiplier(funding_z)
        initial_stop = price - stop_multiplier * atr_at_entry

        self.MarketOrder(self.symbol, qty)

        entry_features = self._calculate_entry_features(price, funding_z, atr_at_entry)

        self.trade_context = TradeContext(  
            entry_time=self.Time,
            entry_price=price,
            quantity=qty,
            funding_z=funding_z,
            atr_at_entry=atr_at_entry,
            stop_multiplier=stop_multiplier,
            risk_multiplier=risk_multiplier,
            initial_stop=initial_stop,
            features=entry_features
        )

        stop_price = self.trade_context.initial_stop
        stop_price = round(stop_price, DonchianBTCWithFunding.BTC_PRICE_ROUND)
        stop_ticket = self.StopMarketOrder(self.symbol, -qty, stop_price)
        self.position_manager.set_stop_ticket(stop_ticket)

    def _manage_position(self, close_price: float):
        """Управляет открытой позицией: выходы и обновление стоп-лосса"""
        tc = self.trade_context
        tc.max_price = max(tc.max_price, close_price)
        
        risk_per_unit = tc.atr_at_entry * tc.stop_multiplier
        r = (close_price - tc.entry_price) / risk_per_unit
        
        # 1. Donchian hard exit
        if self._check_donchian_exit(close_price):
            return
        
        # 2. Breakeven stop
        if r > self.breakeven_r and tc.max_price > tc.entry_price + self.breakeven_atr_frac * tc.atr_at_entry:
            tc.current_stop = tc.entry_price
            self.position_manager.update_stop(tc.current_stop)
        
        # 3. EMA trailing stop (только улучшаем)
        if r > self.trail_start_r:
            current_atr = self.atr.Current.Value
            trail = tc.max_price - tc.stop_multiplier * current_atr
            if trail > tc.current_stop:
                tc.current_stop = trail
                self.position_manager.update_stop(tc.current_stop)

        # 4. Soft EMA exit (только после хорошего хода)
        if r > self.soft_exit_r and close_price < self.ema50.Current.Value:
            self.position_manager.cancel_stop()
            tc.exit_reason_hint = "SoftExit_EMA"
            self.Liquidate(self.symbol)
            return

    def _check_donchian_exit(self, close_price):
        if self.dc_exit.IsReady and close_price < self.dc_exit.LowerBand.Current.Value:
            self.position_manager.cancel_stop()
            self.Liquidate(self.symbol)
            return True
        return False



    def FundingZScore(self):

        if len(self.funding_window) < self.min_funding_samples:
            return 0.0

        mean = sum(self.funding_window) / len(self.funding_window)
        var = sum((x - mean) ** 2 for x in self.funding_window) / len(self.funding_window)

        std = var ** 0.5

        if std < 1e-6:
            return 0.0   # funding стабилен → нет сигнала

        z = (self.last_funding_rate - mean) / std

        # 🔒 защита от числовых выбросов
        return max(-5.0, min(5.0, z))

    def GetSession(self, hour):
        if 0 <= hour < 7:
            return "Asia"
        if 7 <= hour < 13:
            return "Europe"
        if 13 <= hour < 20:
            return "US"
        return "LateUS"

    def GetVolatilityRegime(self, atr, atr_sma):
        ratio = atr / atr_sma
        if ratio < 0.8:
            return "low"
        if ratio > 1.2:
            return "high"
        return "normal"

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
            if self.trade_context is None:
                self.prev_quantity = current_qty
                return

            order = self.Transactions.GetOrderById(orderEvent.OrderId)
            exit_reason = getattr(self.trade_context, "exit_reason_hint", str(order.Type))
            # exit_reason = str(order.Type) if order else "Unknown"

            self.trade_context.close(self.Time, orderEvent.FillPrice, exit_reason)
            self.trade_logger.log_trade(self.trade_context)
            self.run_r.append(self.trade_context.r_multiple)
            self.Debug(f"TRADE CLOSED | R={round(self.trade_context.r_multiple,2)}")
            
            self.trade_context = None
            self.position_manager.clear_stop_ticket()

        self.prev_quantity = current_qty

    def OnEndOfAlgorithm(self):
        self.trade_logger.export_to_csv(debug_callback=self.Debug)

        if self.run_r:
            avg_r = sum(self.run_r) / len(self.run_r)
            median_r = statistics.median(self.run_r)
        else:
            avg_r = 0
            median_r = 0


        sharpe_ratio = self.statistics.total_performance.portfolio_statistics.sharpe_ratio
        sortino_ratio = self.statistics.total_performance.portfolio_statistics.sortino_ratio
        win_rate = self.statistics.total_performance.portfolio_statistics.win_rate
        average_win_rate = self.statistics.total_performance.portfolio_statistics.average_win_rate
        drawdown_val = self.statistics.total_performance.portfolio_statistics.drawdown
        expectancy = self.statistics.total_performance.portfolio_statistics.expectancy
        compounding_annual_return = self.statistics.total_performance.portfolio_statistics.compounding_annual_return
        calmar = compounding_annual_return / drawdown_val if drawdown_val > 0 else 0
        average_loss_rate = self.statistics.total_performance.portfolio_statistics.average_loss_rate
        start_equity = self.statistics.total_performance.portfolio_statistics.start_equity
        end_equity = self.statistics.total_performance.portfolio_statistics.end_equity
        trades_val = self.statistics.total_performance.trade_statistics.total_number_of_trades
        average_trade_duration = self.statistics.total_performance.trade_statistics.average_trade_duration
        profit_factor = self.statistics.total_performance.trade_statistics.profit_factor

        row = {
            "run_id": self.StartDate.strftime("%Y%m%d") + "_" + self.EndDate.strftime("%Y%m%d") + self.strategy_version,

            # --- parameters ---
            "atr_stop_neutral": self.atr_stop_neutral,
            "trail_start_r": self.trail_start_r,
            "breakeven_r": self.breakeven_r,

            # --- metrics from Lean ---
            "sharpe": sharpe_ratio,
            "sortino": sortino_ratio,
            "calmar": calmar,
            "expectancy": expectancy,
            "cagr": compounding_annual_return,
            "win_rate": win_rate,
            "average_win_rate": average_win_rate,
            "average_loss_rate": average_loss_rate,
            "max_drawdown_pct": drawdown_val,
            "end_equity": end_equity,
            "start_equity": start_equity,
            "total_trades": trades_val,
            "average_trade_duration": average_trade_duration,
            "profit_factor": profit_factor,
            "avg_R": avg_r,
            "median_R": median_r
            strategy_version": self.strategy_version
        }

        score = ScoringStrategy.score_strategy(row)
        row["score"] = score

        path = "/Lean/Data/exports/run_metrics.csv"
        file_exists = os.path.isfile(path)

        with open(path, mode="a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=row.keys())
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)


class PositionManager:
    def __init__(self, price_round,
                 atr_stop_negative,
                 atr_stop_neutral,
                 atr_stop_positive,
                 risk_boost_negative,
                 risk_neutral,
                 risk_cut_positive):

        self.stop_ticket = None
        self.price_round = price_round

        self.atr_stop_negative = atr_stop_negative
        self.atr_stop_neutral  = atr_stop_neutral
        self.atr_stop_positive = atr_stop_positive

        self.risk_boost_negative = risk_boost_negative
        self.risk_neutral        = risk_neutral
        self.risk_cut_positive   = risk_cut_positive


    def set_stop_ticket(self, ticket):
        """Устанавливает ордер стоп-лосса"""
        self.stop_ticket = ticket

    def clear_stop_ticket(self):
        """Очищает ссылку на стоп-лосс"""
        self.stop_ticket = None

    def cancel_stop(self):
        """Отменяет стоп-лосс ордер"""
        if self.stop_ticket:
            self.stop_ticket.Cancel()
            self.stop_ticket = None

    def update_stop(self, new_price):
        """Обновляет цену стоп-лосса"""
        if self.stop_ticket is None:
            return False

        update = UpdateOrderFields()
        update.StopPrice = round(new_price, self.price_round)
        self.stop_ticket.Update(update)
        return True

    def calculate_position_size(self, atr_value, portfolio_value, price, funding_z, 
                                base_risk_per_trade, min_risk_per_trade, max_risk_per_trade):
        """
        Рассчитывает размер позиции на основе риска
        
        Args:
            atr_value: текущее значение ATR
            portfolio_value: стоимость портфеля
            price: текущая цена инструмента
            funding_z: Z-score funding rate
            base_risk_per_trade: базовый риск на сделку (доля портфеля)
            min_risk_per_trade: минимальный риск на сделку
            max_risk_per_trade: максимальный риск на сделку
        
        Returns:
            Размер позиции (количество)
        """
        if atr_value <= 0:
            return 0

        # === RISK-BASED SIZE ===
        base_risk = portfolio_value * base_risk_per_trade
        risk_multiplier = self.get_risk_multiplier(funding_z)
        adjusted_risk = base_risk * risk_multiplier

        adjusted_risk = max(
            min_risk_per_trade * portfolio_value,
            min(adjusted_risk, max_risk_per_trade * portfolio_value)
        )

        atr_stop_multiplier = self.get_atr_stop_multiplier(funding_z)
        qty_risk = adjusted_risk / (atr_value * atr_stop_multiplier)

        # === BUYING POWER CAP ===
        # используем не больше 95% капитала
        max_notional = portfolio_value * 0.95
        qty_cap = max_notional / price

        qty = min(qty_risk, qty_cap)
        return round(qty, 4)

    def get_atr_stop_multiplier(self, funding_z):
        if funding_z > 1.0:
            return self.atr_stop_positive
        if funding_z < -1.0:
            return self.atr_stop_negative
        return self.atr_stop_neutral

    def get_risk_multiplier(self, funding_z):
        if funding_z < -1.0:
            return self.risk_boost_negative
        elif funding_z > 1.0:
            return self.risk_cut_positive
        return self.risk_neutral

    def calculate_r_ratio(self, current_price, entry_price, atr_value, funding_z):
        """
        Рассчитывает R-отношение (прибыль/риск)
        
        Args:
            current_price: текущая цена
            entry_price: цена входа
            atr_value: текущее значение ATR
            funding_z: Z-score funding rate
        
        Returns:
            R-отношение
        """
        atr_stop_multiplier = self.get_atr_stop_multiplier(funding_z)
        risk = atr_value * atr_stop_multiplier
        if risk <= 0:
            return 0
        return (current_price - entry_price) / risk
