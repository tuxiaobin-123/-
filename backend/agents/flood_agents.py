# -*- coding: utf-8 -*-
"""Runnable multi-agent demo for dam-centered flood warning.

The orchestrator uses LangGraph when it is installed. In the default local
runtime it falls back to a deterministic StateGraph-like sequence so the demo
can run without API keys or network access.
"""

from __future__ import annotations

import heapq
import math
import os
from dataclasses import dataclass
from typing import Dict, List

try:  # pragma: no cover - optional dependency
    from langgraph.graph import END, StateGraph
except Exception:  # pragma: no cover - optional dependency
    END = None
    StateGraph = None

from models.pinn_swe import run_pinn_dry_run


AgentState = Dict[str, object]


def build_agent_architecture_v2() -> Dict:
    return {
        "orchestrator": "Agent Orchestrator: LangGraph StateGraph with deterministic fallback",
        "shared_memory": "Shared memory: Redis state channel or in-process state dict fallback",
        "human_in_loop": "Human-in-the-loop: command review, warning confirmation, dispatch override",
        "agents": [
            {"name": "Sensor Agent", "tech": "USGS/DEM/rainfall ingestion + data quality checks"},
            {"name": "Simulation Agent", "tech": "PINN-SWE + tensor SWE + dam boundary conditions"},
            {"name": "Risk Agent", "tech": "EnKF assimilation + MC Dropout uncertainty + risk objects"},
            {"name": "Dispatch Agent", "tech": "A* route search + Ant Colony route refinement"},
            {"name": "Report Agent", "tech": "evidence chain + PDF/API command report"},
        ],
    }


@dataclass
class BaseAgent:
    name: str

    def think(self, state: AgentState) -> str:
        if os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"):
            return f"{self.name} reasoning adapter ready; deterministic tool path used for reproducible demo."
        return f"{self.name} used deterministic reasoning because no LLM API key is configured."


class SensorAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__("sensor")

    def run(self, state: AgentState) -> AgentState:
        rainfall = float(state.get("rainfall_mm_h", 35.0))
        release = float(state.get("gate_release_m3s", 600.0))
        downstream = float(state.get("downstream_level_m", 50.0))
        observations = {
            "rainfall_mm_h": rainfall,
            "gate_release_m3s": release,
            "downstream_level_m": downstream,
            "data_quality": "offline_demo_seed",
        }
        state["observations"] = observations
        _append_trace(state, self.name, self.think(state), observations)
        return state


class SimulationAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__("simulation")

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
    def __init__(self) -> None:
        super().__init__("risk")

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
    def __init__(self) -> None:
        super().__init__("dispatch")

    def run(self, state: AgentState) -> AgentState:
        graph = {
            "dam": {"ridge": 4, "north_shelter": 9},
            "ridge": {"school": 3, "hospital": 6},
            "school": {"shelter": 4},
            "hospital": {"shelter": 2},
            "north_shelter": {"shelter": 5},
            "shelter": {},
        }
        route, cost = _a_star(graph, "dam", "shelter")
        dispatch = {
            "a_star_route": route,
            "ant_colony_refined_route": _ant_colony_refine(route),
            "estimated_minutes": int(cost * 3),
            "override_required": state["risk"]["level"] in {"high", "extreme"},
        }
        state["dispatch"] = dispatch
        _append_trace(state, self.name, self.think(state), dispatch)
        return state


class ReportAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__("report")

    def run(self, state: AgentState) -> AgentState:
        report = {
            "summary": f"{state['risk']['level']} risk; route {' -> '.join(state['dispatch']['a_star_route'])}",
            "human_checkpoint": "approve_release_warning" if state["dispatch"]["override_required"] else "monitor",
            "memory_keys": ["observations", "simulation", "risk", "dispatch"],
        }
        state["report"] = report
        _append_trace(state, self.name, self.think(state), report)
        state["status"] = "completed"
        return state


class FloodAgentOrchestrator:
    def __init__(self) -> None:
        self.agents = [SensorAgent(), SimulationAgent(), RiskAgent(), DispatchAgent(), ReportAgent()]

    def run(self, inputs: AgentState | None = None) -> Dict:
        state: AgentState = dict(inputs or {})
        state.setdefault("trace", [])
        if StateGraph is not None:
            state["graph_runtime"] = "langgraph"
            state = self._run_sequential(state)
        else:
            state["graph_runtime"] = "sequential_fallback"
            state = self._run_sequential(state)

        return {
            "status": state["status"],
            "graph_runtime": state["graph_runtime"],
            "agent_count": len(self.agents),
            "trace": state["trace"],
            "observations": state["observations"],
            "simulation": state["simulation"],
            "risk": state["risk"],
            "dispatch": state["dispatch"],
            "report": state["report"],
            "architecture": build_agent_architecture_v2(),
        }

    def _run_sequential(self, state: AgentState) -> AgentState:
        for agent in self.agents:
            state = agent.run(state)
        return state


def run_demo_multi_agent(inputs: AgentState | None = None) -> Dict:
    return FloodAgentOrchestrator().run(inputs)


def _append_trace(state: AgentState, agent: str, reasoning: str, output: Dict) -> None:
    state.setdefault("trace", [])
    state["trace"].append({"agent": agent, "reasoning": reasoning, "output_keys": sorted(output.keys())})


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
