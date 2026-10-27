"""
LangGraph Agent module for the Mini Market Assistant.
Builds a cyclic StateGraph with LLM and analytical database tools.
"""

from datetime import datetime
import os
from typing import Any, Dict, Iterator, Optional, Sequence
from dotenv import load_dotenv
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage, ToolMessage

# Load environment variables from .env
load_dotenv()
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from database import get_schema_string
from tools import ALL_TOOLS


SYSTEM_PROMPT_TEMPLATE = """You are the intelligent Store Operations & Financial Analyst AI Assistant for "Smart Mini Market".
You assist store owners, managers, and staff in tracking inventory, stock management, sales figures, and financial profit calculations.

CURRENT SYSTEM TIME & DATE:
- Today is: {current_date} ({current_day_name})
- Current Reference Year: 2026
- Interpret relative dates accurately:
  * "Today": {current_date}
  * "Yesterday": {yesterday_date}
  * "This week": From {this_week_start} to {current_date}
  * "This month": From {this_month_start} to {current_date}
  * "Last 30 days": From {thirty_days_ago} to {current_date}

YOUR CAPABILITIES & TOOLS:
1. `check_inventory(category, low_stock_only)`:
   - Check stock levels, item quantities, reorder thresholds, and identify low-stock items that need restocking.
2. `get_sales_and_profit(start_date, end_date, product_name, category)`:
   - Calculate total sales receipts, quantity of items sold, gross revenue, Cost of Goods Sold (COGS), gross profit, and gross profit margin percentage for any specific time window.
3. `get_top_selling_products(start_date, end_date, order_by, limit)`:
   - Find top products ranked by volume (quantity sold) or profit (highest dollar profit).
4. `query_database_readonly(sql_query)`:
   - Run custom SELECT queries on the SQLite database for complex or ad-hoc analytics.

DATABASE SCHEMA:
{schema_sql}

RESPONSE GUIDELINES:
- Always use the tools to retrieve accurate facts and figures; never guess or hallucinate numbers.
- When computing financial figures (revenue, profit, cost), clearly state:
  * Period analyzed (Start date to End date)
  * Total Items/Units Sold
  * Gross Revenue ($)
  * Cost of Goods Sold / COGS ($)
  * Gross Profit ($)
  * Profit Margin (%)
- Use clean Markdown tables and bullet points for comparisons and lists.
- Highlight urgent actions (e.g., items with stock <= reorder threshold that need urgent restocking).
- Be polite, professional, concise, and helpful.
"""


def get_system_prompt() -> str:
    """Generates the system prompt with current date dynamic context."""
    # Reference date anchored to 2026-10-27
    today = datetime(2026, 10, 27)
    yesterday = datetime(2026, 10, 26)
    week_start = datetime(2026, 10, 21)
    month_start = datetime(2026, 10, 1)
    thirty_days_ago = datetime(2026, 9, 27)
    
    return SYSTEM_PROMPT_TEMPLATE.format(
        current_date=today.strftime("%Y-%m-%d"),
        current_day_name=today.strftime("%A"),
        yesterday_date=yesterday.strftime("%Y-%m-%d"),
        this_week_start=week_start.strftime("%Y-%m-%d"),
        this_month_start=month_start.strftime("%Y-%m-%d"),
        thirty_days_ago=thirty_days_ago.strftime("%Y-%m-%d"),
        schema_sql=get_schema_string(),
    )


def create_agent_graph(api_key: Optional[str] = None, model_name: str = "gemini-3.5-flash-lite"):
    """
    Constructs and compiles the LangGraph agent workflow.
    """
    effective_api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    
    # gemini-3.5-flash-lite uses fixed sampling defaults, so omit temperature if using lite
    llm_kwargs = {
        "model": model_name,
        "google_api_key": effective_api_key,
    }
    if "lite" not in model_name.lower():
        llm_kwargs["temperature"] = 0.0

    llm = ChatGoogleGenerativeAI(**llm_kwargs)
    llm_with_tools = llm.bind_tools(ALL_TOOLS)
    system_message = SystemMessage(content=get_system_prompt())

    def call_model(state: MessagesState) -> Dict[str, Any]:
        messages = [system_message] + state["messages"]
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    # Define StateGraph
    workflow = StateGraph(MessagesState)

    # Add Nodes
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", ToolNode(ALL_TOOLS))

    # Add Edges
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", tools_condition, ["tools", END])
    workflow.add_edge("tools", "agent")

    checkpointer = MemorySaver()
    app = workflow.compile(checkpointer=checkpointer)
    return app


def run_agent_turn(
    app: Any,
    user_input: str,
    thread_id: str = "default_user",
) -> Dict[str, Any]:
    """
    Synchronous run of one agent turn, returning tool logs and final response.
    """
    config = {"configurable": {"thread_id": thread_id}}
    events = app.stream(
        {"messages": [HumanMessage(content=user_input)]},
        config=config,
        stream_mode="updates",
    )
    
    tool_events: List[Dict[str, Any]] = []
    final_response = ""

    for event in events:
        for node_name, node_output in event.items():
            if node_name == "tools":
                for msg in node_output.get("messages", []):
                    tool_events.append({
                        "tool": msg.name if hasattr(msg, "name") else "tool",
                        "content": msg.content,
                    })
            elif node_name == "agent":
                for msg in node_output.get("messages", []):
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        for tc in msg.tool_calls:
                            tool_events.append({
                                "tool_call": tc["name"],
                                "args": tc.get("args", {}),
                            })
                    if msg.content and not (hasattr(msg, "tool_calls") and msg.tool_calls):
                        if isinstance(msg.content, str):
                            final_response = msg.content
                        elif isinstance(msg.content, list):
                            text_parts = []
                            for part in msg.content:
                                if isinstance(part, str):
                                    text_parts.append(part)
                                elif isinstance(part, dict) and "text" in part:
                                    text_parts.append(part["text"])
                            final_response = "\n".join(text_parts)
                        else:
                            final_response = str(msg.content)

    return {
        "response": final_response,
        "tool_events": tool_events,
    }
