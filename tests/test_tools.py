"""
Unit tests for the analytical tools module.
"""

import os
import unittest
from database import DB_PATH, seed_dummy_data
from tools import check_inventory, get_sales_and_profit, get_top_selling_products, query_database_readonly


class TestTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Ensure database is seeded with standard data
        seed_dummy_data(DB_PATH, days_back=15, force=True)

    def test_check_inventory(self):
        # All inventory
        inv_all = check_inventory.invoke({})
        self.assertGreater(inv_all["total_products_listed"], 20)
        self.assertGreater(inv_all["total_inventory_cost_value"], 0)

        # Low stock filter
        inv_low = check_inventory.invoke({"low_stock_only": True})
        self.assertGreater(inv_low["total_products_listed"], 0)
        for prod in inv_low["products"]:
            self.assertEqual(prod["status"], "REORDER NEEDED")

        # Category filter
        inv_bev = check_inventory.invoke({"category": "Beverages"})
        self.assertGreater(len(inv_bev["products"]), 0)
        for prod in inv_bev["products"]:
            self.assertEqual(prod["category"], "Beverages")

    def test_get_sales_and_profit(self):
        result = get_sales_and_profit.invoke({
            "start_date": "2026-10-20",
            "end_date": "2026-10-27"
        })
        self.assertGreater(result["total_transactions"], 0)
        self.assertGreater(result["total_items_sold"], 0)
        self.assertGreater(result["total_revenue"], 0)
        self.assertGreater(result["gross_profit"], 0)
        self.assertIn("%", result["gross_margin_percentage"])
        self.assertGreater(len(result["top_products_in_period"]), 0)

    def test_get_top_selling_products(self):
        top_by_volume = get_top_selling_products.invoke({
            "start_date": "2026-10-01",
            "end_date": "2026-10-27",
            "order_by": "volume",
            "limit": 5,
        })
        self.assertEqual(len(top_by_volume), 5)
        self.assertGreaterEqual(top_by_volume[0]["units_sold"], top_by_volume[1]["units_sold"])

        top_by_profit = get_top_selling_products.invoke({
            "start_date": "2026-10-01",
            "end_date": "2026-10-27",
            "order_by": "profit",
            "limit": 3,
        })
        self.assertEqual(len(top_by_profit), 3)
        self.assertGreaterEqual(top_by_profit[0]["profit"], top_by_profit[1]["profit"])

    def test_query_database_readonly_safety(self):
        # Valid query
        valid_res = query_database_readonly.invoke({"sql_query": "SELECT COUNT(*) as count FROM products;"})
        self.assertNotIn("error", valid_res)
        self.assertEqual(valid_res["row_count"], 1)

        # Blocked queries
        drop_res = query_database_readonly.invoke({"sql_query": "DROP TABLE products;"})
        self.assertIn("error", drop_res)

        delete_res = query_database_readonly.invoke({"sql_query": "DELETE FROM sales;"})
        self.assertIn("error", delete_res)

        insert_res = query_database_readonly.invoke({"sql_query": "INSERT INTO categories (name) VALUES ('Hacked');"})
        self.assertIn("error", insert_res)


if __name__ == "__main__":
    unittest.main()
