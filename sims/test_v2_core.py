import os
import sys
import json
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# パス追加
sys.path.append(os.getcwd())

from engine.collector import DataCollector
from engine.broker import MockBroker

class TestV2Core(unittest.TestCase):
    def setUp(self):
        self.test_data_dir = tempfile.mkdtemp(prefix="yt_patrol_test_", dir="data")
        self.broker = MockBroker(data_dir=self.test_data_dir)

    def tearDown(self):
        shutil.rmtree(self.test_data_dir, ignore_errors=True)

    def test_broker_reservation(self):
        """予約注文（SL/TP）が正しく保存されるかテスト"""
        ticker = "TEST_TICKER"
        price = 1000
        sl = 900
        tp = 1200
        
        self.broker.place_order(ticker, "buy", 100, price, sl_price=sl, tp_price=tp)
        
        holdings = self.broker.portfolio["holdings"]
        self.assertIn(ticker, holdings)
        self.assertEqual(holdings[ticker]["sl_price"], sl)
        self.assertEqual(holdings[ticker]["tp_price"], tp)

    def test_risk_execution(self):
        """損切りが正しく執行されるかテスト"""
        ticker = "CRASH_STOCK"
        self.broker.place_order(ticker, "buy", 100, 1000, sl_price=950)
        
        # 価格急落をシミュレート
        market_prices = {ticker: {"price": 940}}
        executed = self.broker.monitor_and_execute(market_prices)
        
        self.assertEqual(len(executed), 1)
        self.assertIn("🚨 自動損切り執行", executed[0]["reason"])
        self.assertNotIn(ticker, self.broker.portfolio["holdings"])

if __name__ == "__main__":
    unittest.main()
