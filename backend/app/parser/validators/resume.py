"""Resume parser validation placeholder."""

from typing import Any


class ResumeValidator:
    """Validates structured resume data before normalization."""

    def validate(self, parsed_resume: dict[str, Any]) -> None:
        """Validate parsed resume data."""
        raise NotImplementedError

