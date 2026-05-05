import copy
import unittest
from unittest.mock import patch

import launcher


class LauncherEnvRoutingTest(unittest.TestCase):
    def _fresh_config(self) -> dict:
        return copy.deepcopy(launcher.DEFAULT_CONFIG)

    def test_env_defaults_split_main_and_ground_ark_keys(self) -> None:
        cfg = self._fresh_config()
        env = {
            "ep-id": "ep-main-123",
            "api-key": "ark-main-key",
            "ARK_API_KEY": "ark-ground-key",
        }

        with patch.object(launcher, "_parse_env_txt", return_value=env):
            launcher._apply_env_defaults(cfg, had_main_routing=False)

        self.assertEqual(cfg["main_providers"]["volcano"]["model_id"], "ep-main-123")
        self.assertEqual(
            cfg["main_providers"]["volcano"]["model_api_key"], "ark-main-key"
        )
        self.assertEqual(
            cfg["ground_providers"]["doubao_ark"]["api_key"], "ark-ground-key"
        )

    def test_env_defaults_fallback_to_ground_key_when_main_key_missing(self) -> None:
        cfg = self._fresh_config()
        env = {
            "ep-id": "ep-main-123",
            "ARK_API_KEY": "ark-shared-key",
        }

        with patch.object(launcher, "_parse_env_txt", return_value=env):
            launcher._apply_env_defaults(cfg, had_main_routing=False)

        self.assertEqual(
            cfg["main_providers"]["volcano"]["model_api_key"], "ark-shared-key"
        )
        self.assertEqual(
            cfg["ground_providers"]["doubao_ark"]["api_key"], "ark-shared-key"
        )

    def test_env_defaults_repairs_legacy_main_key_fallback(self) -> None:
        cfg = self._fresh_config()
        cfg["main_providers"]["volcano"]["model_api_key"] = "ark-ground-key"
        env = {
            "ep-id": "ep-main-123",
            "api-key": "ark-main-key",
            "ARK_API_KEY": "ark-ground-key",
        }

        with patch.object(launcher, "_parse_env_txt", return_value=env):
            launcher._apply_env_defaults(cfg, had_main_routing=True)

        self.assertEqual(
            cfg["main_providers"]["volcano"]["model_api_key"], "ark-main-key"
        )


if __name__ == "__main__":
    unittest.main()
