"""
Unit test for LangGraph Agent compilation and workflow structure.
"""

import unittest
from agent import create_agent_graph, get_system_prompt
from tools import ALL_TOOLS


class TestAgentWorkflow(unittest.TestCase):
    def test_system_prompt(self):
        prompt = get_system_prompt()
        self.assertIn("Smart Mini Market", prompt)
        self.assertIn("2026-10-27", prompt)
        self.assertIn("check_inventory", prompt)
        self.assertIn("get_sales_and_profit", prompt)

    def test_agent_graph_compilation(self):
        # Verify graph compilation for available models
        for model in ["gemini-3.5-flash-lite", "gemini-3.8-flash"]:
            app = create_agent_graph(api_key="mock_api_key_for_testing", model_name=model)
            self.assertIsNotNone(app)
            nodes = app.get_graph().nodes
            self.assertIn("agent", nodes)
            self.assertIn("tools", nodes)


if __name__ == "__main__":
    unittest.main()
