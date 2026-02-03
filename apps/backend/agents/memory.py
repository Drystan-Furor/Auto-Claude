"""Backward compatible memory facade.

Some older code/tests expect `agents.memory` to exist.
The implementation was moved to `agents.memory_manager`.
"""

from .memory_manager import *  # noqa: F403
