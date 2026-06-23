"""Tests for milestone 2. Run alone with: pytest tests/test_m2.py"""

from pathlib import Path


class TestMilestone2:
    """Tests for milestone 2: Description of milestone 2."""

    def test_milestone_1_artifact_persists(self) -> None:
        """The /app/hello.txt file from milestone 1 must still exist (files persist across milestones)."""
        hello_path = Path("/app/hello.txt")
        assert hello_path.exists(), (
            f"File {hello_path} does not exist — was milestone 1 completed?"
        )

    def test_milestone_2_done_file_exists(self) -> None:
        """The /app/milestone2_done.txt file must exist."""
        done_path = Path("/app/milestone2_done.txt")
        assert done_path.exists(), f"File {done_path} does not exist"
