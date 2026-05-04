# -*- coding: utf-8 -*-
"""
Risk assessment and evacuation routing models.

The previous evacuation implementation returned straight interpolation lines.
This version computes real least-cost paths over the current flood-risk grid.
"""

from __future__ import annotations

import heapq
from typing import Dict, List, Optional, Tuple

import numpy as np

from config import KEY_POINTS


class RiskAssessor:
    def __init__(self) -> None:
        self.critical_depth = 2.0
        self.dangerous_depth = 1.0
        self.alert_depth = 0.5

    def assess_grid(self, flood_grid: List[Dict]) -> List[Dict]:
        assessed_grid = []
        for point in flood_grid:
            depth = float(point["depth"])
            vel_mag = float(point.get("velocity_mag", 0.0))
            danger_indicator = depth * (vel_mag + 0.5)

            if depth >= self.critical_depth or danger_indicator > 2.5:
                risk_level = "critical"
                risk_score = 100
            elif depth >= self.dangerous_depth or danger_indicator > 1.5:
                risk_level = "high"
                risk_score = 75
            elif depth >= self.alert_depth or danger_indicator > 0.7:
                risk_level = "medium"
                risk_score = 50
            else:
                risk_level = "low"
                risk_score = 25

            point_with_risk = point.copy()
            point_with_risk["risk_level"] = risk_level
            point_with_risk["risk_score"] = risk_score
            point_with_risk["danger_indicator"] = float(danger_indicator)
            assessed_grid.append(point_with_risk)

        return assessed_grid

    def get_risk_statistics(self, flood_grid: List[Dict]) -> Dict:
        if not flood_grid:
            return {
                "total_flooded_area": 0,
                "critical_area": 0,
                "high_risk_area": 0,
                "medium_risk_area": 0,
                "low_risk_area": 0,
                "estimated_affected_population": 0,
                "affected_key_points": [],
            }

        grid_area = 300 * 300
        critical_count = high_risk_count = medium_risk_count = low_risk_count = flooded_count = 0

        for point in flood_grid:
            if not point.get("flooded", False):
                continue
            flooded_count += 1
            risk_level = point.get("risk_level", "low")
            if risk_level == "critical":
                critical_count += 1
            elif risk_level == "high":
                high_risk_count += 1
            elif risk_level == "medium":
                medium_risk_count += 1
            else:
                low_risk_count += 1

        affected_population = critical_count * 5000 + high_risk_count * 3000 + medium_risk_count * 1000

        return {
            "total_flooded_area": float(flooded_count * grid_area),
            "critical_area": float(critical_count * grid_area),
            "high_risk_area": float(high_risk_count * grid_area),
            "medium_risk_area": float(medium_risk_count * grid_area),
            "low_risk_area": float(low_risk_count * grid_area),
            "estimated_affected_population": affected_population,
            "affected_key_points": self._check_affected_key_points(flood_grid),
        }

    def _check_affected_key_points(self, flood_grid: List[Dict]) -> List[Dict]:
        affected = []
        for key_id, key_point in KEY_POINTS.items():
            key_lat = key_point["lat"]
            key_lng = key_point["lng"]

            closest_point = min(
                flood_grid,
                key=lambda grid_point: ((grid_point["lat"] - key_lat) ** 2 + (grid_point["lng"] - key_lng) ** 2),
            )

            if closest_point.get("flooded", False):
                affected.append(
                    {
                        "id": key_id,
                        "name": key_point["name"],
                        "lat": key_lat,
                        "lng": key_lng,
                        "type": key_point["type"],
                        "risk_level": closest_point.get("risk_level", "low"),
                        "water_depth": float(closest_point["depth"]),
                    }
                )

        return affected


class EvacuationRouter:
    def __init__(self, key_points: Dict):
        self.key_points = key_points

    def find_routes(self, flood_grid: List[Dict], current_risk: Dict) -> List[Dict]:
        if not flood_grid:
            return []

        grid_data = self._build_grid_index(flood_grid)
        shelter_points = {k: v for k, v in self.key_points.items() if v["type"] == "shelter"}
        start_points = {k: v for k, v in self.key_points.items() if v["type"] in ["hospital", "school", "civic"]}

        routes = []
        for start_id, start_point in start_points.items():
            for shelter_id, shelter_point in shelter_points.items():
                route = self._find_optimal_path(grid_data, start_id, start_point, shelter_id, shelter_point)
                if route:
                    routes.append(route)

        routes.sort(key=lambda route: (route["status_rank"], route["risk_score"], route["estimated_minutes"]))
        return routes[:3]

    def _build_grid_index(self, flood_grid: List[Dict]) -> Dict:
        latitudes = sorted({round(point["lat"], 6) for point in flood_grid}, reverse=True)
        longitudes = sorted({round(point["lng"], 6) for point in flood_grid})
        row_map = {lat: index for index, lat in enumerate(latitudes)}
        col_map = {lng: index for index, lng in enumerate(longitudes)}

        cells: Dict[Tuple[int, int], Dict] = {}
        for point in flood_grid:
            row = row_map[round(point["lat"], 6)]
            col = col_map[round(point["lng"], 6)]
            cells[(row, col)] = point

        return {
            "latitudes": latitudes,
            "longitudes": longitudes,
            "row_map": row_map,
            "col_map": col_map,
            "cells": cells,
            "rows": len(latitudes),
            "cols": len(longitudes),
        }

    def _point_to_index(self, point: Dict, grid_data: Dict) -> tuple[int, int]:
        latitudes = grid_data["latitudes"]
        longitudes = grid_data["longitudes"]

        row = min(range(len(latitudes)), key=lambda idx: abs(latitudes[idx] - point["lat"]))
        col = min(range(len(longitudes)), key=lambda idx: abs(longitudes[idx] - point["lng"]))
        return row, col

    def _heuristic(self, a: tuple[int, int], b: tuple[int, int]) -> float:
        return float(np.hypot(a[0] - b[0], a[1] - b[1]))

    def _cell_cost(self, cell: Dict) -> float:
        risk_score = float(cell.get("risk_score", 0.0))
        depth = float(cell.get("depth", 0.0))
        velocity = float(cell.get("velocity_mag", 0.0))

        if cell.get("risk_level") == "critical":
            return 1200.0 + risk_score

        return 1.0 + risk_score / 30.0 + depth * 8.0 + velocity * 5.0

    def _neighbor_offsets(self) -> List[Tuple[int, int, float]]:
        return [
            (-1, 0, 1.0),
            (1, 0, 1.0),
            (0, -1, 1.0),
            (0, 1, 1.0),
            (-1, -1, 1.414),
            (-1, 1, 1.414),
            (1, -1, 1.414),
            (1, 1, 1.414),
        ]

    def _reconstruct_path(self, came_from: Dict[Tuple[int, int], Tuple[int, int]], current: tuple[int, int]) -> List[tuple[int, int]]:
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        path.reverse()
        return path

    def _grid_path_to_waypoints(
        self, path: List[tuple[int, int]], grid_data: Dict, start_point: Dict, end_point: Dict
    ) -> List[Tuple[float, float]]:
        if len(path) <= 8:
            sampled = path
        else:
            step = max(1, len(path) // 8)
            sampled = path[::step]
            if sampled[-1] != path[-1]:
                sampled.append(path[-1])

        waypoints = [(float(start_point["lat"]), float(start_point["lng"]))]
        for row, col in sampled:
            cell = grid_data["cells"][(row, col)]
            waypoint = (float(cell["lat"]), float(cell["lng"]))
            if waypoint != waypoints[-1]:
                waypoints.append(waypoint)
        final_waypoint = (float(end_point["lat"]), float(end_point["lng"]))
        if final_waypoint != waypoints[-1]:
            waypoints.append(final_waypoint)
        return waypoints

    def _evaluate_path(self, path: List[tuple[int, int]], grid_data: Dict) -> tuple[float, float, str, int]:
        if not path:
            return 100.0, 0.0, "dangerous", 2

        cells = [grid_data["cells"][index] for index in path]
        risk_scores = [float(cell.get("risk_score", 0.0)) for cell in cells]
        avg_risk = float(np.mean(risk_scores))
        peak_risk = float(np.max(risk_scores))
        combined_score = float(np.clip(avg_risk * 0.55 + peak_risk * 0.45, 0.0, 100.0))

        if combined_score < 35:
            return combined_score, 4.2, "safe", 0
        if combined_score < 65:
            return combined_score, 3.2, "warning", 1
        return combined_score, 2.1, "dangerous", 2

    def _find_optimal_path(
        self,
        grid_data: Dict,
        start_id: str,
        start_point: Dict,
        end_id: str,
        end_point: Dict,
    ) -> Optional[Dict]:
        start = self._point_to_index(start_point, grid_data)
        goal = self._point_to_index(end_point, grid_data)

        open_heap: List[Tuple[float, tuple[int, int]]] = [(0.0, start)]
        came_from: Dict[Tuple[int, int], Tuple[int, int]] = {}
        g_score: Dict[Tuple[int, int], float] = {start: 0.0}

        while open_heap:
            _priority, current = heapq.heappop(open_heap)
            if current == goal:
                break

            for row_offset, col_offset, distance_factor in self._neighbor_offsets():
                neighbor = (current[0] + row_offset, current[1] + col_offset)
                cell = grid_data["cells"].get(neighbor)
                if cell is None:
                    continue

                tentative_score = g_score[current] + self._cell_cost(cell) * distance_factor
                if tentative_score >= g_score.get(neighbor, float("inf")):
                    continue

                came_from[neighbor] = current
                g_score[neighbor] = tentative_score
                priority = tentative_score + self._heuristic(neighbor, goal)
                heapq.heappush(open_heap, (priority, neighbor))

        if goal not in g_score:
            return None

        grid_path = self._reconstruct_path(came_from, goal)
        waypoints = self._grid_path_to_waypoints(grid_path, grid_data, start_point, end_point)
        risk_score, avg_speed_kmh, status, status_rank = self._evaluate_path(grid_path, grid_data)

        distance_m = 0.0
        for idx in range(1, len(waypoints)):
            prev_lat, prev_lng = waypoints[idx - 1]
            lat, lng = waypoints[idx]
            distance_m += float(
                np.hypot((lat - prev_lat) * 111000, (lng - prev_lng) * 111000 * np.cos(np.radians(lat)))
            )

        estimated_minutes = (distance_m / 1000.0) / max(avg_speed_kmh, 0.1) * 60.0

        if len(waypoints) < 2 or distance_m <= 1.0:
            return None

        return {
            "origin": start_id,
            "origin_name": start_point["name"],
            "destination": end_id,
            "destination_name": end_point["name"],
            "waypoints": waypoints,
            "distance": float(distance_m),
            "risk_score": float(risk_score),
            "estimated_minutes": float(estimated_minutes),
            "status": status,
            "status_rank": status_rank,
        }
