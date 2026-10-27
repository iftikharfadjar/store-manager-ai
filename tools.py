"""
Tools module for the Mini Market Chatbot.
Provides LangChain @tool decorated functions for inventory management,
sales calculation, profit analysis, and ad-hoc read-only SQLite queries.
"""

from datetime import datetime, timedelta
import re
from typing import Any, Dict, List, Optional
from langchain_core.tools import tool

from database import DB_PATH, get_connection, get_schema_string


def _normalize_date_range(start_date: Optional[str], end_date: Optional[str]) -> tuple[str, str]:
    """
    Normalizes date strings to full datetime bounds.
    E.g. '2026-10-27' -> start '2026-10-27 00:00:00', end '2026-10-27 23:59:59'
    """
    now = datetime(2026, 10, 27, 23, 59, 59)
    
    if not start_date and not end_date:
        start_str = (now - timedelta(days=7)).strftime("%Y-%m-%d 00:00:00")
        end_str = now.strftime("%Y-%m-%d 23:59:59")
        return start_str, end_str

    if start_date and len(start_date.strip()) == 10:
        start_str = f"{start_date.strip()} 00:00:00"
    elif start_date:
        start_str = start_date.strip()
    else:
        start_str = "2020-01-01 00:00:00"

    if end_date and len(end_date.strip()) == 10:
        end_str = f"{end_date.strip()} 23:59:59"
    elif end_date:
        end_str = end_date.strip()
    else:
        end_str = now.strftime("%Y-%m-%d 23:59:59")

    return start_str, end_str


@tool
def check_inventory(category: Optional[str] = None, low_stock_only: bool = False) -> Dict[str, Any]:
    """
    Check stock management and inventory levels in the mini market.
    
    Args:
        category: Optional category name to filter by (e.g. 'Beverages', 'Snacks & Confectionery', 'Dairy & Eggs', 'Instant Foods', 'Personal Care & Household').
        low_stock_only: If True, only returns items whose current stock is at or below their reorder threshold.
    
    Returns:
        Dictionary containing inventory summary and a list of products with current stock, threshold, and status.
    """
    conn = get_connection(DB_PATH)
    try:
        cursor = conn.cursor()
        query = """
            SELECT p.id, p.name, c.name as category, p.stock_quantity, p.reorder_threshold, 
                   p.unit, p.cost_price, p.selling_price,
                   ROUND(p.stock_quantity * p.cost_price, 2) as inventory_value,
                   CASE WHEN p.stock_quantity <= p.reorder_threshold THEN 'LOW_STOCK' ELSE 'OK' END as status
            FROM products p
            JOIN categories c ON p.category_id = c.id
            WHERE 1=1
        """
        params: List[Any] = []
        if category:
            query += " AND LOWER(c.name) LIKE ?"
            params.append(f"%{category.strip().lower()}%")
        if low_stock_only:
            query += " AND p.stock_quantity <= p.reorder_threshold"
        
        query += " ORDER BY (p.stock_quantity <= p.reorder_threshold) DESC, p.stock_quantity ASC;"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        items = []
        low_stock_count = 0
        total_units = 0
        total_value = 0.0
        
        for r in rows:
            is_low = r["status"] == "LOW_STOCK"
            if is_low:
                low_stock_count += 1
            total_units += r["stock_quantity"]
            total_value += r["inventory_value"]
            
            items.append({
                "product_id": r["id"],
                "name": r["name"],
                "category": r["category"],
                "current_stock": r["stock_quantity"],
                "reorder_threshold": r["reorder_threshold"],
                "unit": r["unit"],
                "cost_price": r["cost_price"],
                "selling_price": r["selling_price"],
                "inventory_value": r["inventory_value"],
                "status": "REORDER NEEDED" if is_low else "IN STOCK",
            })
            
        return {
            "total_products_listed": len(items),
            "low_stock_alerts_count": low_stock_count,
            "total_units_in_stock": total_units,
            "total_inventory_cost_value": round(total_value, 2),
            "products": items,
        }
    finally:
        conn.close()


@tool
def get_sales_and_profit(
    start_date: str,
    end_date: str,
    product_name: Optional[str] = None,
    category: Optional[str] = None
) -> Dict[str, Any]:
    """
    Calculate sales performance, units sold, gross revenue, cost of goods sold (COGS),
    and net/gross profit for a specific time window.
    
    Args:
        start_date: Start date string (format: 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM:SS').
        end_date: End date string (format: 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM:SS').
        product_name: Optional product name filter (e.g. 'Fresh Milk 1L').
        category: Optional category name filter (e.g. 'Beverages').
        
    Returns:
        Detailed financial metrics: items sold count, revenue, COGS, gross profit, margin %, and transaction count.
    """
    start_dt, end_dt = _normalize_date_range(start_date, end_date)
    conn = get_connection(DB_PATH)
    try:
        cursor = conn.cursor()
        
        # Base query joining sales and sale_items
        query = """
            SELECT 
                COUNT(DISTINCT s.id) as total_receipts,
                COALESCE(SUM(si.quantity), 0) as total_items_sold,
                COALESCE(SUM(si.subtotal), 0) as total_revenue,
                COALESCE(SUM(si.quantity * si.unit_cost), 0) as total_cogs,
                COALESCE(SUM(si.profit), 0) as gross_profit
            FROM sales s
            JOIN sale_items si ON s.id = si.sale_id
            JOIN products p ON si.product_id = p.id
            JOIN categories c ON p.category_id = c.id
            WHERE s.sale_timestamp BETWEEN ? AND ?
        """
        params: List[Any] = [start_dt, end_dt]
        
        if product_name:
            query += " AND LOWER(p.name) LIKE ?"
            params.append(f"%{product_name.strip().lower()}%")
            
        if category:
            query += " AND LOWER(c.name) LIKE ?"
            params.append(f"%{category.strip().lower()}%")
            
        cursor.execute(query, params)
        row = cursor.fetchone()
        
        total_receipts = row["total_receipts"]
        total_items_sold = row["total_items_sold"]
        total_revenue = round(row["total_revenue"], 2)
        total_cogs = round(row["total_cogs"], 2)
        gross_profit = round(row["gross_profit"], 2)
        margin_pct = round((gross_profit / total_revenue * 100), 2) if total_revenue > 0 else 0.0
        
        # Get item breakdown top 5 in this period
        item_breakdown_query = """
            SELECT p.name, c.name as category,
                   SUM(si.quantity) as units_sold,
                   ROUND(SUM(si.subtotal), 2) as revenue,
                   ROUND(SUM(si.profit), 2) as profit
            FROM sales s
            JOIN sale_items si ON s.id = si.sale_id
            JOIN products p ON si.product_id = p.id
            JOIN categories c ON p.category_id = c.id
            WHERE s.sale_timestamp BETWEEN ? AND ?
        """
        item_params: List[Any] = [start_dt, end_dt]
        if product_name:
            item_breakdown_query += " AND LOWER(p.name) LIKE ?"
            item_params.append(f"%{product_name.strip().lower()}%")
        if category:
            item_breakdown_query += " AND LOWER(c.name) LIKE ?"
            item_params.append(f"%{category.strip().lower()}%")
            
        item_breakdown_query += " GROUP BY p.id, p.name ORDER BY units_sold DESC LIMIT 5;"
        cursor.execute(item_breakdown_query, item_params)
        top_items = [
            {
                "product": r["name"],
                "category": r["category"],
                "units_sold": r["units_sold"],
                "revenue": r["revenue"],
                "profit": r["profit"],
            }
            for r in cursor.fetchall()
        ]
        
        return {
            "period": {"start": start_dt, "end": end_dt},
            "total_transactions": total_receipts,
            "total_items_sold": total_items_sold,
            "total_revenue": total_revenue,
            "total_cogs": total_cogs,
            "gross_profit": gross_profit,
            "gross_margin_percentage": f"{margin_pct}%",
            "top_products_in_period": top_items,
        }
    finally:
        conn.close()


@tool
def get_top_selling_products(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    order_by: str = "volume",
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    Get ranking of best selling products ordered by volume (quantity sold) or profit.
    
    Args:
        start_date: Optional start date (e.g. '2026-10-01').
        end_date: Optional end date (e.g. '2026-10-27').
        order_by: Metric to rank by: 'volume' (default, most units sold) or 'profit' (highest gross profit) or 'revenue'.
        limit: Number of top items to return (default: 5, max: 20).
        
    Returns:
        List of top products with units sold, revenue, profit, and profit margin.
    """
    start_dt, end_dt = _normalize_date_range(start_date, end_date)
    conn = get_connection(DB_PATH)
    try:
        cursor = conn.cursor()
        
        order_clause = "SUM(si.quantity) DESC"
        if order_by.lower() == "profit":
            order_clause = "SUM(si.profit) DESC"
        elif order_by.lower() == "revenue":
            order_clause = "SUM(si.subtotal) DESC"
            
        limit = max(1, min(limit, 20))
        
        query = f"""
            SELECT p.id, p.name, c.name as category,
                   p.selling_price, p.cost_price, p.stock_quantity as current_stock,
                   SUM(si.quantity) as units_sold,
                   ROUND(SUM(si.subtotal), 2) as total_revenue,
                   ROUND(SUM(si.profit), 2) as total_profit,
                   ROUND((SUM(si.profit) / SUM(si.subtotal)) * 100, 2) as margin_pct
            FROM sales s
            JOIN sale_items si ON s.id = si.sale_id
            JOIN products p ON si.product_id = p.id
            JOIN categories c ON p.category_id = c.id
            WHERE s.sale_timestamp BETWEEN ? AND ?
            GROUP BY p.id, p.name, c.name
            ORDER BY {order_clause}
            LIMIT ?;
        """
        cursor.execute(query, (start_dt, end_dt, limit))
        rows = cursor.fetchall()
        
        return [
            {
                "rank": idx + 1,
                "product_name": r["name"],
                "category": r["category"],
                "current_stock": r["current_stock"],
                "units_sold": r["units_sold"],
                "revenue": r["total_revenue"],
                "profit": r["total_profit"],
                "margin_pct": f"{r['margin_pct']}%",
            }
            for idx, r in enumerate(rows)
        ]
    finally:
        conn.close()


@tool
def query_database_readonly(sql_query: str) -> Dict[str, Any]:
    """
    Executes a read-only SQLite SELECT query to answer specific or ad-hoc questions.
    Only SELECT statements are allowed. Schema:
    - categories (id, name, description)
    - products (id, name, category_id, cost_price, selling_price, stock_quantity, reorder_threshold, unit)
    - sales (id, receipt_number, sale_timestamp, total_amount, payment_method)
    - sale_items (id, sale_id, product_id, quantity, unit_cost, unit_price, subtotal, profit)
    
    Args:
        sql_query: Valid SQLite SELECT statement.
        
    Returns:
        Query results as rows or an error message.
    """
    clean_query = sql_query.strip()
    # Security check: Disallow modifying statements
    prohibited_keywords = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "ATTACH", "DETACH", "REPLACE"]
    first_word = clean_query.split()[0].upper() if clean_query else ""
    
    if first_word != "SELECT" and first_word != "WITH":
        return {"error": "Security rejection: Only SELECT and WITH (CTE) queries are permitted."}
        
    for kw in prohibited_keywords:
        if re.search(rf"\b{kw}\b", clean_query, re.IGNORECASE):
            return {"error": f"Security rejection: Keyword '{kw}' is not permitted."}
            
    conn = get_connection(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute(clean_query)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        results = [dict(zip(columns, row)) for row in rows[:50]]  # limit to 50 rows
        
        return {
            "columns": columns,
            "row_count": len(rows),
            "sample_rows": results,
            "note": "Output limited to top 50 rows for brevity" if len(rows) > 50 else "All rows included",
        }
    except Exception as e:
        return {"error": f"SQL Execution error: {str(e)}"}
    finally:
        conn.close()


ALL_TOOLS = [
    check_inventory,
    get_sales_and_profit,
    get_top_selling_products,
    query_database_readonly,
]
