"""
Agent Session Management
========================

Handles running agent sessions and post-session processing including
memory updates, recovery tracking, and Linear integration.
"""

import logging
from pathlib import Path

from claude_agent_sdk import ClaudeSDKClient
from debug import debug, debug_detailed, debug_error, debug_section, debug_success

from llm.engine import LLMEngine
from llm.observability import ToolObservationState, observe_event
from llm.providers.claude_sdk.engine import ClaudeSDKEngine
from llm.types import TextEvent, ToolCallEvent, ToolResultEvent
from insight_extractor import extract_session_insights
from linear_updater import (
    linear_subtask_completed,
    linear_subtask_failed,
)
from progress import (
    count_subtasks_detailed,
    is_build_complete,
)
from recovery import RecoveryManager
from security.tool_input_validator import get_safe_tool_input
from task_logger import (
    LogEntryType,
    LogPhase,
    get_task_logger,
)
from ui import (
    StatusManager,
    muted,
    print_key_value,
    print_status,
)

from .memory_manager import save_session_memory
from .utils import (
    find_subtask_in_plan,
    get_commit_count,
    get_latest_commit,
    load_implementation_plan,
    sync_spec_to_source,
)

logger = logging.getLogger(__name__)


def is_tool_concurrency_error(error: Exception) -> bool:
    """
    Check if an error is a 400 tool concurrency error from Claude API.

    Tool concurrency errors occur when too many tools are used simultaneously
    in a single API request, hitting Claude's concurrent tool use limit.

    Args:
        error: The exception to check

    Returns:
        True if this is a tool concurrency error, False otherwise
    """
    error_str = str(error).lower()
    # Check for 400 status AND tool concurrency keywords
    return "400" in error_str and (
        ("tool" in error_str and "concurrency" in error_str)
        or "too many tools" in error_str
        or "concurrent tool" in error_str
    )


async def post_session_processing(
    spec_dir: Path,
    project_dir: Path,
    subtask_id: str,
    session_num: int,
    commit_before: str | None,
    commit_count_before: int,
    recovery_manager: RecoveryManager,
    linear_enabled: bool = False,
    status_manager: StatusManager | None = None,
    source_spec_dir: Path | None = None,
) -> bool:
    """
    Process session results and update memory automatically.

    This runs in Python (100% reliable) instead of relying on agent compliance.

    Args:
        spec_dir: Spec directory containing memory/
        project_dir: Project root for git operations
        subtask_id: The subtask that was being worked on
        session_num: Current session number
        commit_before: Git commit hash before session
        commit_count_before: Number of commits before session
        recovery_manager: Recovery manager instance
        linear_enabled: Whether Linear integration is enabled
        status_manager: Optional status manager for ccstatusline
        source_spec_dir: Original spec directory (for syncing back from worktree)

    Returns:
        True if subtask was completed successfully
    """
    print()
    print(muted("--- Post-Session Processing ---"))

    # Sync implementation plan back to source (for worktree mode)
    if sync_spec_to_source(spec_dir, source_spec_dir):
        print_status("Implementation plan synced to main project", "success")

    # Check if implementation plan was updated
    plan = load_implementation_plan(spec_dir)
    if not plan:
        print("  Warning: Could not load implementation plan")
        return False

    subtask = find_subtask_in_plan(plan, subtask_id)
    if not subtask:
        print(f"  Warning: Subtask {subtask_id} not found in plan")
        return False

    subtask_status = subtask.get("status", "pending")

    # Check for new commits
    commit_after = get_latest_commit(project_dir)
    commit_count_after = get_commit_count(project_dir)
    new_commits = commit_count_after - commit_count_before

    print_key_value("Subtask status", subtask_status)
    print_key_value("New commits", str(new_commits))

    if subtask_status == "completed":
        # Success! Record the attempt and good commit
        print_status(f"Subtask {subtask_id} completed successfully", "success")

        # Update status file
        if status_manager:
            subtasks = count_subtasks_detailed(spec_dir)
            status_manager.update_subtasks(
                completed=subtasks["completed"],
                total=subtasks["total"],
                in_progress=0,
            )

        # Record successful attempt
        recovery_manager.record_attempt(
            subtask_id=subtask_id,
            session=session_num,
            success=True,
            approach=f"Implemented: {subtask.get('description', 'subtask')[:100]}",
        )

        # Record good commit for rollback safety
        if commit_after and commit_after != commit_before:
            recovery_manager.record_good_commit(commit_after, subtask_id)
            print_status(f"Recorded good commit: {commit_after[:8]}", "success")

        # Record Linear session result (if enabled)
        if linear_enabled:
            # Get progress counts for the comment
            subtasks_detail = count_subtasks_detailed(spec_dir)
            await linear_subtask_completed(
                spec_dir=spec_dir,
                subtask_id=subtask_id,
                completed_count=subtasks_detail["completed"],
                total_count=subtasks_detail["total"],
            )
            print_status("Linear progress recorded", "success")

        # Extract rich insights from session (LLM-powered analysis)
        try:
            extracted_insights = await extract_session_insights(
                spec_dir=spec_dir,
                project_dir=project_dir,
                subtask_id=subtask_id,
                session_num=session_num,
                commit_before=commit_before,
                commit_after=commit_after,
                success=True,
                recovery_manager=recovery_manager,
            )
            insight_count = len(extracted_insights.get("file_insights", []))
            pattern_count = len(extracted_insights.get("patterns_discovered", []))
            if insight_count > 0 or pattern_count > 0:
                print_status(
                    f"Extracted {insight_count} file insights, {pattern_count} patterns",
                    "success",
                )
        except Exception as e:
            logger.warning(f"Insight extraction failed: {e}")
            extracted_insights = None

        # Save session memory (Graphiti=primary, file-based=fallback)
        try:
            save_success, storage_type = await save_session_memory(
                spec_dir=spec_dir,
                project_dir=project_dir,
                subtask_id=subtask_id,
                session_num=session_num,
                success=True,
                subtasks_completed=[subtask_id],
                discoveries=extracted_insights,
            )
            if save_success:
                if storage_type == "graphiti":
                    print_status("Session saved to Graphiti memory", "success")
                else:
                    print_status(
                        "Session saved to file-based memory (fallback)", "info"
                    )
            else:
                print_status("Failed to save session memory", "warning")
        except Exception as e:
            logger.warning(f"Error saving session memory: {e}")
            print_status("Memory save failed", "warning")

        return True

    elif subtask_status == "in_progress":
        # Session ended without completion
        print_status(f"Subtask {subtask_id} still in progress", "warning")

        recovery_manager.record_attempt(
            subtask_id=subtask_id,
            session=session_num,
            success=False,
            approach="Session ended with subtask in_progress",
            error="Subtask not marked as completed",
        )

        # Still record commit if one was made (partial progress)
        if commit_after and commit_after != commit_before:
            recovery_manager.record_good_commit(commit_after, subtask_id)
            print_status(
                f"Recorded partial progress commit: {commit_after[:8]}", "info"
            )

        # Record Linear session result (if enabled)
        if linear_enabled:
            attempt_count = recovery_manager.get_attempt_count(subtask_id)
            await linear_subtask_failed(
                spec_dir=spec_dir,
                subtask_id=subtask_id,
                attempt=attempt_count,
                error_summary="Session ended without completion",
            )

        # Extract insights even from failed sessions (valuable for future attempts)
        try:
            extracted_insights = await extract_session_insights(
                spec_dir=spec_dir,
                project_dir=project_dir,
                subtask_id=subtask_id,
                session_num=session_num,
                commit_before=commit_before,
                commit_after=commit_after,
                success=False,
                recovery_manager=recovery_manager,
            )
        except Exception as e:
            logger.debug(f"Insight extraction failed for incomplete session: {e}")
            extracted_insights = None

        # Save failed session memory (to track what didn't work)
        try:
            await save_session_memory(
                spec_dir=spec_dir,
                project_dir=project_dir,
                subtask_id=subtask_id,
                session_num=session_num,
                success=False,
                subtasks_completed=[],
                discoveries=extracted_insights,
            )
        except Exception as e:
            logger.debug(f"Failed to save incomplete session memory: {e}")

        return False

    else:
        # Subtask still pending or failed
        print_status(
            f"Subtask {subtask_id} not completed (status: {subtask_status})", "error"
        )

        recovery_manager.record_attempt(
            subtask_id=subtask_id,
            session=session_num,
            success=False,
            approach="Session ended without progress",
            error=f"Subtask status is {subtask_status}",
        )

        # Record Linear session result (if enabled)
        if linear_enabled:
            attempt_count = recovery_manager.get_attempt_count(subtask_id)
            await linear_subtask_failed(
                spec_dir=spec_dir,
                subtask_id=subtask_id,
                attempt=attempt_count,
                error_summary=f"Subtask status: {subtask_status}",
            )

        # Extract insights even from completely failed sessions
        try:
            extracted_insights = await extract_session_insights(
                spec_dir=spec_dir,
                project_dir=project_dir,
                subtask_id=subtask_id,
                session_num=session_num,
                commit_before=commit_before,
                commit_after=commit_after,
                success=False,
                recovery_manager=recovery_manager,
            )
        except Exception as e:
            logger.debug(f"Insight extraction failed for failed session: {e}")
            extracted_insights = None

        # Save failed session memory (to track what didn't work)
        try:
            await save_session_memory(
                spec_dir=spec_dir,
                project_dir=project_dir,
                subtask_id=subtask_id,
                session_num=session_num,
                success=False,
                subtasks_completed=[],
                discoveries=extracted_insights,
            )
        except Exception as e:
            logger.debug(f"Failed to save failed session memory: {e}")

        return False


async def run_llm_session(
    engine: LLMEngine,
    message: str,
    spec_dir: Path,
    verbose: bool = False,
    phase: LogPhase = LogPhase.CODING,
) -> tuple[str, str, dict]:
    """Run a single agent session using a provider-neutral LLMEngine.

    This function is the refactor target for Epic 1 / Task 1.3.

    Note:
    - Tool execution is still provider-managed for the Claude SDK engine.
    - We preserve the existing logging + UI behavior as much as possible.

    Returns:
        (status, response_text, error_info) where:
        - status: "continue", "complete", or "error"
        - response_text: Agent's response text
        - error_info: Dict with error details (empty if no error):
            - "type": "tool_concurrency" or "other"
            - "message": Error message string
            - "exception_type": Exception class name string
    """

    debug_section("session", f"Agent Session - {phase.value}")
    debug(
        "session",
        "Starting agent session",
        spec_dir=str(spec_dir),
        phase=phase.value,
        prompt_length=len(message),
        prompt_preview=message[:200] + "..." if len(message) > 200 else message,
    )
    print("Sending prompt to LLM engine...\n")

    task_logger = get_task_logger(spec_dir)
    obs_state = ToolObservationState()
    current_tool = None
    message_count = 0
    tool_count = 0

    try:
        debug("session", "Starting engine...")
        await engine.start(message)
        debug_success("session", "Engine started successfully")

        response_text = ""
        debug("session", "Starting to receive engine stream...")

        async for ev in engine.stream():
            message_count += 1
            ev_type = type(ev).__name__
            debug_detailed("session", f"Received event #{message_count}", ev_type=ev_type)

            # Persist to task logger (tool/text visibility) in a provider-neutral way.
            observe_event(
                ev=ev,
                state=obs_state,
                task_logger=task_logger,
                phase=phase,
                verbose=verbose,
                text_entry_type=LogEntryType.TEXT,
            )

            if isinstance(ev, TextEvent):
                response_text += ev.text
                print(ev.text, end="", flush=True)

            elif isinstance(ev, ToolCallEvent) and ev.tool_call is not None:
                tool_count += 1
                tool_name = ev.tool_call.name
                inp = ev.tool_call.input or {}

                tool_input_display = None
                if isinstance(inp, dict) and inp:
                    if "pattern" in inp:
                        tool_input_display = f"pattern: {inp['pattern']}"
                    elif "file_path" in inp:
                        fp = str(inp["file_path"])
                        if len(fp) > 50:
                            fp = "..." + fp[-47:]
                        tool_input_display = fp
                    elif "command" in inp:
                        cmd = str(inp["command"])
                        if len(cmd) > 50:
                            cmd = cmd[:47] + "..."
                        tool_input_display = cmd
                    elif "path" in inp:
                        tool_input_display = str(inp["path"])

                debug(
                    "session",
                    f"Tool call #{tool_count}: {tool_name}",
                    tool_input=tool_input_display,
                    full_input=str(inp)[:500] if inp else None,
                )

                # Note: Tool start logging is handled by observe_event (above) when task_logger is available.
                if not task_logger:
                    print(f"\n[Tool: {tool_name}]", flush=True)

                if verbose:
                    input_str = str(inp)
                    if len(input_str) > 300:
                        print(f"   Input: {input_str[:300]}...", flush=True)
                    else:
                        print(f"   Input: {input_str}", flush=True)

                current_tool = tool_name

            elif isinstance(ev, ToolResultEvent) and ev.tool_result is not None:
                result_content = ev.tool_result.content
                is_error = ev.tool_result.is_error

                if is_error and "blocked" in str(result_content).lower():
                    debug_error("session", f"Tool BLOCKED: {current_tool}", result=str(result_content)[:300])
                    print(f"   [BLOCKED] {result_content}", flush=True)
                elif is_error:
                    error_str = str(result_content)[:500]
                    debug_error("session", f"Tool error: {current_tool}", error=error_str[:200])
                    print(f"   [Error] {error_str}", flush=True)
                else:
                    debug_detailed(
                        "session",
                        f"Tool success: {current_tool}",
                        result_length=len(str(result_content)),
                    )
                    if verbose:
                        result_str = str(result_content)[:200]
                        print(f"   [Done] {result_str}", flush=True)
                    else:
                        print("   [Done]", flush=True)

                # Note: Tool end logging is handled by observe_event (above) when task_logger is available.

                current_tool = None

        print("\n" + "-" * 70 + "\n")

        if is_build_complete(spec_dir):
            debug_success(
                "session",
                "Session completed - build is complete",
                message_count=message_count,
                tool_count=tool_count,
                response_length=len(response_text),
            )
            return "complete", response_text, {}

        debug_success(
            "session",
            "Session completed - continuing",
            message_count=message_count,
            tool_count=tool_count,
            response_length=len(response_text),
        )
        return "continue", response_text, {}

    except Exception as e:
        is_concurrency = is_tool_concurrency_error(e)
        error_type = "tool_concurrency" if is_concurrency else "other"

        debug_error(
            "session",
            f"Session error: {e}",
            exception_type=type(e).__name__,
            error_category=error_type,
            message_count=message_count,
            tool_count=tool_count,
        )

        if is_concurrency:
            print("\n⚠️  Tool concurrency limit reached (400 error)")
            print("   Claude API limits concurrent tool use in a single request")
            print(f"   Error: {str(e)[:200]}\n")
        else:
            print(f"Error during agent session: {e}")

        if task_logger:
            task_logger.log_error(f"Session error: {e}", phase)

        error_info = {
            "type": error_type,
            "message": str(e),
            "exception_type": type(e).__name__,
        }
        return "error", str(e), error_info


async def run_agent_session(
    client: ClaudeSDKClient,
    message: str,
    spec_dir: Path,
    verbose: bool = False,
    phase: LogPhase = LogPhase.CODING,
) -> tuple[str, str, dict]:
    """Back-compat wrapper: run a session using Claude Agent SDK."""

    engine = ClaudeSDKEngine(client)
    return await run_llm_session(engine, message, spec_dir, verbose=verbose, phase=phase)
