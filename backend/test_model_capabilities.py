# -*- coding: utf-8 -*-
"""
Model capability profile tests.
"""

import unittest

from routers.flood import build_model_capability_profile


class ModelCapabilityProfileTest(unittest.TestCase):
    def test_capability_profile_exposes_innovation_evidence(self) -> None:
        profile = build_model_capability_profile()

        self.assertEqual(profile["focus"], "dam_centered_flood_warning")
        self.assertIn("physics_ai_fusion", profile["innovation_points"])
        self.assertIn("dam_boundary_conditions", profile["innovation_points"])
        self.assertIn("monitor_simulate_warn_respond_loop", profile["innovation_points"])
        self.assertGreaterEqual(len(profile["boundary_conditions"]), 4)
        self.assertGreaterEqual(len(profile["decision_loop"]), 4)
        self.assertIn("current_engine", profile["model_runtime"])


if __name__ == "__main__":
    unittest.main()
