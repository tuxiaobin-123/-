import unittest

from agents import flood_agents
from agents.flood_agents import FloodAgentOrchestrator, LLMReasoningAdapter, build_agent_architecture_v2
from routers.flood import MultiAgentRunRequest


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
        self.assertEqual(
            [step["agent"] for step in result["trace"][:5]],
            ["communication", "simulation", "risk", "dispatch", "evaluation"],
        )
        self.assertIn("message_route", result["communication"])
        self.assertIn("pinn_swe", result["simulation"])
        self.assertIn("enkf", result["risk"])
        self.assertIn("a_star_route", result["dispatch"])
        self.assertIn("plan_score", result["evaluation"])
        self.assertIn("serial_pipeline", result["collaboration_modes"])
        self.assertIn("parallel_merge", result["collaboration_modes"])
        self.assertIn("evaluation_loop", result["collaboration_modes"])
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
        self.assertIn("multi-criteria", text)
        self.assertIn("message routing", text)
        self.assertIn("Redis", architecture["shared_memory"])
        self.assertIn("serial_pipeline", architecture["collaboration_modes"])
        self.assertIn("parallel_merge", architecture["collaboration_modes"])
        self.assertIn("evaluation_loop", architecture["collaboration_modes"])

    def test_demo_result_is_browser_friendly_summary(self):
        result = FloodAgentOrchestrator().run_demo_summary()

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["agent_flow"], "communication -> simulation -> risk -> dispatch -> evaluation")
        self.assertIn("risk_level", result)
        self.assertIn("route", result)
        self.assertEqual(len(result["steps"]), 5)
        self.assertIn("plan_score", result)

    def test_communication_agent_routes_natural_language_instruction(self):
        result = FloodAgentOrchestrator().run(
            {
                "user_instruction": "请按强降雨情景评估下游学校和医院风险，并给出调度路线",
                "rainfall_mm_h": 70.0,
                "gate_release_m3s": 720.0,
            }
        )

        self.assertEqual(result["communication"]["message_route"]["intent"], "risk_dispatch")
        self.assertIn("simulation", result["communication"]["message_route"]["target_agents"])
        self.assertIn("dispatch", result["communication"]["message_route"]["target_agents"])

    def test_evaluation_loop_can_trigger_replan(self):
        result = FloodAgentOrchestrator().run(
            {
                "rainfall_mm_h": 95.0,
                "gate_release_m3s": 1100.0,
                "min_plan_score": 95.0,
                "max_replans": 1,
            }
        )

        self.assertEqual(result["replan_count"], 1)
        self.assertEqual(result["collaboration_modes"]["evaluation_loop"]["status"], "triggered")
        self.assertEqual([step["agent"] for step in result["trace"][-2:]], ["dispatch", "evaluation"])

    def test_api_run_request_preserves_agent_control_fields(self):
        payload = MultiAgentRunRequest(
            user_instruction="请重新评估调度方案",
            rainfall_mm_h=95.0,
            gate_release_m3s=1100.0,
            min_plan_score=95.0,
            max_replans=1,
        ).model_dump()

        result = FloodAgentOrchestrator().run(payload)

        self.assertEqual(result["communication"]["user_instruction"], "请重新评估调度方案")
        self.assertEqual(result["replan_count"], 1)

    def test_reasoning_adapter_falls_back_without_api_key(self):
        adapter = LLMReasoningAdapter(env={})

        result = adapter.reason("sensor", {"rainfall_mm_h": 10})

        self.assertEqual(result["mode"], "deterministic")
        self.assertIn("no LLM API key", result["text"])

    def test_orchestrator_uses_langgraph_runtime_when_available(self):
        class FakeCompiledGraph:
            def invoke(self, state):
                return FloodAgentOrchestrator()._run_sequential(state)

        class FakeStateGraph:
            def __init__(self, _state_type):
                self.nodes = {}

            def add_node(self, name, fn):
                self.nodes[name] = fn

            def set_entry_point(self, _name):
                pass

            def add_edge(self, _source, _target):
                pass

            def compile(self):
                return FakeCompiledGraph()

        original_graph = flood_agents.StateGraph
        original_end = flood_agents.END
        try:
            flood_agents.StateGraph = FakeStateGraph
            flood_agents.END = "__end__"
            result = FloodAgentOrchestrator().run()
        finally:
            flood_agents.StateGraph = original_graph
            flood_agents.END = original_end

        self.assertEqual(result["graph_runtime"], "langgraph")
        self.assertEqual(result["status"], "completed")


if __name__ == "__main__":
    unittest.main()
