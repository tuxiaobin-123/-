import unittest
from unittest.mock import patch

from routers import flood


class SolverEngineSelectionTests(unittest.TestCase):
    def test_numpy_engine_can_be_selected_explicitly(self):
        model = flood.build_swe_model({"solver_engine": "numpy"})

        self.assertEqual(getattr(model, "engine_name", None), "numpy_swe_runtime")

    def test_torch_engine_falls_back_when_tensor_runtime_missing(self):
        with patch.object(flood, "TensorSWEModel", None):
            model = flood.build_swe_model({"solver_engine": "torch"})

        self.assertEqual(getattr(model, "engine_name", None), "numpy_swe_runtime")

    def test_torch_engine_is_used_when_tensor_runtime_is_available(self):
        class FakeTorch:
            pass

        class FakeTensorModel:
            def __init__(self, rows, cols, dx, dy, dam_config, device="auto"):
                self.rows = rows
                self.cols = cols
                self.dx = dx
                self.dy = dy
                self.dam_config = dam_config
                self.device = device
                self.engine_name = f"torch_tensor_{device}"

        with patch.object(flood, "TensorSWEModel", FakeTensorModel), patch.object(flood, "torch", FakeTorch()):
            model = flood.build_swe_model({"solver_engine": "torch", "solver_device": "cuda"})

        self.assertEqual(model.engine_name, "torch_tensor_cuda")
        self.assertEqual(model.device, "cuda")


if __name__ == "__main__":
    unittest.main()
