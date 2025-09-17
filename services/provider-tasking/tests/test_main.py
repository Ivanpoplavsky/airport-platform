import asyncio
import sys
import unittest
from pathlib import Path
from uuid import uuid4
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from app.main import _change_status
from app.models import TaskStatus
from app.service import InvalidStatusTransition


class ChangeStatusTests(unittest.TestCase):
    """Ensure HTTP responses mirror the service error semantics."""

    def test_invalid_transition_results_in_conflict(self) -> None:
        db = object()
        task_id = uuid4()
        error = InvalidStatusTransition(TaskStatus.new, TaskStatus.done)

        async_mock = AsyncMock(side_effect=error)

        with patch("app.main.service.set_status", new=async_mock):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(_change_status(db, task_id, TaskStatus.done, "TEST"))

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIs(ctx.exception.__cause__, error)

