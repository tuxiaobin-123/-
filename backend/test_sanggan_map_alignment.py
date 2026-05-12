from pathlib import Path
import unittest


class SangganMapAlignmentTests(unittest.TestCase):
    def test_flood_map_is_single_case_sanggan_thematic_map(self):
        repo_root = Path(__file__).resolve().parents[1]
        source = (repo_root / "frontend" / "src" / "components" / "FloodMap" / "index.tsx").read_text(encoding="utf-8")

        self.assertIn("桑干河怀仁段10年一遇洪水淹没范围图", source)
        self.assertIn("遥感底图 + DEM推演淹没面 + 1996历史种子校准", source)
        self.assertIn("SANGGAN_CONTEXT", source)
        self.assertNotIn("OROVILLE_CONTEXT", source)
        self.assertNotIn("Oroville", source)
        self.assertNotIn("oroville", source)
        self.assertNotIn("lng < 0", source)


if __name__ == "__main__":
    unittest.main()
