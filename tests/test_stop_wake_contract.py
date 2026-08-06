import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "stop-wake.ps1"


class StopWakeContractTests(unittest.TestCase):
    def test_pid_file_value_does_not_use_powershell_reserved_pid_variable(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("$pid = Get-Content", source)
        self.assertIn("$listenerPid = Get-Content", source)


if __name__ == "__main__":
    unittest.main()
