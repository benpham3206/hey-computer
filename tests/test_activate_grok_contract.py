import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "activate_grok.ps1"


class ActivateGrokContractTests(unittest.TestCase):
    def setUp(self):
        self.source = SCRIPT.read_text(encoding="utf-8")

    def test_always_launches_a_new_visible_powershell_host(self):
        self.assertIn("Start-Process -FilePath $PowerShellExe", self.source)
        self.assertIn("$Host.UI.RawUI.WindowTitle = 'Grok Build'", self.source)
        self.assertIn("'-NoExit'", self.source)

    def test_discovers_only_the_new_host_window_and_fails_closed(self):
        self.assertIn("WaitForWindow($grokHostProcess.Id, 15000)", self.source)
        self.assertIn("if ($target -eq [IntPtr]::Zero)", self.source)
        self.assertIn("if (-not $ok)", self.source)
        self.assertNotIn("FindCandidates", self.source)

    def test_does_not_assign_to_powershells_reserved_host_variable(self):
        self.assertNotIn("$host = Start-Process", self.source)
        self.assertIn("$grokHostProcess = Start-Process", self.source)


if __name__ == "__main__":
    unittest.main()
