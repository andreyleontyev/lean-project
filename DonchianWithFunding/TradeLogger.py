from datetime import datetime
import csv
import os


class TradeLogger:
    """Класс для логирования сделок и экспорта в CSV"""
    
    def __init__(self, export_path=None):
        self.trade_logs = []
        self.current_trade = None
        self.export_path = export_path or "/Lean/Data/exports"
    
    def log_entry(self, entry_time, entry_price, quantity, funding, funding_z, bucket, atr_at_entry, atr_stop_multiplier):
        """Логирует вход в сделку"""
        self.current_trade = {
            "entry_time": entry_time,
            "entry_price": entry_price,
            "quantity": quantity,
            "funding": funding,
            "funding_z": funding_z,
            "bucket": bucket,
            "atr_at_entry": atr_at_entry,   
            "atr_stop_multiplier": atr_stop_multiplier
        }
    
    def log_exit(self, exit_time, exit_price, pnl, r, holding_hours):
        """Логирует выход из сделки"""
        if self.current_trade is None:
            return
        
        trade = self.current_trade
        trade["exit_time"] = exit_time
        trade["exit_price"] = exit_price
        trade["pnl"] = pnl
        trade["R"] = r
        trade["holding_hours"] = holding_hours
        
        self.trade_logs.append(trade)
        self.current_trade = None
    
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
            "atr_stop_multiplier"
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
                    "atr_stop_multiplier": trade["atr_stop_multiplier"]
                })
        
        if debug_callback:
            debug_callback(f"Exported {len(self.trade_logs)} trades to {filepath}")

