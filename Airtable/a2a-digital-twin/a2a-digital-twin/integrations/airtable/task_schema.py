"""
integrations/airtable/task_schema.py

Airtable is the source of truth for:
  - Tasks     → what work to do
  - Roles     → which agent does it
  - Workflows → in what sequence
  - Actions   → GitHub Actions triggers

Schema maps directly to A2A_MCP's IntentEngine 5-stage pipeline.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx

AIRTABLE_API_KEY = os.environ.get("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID", "")
AIRTABLE_BASE_URL = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}"


# ── Enums matching Airtable dropdown fields ───────────────────────────────────
class AgentRole(str, Enum):
    MANAGER       = "managing_agent"
    ORCHESTRATOR  = "orchestration_agent"
    ARCHITECT     = "architecture_agent"
    CODER         = "coder"
    TESTER        = "tester"
    RESEARCHER    = "researcher"
    JUDGE         = "judge"
    DIGITAL_TWIN  = "digital_twin"


class TaskStatus(str, Enum):
    BACKLOG     = "Backlog"
    READY       = "Ready"
    IN_PROGRESS = "In Progress"
    IN_REVIEW   = "In Review"
    DONE        = "Done"
    BLOCKED     = "Blocked"


class WorkflowStage(str, Enum):
    INTAKE       = "1-Intake"
    RESEARCH     = "2-Research"
    ARCHITECT    = "3-Architect"
    IMPLEMENT    = "4-Implement"
    VERIFY       = "5-Verify"
    CHECKPOINT   = "6-Checkpoint"   # MS Office output
    DEPLOY       = "7-Deploy"


# ── Data models ───────────────────────────────────────────────────────────────
@dataclass
class AirtableTask:
    """
    Maps to the 'Tasks' table in Airtable base.

    Airtable field names (case-sensitive):
        Name, Status, Agent Role, Workflow Stage,
        Description, Acceptance Criteria, Browser Steps,
        GitHub Action, Office Checkpoint, Related Tasks
    """
    record_id: str
    name: str
    status: TaskStatus
    agent_role: AgentRole
    workflow_stage: WorkflowStage
    description: str
    acceptance_criteria: list[str] = field(default_factory=list)
    browser_steps: list[str] = field(default_factory=list)
    github_action: str = ""           # workflow file to trigger, e.g. "ci.yml"
    office_checkpoint: str = ""       # "word" | "excel" | "outlook" | ""
    related_task_ids: list[str] = field(default_factory=list)
    embedding_vector: list[float] = field(default_factory=list)  # cached NDP vector


@dataclass
class AirtableRole:
    """Maps to the 'Roles' table in Airtable base."""
    record_id: str
    name: str
    agent_class: AgentRole
    system_prompt: str
    tools: list[str] = field(default_factory=list)
    mcp_tools: list[str] = field(default_factory=list)


@dataclass
class AirtableWorkflow:
    """Maps to the 'Workflows' table — defines task sequences per pipeline stage."""
    record_id: str
    name: str
    stages: list[WorkflowStage]
    task_ids: list[str]
    trigger: str = "manual"    # "manual" | "push" | "schedule" | "webhook"
    github_action_file: str = ""


# ── Airtable API client ───────────────────────────────────────────────────────
class AirtableClient:
    def __init__(self, api_key: str = AIRTABLE_API_KEY, base_id: str = AIRTABLE_BASE_ID):
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self.base_url = f"https://api.airtable.com/v0/{base_id}"

    async def list_tasks(
        self,
        status: TaskStatus | None = None,
        stage: WorkflowStage | None = None,
    ) -> list[AirtableTask]:
        params: dict[str, str] = {}
        filters = []
        if status:
            filters.append(f"{{Status}} = '{status.value}'")
        if stage:
            filters.append(f"{{Workflow Stage}} = '{stage.value}'")
        if filters:
            params["filterByFormula"] = "AND(" + ", ".join(filters) + ")"

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/Tasks",
                headers=self.headers,
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()

        return [self._parse_task(r) for r in data.get("records", [])]

    async def update_task_status(self, record_id: str, status: TaskStatus) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.patch(
                f"{self.base_url}/Tasks/{record_id}",
                headers=self.headers,
                json={"fields": {"Status": status.value}},
            )
            resp.raise_for_status()
            return resp.json()

    async def create_task(self, task: dict[str, Any]) -> str:
        """Creates a task record and returns the new record_id."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/Tasks",
                headers=self.headers,
                json={"fields": task},
            )
            resp.raise_for_status()
            return resp.json()["id"]

    async def list_roles(self) -> list[AirtableRole]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.base_url}/Roles", headers=self.headers)
            resp.raise_for_status()
        return [self._parse_role(r) for r in resp.json().get("records", [])]

    async def get_workflow(self, workflow_name: str) -> AirtableWorkflow | None:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/Workflows",
                headers=self.headers,
                params={"filterByFormula": f"{{Name}} = '{workflow_name}'"},
            )
            resp.raise_for_status()
        records = resp.json().get("records", [])
        return self._parse_workflow(records[0]) if records else None

    def _parse_task(self, record: dict) -> AirtableTask:
        f = record.get("fields", {})
        return AirtableTask(
            record_id=record["id"],
            name=f.get("Name", ""),
            status=TaskStatus(f.get("Status", "Backlog")),
            agent_role=AgentRole(f.get("Agent Role", "managing_agent")),
            workflow_stage=WorkflowStage(f.get("Workflow Stage", "1-Intake")),
            description=f.get("Description", ""),
            acceptance_criteria=f.get("Acceptance Criteria", "").splitlines(),
            browser_steps=f.get("Browser Steps", "").splitlines(),
            github_action=f.get("GitHub Action", ""),
            office_checkpoint=f.get("Office Checkpoint", ""),
            related_task_ids=f.get("Related Tasks", []),
        )

    def _parse_role(self, record: dict) -> AirtableRole:
        f = record.get("fields", {})
        return AirtableRole(
            record_id=record["id"],
            name=f.get("Name", ""),
            agent_class=AgentRole(f.get("Agent Class", "managing_agent")),
            system_prompt=f.get("System Prompt", ""),
            tools=f.get("Tools", "").split(","),
            mcp_tools=f.get("MCP Tools", "").split(","),
        )

    def _parse_workflow(self, record: dict) -> AirtableWorkflow:
        f = record.get("fields", {})
        return AirtableWorkflow(
            record_id=record["id"],
            name=f.get("Name", ""),
            stages=[WorkflowStage(s) for s in f.get("Stages", [])],
            task_ids=f.get("Tasks", []),
            trigger=f.get("Trigger", "manual"),
            github_action_file=f.get("GitHub Action File", ""),
        )
