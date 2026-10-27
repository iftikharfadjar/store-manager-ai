"""
Unit tests for database module.
"""

import os
import tempfile
import unittest

from database import init_db, seed_dummy_data, get_db_stats, get_connection


class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_market.db")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_init_and_seed(self):
        # Initialize
        init_db(self.db_path)
        stats_initial = get_db_stats(self.db_path)
        self.assertEqual(stats_initial["total_products"], 0)

        # Seed 10 days of data
        result = seed_dummy_data(self.db_path, days_back=10, force=True)
        self.assertGreater(result["products"], 20)
        self.assertGreater(result["sales"], 50)
        self.assertGreater(result["sale_items"], 50)

        # Verify stats
        stats = get_db_stats(self.db_path)
        self.assertGreater(stats["total_products"], 20)
        self.assertGreater(stats["total_transactions"], 50)
        self.assertGreater(stats["total_revenue"], 0)
        self.assertGreater(stats["total_profit"], 0)
        self.assertIsNotNone(stats["earliest_sale"])
        self.assertIsNotNone(stats["latest_sale"])

    def test_reorder_low_stock(self):
        seed_dummy_data(self.db_path, days_back=5, force=True)
        stats = get_db_stats(self.db_path)
        self.assertGreater(stats["low_stock_products"], 0)


if __name__ == "__main__":
    unittest.main()
