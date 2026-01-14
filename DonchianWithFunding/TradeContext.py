
class TradeContext:
    def __init__(self,
                 entry_time,
                 entry_price,
                 quantity,
                 funding_z,
                 atr_at_entry,
                 stop_multiplier,
                 risk_multiplier,
                 initial_stop,
                 features):

        self.entry_time = entry_time
        self.entry_price = entry_price
        self.quantity = quantity
        self.features = features

        # === FIXED REGIME ===
        self.funding_z = funding_z
        self.atr_at_entry = atr_at_entry
        self.stop_multiplier = stop_multiplier
        self.risk_multiplier = risk_multiplier

        # === RUNTIME STATE ===
        self.max_price = self.entry_price
        self.initial_stop = initial_stop
        self.current_stop = self.initial_stop
        self.max_price = entry_price  # для трейлинга
        
        # === EXIT STATE ===
        self.exit_time = None
        self.exit_price = None
        self.pnl = 0.0
        self.r_multiple = 0.0
        self.holding_hours = 0.0
        self.exit_reason = None
        self.exit_features = {}

    def close(self, time, price, reason):
        self.exit_time = time
        self.exit_price = price
        self.exit_reason = reason
        
        qty = abs(self.quantity)
        self.pnl = (price - self.entry_price) * qty
        
        risk = self.atr_at_entry * self.stop_multiplier * qty
        self.r_multiple = self.pnl / risk if risk > 0 else 0.0
        
        self.holding_hours = (time - self.entry_time).total_seconds() / 3600.0
        
        self.exit_features = {
            "exit_weekday": time.weekday(),
            "exit_hour": time.hour,
            "holding_bucket": self._holding_bucket(self.holding_hours),
            "exit_reason": reason
        }

    def _holding_bucket(self, hours):
        if hours < 12: return "<12h"
        if hours < 48: return "12-48h"
        return "48h+"

    def to_dict(self):
        data = self.features.copy()
        data.update(self.exit_features)
        data.update({
            "entry_time": self.entry_time,
            "exit_time": self.exit_time,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "pnl": self.pnl,
            "R": self.r_multiple,
            "holding_hours": self.holding_hours,
            "quantity": self.quantity,
            "atr_at_entry": self.atr_at_entry,
            "atr_stop_multiplier": self.stop_multiplier,
            "funding_z": self.funding_z
        })
        return data

