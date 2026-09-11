import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


class OutputCapabilityTests(unittest.TestCase):
    def test_vm_name_uses_configured_name(self):
        capabilities = yaml.safe_load((ROOT / "vm/outputs.yaml").read_text())["capabilities"]
        self.assertEqual(
            {"get_property": ["vm", "vm_config", "name"]},
            capabilities["vm_name"]["value"],
        )


if __name__ == "__main__":
    unittest.main()
