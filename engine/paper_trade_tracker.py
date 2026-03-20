import json
import os
from datetime import datetime


class PaperTradeTracker:
    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        self.positions_path = os.path.join(self.data_dir, "paper_ai_positions.json")
        self.history_path = os.path.join(self.data_dir, "paper_ai_history.json")
        self.signals_path = os.path.join(self.data_dir, "paper_ai_signals.json")
        self.summary_path = os.path.join(self.data_dir, "paper_ai_summary.json")

        self.positions = self._load_json(self.positions_path, {})
        self.history = self._load_json(self.history_path, [])
        self.signals = self._load_json(self.signals_path, [])

    def mark_to_market(self, market_data, timestamp=None):
        timestamp = timestamp or self._now_text()
        events = []
        for ticker in list(self.positions.keys()):
            if ticker not in market_data:
                continue
            price = self._safe_float(market_data[ticker].get("price"))
            if price <= 0:
                continue

            position = self.positions[ticker]
            position["current_price"] = price
            position["unrealized_pnl"] = round(
                (price - position["entry_price"]) * position["quantity"], 1
            )

            sl_price = position.get("sl_price")
            tp_price = position.get("tp_price")
            if sl_price and price <= sl_price:
                events.append(
                    self._close_position(
                        ticker=ticker,
                        price=price,
                        timestamp=timestamp,
                        reason="paper stop loss",
                        close_type="risk_exit",
                    )
                )
            elif tp_price and price >= tp_price:
                events.append(
                    self._close_position(
                        ticker=ticker,
                        price=price,
                        timestamp=timestamp,
                        reason="paper take profit",
                        close_type="risk_exit",
                    )
                )
        self._save_all()
        return events

    def record_signal_run(self, ai_proposals, shortlisted_candidates, market_data, timestamp=None):
        timestamp = timestamp or self._now_text()
        referenced_tickers = []
        for item in (ai_proposals or [])[:5]:
            if item.get("ticker"):
                referenced_tickers.append(item["ticker"])
        for item in (shortlisted_candidates or [])[:5]:
            if item.get("ticker"):
                referenced_tickers.append(item["ticker"])

        price_snapshot = {}
        for ticker in dict.fromkeys(referenced_tickers):
            market_item = market_data.get(ticker, {})
            if market_item:
                price_snapshot[ticker] = {
                    "price": market_item.get("price"),
                    "change_rate": market_item.get("change_rate"),
                }

        self.signals.append(
            {
                "timestamp": timestamp,
                "ai_proposals": list(ai_proposals or [])[:5],
                "shortlisted_candidates": list(shortlisted_candidates or [])[:5],
                "market_prices": price_snapshot,
            }
        )
        self.signals = self.signals[-200:]
        self._write_json(self.signals_path, self.signals)

    def apply_shortlisted_candidates(
        self, shortlisted_candidates, market_data, risk_config=None, timestamp=None
    ):
        timestamp = timestamp or self._now_text()
        risk_config = risk_config or {}
        events = []
        quantity = int(risk_config.get("paper_trade_quantity", 100))
        sl_rate = self._safe_float(risk_config.get("default_stop_loss"), 0.05)
        tp_rate = self._safe_float(risk_config.get("default_profit_taking"), 0.15)

        for item in shortlisted_candidates or []:
            ticker = item.get("ticker")
            action = str(item.get("action", "")).upper()
            if not ticker or ticker not in market_data:
                continue
            price = self._safe_float(market_data[ticker].get("price"))
            if price <= 0:
                continue

            if action == "BUY" and ticker not in self.positions:
                events.append(
                    self._open_position(
                        ticker=ticker,
                        price=price,
                        quantity=quantity,
                        timestamp=timestamp,
                        reason=item.get("logic", "ai shortlisted buy"),
                        confidence=item.get("confidence"),
                        sl_price=round(price * (1 - sl_rate), 1),
                        tp_price=round(price * (1 + tp_rate), 1),
                    )
                )
            elif action in {"SELL", "AVOID"} and ticker in self.positions:
                events.append(
                    self._close_position(
                        ticker=ticker,
                        price=price,
                        timestamp=timestamp,
                        reason=item.get("logic", "ai shortlisted exit"),
                        close_type="signal_exit",
                    )
                )

        self._save_all()
        return events

    def build_summary(self, market_data):
        open_positions = []
        unrealized_total = 0.0
        now_dt = datetime.now()
        for ticker, position in self.positions.items():
            current_price = self._safe_float(
                market_data.get(ticker, {}).get("price", position.get("current_price"))
            )
            unrealized = round(
                (current_price - position["entry_price"]) * position["quantity"], 1
            )
            unrealized_total += unrealized
            opened_dt = self._parse_timestamp(position.get("opened_at"))
            open_positions.append(
                {
                    "ticker": ticker,
                    "quantity": position.get("quantity"),
                    "entry_price": position.get("entry_price"),
                    "current_price": current_price,
                    "unrealized_pnl": unrealized,
                    "opened_at": position.get("opened_at"),
                    "holding_days": self._holding_days(opened_dt, now_dt),
                }
            )

        closed_trades = [item for item in self.history if item.get("event") == "close"]
        realized_total = round(
            sum(self._safe_float(item.get("realized_pnl")) for item in closed_trades), 1
        )
        wins = sum(1 for item in closed_trades if self._safe_float(item.get("realized_pnl")) > 0)
        holding_days = [
            self._safe_float(item.get("holding_days"))
            for item in closed_trades
            if item.get("holding_days") is not None
        ]
        summary = {
            "open_positions": len(open_positions),
            "closed_trades": len(closed_trades),
            "wins": wins,
            "win_rate": round((wins / len(closed_trades)) * 100, 1) if closed_trades else 0.0,
            "realized_pnl": realized_total,
            "unrealized_pnl": round(unrealized_total, 1),
            "total_pnl": round(realized_total + unrealized_total, 1),
            "average_holding_days": round(sum(holding_days) / len(holding_days), 1)
            if holding_days
            else 0.0,
            "best_win_streak": self._best_streak(closed_trades, positive=True),
            "best_loss_streak": self._best_streak(closed_trades, positive=False),
            "ticker_pnl": self._ticker_pnl(closed_trades),
            "recent_signals": len(self.signals[-5:]),
            "recent_signal_actions": self._recent_signal_actions(),
            "positions": open_positions[:5],
        }
        self._write_json(self.summary_path, summary)
        return summary

    def _open_position(
        self,
        ticker,
        price,
        quantity,
        timestamp,
        reason,
        confidence,
        sl_price=None,
        tp_price=None,
    ):
        position = {
            "ticker": ticker,
            "quantity": quantity,
            "entry_price": round(price, 1),
            "current_price": round(price, 1),
            "unrealized_pnl": 0.0,
            "opened_at": timestamp,
            "reason": reason,
            "confidence": confidence,
            "sl_price": sl_price,
            "tp_price": tp_price,
        }
        self.positions[ticker] = position
        event = {
            "timestamp": timestamp,
            "event": "open",
            "ticker": ticker,
            "quantity": quantity,
            "price": round(price, 1),
            "reason": reason,
            "confidence": confidence,
        }
        self.history.append(event)
        return event

    def _close_position(self, ticker, price, timestamp, reason, close_type):
        position = self.positions.pop(ticker)
        realized_pnl = round((price - position["entry_price"]) * position["quantity"], 1)
        opened_dt = self._parse_timestamp(position.get("opened_at"))
        closed_dt = self._parse_timestamp(timestamp)
        event = {
            "timestamp": timestamp,
            "event": "close",
            "ticker": ticker,
            "quantity": position["quantity"],
            "entry_price": position["entry_price"],
            "price": round(price, 1),
            "realized_pnl": realized_pnl,
            "reason": reason,
            "close_type": close_type,
            "opened_at": position.get("opened_at"),
            "holding_days": self._holding_days(opened_dt, closed_dt),
        }
        self.history.append(event)
        return event

    def _save_all(self):
        self._write_json(self.positions_path, self.positions)
        self._write_json(self.history_path, self.history[-500:])

    def _load_json(self, path, default):
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write_json(self, path, payload):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def _now_text(self):
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _parse_timestamp(self, value):
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        except (TypeError, ValueError):
            return None

    def _holding_days(self, opened_dt, current_dt):
        if not opened_dt or not current_dt:
            return 0.0
        return round(max((current_dt - opened_dt).total_seconds(), 0) / 86400, 1)

    def _recent_signal_actions(self):
        actions = []
        for run in self.signals[-5:]:
            shortlisted = run.get("shortlisted_candidates") or []
            for item in shortlisted[:3]:
                ticker = item.get("ticker")
                action = item.get("action")
                if ticker and action:
                    actions.append(f"{ticker}:{action}")
        return actions[-5:]

    def _best_streak(self, closed_trades, positive=True):
        best = 0
        current = 0
        for item in closed_trades:
            pnl = self._safe_float(item.get("realized_pnl"))
            matched = pnl > 0 if positive else pnl < 0
            if matched:
                current += 1
                best = max(best, current)
            else:
                current = 0
        return best

    def _ticker_pnl(self, closed_trades):
        totals = {}
        for item in closed_trades:
            ticker = item.get("ticker")
            if not ticker:
                continue
            totals[ticker] = round(
                self._safe_float(totals.get(ticker)) + self._safe_float(item.get("realized_pnl")),
                1,
            )
        ranked = sorted(totals.items(), key=lambda item: abs(item[1]), reverse=True)
        return [{"ticker": ticker, "realized_pnl": pnl} for ticker, pnl in ranked[:5]]

    def _safe_float(self, value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
