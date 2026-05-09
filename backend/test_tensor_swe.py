# -*- coding: utf-8 -*-
"""
Tensor SWE solver behavior tests.
"""

import math
import unittest

import numpy as np

from models.hydraulic import TensorSWEModel
from models import hydraulic


@unittest.skipIf(hydraulic.torch is None, "torch is not installed in this Python environment")
class TensorSWEModelTest(unittest.TestCase):
    def test_tensor_swe_initializes_on_cpu_with_numpy_state(self) -> None:
        model = TensorSWEModel(rows=12, cols=14, dx=20.0, dy=20.0, device="cpu")

        state = model.get_state()

        self.assertEqual(model.device.type, "cpu")
        self.assertEqual(state["h"].shape, (12, 14))
        self.assertEqual(state["u"].shape, (12, 14))
        self.assertEqual(state["v"].shape, (12, 14))
        self.assertEqual(state["dem"].dtype, np.float32)

    def test_tensor_swe_compute_dt_is_positive_and_finite(self) -> None:
        model = TensorSWEModel(rows=12, cols=14, dx=20.0, dy=20.0, device="cpu")

        dt = model.compute_dt(cfl=0.45)

        self.assertTrue(math.isfinite(dt))
        self.assertGreater(dt, 0)

    def test_tensor_swe_rk2_step_keeps_state_physical(self) -> None:
        model = TensorSWEModel(rows=16, cols=18, dx=15.0, dy=15.0, device="cpu")

        dt = min(model.compute_dt(cfl=0.35), 0.5)
        model.step_rk2(dt=dt, rainfall_rate=0.0002, upstream_inflow=25.0, gate_release=12.0)
        state = model.get_state()

        self.assertEqual(model.time_step, 1)
        self.assertEqual(model.total_time, dt)
        self.assertTrue(np.isfinite(state["h"]).all())
        self.assertTrue(np.isfinite(state["u"]).all())
        self.assertTrue(np.isfinite(state["v"]).all())
        self.assertGreaterEqual(float(state["h"].min()), 0.0)


if __name__ == "__main__":
    unittest.main()
