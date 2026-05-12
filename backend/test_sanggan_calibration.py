import unittest

from services.real_observations import get_sanggan_1996_calibration_summary


class SangganCalibrationTests(unittest.TestCase):
    def test_calibration_summary_exposes_rmse_and_limitations(self):
        summary = get_sanggan_1996_calibration_summary()

        self.assertEqual(summary["case_id"], "sanggan_river_huairen")
        self.assertEqual(summary["event_id"], "sanggan_1996_huairen_flood")
        self.assertEqual(summary["data_status"], "historical_seed")
        self.assertFalse(summary["certified"])
        self.assertIn("water_level_rmse_m", summary["metrics"])
        self.assertIn("flow_rmse_m3s", summary["metrics"])
        self.assertIn("arrival_time_error_h", summary["metrics"])
        self.assertGreaterEqual(len(summary["station_rows"]), 3)
        self.assertTrue(all("observed_peak" in row for row in summary["station_rows"]))


if __name__ == "__main__":
    unittest.main()
