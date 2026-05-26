"""Resume data normalization placeholder."""

from typing import Any


class ResumeNormalizer:
    """Normalizes parsed resume data into the backend's canonical shape."""

    def normalize(self, parsed_resume: dict[str, Any]) -> dict[str, Any]:
        """Return normalized resume data."""
        raise NotImplementedError

