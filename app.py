"""
Smart Mini Market Chatbot & Management Dashboard.
Built with Streamlit, LangChain, LangGraph, and SQLite.
"""

from datetime import datetime, timedelta
import os
import sqlite3
from dotenv import load_dotenv
import pandas as pd
import streamlit as st

# Load environment variables from .env if present
load_dotenv()

from agent import create_agent_graph, run_agent_turn
from database import DB_PATH, get_connection, get_db_stats, init_db, seed_dummy_data
from tools import check_inventory, get_sales_and_profit, get_top_selling_products

# --- Page Configuration ---
st.set_page_config(
    page_title="Smart Mini Market Assistant",
    page_icon="🏪",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Ensure Database Initialization ---
if not os.path.exists(DB_PATH):
    seed_dummy_data(DB_PATH, days_back=30, force=True)


# --- Session State Initialization ---
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "👋 Hello! I am your **Smart Mini Market AI Assistant**.\n\n"
                "I can help you monitor inventory, track low stock, calculate total items sold, "
                "and analyze revenues and profits for any given time period.\n\n"
                "Try asking me a question below, or click one of the suggested prompts!"
            ),
            "tool_events": [],
        }
    ]

if "thread_id" not in st.session_state:
    st.session_state.thread_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

if "agent_app" not in st.session_state:
    st.session_state.agent_app = None


# --- Helper to Get API Key ---
def get_gemini_api_key(user_entered_key: str) -> str:
    if user_entered_key.strip():
        return user_entered_key.strip()
    env_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if env_key:
        return env_key.strip()
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return str(st.secrets["GEMINI_API_KEY"]).strip()
        if "GOOGLE_API_KEY" in st.secrets:
            return str(st.secrets["GOOGLE_API_KEY"]).strip()
    except Exception:
        pass
    return ""


# --- Sidebar ---
with st.sidebar:
    st.markdown("### :material/store: Smart Mini Market")
    st.caption("AI-Powered Inventory & Profit Analytics")
    st.divider()

    # Settings
    st.markdown("#### :material/settings: Configuration")
    api_key_input = st.text_input(
        "Google Gemini API Key",
        type="password",
        value=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "",
        help="Enter your Gemini API key, or define GEMINI_API_KEY in your environment.",
    )
    active_api_key = get_gemini_api_key(api_key_input)

    model_options = [
        "gemini-3.5-flash-lite",
        "gemini-flash-lite-latest",
        "gemini-3.8-flash",
        "gemini-3.7-flash",
        "gemini-flash-latest",
    ]
    env_model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    default_idx = model_options.index(env_model) if env_model in model_options else 0

    model_name = st.selectbox(
        "Model",
        model_options,
        index=default_idx,
        help="Select Google Gemini model for the LangGraph agent.",
        key="selected_model_name",
    )

    if "current_model" not in st.session_state:
        st.session_state.current_model = model_name
    elif st.session_state.current_model != model_name:
        st.session_state.current_model = model_name
        st.session_state.agent_app = None  # Re-initialize agent graph with newly selected model

    if not active_api_key:
        st.warning(
            "Please provide a Gemini API Key to enable the AI Chatbot.",
            icon=":material/key:",
        )
    else:
        st.success("API Key detected and active.", icon=":material/check_circle:")

    st.divider()

    # Database Status & Tools
    st.markdown("#### :material/database: Database status")
    stats = get_db_stats()
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total items", f"{stats['total_products']}")
        st.metric("Transactions", f"{stats['total_transactions']}")
    with col2:
        st.metric(
            "Low stock alerts",
            f"{stats['low_stock_products']}",
            delta=None if stats["low_stock_products"] == 0 else f"{stats['low_stock_products']} items",
            delta_color="inverse",
        )
        st.metric("Total revenue", f"${stats['total_revenue']:,.2f}")

    if st.button("Reset & re-seed dummy data", icon=":material/refresh:", width="stretch"):
        with st.spinner("Re-seeding 30 days of synthetic transactions..."):
            res = seed_dummy_data(DB_PATH, days_back=30, force=True)
            st.session_state.agent_app = None  # Reset agent state
            st.toast(f"Database refreshed! {res['products']} products, {res['sales']} sales recorded.", icon="✅")
            st.rerun()

    st.divider()
    if st.button("Clear chat history", icon=":material/delete:", width="stretch"):
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "Chat history cleared. How can I help you today?",
                "tool_events": [],
            }
        ]
        st.session_state.thread_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        st.rerun()


# --- Main Navigation Tabs ---
tab_chat, tab_inventory, tab_dashboard = st.tabs([
    ":material/chat: Chat assistant",
    ":material/inventory_2: Live inventory",
    ":material/insights: Sales & profit dashboard",
])


# ==========================================
# TAB 1: Chat Assistant
# ==========================================
with tab_chat:
    st.subheader("Store Manager AI Assistant", anchor=False)
    st.caption("Ask questions about stock levels, low-stock warnings, sales volume, and profit across any date range.")

    # Suggested Prompts
    st.markdown("**Suggested questions:**")
    prompt_cols = st.columns(4)
    suggested_clicked = None

    with prompt_cols[0]:
        if st.button("⚠️ Which items need restocking?", width="stretch"):
            suggested_clicked = "Which items currently have low stock and need urgent restocking?"
    with prompt_cols[1]:
        if st.button("📈 Sales and profit yesterday", width="stretch"):
            suggested_clicked = "How many items did we sell yesterday, and what was our total revenue and gross profit?"
    with prompt_cols[2]:
        if st.button("🏆 Top 5 best sellers this month", width="stretch"):
            suggested_clicked = "Show me the top 5 best selling products this month by sales volume and profit."
    with prompt_cols[3]:
        if st.button("💰 Overall 7-day profit margin", width="stretch"):
            suggested_clicked = "What is our overall sales revenue, COGS, and profit margin for the last 7 days?"

    # Render Chat History
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.messages:
            avatar = "🤖" if msg["role"] == "assistant" else "👤"
            with st.chat_message(msg["role"], avatar=avatar):
                # If there were tool events, show in expander
                if msg.get("tool_events"):
                    with st.expander("🛠️ View agent reasoning & tool execution", expanded=False):
                        for event in msg["tool_events"]:
                            if "tool_call" in event:
                                st.code(f"Tool Called: {event['tool_call']}\nArguments: {event['args']}", language="python")
                            elif "tool" in event:
                                st.write(f"**Result from `{event['tool']}`:**")
                                st.json(event["content"])
                st.markdown(msg["content"])

    # Chat Input
    user_prompt = st.chat_input("Ask about stock levels, sales numbers, or profit...") or suggested_clicked

    if user_prompt:
        # Check API Key
        if not active_api_key:
            st.error("Please enter a Google Gemini API Key in the left sidebar to use the chat assistant.", icon=":material/key:")
        else:
            # Add user message to UI
            st.session_state.messages.append({"role": "user", "content": user_prompt, "tool_events": []})
            with st.chat_message("user", avatar="👤"):
                st.markdown(user_prompt)

            # Generate Agent Response
            with st.chat_message("assistant", avatar="🤖"):
                with st.status("Analyzing store data...", expanded=True) as status_box:
                    try:
                        # Lazy create or reuse agent
                        if st.session_state.agent_app is None:
                            st.session_state.agent_app = create_agent_graph(
                                api_key=active_api_key,
                                model_name=model_name,
                            )
                        
                        agent_result = run_agent_turn(
                            app=st.session_state.agent_app,
                            user_input=user_prompt,
                            thread_id=st.session_state.thread_id,
                        )

                        # Display tools used in status
                        tool_events = agent_result["tool_events"]
                        if tool_events:
                            for event in tool_events:
                                if "tool_call" in event:
                                    st.write(f"⚙️ Invoked `{event['tool_call']}` with {event['args']}")
                            status_box.update(label="Calculations complete!", state="complete", expanded=False)
                        else:
                            status_box.update(label="Response ready!", state="complete", expanded=False)

                        final_text = agent_result["response"] or "I've analyzed the database, but no final response was produced."
                        st.markdown(final_text)

                        # Save to history
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": final_text,
                            "tool_events": tool_events,
                        })

                    except Exception as e:
                        status_box.update(label="Error executing request", state="error", expanded=True)
                        err_msg = f"An error occurred while interacting with the agent: `{str(e)}`"
                        st.error(err_msg)
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": err_msg,
                            "tool_events": [],
                        })


# ==========================================
# TAB 2: Live Inventory
# ==========================================
with tab_inventory:
    st.subheader("Inventory Stock Management", anchor=False)
    
    # Filter Controls
    fcol1, fcol2 = st.columns([3, 1], vertical_alignment="bottom")
    with fcol1:
        # Load categories
        conn = get_connection(DB_PATH)
        cat_df = pd.read_sql_query("SELECT id, name FROM categories ORDER BY name;", conn)
        conn.close()
        categories = ["All Categories"] + cat_df["name"].tolist()
        selected_cat = st.selectbox("Filter by Category", categories, index=0)

    with fcol2:
        low_stock_only = st.toggle("Show Low Stock Only", value=False)

    # Fetch inventory data
    cat_arg = None if selected_cat == "All Categories" else selected_cat
    inv_data = check_inventory.invoke({"category": cat_arg, "low_stock_only": low_stock_only})
    
    # Summary KPI cards
    mcol1, mcol2, mcol3, mcol4 = st.columns(4)
    with mcol1:
        with st.container(border=True):
            st.metric("Listed Products", inv_data["total_products_listed"])
    with mcol2:
        with st.container(border=True):
            st.metric(
                "Restock Needed",
                inv_data["low_stock_alerts_count"],
                delta=f"{inv_data['low_stock_alerts_count']} alerts" if inv_data["low_stock_alerts_count"] > 0 else "Optimal",
                delta_color="inverse",
            )
    with mcol3:
        with st.container(border=True):
            st.metric("Total Units on Shelf", f"{inv_data['total_units_in_stock']:,}")
    with mcol4:
        with st.container(border=True):
            st.metric("Inventory Cost Value", f"${inv_data['total_inventory_cost_value']:,.2f}")

    # Table Display
    if inv_data["products"]:
        df_inv = pd.DataFrame(inv_data["products"])
        # Format DataFrame
        df_display = df_inv[[
            "name", "category", "current_stock", "reorder_threshold", "unit",
            "cost_price", "selling_price", "inventory_value", "status"
        ]].rename(columns={
            "name": "Product Name",
            "category": "Category",
            "current_stock": "Current Stock",
            "reorder_threshold": "Min Threshold",
            "unit": "Unit",
            "cost_price": "Cost ($)",
            "selling_price": "Price ($)",
            "inventory_value": "Total Value ($)",
            "status": "Stock Status",
        })

        st.dataframe(
            df_display,
            width="stretch",
            hide_index=True,
            column_config={
                "Current Stock": st.column_config.NumberColumn(format="%d"),
                "Cost ($)": st.column_config.NumberColumn(format="$%.2f"),
                "Price ($)": st.column_config.NumberColumn(format="$%.2f"),
                "Total Value ($)": st.column_config.NumberColumn(format="$%.2f"),
                "Stock Status": st.column_config.TextColumn(),
            },
        )
    else:
        st.info("No products match the selected criteria.", icon=":material/info:")


# ==========================================
# TAB 3: Sales & Profit Dashboard
# ==========================================
with tab_dashboard:
    st.subheader("Sales & Profit Analytics", anchor=False)

    # Date Range Selector
    dcol1, dcol2 = st.columns(2)
    default_end = datetime(2026, 10, 27).date()
    default_start = default_end - timedelta(days=29)

    with dcol1:
        start_date_val = st.date_input("Start Date", value=default_start)
    with dcol2:
        end_date_val = st.date_input("End Date", value=default_end)

    start_str = start_date_val.strftime("%Y-%m-%d")
    end_str = end_date_val.strftime("%Y-%m-%d")

    # Fetch sales metrics
    sales_metrics = get_sales_and_profit.invoke({"start_date": start_str, "end_date": end_str})

    # KPI Metric Cards
    kpi_col1, kpi_col2, kpi_col3, kpi_col4, kpi_col5 = st.columns(5)
    with kpi_col1:
        with st.container(border=True):
            st.metric("Total Revenue", f"${sales_metrics['total_revenue']:,.2f}")
    with kpi_col2:
        with st.container(border=True):
            st.metric("COGS (Cost)", f"${sales_metrics['total_cogs']:,.2f}")
    with kpi_col3:
        with st.container(border=True):
            st.metric("Gross Profit", f"${sales_metrics['gross_profit']:,.2f}")
    with kpi_col4:
        with st.container(border=True):
            st.metric("Profit Margin", sales_metrics["gross_margin_percentage"])
    with kpi_col5:
        with st.container(border=True):
            st.metric("Units Sold", f"{sales_metrics['total_items_sold']:,}")

    st.divider()

    # Charts: Daily Trend & Top Products
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.markdown("##### 📅 Daily Revenue & Profit Trend")
        conn = get_connection(DB_PATH)
        daily_df = pd.read_sql_query(
            """
            SELECT DATE(s.sale_timestamp) as sale_day,
                   ROUND(SUM(si.subtotal), 2) as Revenue,
                   ROUND(SUM(si.profit), 2) as Profit
            FROM sales s
            JOIN sale_items si ON s.id = si.sale_id
            WHERE s.sale_timestamp BETWEEN ? AND ?
            GROUP BY sale_day
            ORDER BY sale_day ASC;
            """,
            conn,
            params=(f"{start_str} 00:00:00", f"{end_str} 23:59:59"),
        )
        conn.close()

        if not daily_df.empty:
            daily_df["sale_day"] = pd.to_datetime(daily_df["sale_day"])
            daily_df = daily_df.set_index("sale_day")
            st.line_chart(daily_df, width="stretch")
        else:
            st.info("No transaction data in this period.")

    with chart_col2:
        st.markdown("##### 🏆 Top 5 Selling Products by Volume")
        top_items = get_top_selling_products.invoke({
            "start_date": start_str,
            "end_date": end_str,
            "order_by": "volume",
            "limit": 5,
        })
        if top_items:
            top_df = pd.DataFrame(top_items)
            chart_data = top_df[["product_name", "units_sold"]].set_index("product_name")
            st.bar_chart(chart_data, width="stretch")
        else:
            st.info("No product sales data in this period.")
