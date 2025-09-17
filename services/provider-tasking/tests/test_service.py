import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from app.models import TaskStatus
from app.service import ALLOWED_TRANSITIONS


class AllowedTransitionsTests(unittest.TestCase):
    """Validate the task state machine reflects the upstream configuration."""

    def test_cancelled_state_is_configured(self) -> None:
        """Tasks should be able to transition into the cancelled state."""

        self.assertIn(TaskStatus.cancelled, ALLOWED_TRANSITIONS[TaskStatus.new])
        self.assertIn(TaskStatus.cancelled, ALLOWED_TRANSITIONS[TaskStatus.assigned])
        self.assertIn(TaskStatus.cancelled, ALLOWED_TRANSITIONS[TaskStatus.in_progress])
        self.assertEqual(set(), ALLOWED_TRANSITIONS[TaskStatus.cancelled])
