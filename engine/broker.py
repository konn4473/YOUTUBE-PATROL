import os
import json
from datetime import datetime

class MockBroker:
    """
    仮想取引の執行と、IFDOCO形式の予約注文管理を担当するクラス
    """
    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        self.state_path = os.path.join(self.data_dir, "portfolio_v2.json")
        self.history_path = os.path.join(self.data_dir, "trade_history_v2.json")
        
        self.portfolio = self.load_state()
        self.trade_history = self.load_history()

    def load_state(self):
        if os.path.exists(self.state_path):
            with open(self.state_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {
            "cash": 1000000,
            "holdings": {}, # {ticker: {qty, avg_price, sl_price, tp_price}}
            "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    def load_history(self):
        if os.path.exists(self.history_path):
            with open(self.history_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def save_all(self):
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(self.portfolio, f, indent=2, ensure_ascii=False)
        with open(self.history_path, "w", encoding="utf-8") as f:
            json.dump(self.trade_history, f, indent=2, ensure_ascii=False)

    def place_order(self, ticker, action, quantity, price, rationale="", sl_price=None, tp_price=None):
        """注文執行。buy時のみ sl/tp をセット可能。"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if action == "buy":
            cost = quantity * price
            if self.portfolio["cash"] < cost:
                print(f"❌ 資金不足: {ticker}")
                return None
            
            self.portfolio["cash"] -= cost
            holding = self.portfolio["holdings"].get(ticker, {"quantity": 0, "avg_price": 0})
            new_qty = holding["quantity"] + quantity
            new_avg = ((holding["avg_price"] * holding["quantity"]) + cost) / new_qty
            
            # 予約価格のセット
            self.portfolio["holdings"][ticker] = {
                "quantity": new_qty,
                "avg_price": round(new_avg, 1),
                "sl_price": sl_price,
                "tp_price": tp_price
            }
        
        elif action == "sell":
            holding = self.portfolio["holdings"].get(ticker)
            if not holding or holding["quantity"] < quantity:
                print(f"❌ 保有不足: {ticker}")
                return None
            
            self.portfolio["cash"] += quantity * price
            holding["quantity"] -= quantity
            if holding["quantity"] <= 0:
                del self.portfolio["holdings"][ticker]
            else:
                self.portfolio["holdings"][ticker] = holding

        order = {
            "timestamp": timestamp,
            "ticker": ticker,
            "action": action,
            "quantity": quantity,
            "price": price,
            "rationale": rationale
        }
        self.trade_history.append(order)
        self.save_all()
        print(f"✅ {action.upper()} 完了: {ticker} @ {price:,.1f}円")
        return order

    def monitor_and_execute(self, market_prices):
        """現在の市場価格と予約価格を比較し、条件を満たせば強制決済。"""
        executed = []
        # イテレーション中の辞書削除を避ける
        tickers = list(self.portfolio["holdings"].keys())
        
        for ticker in tickers:
            if ticker not in market_prices: continue
            
            price_info = market_prices[ticker]
            current_price = price_info["price"]
            hold = self.portfolio["holdings"][ticker]
            
            sl = hold.get("sl_price")
            tp = hold.get("tp_price")
            
            action = None
            reason = ""
            if sl and current_price <= sl:
                action = "sell"
                reason = f"🚨 自動損切り執行 (SL: {sl:,.1f}円 / 現値: {current_price:,.1f}円)"
            elif tp and current_price >= tp:
                action = "sell"
                reason = f"🎊 自動利確執行 (TP: {tp:,.1f}円 / 現値: {current_price:,.1f}円)"
            
            if action:
                self.place_order(ticker, action, hold["quantity"], current_price, reason)
                executed.append({"ticker": ticker, "reason": reason})
        return executed
