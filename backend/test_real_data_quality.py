# -*- coding: utf-8 -*-
"""
Quality and evidence-chain tests for real-data integration.
"""

import unittest

from services.real_observations import build_agent_evidence_chain, build_data_quality_report


class RealDataQualityTests(unittest.TestCase):
    def test_quality_report_scores_live_usgs_dem_and_historical_event(self) -> None:
        usgs_probe = {
            "status": "live",
            "endpoint": "https://waterservices.usgs.gov/nwis/iv/?sites=11406800",
            "series": [
                {"station_id": "11406800", "count": 84, "latest_value": 266.2},
                {"station_id": "11406818", "count": 84, "latest_value": 920.0},
            ],
        }
        dem_status = {
            "status": "cached",
            "path": "backend/data/oroville_dem_cache.json",
            "mode": "local DEM grid cache",
        }
        event = {
            "event_id": "oroville_2017_spillway_incident",
            "calibration_targets": ["reservoir elevation", "downstream gage"],
            "known_milestones": [{"time": "2017-02-11", "label": "overtopping"}],
        }

        report = build_data_quality_report(usgs_probe, dem_status, event)

        self.assertGreaterEqual(report["score"], 80)
        self.assertEqual(report["grade"], "trusted")
        self.assertEqual(report["decision_status"], "auto_advisory_allowed")
        self.assertGreaterEqual(len(report["checks"]), 4)
        self.assertTrue(any(ref["label"] == "USGS time series endpoint" for ref in report["evidence_refs"]))

    def test_quality_report_marks_offline_seed_as_human_review_required(self) -> None:
        usgs_probe = {
            "status": "offline_seed",
            "endpoint": "offline",
            "series": [{"station_id": "11406800", "count": 24, "latest_value": 266.0}],
        }
        dem_status = {"status": "cached", "path": "cache.json", "mode": "local DEM grid cache"}
        event = {"event_id": "seed", "calibration_targets": [], "known_milestones": []}

        report = build_data_quality_report(usgs_probe, dem_status, event)

        self.assertEqual(report["grade"], "demo_only")
        self.assertEqual(report["decision_status"], "human_review_required")
        self.assertLess(report["score"], 55)

    def test_agent_evidence_chain_names_all_five_agents(self) -> None:
        usgs_probe = {"status": "cached", "endpoint": "cached", "series": [{"station_id": "11406800", "count": 24}]}
        report = {
            "score": 68,
            "grade": "usable_with_review",
            "decision_status": "human_review_required",
            "evidence_refs": [{"label": "USGS time series endpoint", "value": "cached"}],
        }
        event = {
            "event_id": "oroville_2017_spillway_incident",
            "calibration_targets": ["reservoir elevation"],
            "known_milestones": [{"time": "2017-02-11", "label": "overtopping"}],
        }

        chain = build_agent_evidence_chain(usgs_probe, report, event)

        self.assertEqual(
            [item["agent"] for item in chain],
            ["communication", "simulation", "risk", "dispatch", "evaluation"],
        )
        self.assertTrue(all(item["input_evidence"] for item in chain))
        self.assertTrue(all(item["output_evidence"] for item in chain))
        self.assertTrue(all(0 <= item["confidence"] <= 1 for item in chain))
        self.assertIn("review", chain[-1]["audit_status"])


if __name__ == "__main__":
    unittest.main()
