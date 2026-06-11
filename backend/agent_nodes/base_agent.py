from abc import ABC, abstractmethod

from models import AgentState, Task


# ==========================================================
# AGENT EXECUTION ERROR
# ==========================================================

class AgentExecutionError(Exception):
    """
    Raised when an agent fails during task execution.

    Carries task_id, agent, action, and cause so the Workflow Executor
    can set state.status = "failed" and state.error_message without
    knowing anything about the agent's internals.
    """

    def __init__(
        self,
        task_id: str,
        agent: str,
        action: str,
        cause: Exception,
    ) -> None:
        self.task_id = task_id
        self.agent = agent
        self.action = action
        self.cause = cause

        super().__init__(
            f"[{agent}] Task '{task_id}' (action='{action}') failed: {cause}"
        )


# ==========================================================
# BASE AGENT
# ==========================================================

class BaseAgent(ABC):
    """
    Abstract base class for all workflow agents.

    - Reads from state.params and state.outputs.
    - Returns a plain output dict — never mutates AgentState directly.
    - The Workflow Executor stores the result as state.outputs[task.task_id].
    - execute() raises standard exceptions; run() wraps them as AgentExecutionError.
    """

    def __init__(self, agent_type: str) -> None:
        """
        Args:
            agent_type: Domain identifier matching the agent field in Task
                        (e.g. "recruitment", "hr", "sales", "research", "reporting").
        """
        self.agent_type = agent_type

    # ----------------------------------------------------------
    # PUBLIC ENTRY POINT
    # ----------------------------------------------------------

    def run(self, task: Task, state: AgentState) -> dict:
        """
        Public entry point called by the Workflow Executor.

        Wraps execute() and re-raises any failure as AgentExecutionError
        so the executor always receives a consistent failure type.

        Raises:
            AgentExecutionError: If execute() raises any exception.
        """
        try:
            return self.execute(task, state)
        except AgentExecutionError:
            # Already wrapped — let it propagate unchanged.
            raise
        except Exception as e:
            raise AgentExecutionError(
                task_id=task.task_id,
                agent=self.agent_type,
                action=task.action,
                cause=e,
            ) from e

    # ----------------------------------------------------------
    # ABSTRACT INTERFACE
    # ----------------------------------------------------------

    @abstractmethod
    def execute(self, task: Task, state: AgentState) -> dict:
        """
        Execute a task and return its output dict.

        Inspect task.action and dispatch to the appropriate internal method.
        Return only the keys specified in task_contracts.md for that action.

        Raises:
            NotImplementedError: If task.action is unrecognised.
            KeyError:            If a required upstream output is missing.
            ValueError:          If required params are absent or invalid.
        """
        ...

    # ----------------------------------------------------------
    # HELPERS
    # ----------------------------------------------------------

    def get_output(self, state: AgentState, task_id: str) -> dict:
        """
        Retrieve a completed task's output from state.outputs.

        Prefer this over direct dict access — the error message names
        the agent and task to make missing dependencies easy to diagnose.

        Raises:
            KeyError: If task_id is absent from state.outputs.

        Example:
            job_desc = self.get_output(state, "t1")["job_description"]
        """
        if task_id not in state.outputs:
            raise KeyError(
                f"[{self.agent_type}] Output for task '{task_id}' not found in "
                f"state.outputs. Verify that '{task_id}' is listed in depends_on "
                f"and completed before this task."
            )
        return state.outputs[task_id]

    def get_outputs(self, state: AgentState, *task_ids: str) -> dict[str, dict]:
        """
        Retrieve multiple completed task outputs in one call.

        Returns a dict mapping each task_id to its output dict.

        Raises:
            KeyError: If any task_id is missing from state.outputs.

        Example:
            outputs  = self.get_outputs(state, "t1", "t2")
            employee = outputs["t1"]["employee_details"]
            plan     = outputs["t2"]["onboarding_plan"]
        """
        return {task_id: self.get_output(state, task_id) for task_id in task_ids}