import tempfile
import unittest
from pathlib import Path

from benchmarks.toce_river import score_toce_benchmark, score_toce_csv


class ToceBenchmarkTests(unittest.TestCase):
    def test_score_toce_benchmark_returns_rmse_table(self):
        rows = [
            {
                "station_id": "P1",
                "observed_peak_depth_m": 1.0,
                "simulated_peak_depth_m": 1.2,
                "mike21_peak_depth_m": 1.1,
                "observed_arrival_s": 10.0,
                "simulated_arrival_s": 12.0,
                "mike21_arrival_s": 11.0,
            },
            {
                "station_id": "P2",
                "observed_peak_depth_m": 2.0,
                "simulated_peak_depth_m": 1.8,
                "mike21_peak_depth_m": 2.3,
                "observed_arrival_s": 20.0,
                "simulated_arrival_s": 18.0,
                "mike21_arrival_s": 19.0,
            },
        ]

        result = score_toce_benchmark(rows)

        self.assertEqual(result["station_count"], 2)
        self.assertEqual(result["metrics"]["peak_depth_rmse_m"]["this_model"], 0.2)
        self.assertEqual(result["metrics"]["arrival_time_rmse_s"]["this_model"], 2.0)

    def test_score_toce_csv_validates_required_columns(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "toce.csv"
            csv_path.write_text(
                "station_id,observed_peak_depth_m,simulated_peak_depth_m,mike21_peak_depth_m,"
                "observed_arrival_s,simulated_arrival_s,mike21_arrival_s\n"
                "P1,1.0,1.2,1.1,10,12,11\n",
                encoding="utf-8",
            )

            result = score_toce_csv(csv_path)

        self.assertEqual(result["benchmark"], "Toce River dam-break")
        self.assertEqual(result["station_count"], 1)


if __name__ == "__main__":
    unittest.main()
