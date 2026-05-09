import unittest

from models import pinn_swe


@unittest.skipIf(pinn_swe.torch is None, "torch is not installed in this runtime")
class PINNSWETests(unittest.TestCase):
    def test_fourier_features_expand_input_dimension(self):
        features = pinn_swe.FourierFeatures(input_dim=3, num_frequencies=8, sigma=2.0)
        coords = pinn_swe.torch.zeros((5, 3), dtype=pinn_swe.torch.float32)

        encoded = features(coords)

        self.assertEqual(encoded.shape, (5, 3 + 3 * 8 * 2))

    def test_pinn_predicts_shallow_water_fields(self):
        model = pinn_swe.PINNSWENetwork(input_dim=3, hidden_dim=16, hidden_layers=2, num_frequencies=4)
        coords = pinn_swe.torch.rand((7, 3), dtype=pinn_swe.torch.float32)

        output = model(coords)

        self.assertEqual(set(output.keys()), {"h", "u", "v"})
        self.assertEqual(output["h"].shape, (7, 1))

    def test_adaptive_balancer_updates_positive_weights(self):
        balancer = pinn_swe.NTKAdaptiveLossBalancer(["data", "pde", "bc"])
        losses = {
            "data": pinn_swe.torch.tensor(2.0, requires_grad=True),
            "pde": pinn_swe.torch.tensor(8.0, requires_grad=True),
            "bc": pinn_swe.torch.tensor(1.0, requires_grad=True),
        }

        weights = balancer.update(losses)

        self.assertEqual(set(weights.keys()), {"data", "pde", "bc"})
        self.assertTrue(all(weight > 0 for weight in weights.values()))


if __name__ == "__main__":
    unittest.main()
