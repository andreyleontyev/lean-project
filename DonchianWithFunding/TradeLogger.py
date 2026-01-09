from datetime import datetime
import csv
import os


class TradeLogger:
    """Класс для логирования сделок и экспорта в CSV"""
    
    def __init__(self, export_path=None):
        self.trade_logs = []
        self.export_path = export_path or "/Lean/Data/exports"
    
    def log_trade(self, trade_context):
        """Логирует завершенную сделку"""
        if trade_context is None:
            return
        self.trade_logs.append(trade_context.to_dict())
    
    def export_to_csv(self, filename="trade_log.csv", debug_callback=None):
        """Экспортирует все логированные сделки в CSV файл"""
        if not self.trade_logs:
            if debug_callback:
                debug_callback("No trades to export")
            return
        
        if debug_callback:
            debug_callback(f"Total trades collected: {len(self.trade_logs)}")
        
        filepath = os.path.join(self.export_path, filename)
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
            "bucket",
            "quantity",
            "atr_at_entry",
            "atr_stop_multiplier",
            "entry_weekday",
            "is_weekend",
            "entry_hour",
            "hour_bucket_4h",
            "session",
            "funding_sign",
            "funding_extreme",
            "atr_pct",
            "ema_distance_pct",
            "volatility_regime",
            "exit_weekday",
            "exit_hour",
            "holding_bucket",
            "exit_reason"
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
                    "bucket": trade["bucket"],
                    "quantity": trade["quantity"],
                    "atr_at_entry": trade["atr_at_entry"],
                    "atr_stop_multiplier": trade["atr_stop_multiplier"],
                    "entry_weekday": trade.get("entry_weekday", ""),
                    "is_weekend": trade.get("is_weekend", ""),
                    "entry_hour": trade.get("entry_hour", ""),
                    "hour_bucket_4h": trade.get("hour_bucket_4h", ""),
                    "session": trade.get("session", ""),
                    "funding_sign": trade.get("funding_sign", ""),
                    "funding_extreme": trade.get("funding_extreme", ""),
                    "atr_pct": trade.get("atr_pct", ""),
                    "ema_distance_pct": trade.get("ema_distance_pct", ""),
                    "volatility_regime": trade.get("volatility_regime", ""),
                    "exit_weekday": trade.get("exit_weekday", ""),
                    "exit_hour": trade.get("exit_hour", ""),
                    "holding_bucket": trade.get("holding_bucket", ""),
                    "exit_reason": trade.get("exit_reason", "")
                })
        
        if debug_callback:
            debug_callback(f"Exported {len(self.trade_logs)} trades to {filepath}")

