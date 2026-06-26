import unittest

from app.patch_service import generate_patch


class PatchServiceAgentTests(unittest.TestCase):
    def test_agent_patch_uses_code_context_for_python_bug(self):
        result = generate_patch(
            repo_url="demo-repo",
            issue_text="The function should add values instead of subtracting them.",
            code="def add(a, b):\n    return a - b",
            language="python",
        )

        self.assertEqual(result["status"], "success")
        self.assertGreaterEqual(len(result["plan"]), 3)
        self.assertIn("return a + b", result["generated_diff"])
        self.assertEqual(result["verification"]["status"], "passed")


if __name__ == "__main__":
    unittest.main()
