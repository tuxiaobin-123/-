import unittest

from agents.flood_agents import FloodAgentOrchestrator, build_agent_architecture_v2


class MultiAgentOrchestratorTests(unittest.TestCase):
    def test_demo_orchestrator_runs_all_agents(self):
        result = FloodAgentOrchestrator().run(
            {
                "scenario": "strong_rain_release",
                "rainfall_mm_h": 46.0,
                "gate_release_m3s": 900.0,
                "downstream_level_m": 50.5,
            }
        )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["graph_runtime"] in {"sequential_fallback", "langgraph"}, True)
        self.assertEqual(result["agent_count"], 5)
        self.assertEqual([step["agent"] for step in result["trace"]], ["sensor", "simulation", "risk", "dispatch", "report"])
        self.assertIn("pinn_swe", result["simulation"])
        self.assertIn("enkf", result["risk"])
        self.assertIn("a_star_route", result["dispatch"])
        self.assertGreaterEqual(result["risk"]["risk_score"], 0)

    def test_architecture_v2_contains_required_technologies(self):
        architecture = build_agent_architecture_v2()
        text = " ".join(
            [architecture["orchestrator"], *[agent["tech"] for agent in architecture["agents"]]]
        )

        self.assertIn("LangGraph", text)
        self.assertIn("PINN-SWE", text)
        self.assertIn("EnKF", text)
        self.assertIn("MC Dropout", text)
        self.assertIn("A*", text)
        self.assertIn("Ant Colony", text)
        self.assertIn("Redis", architecture["shared_memory"])

    def test_demo_result_is_browser_friendly_summary(self):
        result = FloodAgentOrchestrator().run_demo_summary()

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["agent_flow"], "sensor -> simulation -> risk -> dispatch -> report")
        self.assertIn("risk_level", result)
        self.assertIn("route", result)
        self.assertEqual(len(result["steps"]), 5)


if __name__ == "__main__":
    unittest.main()
