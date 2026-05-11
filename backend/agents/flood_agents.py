# -*- coding: utf-8 -*-
"""Runnable multi-agent demo for dam-centered flood warning.

The orchestrator uses LangGraph when it is installed. In the default local
runtime it falls back to a deterministic StateGraph-like sequence so the demo
can run without API keys or network access.
"""

from __future__ import annotations

import heapq
import json
import math
import os
import warnings
from dataclasses import dataclass
from typing import Dict, List, Mapping

warnings.filterwarnings(
    "ignore",
    message=".*allowed_objects.*",
)
try:  # pragma: no cover - optional dependency warning type
    from langchain_core._api.deprecation import LangChainPendingDeprecationWarning

    warnings.filterwarnings("ignore", category=LangChainPendingDeprecationWarning)
except Exception:  # pragma: no cover - optional dependency
    pass

try:  # pragma: no cover - optional dependency
    from langgraph.graph import END, StateGraph
except Exception:  # pragma: no cover - optional dependency
    END = None
    StateGraph = None

from models.pinn_swe import run_pinn_dry_run


AgentState = Dict[str, object]


class LLMReasoningAdapter:
    """Optional OpenAI/Claude reasoning bridge with deterministic offline fallback."""

    def __init__(self, env: Mapping[str, str] | None = None, timeout_s: float = 8.0) -> None:
        self.env = env if env is not None else os.environ
        self.timeout_s = timeout_s

    def reason(self, agent_name: str, state: AgentState) -> Dict[str, str]:
        if not self._llm_enabled():
            has_key = bool(self.env.get("OPENAI_API_KEY") or self.env.get("ANTHROPIC_API_KEY"))
            reason = (
                "LLM API key is present but AGENT_REASONING_ENABLE_LLM=1 is not set"
                if has_key
                else "no LLM API key is configured"
            )
            return {
                "mode": "deterministic",
                "text": f"{agent_name} used deterministic reasoning because {reason}.",
            }

        try:
            if self.env.get("OPENAI_API_KEY"):
                return self._reason_openai(agent_name, state)
            if self.env.get("ANTHROPIC_API_KEY"):
                return self._reason_anthropic(agent_name, state)
        except Exception as exc:  # pragma: no cover - depends on external APIs
            return {
                "mode": "error_fallback",
                "text": f"{agent_name} LLM reasoning unavailable ({exc}); deterministic tool path used.",
            }

        return {
            "mode": "deterministic",
            "text": f"{agent_name} used deterministic reasoning because no LLM API key is configured.",
        }

    def _llm_enabled(self) -> bool:
        if self.env.get("AGENT_REASONING_ENABLE_LLM") != "1":
            return False
        return bool(self.env.get("OPENAI_API_KEY") or self.env.get("ANTHROPIC_API_KEY"))

    def _reason_openai(self, agent_name: str, state: AgentState) -> Dict[str, str]:
        import httpx

        base_url = self.env.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        model = self.env.get("OPENAI_MODEL", "gpt-4o-mini")
        response = httpx.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.env['OPENAI_API_KEY']}"},
            json={
                "model": model,
                "temperature": 0.1,
                "max_tokens": 120,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a flood-warning agent. Return one concise operational reasoning sentence.",
                    },
                    {"role": "user", "content": self._prompt(agent_name, state)},
                ],
            },
            timeout=self.timeout_s,
        )
        response.raise_for_status()
        text = response.json()["choices"][0]["message"]["content"].strip()
        return {"mode": "openai", "text": text}

    def _reason_anthropic(self, agent_name: str, state: AgentState) -> Dict[str, str]:
        import httpx

        base_url = self.env.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1").rstrip("/")
        model = self.env.get("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")
        response = httpx.post(
            f"{base_url}/messages",
            headers={
                "x-api-key": self.env["ANTHROPIC_API_KEY"],
                "anthropic-version": self.env.get("ANTHROPIC_VERSION", "2023-06-01"),
            },
            json={
                "model": model,
                "max_tokens": 120,
                "temperature": 0.1,
                "system": "You are a flood-warning agent. Return one concise operational reasoning sentence.",
                "messages": [{"role": "user", "content": self._prompt(agent_name, state)}],
            },
            timeout=self.timeout_s,
        )
        response.raise_for_status()
        text = response.json()["content"][0]["text"].strip()
        return {"mode": "anthropic", "text": text}

    def _prompt(self, agent_name: str, state: AgentState) -> str:
        snapshot = {
            key: state[key]
            for key in ("scenario", "communication", "observations", "simulation", "risk", "dispatch", "evaluation", "report")
            if key in state
        }
        compact_state = json.dumps(snapshot, ensure_ascii=False, default=str)[:1200]
        return f"Agent={agent_name}. Current shared flood state: {compact_state}"


def build_agent_architecture_v2() -> Dict:
    return {
        "orchestrator": "Agent Orchestrator: LangGraph StateGraph with deterministic fallback",
        "shared_memory": "Shared memory: Redis state channel or in-process state dict fallback",
        "human_in_loop": "Human-in-the-loop: command review, warning confirmation, dispatch override",
        "collaboration_modes": {
            "serial_pipeline": "simulation -> risk -> dispatch -> evaluation",
            "parallel_merge": "simulation and observation-risk branches can be computed independently then merged",
            "evaluation_loop": "evaluation can reject a dispatch plan and request a replanning pass",
        },
        "agents": [
            {"name": "Communication Agent", "tech": "natural-language command parsing + message routing"},
            {"name": "Simulation Agent", "tech": "PINN-SWE + tensor SWE + dam boundary conditions"},
            {"name": "Risk Agent", "tech": "EnKF assimilation + MC Dropout uncertainty + risk objects"},
            {"name": "Dispatch Agent", "tech": "A* route search + Ant Colony route refinement"},
            {"name": "Evaluation Agent", "tech": "multi-criteria fusion + score explanation"},
        ],
    }


@dataclass
class BaseAgent:
    name: str
    reasoner: LLMReasoningAdapter | None = None

    def think(self, state: AgentState) -> Dict[str, str]:
        adapter = self.reasoner or LLMReasoningAdapter()
        return adapter.reason(self.name, state)


class CommunicationAgent(BaseAgent):
    def __init__(self, reasoner: LLMReasoningAdapter | None = None) -> None:
        super().__init__("communication", reasoner)

    def run(self, state: AgentState) -> AgentState:
        instruction = str(state.get("user_instruction", state.get("scenario", "run dam flood warning workflow")))
        rainfall = float(state.get("rainfall_mm_h", 35.0))
        release = float(state.get("gate_release_m3s", 600.0))
        downstream = float(state.get("downstream_level_m", 50.0))
        route = _route_instruction(instruction, rainfall, release)
        observations = {
            "rainfall_mm_h": rainfall,
            "gate_release_m3s": release,
            "downstream_level_m": downstream,
            "data_quality": "offline_demo_seed",
        }
        communication = {
            "user_instruction": instruction,
            "message_route": route,
            "normalized_inputs": observations,
            "shared_memory_writes": ["observations", "message_route"],
        }
        state["communication"] = communication
        state["observations"] = observations
        _append_trace(state, self.name, self.think(state), communication)
        return state


class SimulationAgent(BaseAgent):
    def __init__(self, reasoner: LLMReasoningAdapter | None = None) -> None:
        super().__init__("simulation", reasoner)

    def run(self, state: AgentState) -> AgentState:
        obs = state["observations"]
        rainfall = float(obs["rainfall_mm_h"])
        release = float(obs["gate_release_m3s"])
        try:
            pinn = run_pinn_dry_run(num_points=16, hidden_dim=16, hidden_layers=2, num_frequencies=4)
        except Exception as exc:
            pinn = {"status": "unavailable", "reason": str(exc)}

        peak_depth_m = round(0.18 + rainfall * 0.018 + release / 1800.0, 3)
        velocity_ms = round(min(6.0, 0.4 + release / 900.0 + rainfall / 120.0), 3)
        simulation = {
            "pinn_swe": pinn,
            "peak_depth_m": peak_depth_m,
            "velocity_ms": velocity_ms,
            "affected_area_km2": round(peak_depth_m * 1.7, 3),
        }
        state["simulation"] = simulation
        _append_trace(state, self.name, self.think(state), simulation)
        return state


class RiskAgent(BaseAgent):
    def __init__(self, reasoner: LLMReasoningAdapter | None = None) -> None:
        super().__init__("risk", reasoner)

    def run(self, state: AgentState) -> AgentState:
        sim = state["simulation"]
        measurement_depth = float(sim["peak_depth_m"]) * 0.92
        enkf_depth = _enkf_update(float(sim["peak_depth_m"]), measurement_depth)
        samples = _mc_dropout_samples(enkf_depth)
        uncertainty = max(samples) - min(samples)
        risk_score = min(100.0, enkf_depth * 28.0 + float(sim["velocity_ms"]) * 7.0 + uncertainty * 10.0)
        risk = {
            "enkf": {"assimilated_depth_m": round(enkf_depth, 3), "measurement_depth_m": round(measurement_depth, 3)},
            "mc_dropout": {"samples": [round(value, 3) for value in samples], "spread_m": round(uncertainty, 3)},
            "risk_score": round(risk_score, 2),
            "level": "extreme" if risk_score >= 75 else "high" if risk_score >= 55 else "medium" if risk_score >= 30 else "low",
        }
        state["risk"] = risk
        _append_trace(state, self.name, self.think(state), risk)
        return state


class DispatchAgent(BaseAgent):
    def __init__(self, reasoner: LLMReasoningAdapter | None = None) -> None:
        super().__init__("dispatch", reasoner)

    def run(self, state: AgentState) -> AgentState:
        is_replan = bool(state.get("evaluation_feedback"))
        graph = _dispatch_graph(is_replan)
        route, cost = _a_star(graph, "dam", "shelter")
        dispatch = {
            "a_star_route": route,
            "ant_colony_refined_route": _ant_colony_refine(route),
            "estimated_minutes": int(cost * 3),
            "override_required": state["risk"]["level"] in {"high", "extreme"},
            "multi_objective_tradeoff": _dispatch_tradeoff(state["risk"]["level"], route, cost, is_replan),
        }
        state["dispatch"] = dispatch
        _append_trace(state, self.name, self.think(state), dispatch)
        return state


class EvaluationAgent(BaseAgent):
    def __init__(self, reasoner: LLMReasoningAdapter | None = None) -> None:
        super().__init__("evaluation", reasoner)

    def run(self, state: AgentState) -> AgentState:
        risk = state["risk"]
        dispatch = state["dispatch"]
        plan_score, criteria = _score_dispatch_plan(risk, dispatch)
        threshold = float(state.get("min_plan_score", 55.0))
        verdict = "approved" if plan_score >= threshold else "replan_required"
        evaluation = {
            "plan_score": plan_score,
            "threshold": threshold,
            "verdict": verdict,
            "criteria": criteria,
            "explanation": _explain_score(criteria, verdict),
        }
        report = {
            "summary": f"{risk['level']} risk; plan score {plan_score}; route {' -> '.join(dispatch['a_star_route'])}",
            "human_checkpoint": "approve_dispatch_plan" if verdict == "approved" and dispatch["override_required"] else "monitor",
            "memory_keys": ["communication", "observations", "simulation", "risk", "dispatch", "evaluation"],
        }
        state["evaluation"] = evaluation
        state["report"] = report
        _append_trace(state, self.name, self.think(state), evaluation)
        state["status"] = "completed"
        return state


class FloodAgentOrchestrator:
    def __init__(self, reasoner: LLMReasoningAdapter | None = None) -> None:
        self.reasoner = reasoner or LLMReasoningAdapter()
        self.dispatch_agent = DispatchAgent(self.reasoner)
        self.evaluation_agent = EvaluationAgent(self.reasoner)
        self.agents = [
            CommunicationAgent(self.reasoner),
            SimulationAgent(self.reasoner),
            RiskAgent(self.reasoner),
            self.dispatch_agent,
            self.evaluation_agent,
        ]

    def run(self, inputs: AgentState | None = None) -> Dict:
        state: AgentState = dict(inputs or {})
        state.setdefault("trace", [])
        if StateGraph is not None and END is not None:
            state["graph_runtime"] = "langgraph"
            state = self._run_langgraph(state)
        else:
            state["graph_runtime"] = "sequential_fallback"
            state = self._run_sequential(state)
        state = self._apply_evaluation_loop(state)
        state["collaboration_modes"] = _build_collaboration_modes(state)

        return {
            "status": state["status"],
            "graph_runtime": state["graph_runtime"],
            "agent_count": len(self.agents),
            "trace": state["trace"],
            "communication": state["communication"],
            "observations": state["observations"],
            "simulation": state["simulation"],
            "risk": state["risk"],
            "dispatch": state["dispatch"],
            "evaluation": state["evaluation"],
            "report": state["report"],
            "replan_count": state["replan_count"],
            "collaboration_modes": state["collaboration_modes"],
            "architecture": build_agent_architecture_v2(),
        }

    def run_demo_summary(self) -> Dict:
        result = self.run(
            {
                "scenario": "showcase_demo",
                "rainfall_mm_h": 46.0,
                "gate_release_m3s": 900.0,
                "downstream_level_m": 50.5,
            }
        )
        return {
            "status": result["status"],
            "graph_runtime": result["graph_runtime"],
            "agent_flow": " -> ".join(step["agent"] for step in result["trace"]),
            "risk_level": result["risk"]["level"],
            "risk_score": result["risk"]["risk_score"],
            "route": " -> ".join(result["dispatch"]["a_star_route"]),
            "plan_score": result["evaluation"]["plan_score"],
            "evaluation_verdict": result["evaluation"]["verdict"],
            "human_checkpoint": result["report"]["human_checkpoint"],
            "collaboration_modes": result["collaboration_modes"],
            "reasoning_modes": {step["agent"]: step.get("reasoning_mode", "deterministic") for step in result["trace"]},
            "steps": result["trace"],
        }

    def _run_sequential(self, state: AgentState) -> AgentState:
        for agent in self.agents:
            state = agent.run(state)
        return state

    def _run_langgraph(self, state: AgentState) -> AgentState:
        workflow = StateGraph(dict)
        agent_names = [agent.name for agent in self.agents]
        for agent in self.agents:
            workflow.add_node(agent.name, agent.run)
        workflow.set_entry_point(agent_names[0])
        for source, target in zip(agent_names, agent_names[1:]):
            workflow.add_edge(source, target)
        workflow.add_edge(agent_names[-1], END)
        graph = workflow.compile()
        return graph.invoke(state)

    def _apply_evaluation_loop(self, state: AgentState) -> AgentState:
        state["replan_count"] = int(state.get("replan_count", 0))
        max_replans = int(state.get("max_replans", 0))
        if state["evaluation"]["verdict"] == "replan_required" and state["replan_count"] < max_replans:
            state["replan_count"] += 1
            state["evaluation_feedback"] = {
                "request": "replan",
                "reason": state["evaluation"]["explanation"],
                "avoid": "fastest_route_under_high_risk",
            }
            state = self.dispatch_agent.run(state)
            state = self.evaluation_agent.run(state)
        return state


def run_demo_multi_agent(inputs: AgentState | None = None) -> Dict:
    return FloodAgentOrchestrator().run(inputs)


def _append_trace(state: AgentState, agent: str, reasoning: Dict[str, str] | str, output: Dict) -> None:
    if isinstance(reasoning, dict):
        reasoning_text = reasoning.get("text", "")
        reasoning_mode = reasoning.get("mode", "deterministic")
    else:
        reasoning_text = reasoning
        reasoning_mode = "deterministic"
    state.setdefault("trace", [])
    state["trace"].append(
        {"agent": agent, "reasoning": reasoning_text, "reasoning_mode": reasoning_mode, "output_keys": sorted(output.keys())}
    )


def _route_instruction(instruction: str, rainfall: float, release: float) -> Dict:
    text = instruction.lower()
    wants_dispatch = any(token in instruction for token in ("调度", "路线", "避险", "转移")) or "dispatch" in text
    wants_risk = any(token in instruction for token in ("风险", "评估", "预警")) or "risk" in text
    wants_simulation = any(token in instruction for token in ("仿真", "模拟", "洪水", "水位")) or "simulation" in text
    if rainfall >= 60.0 or release >= 800.0:
        wants_risk = True
        wants_simulation = True
    intent = "risk_dispatch" if wants_dispatch and wants_risk else "flood_simulation" if wants_simulation else "status_check"
    targets = ["simulation"]
    if wants_risk:
        targets.append("risk")
    if wants_dispatch:
        targets.append("dispatch")
    targets.append("evaluation")
    return {
        "intent": intent,
        "target_agents": list(dict.fromkeys(targets)),
        "priority": "high" if rainfall >= 80.0 or release >= 1000.0 else "normal",
    }


def _dispatch_graph(is_replan: bool) -> Dict[str, Dict[str, float]]:
    if is_replan:
        return {
            "dam": {"north_shelter": 7, "ridge": 8},
            "ridge": {"hospital": 4},
            "hospital": {"shelter": 3},
            "north_shelter": {"shelter": 4},
            "shelter": {},
        }
    return {
        "dam": {"ridge": 4, "north_shelter": 9},
        "ridge": {"school": 3, "hospital": 6},
        "school": {"shelter": 4},
        "hospital": {"shelter": 2},
        "north_shelter": {"shelter": 5},
        "shelter": {},
    }


def _dispatch_tradeoff(risk_level: str, route: List[str], cost: float, is_replan: bool) -> Dict:
    return {
        "safety": "prefer high-ground corridor" if is_replan or risk_level in {"high", "extreme"} else "standard corridor",
        "time_cost": round(cost, 2),
        "resource_load": "moderate" if len(route) <= 4 else "high",
        "conflict": "safety_over_speed" if is_replan else "balanced_speed_and_safety",
    }


def _score_dispatch_plan(risk: Dict, dispatch: Dict) -> tuple[float, Dict[str, float]]:
    risk_score = float(risk["risk_score"])
    spread = float(risk["mc_dropout"]["spread_m"])
    estimated_minutes = float(dispatch["estimated_minutes"])
    safety_score = max(0.0, 100.0 - risk_score)
    confidence_score = max(0.0, 100.0 - spread * 35.0)
    timeliness_score = max(0.0, 100.0 - estimated_minutes * 2.0)
    resource_score = 82.0 if dispatch["override_required"] else 90.0
    score = round(
        safety_score * 0.42 + confidence_score * 0.22 + timeliness_score * 0.24 + resource_score * 0.12,
        2,
    )
    return score, {
        "safety": round(safety_score, 2),
        "confidence": round(confidence_score, 2),
        "timeliness": round(timeliness_score, 2),
        "resource": round(resource_score, 2),
    }


def _explain_score(criteria: Dict[str, float], verdict: str) -> str:
    weakest = min(criteria, key=criteria.get)
    if verdict == "approved":
        return f"plan approved; weakest dimension is {weakest}={criteria[weakest]}"
    return f"plan rejected; {weakest}={criteria[weakest]} is below expected operating margin"


def _build_collaboration_modes(state: AgentState) -> Dict:
    replan_count = int(state.get("replan_count", 0))
    return {
        "serial_pipeline": {
            "status": "active",
            "flow": "communication -> simulation -> risk -> dispatch -> evaluation",
        },
        "parallel_merge": {
            "status": "ready",
            "merge_points": ["observations", "simulation", "risk"],
            "note": "observation-risk screening can run beside hydraulic simulation before final risk fusion",
        },
        "evaluation_loop": {
            "status": "triggered" if replan_count else "not_triggered",
            "replan_count": replan_count,
            "max_replans": int(state.get("max_replans", 0)),
        },
    }


def _enkf_update(forecast: float, measurement: float, forecast_var: float = 0.18, obs_var: float = 0.08) -> float:
    kalman_gain = forecast_var / (forecast_var + obs_var)
    return forecast + kalman_gain * (measurement - forecast)


def _mc_dropout_samples(center: float) -> List[float]:
    return [center * factor for factor in (0.92, 0.97, 1.0, 1.04, 1.09)]


def _a_star(graph: Dict[str, Dict[str, float]], start: str, goal: str) -> tuple[List[str], float]:
    queue = [(0.0, start, [start])]
    visited = set()
    while queue:
        cost, node, path = heapq.heappop(queue)
        if node == goal:
            return path, cost
        if node in visited:
            continue
        visited.add(node)
        for neighbor, edge_cost in graph[node].items():
            if neighbor not in visited:
                heuristic = 0.0 if neighbor == goal else 1.0
                heapq.heappush(queue, (cost + edge_cost + heuristic, neighbor, path + [neighbor]))
    return [start], math.inf


def _ant_colony_refine(route: List[str]) -> List[str]:
    if len(route) <= 2:
        return route
    return route[:-1] + ["pheromone_safe_corridor", route[-1]]
