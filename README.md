# Smart Mini Market Management Chatbot 🏪

An intelligent store management assistant and dashboard built with **Python**, **LangChain**, **LangGraph**, **Streamlit**, and **SQLite**.

The chatbot helps store owners and managers monitor inventory, identify items that need restocking, calculate how many items were sold, and analyze revenues and profits for any given timeframe.

---

## 🚀 Features

1. **💬 Conversational AI Store Manager (`agent.py` & `tools.py`)**:
   - Built with **LangGraph** (cyclic StateGraph) and **LangChain**.
   - Powered by **Google Gemini** (`gemini-3.8-flash`, `gemini-3.8-flash-lite`, `gemini-2.5-flash`, `gemini-2.0-flash`).
   - Maintains conversational memory across multi-turn queries.
   - Transparent tool execution with expanders to inspect reasoning.
2. **📦 Stock & Inventory Management**:
   - Tracks current on-hand stock and reorder thresholds.
   - Highlights items needing restocking immediately (`status = 'REORDER NEEDED'`).
   - Computes total on-hand inventory valuation.
3. **📊 Sales & Profit Analytics**:
   - Calculates total receipts, units sold, gross revenue, Cost of Goods Sold (COGS), and gross profit margin.
   - Dynamic date filtering (e.g., yesterday, this week, custom date ranges).
   - Identifies top-selling items by sales volume and profitability.
4. **🖥️ Modern Streamlit Interface (`app.py`)**:
   - **Tab 1: Chat Assistant** with pre-configured quick prompt buttons and tool execution logs.
   - **Tab 2: Live Inventory** table with category and low-stock filters.
   - **Tab 3: Sales & Profit Dashboard** with interactive date range picker, revenue/profit trend charts, and KPI metric cards.
   - **Sidebar**: One-click database re-seeding, API key management, and real-time database stats.

---

## 🛠️ Project Structure

```text
agent_lang/
├── app.py              # Streamlit frontend & interactive dashboard
├── agent.py            # LangGraph StateGraph agent definition
├── tools.py            # LangChain @tool analytics & safe SQLite queries
├── database.py         # SQLite schema, initial dummy data seeder & helpers
├── minimarket.db       # SQLite database (auto-generated)
├── tests/
│   ├── test_db.py      # Database schema and seeder tests
│   ├── test_tools.py   # Analytical tool validation tests
│   └── test_agent.py   # LangGraph workflow compilation tests
├── .env.example        # Environment variable sample
└── README.md           # Documentation
```

---

## 🏃 Running the Application

### 1. Set your Gemini API Key
You can provide your Google Gemini API key in one of three ways:
1. Export it in your environment:
   ```bash
   export GEMINI_API_KEY="your-gemini-api-key"
   ```
2. Create a `.env` file based on `.env.example`.
3. Enter it directly in the Streamlit sidebar password field when running the app.

### 2. Launch the Streamlit App
```bash
streamlit run app.py
```

### 3. Run the Automated Tests
```bash
python -m unittest discover tests
```

---

## 💡 Example Chat Prompts
- *"Which products have low stock and need urgent reordering?"*
- *"How many items did we sell yesterday, and what was our total profit?"*
- *"Show me the top 5 best selling snacks this month."*
- *"What is our overall sales revenue and profit margin for the last 7 days?"*
- *"Which category generated the highest gross revenue?"*
