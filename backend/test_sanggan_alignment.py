import unittest
from unittest.mock import AsyncMock, patch

from routers.flood import get_active_case, get_real_data_status, start_sanggan_1996_replay


class SangganAlignmentTests(unittest.IsolatedAsyncioTestCase):
    async def test_active_case_profile_is_sanggan_centered(self):
        case = await get_active_case()

        self.assertEqual(case["case_id"], "sanggan_river_huairen")
        self.assertIn("桑干河", case["dam"]["name"])
        self.assertIn("桑干河", case["dam"]["river"])
        self.assertIn("sanggan_dem_grid.json", case["dem_grid_cache"]["path"])
        self.assertTrue(all(station_id.startswith("sgr_") for station_id in case["sensor_stations"]))

    async def test_real_data_status_uses_sanggan_1996_event(self):
        with patch("routers.flood.fetch_sanggan_probe", new=AsyncMock(return_value={"status": "historical_seed", "series": [], "endpoint": "local"})):
            status = await get_real_data_status()

        self.assertEqual(status["case_id"], "sanggan_river_huairen")
        self.assertEqual(status["historical_event"]["event_id"], "sanggan_1996_huairen_flood")
        self.assertNotIn("Oroville", " ".join(status["next_steps"]))

    async def test_sanggan_historical_replay_endpoint_exists(self):
        class DummyAppState:
            pass

        class DummyApp:
            state = DummyAppState()

        class DummyRequest:
            app = DummyApp()

        response = await start_sanggan_1996_replay(DummyRequest())

        self.assertEqual(response["status"], "historical_replay_started")
        self.assertEqual(response["event"]["event_id"], "sanggan_1996_huairen_flood")


if __name__ == "__main__":
    unittest.main()
