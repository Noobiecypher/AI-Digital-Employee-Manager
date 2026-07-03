from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from enum import Enum


class TaskOutputItem(BaseModel):
    task_id: str
    task_name: str
    output: dict[str, Any] | None = None


class WorkflowStatus(str, Enum):
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class StartWorkflowRequest(BaseModel):
    objective_id: str
    params: dict[str, Any]


class ResumeWorkflowRequest(BaseModel):
    approval_status: ApprovalStatus
    human_feedback: str | None = Field(
        default=None,
        max_length=2000,
    )
    human_input_data: dict[str, Any] = Field(
        default_factory=dict
    )


class StartWorkflowResponse(BaseModel):
    workflow_id: str
    objective_id: str
    status: WorkflowStatus
    message: str


class ResumeWorkflowResponse(BaseModel):
    workflow_id: str
    objective_id: str
    approval_status: ApprovalStatus
    status: WorkflowStatus
    message: str


class WorkflowResponse(BaseModel):
    workflow_id: str
    objective_id: str
    status: WorkflowStatus

    current_task_id: str
    current_agent: str

    awaiting_human_input: bool
    approval_status: ApprovalStatus

    approval_context: dict[str, Any] | None = None

    human_feedback: str | None = None
    error_message: str | None = None
    
    task_outputs: list[TaskOutputItem] | None = None
    result: dict[str, Any] | None = None

    created_at: str | None = None
    updated_at: str | None = None


class WorkflowListItem(BaseModel):
    workflow_id: str
    objective_id: str
    status: WorkflowStatus

    awaiting_human_input: bool
    approval_status: ApprovalStatus

    created_at: str | None = None
    updated_at: str | None = None


class WorkflowListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[WorkflowListItem]


class ErrorPayload(BaseModel):
    code: str
    message: str
    field: str | None = None
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    error: ErrorPayload
