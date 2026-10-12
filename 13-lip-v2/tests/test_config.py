import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Config


class ConfigTests(unittest.TestCase):
    def test_db_config_defaults_when_env_is_missing(self):
        with patch.dict("os.environ", {}, clear=True):
            config = Config.get_db_config()

        self.assertEqual(config.dbname, "unspsc")
        self.assertEqual(config.user, "postgres")
        self.assertEqual(config.password, "postgres")
        self.assertEqual(config.host, "localhost")
        self.assertEqual(config.port, 5432)
        self.assertTrue(config.schema_sync)

    def test_schema_sync_defaults_true(self):
        env = {
            "POSTGRES_DB": "unspsc",
            "POSTGRES_USER": "postgres",
            "POSTGRES_PASSWORD": "postgres",
            "POSTGRES_HOST": "localhost",
        }
        with patch.dict("os.environ", env, clear=True):
            config = Config.get_db_config()

        self.assertTrue(config.schema_sync)

    def test_schema_sync_can_be_disabled(self):
        env = {
            "POSTGRES_DB": "unspsc",
            "POSTGRES_USER": "postgres",
            "POSTGRES_PASSWORD": "postgres",
            "POSTGRES_HOST": "localhost",
            "DB_SCHEMA_SYNC": "false",
        }
        with patch.dict("os.environ", env, clear=True):
            config = Config.get_db_config()

        self.assertFalse(config.schema_sync)


if __name__ == "__main__":
    unittest.main()
