"""
Database module for the Mini Market Chatbot.
Handles SQLite schema creation, initial dummy data generation, and querying.
"""

from datetime import datetime, timedelta
import os
import random
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "minimarket.db")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    category_id INTEGER NOT NULL,
    cost_price REAL NOT NULL,
    selling_price REAL NOT NULL,
    stock_quantity INTEGER NOT NULL DEFAULT 0,
    reorder_threshold INTEGER NOT NULL DEFAULT 10,
    unit TEXT NOT NULL DEFAULT 'pcs',
    FOREIGN KEY (category_id) REFERENCES categories (id)
);

CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_number TEXT NOT NULL UNIQUE,
    sale_timestamp TEXT NOT NULL,
    total_amount REAL NOT NULL,
    payment_method TEXT NOT NULL DEFAULT 'Cash'
);

CREATE TABLE IF NOT EXISTS sale_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    unit_cost REAL NOT NULL,
    unit_price REAL NOT NULL,
    subtotal REAL NOT NULL,
    profit REAL NOT NULL,
    FOREIGN KEY (sale_id) REFERENCES sales (id),
    FOREIGN KEY (product_id) REFERENCES products (id)
);

CREATE INDEX IF NOT EXISTS idx_sales_timestamp ON sales(sale_timestamp);
CREATE INDEX IF NOT EXISTS idx_sale_items_sale_id ON sale_items(sale_id);
CREATE INDEX IF NOT EXISTS idx_sale_items_product_id ON sale_items(product_id);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
"""

INITIAL_CATEGORIES = [
    ("Beverages", "Soft drinks, bottled water, juices, and tea"),
    ("Snacks & Confectionery", "Chips, cookies, chocolates, and candy"),
    ("Instant Foods", "Instant noodles, canned foods, and ready-to-eat meals"),
    ("Dairy & Eggs", "Milk, yogurt, cheese, butter, and fresh eggs"),
    ("Personal Care & Household", "Soaps, shampoo, detergent, and tissue papers"),
]

INITIAL_PRODUCTS = [
    # Beverages
    ("Mineral Water 600ml", "Beverages", 0.30, 0.60, 45, 20, "bottle"),
    ("Iced Green Tea 500ml", "Beverages", 0.70, 1.30, 18, 15, "bottle"),
    ("Sparkling Soda Can 330ml", "Beverages", 0.60, 1.20, 12, 15, "can"),
    ("Orange Juice 1L", "Beverages", 1.40, 2.50, 8, 10, "bottle"),  # Low stock
    ("Cold Brew Coffee 250ml", "Beverages", 1.10, 2.20, 24, 15, "bottle"),
    ("Energy Drink 250ml", "Beverages", 0.90, 1.80, 5, 10, "can"),    # Low stock

    # Snacks & Confectionery
    ("Potato Chips BBQ 75g", "Snacks & Confectionery", 0.80, 1.60, 32, 15, "pack"),
    ("Chocolate Bar 50g", "Snacks & Confectionery", 0.90, 1.75, 40, 20, "bar"),
    ("Salted Peanuts 100g", "Snacks & Confectionery", 0.50, 1.10, 14, 10, "pack"),
    ("Butter Cookies 150g", "Snacks & Confectionery", 1.20, 2.40, 9, 12, "box"),   # Low stock
    ("Chewy Fruit Candies", "Snacks & Confectionery", 0.40, 0.90, 55, 25, "pack"),
    ("Tortilla Chips 120g", "Snacks & Confectionery", 1.10, 2.10, 6, 12, "pack"),  # Low stock

    # Instant Foods
    ("Instant Ramen Spicy 85g", "Instant Foods", 0.35, 0.75, 60, 25, "pack"),
    ("Instant Cup Noodles 70g", "Instant Foods", 0.55, 1.10, 38, 20, "cup"),
    ("Canned Tuna in Oil 185g", "Instant Foods", 1.50, 2.80, 15, 10, "can"),
    ("Canned Sweet Corn 400g", "Instant Foods", 0.85, 1.60, 4, 10, "can"),   # Low stock
    ("Microwave Popcorn 90g", "Instant Foods", 0.95, 1.90, 20, 10, "pack"),
    ("Ready Rice Meal 200g", "Instant Foods", 1.30, 2.50, 11, 10, "pack"),

    # Dairy & Eggs
    ("Fresh Milk 1L", "Dairy & Eggs", 1.20, 2.10, 14, 15, "carton"),  # Low stock
    ("Cheddar Cheese 200g", "Dairy & Eggs", 1.80, 3.20, 8, 10, "pack"),  # Low stock
    ("Greek Yogurt 150g", "Dairy & Eggs", 0.75, 1.50, 22, 12, "cup"),
    ("Fresh Eggs 10pcs", "Dairy & Eggs", 1.50, 2.60, 7, 12, "box"),     # Low stock
    ("Salted Butter 200g", "Dairy & Eggs", 1.70, 3.00, 16, 10, "pack"),

    # Personal Care & Household
    ("Liquid Hand Soap 250ml", "Personal Care & Household", 1.10, 2.20, 19, 10, "bottle"),
    ("Toothpaste Mint 120g", "Personal Care & Household", 1.00, 2.00, 28, 15, "tube"),
    ("Facial Tissue 200 sheets", "Personal Care & Household", 0.70, 1.40, 35, 15, "box"),
    ("Dishwashing Liquid 400ml", "Personal Care & Household", 0.90, 1.80, 15, 10, "bottle"),
    ("Laundry Detergent 800g", "Personal Care & Household", 1.80, 3.40, 6, 12, "bag"),   # Low stock
    ("Shampoo 170ml", "Personal Care & Household", 1.40, 2.70, 21, 10, "bottle"),
]


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Returns a connection to the SQLite database with row factory enabled."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: str = DB_PATH) -> None:
    """Initializes tables and indexes."""
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()


def seed_dummy_data(db_path: str = DB_PATH, days_back: int = 30, force: bool = False) -> Dict[str, int]:
    """
    Populates categories, products, and realistic historical sales over `days_back`.
    If data already exists and force is False, returns existing count.
    """
    init_db(db_path)

    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        
        # Check if already seeded
        cursor.execute("SELECT COUNT(*) FROM products;")
        prod_count = cursor.fetchone()[0]
        if prod_count > 0 and not force:
            cursor.execute("SELECT COUNT(*) FROM sales;")
            sales_count = cursor.fetchone()[0]
            return {"products": prod_count, "sales": sales_count}

        if force:
            cursor.execute("DELETE FROM sale_items;")
            cursor.execute("DELETE FROM sales;")
            cursor.execute("DELETE FROM products;")
            cursor.execute("DELETE FROM categories;")

        # Insert categories
        category_map = {}
        for cat_name, desc in INITIAL_CATEGORIES:
            cursor.execute(
                "INSERT INTO categories (name, description) VALUES (?, ?) ON CONFLICT(name) DO UPDATE SET description=excluded.description RETURNING id;",
                (cat_name, desc),
            )
            cat_id = cursor.fetchone()[0]
            category_map[cat_name] = cat_id

        # Insert products
        product_list = []
        for name, cat_name, cost, price, stock, threshold, unit in INITIAL_PRODUCTS:
            cat_id = category_map[cat_name]
            cursor.execute(
                """INSERT INTO products 
                   (name, category_id, cost_price, selling_price, stock_quantity, reorder_threshold, unit)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(name) DO UPDATE SET 
                       cost_price=excluded.cost_price, 
                       selling_price=excluded.selling_price, 
                       stock_quantity=excluded.stock_quantity,
                       reorder_threshold=excluded.reorder_threshold,
                       unit=excluded.unit
                   RETURNING id, cost_price, selling_price;""",
                (name, cat_id, cost, price, stock, threshold, unit),
            )
            p_id, p_cost, p_price = cursor.fetchone()
            product_list.append({"id": p_id, "name": name, "cost": p_cost, "price": p_price})

        # Generate realistic sales data
        # Anchor date: Current reference time 2026-10-27
        reference_date = datetime(2026, 10, 27, 21, 0, 0)
        random.seed(42)

        sales_inserted = 0
        sale_items_inserted = 0
        payment_methods = ["Cash", "QRIS", "Debit Card"]
        method_weights = [0.45, 0.40, 0.15]

        for d in range(days_back, -1, -1):
            day_date = reference_date - timedelta(days=d)
            # More sales on weekends (Friday=4, Saturday=5, Sunday=6)
            is_weekend = day_date.weekday() >= 4
            num_transactions = random.randint(18, 32) if is_weekend else random.randint(10, 20)

            for t in range(num_transactions):
                hour = random.randint(8, 21)
                minute = random.randint(0, 59)
                second = random.randint(0, 59)
                tx_timestamp = day_date.replace(hour=hour, minute=minute, second=second).strftime("%Y-%m-%d %H:%M:%S")
                receipt_no = f"RCP-{day_date.strftime('%Y%m%d')}-{t+1:04d}-{random.randint(100, 999)}"
                pm = random.choices(payment_methods, weights=method_weights)[0]

                # Select 1 to 5 distinct items per receipt
                num_items = random.choices([1, 2, 3, 4, 5], weights=[0.35, 0.30, 0.20, 0.10, 0.05])[0]
                selected_prods = random.sample(product_list, k=min(num_items, len(product_list)))

                tx_total = 0.0
                items_to_insert = []

                for prod in selected_prods:
                    qty = random.choices([1, 2, 3, 4], weights=[0.65, 0.22, 0.09, 0.04])[0]
                    subtotal = round(qty * prod["price"], 2)
                    profit = round(qty * (prod["price"] - prod["cost"]), 2)
                    tx_total += subtotal
                    items_to_insert.append((prod["id"], qty, prod["cost"], prod["price"], subtotal, profit))

                tx_total = round(tx_total, 2)
                cursor.execute(
                    "INSERT INTO sales (receipt_number, sale_timestamp, total_amount, payment_method) VALUES (?, ?, ?, ?) RETURNING id;",
                    (receipt_no, tx_timestamp, tx_total, pm),
                )
                sale_id = cursor.fetchone()[0]
                sales_inserted += 1

                for p_id, qty, u_cost, u_price, subtotal, profit in items_to_insert:
                    cursor.execute(
                        """INSERT INTO sale_items (sale_id, product_id, quantity, unit_cost, unit_price, subtotal, profit)
                           VALUES (?, ?, ?, ?, ?, ?, ?);""",
                        (sale_id, p_id, qty, u_cost, u_price, subtotal, profit),
                    )
                    sale_items_inserted += 1

        conn.commit()
        return {
            "products": len(product_list),
            "sales": sales_inserted,
            "sale_items": sale_items_inserted,
        }
    finally:
        conn.close()


def get_db_stats(db_path: str = DB_PATH) -> Dict[str, Any]:
    """Returns general statistics about the database."""
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM products;")
        total_products = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM products WHERE stock_quantity <= reorder_threshold;")
        low_stock_products = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM sales;")
        total_sales_count = cursor.fetchone()[0]

        cursor.execute("SELECT COALESCE(SUM(total_amount), 0) FROM sales;")
        total_revenue = cursor.fetchone()[0]

        cursor.execute("SELECT COALESCE(SUM(profit), 0) FROM sale_items;")
        total_profit = cursor.fetchone()[0]

        cursor.execute("SELECT MIN(sale_timestamp), MAX(sale_timestamp) FROM sales;")
        row = cursor.fetchone()
        earliest_sale = row[0] if row else None
        latest_sale = row[1] if row else None

        return {
            "total_products": total_products,
            "low_stock_products": low_stock_products,
            "total_transactions": total_sales_count,
            "total_revenue": round(total_revenue, 2),
            "total_profit": round(total_profit, 2),
            "earliest_sale": earliest_sale,
            "latest_sale": latest_sale,
        }
    finally:
        conn.close()


def get_schema_string() -> str:
    """Returns SQLite DDL schema description for LLM prompt context."""
    return SCHEMA_SQL.strip()
