"""Tests for milestone 1. Run alone with: pytest tests/test_m1.py"""

from pathlib import Path


class TestMilestone1:
    """Tests for milestone 1: Description of milestone 1."""

    def test_milestone_1_file_exists(self) -> None:
        """The /app/hello.txt file must exist."""
        hello_path = Path("/app/hello.txt")
        assert hello_path.exists(), f"File {hello_path} does not exist"

    def test_milestone_1_file_contents(self) -> None:
        """The /app/hello.txt file must contain 'Hello, world!'."""
        hello_path = Path("/app/hello.txt")
        assert hello_path.read_text().strip() == "Hello, world!", (
            f"Expected 'Hello, world!' but got '{hello_path.read_text().strip()}'"
        )
