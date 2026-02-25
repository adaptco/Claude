"""
digital_twin/twin_registry.py

The Digital Twin is a live JSON mirror of the A2A_MCP repo state.
It tracks:
  - Every source file → its embedding vector key + last modified
  - Every agent → its capability vector + current task assignment
  - Every task → status, assigned agent, % complete, fossil record
  - CI/CD state → last run result, coverage, pass rate

The twin is updated on every git push via GitHub Actions (see ci_twin_sync.yml).
It's queryable by any agent via the MCP tool get_twin_state.

The twin IS the grounding document for long-horizon task planning.
When an agent asks "what's left to do?" — the twin answers, not the LLM's memory.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

TWIN_STATE_FILE = Path(os.environ.get("TWIN_STATE_FILE", "digital_twin/twin_state.json"))


@dataclass
class FileTwinNode:
    """One source file in the twin."""
    path: str
    embedding_key: str       # key in embedding store
    last_modified: float
    last_agent: str = ""     # which agent last touched this
    test_coverage: float = 0.0


@dataclass
class AgentTwinNode:
    """One agent's state in the twin."""
    agent_id: str
    role: str
    capability_vector_key: str    # key to retrieve from embedding store
    current_task_id: str = ""
    tasks_completed: int = 0
    last_active: float = 0.0
    status: str = "idle"          # idle | working | blocked | error


@dataclass
class TaskTwinNode:
    """One task's state in the twin."""
    task_id: str
    name: str
    airtable_record_id: str
    status: str                   # mirrors AirtableTask.status
    assigned_agent: str = ""
    completion_pct: float = 0.0
    fossil_hashes: list[str] = field(default_factory=list)
    browser_actions_completed: int = 0
    browser_actions_total: int = 0
    office_checkpoint_path: str = ""
    started_at: float = 0.0
    completed_at: float = 0.0


@dataclass
class CIState:
    """Latest CI/CD pipeline state."""
    last_run_sha: str = ""
    last_run_status: str = "unknown"    # success | failure | in_progress
    passed_tests: int = 0
    failed_tests: int = 0
    coverage_pct: float = 0.0
    last_run_at: float = 0.0
    workflow_url: str = ""


@dataclass
class DigitalTwin:
    """
    The complete twin state.
    Serialized to/from digital_twin/twin_state.json on every sync.
    """
    version: str = "1.0.0"
    repo_url: str = "https://github.com/adaptco-main/A2A_MCP"
    last_sync: float = field(default_factory=time.time)
    files: dict[str, FileTwinNode] = field(default_factory=dict)
    agents: dict[str, AgentTwinNode] = field(default_factory=dict)
    tasks: dict[str, TaskTwinNode] = field(default_factory=dict)
    ci: CIState = field(default_factory=CIState)
    embedding_store_path: str = "rag/embedding_store.npz"
    total_chunks: int = 0


class TwinRegistry:
    """
    Read/write interface for the Digital Twin.

    All agents interact with the twin via this class.
    GitHub Actions syncs it on every push.
    """

    def __init__(self, state_file: Path = TWIN_STATE_FILE):
        self.state_file = state_file
        self._twin: DigitalTwin | None = None

    def load(self) -> DigitalTwin:
        if self.state_file.exists():
            data = json.loads(self.state_file.read_text())
            self._twin = self._from_dict(data)
        else:
            self._twin = DigitalTwin()
        return self._twin

    def save(self) -> None:
        if self._twin is None:
            return
        self._twin.last_sync = time.time()
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(
            json.dumps(asdict(self._twin), indent=2, default=str)
        )

    def get(self) -> DigitalTwin:
        if self._twin is None:
            self.load()
        return self._twin  # type: ignore

    # ── Agent ops ─────────────────────────────────────────────────────────────
    def register_agent(self, agent_id: str, role: str, capability_key: str) -> None:
        twin = self.get()
        twin.agents[agent_id] = AgentTwinNode(
            agent_id=agent_id,
            role=role,
            capability_vector_key=capability_key,
            last_active=time.time(),
        )

    def assign_task(self, agent_id: str, task_id: str) -> None:
        twin = self.get()
        if agent_id in twin.agents:
            twin.agents[agent_id].current_task_id = task_id
            twin.agents[agent_id].status = "working"
            twin.agents[agent_id].last_active = time.time()
        if task_id in twin.tasks:
            twin.tasks[task_id].assigned_agent = agent_id
            twin.tasks[task_id].status = "In Progress"
            twin.tasks[task_id].started_at = time.time()

    def complete_task(self, task_id: str, fossil_hash: str = "") -> None:
        twin = self.get()
        if task_id in twin.tasks:
            twin.tasks[task_id].status = "Done"
            twin.tasks[task_id].completion_pct = 100.0
            twin.tasks[task_id].completed_at = time.time()
            if fossil_hash:
                twin.tasks[task_id].fossil_hashes.append(fossil_hash)
        agent_id = twin.tasks[task_id].assigned_agent if task_id in twin.tasks else ""
        if agent_id and agent_id in twin.agents:
            twin.agents[agent_id].current_task_id = ""
            twin.agents[agent_id].status = "idle"
            twin.agents[agent_id].tasks_completed += 1

    # ── File ops ──────────────────────────────────────────────────────────────
    def sync_files(self, repo_root: Path) -> None:
        """Scan repo files and update twin file nodes."""
        twin = self.get()
        for path in repo_root.rglob("*.py"):
            rel = str(path.relative_to(repo_root))
            twin.files[rel] = FileTwinNode(
                path=rel,
                embedding_key=rel,
                last_modified=path.stat().st_mtime,
            )

    # ── CI ops ────────────────────────────────────────────────────────────────
    def update_ci(self, sha: str, status: str, passed: int, failed: int, coverage: float, url: str) -> None:
        twin = self.get()
        twin.ci = CIState(
            last_run_sha=sha,
            last_run_status=status,
            passed_tests=passed,
            failed_tests=failed,
            coverage_pct=coverage,
            last_run_at=time.time(),
            workflow_url=url,
        )

    # ── Query ops ─────────────────────────────────────────────────────────────
    def get_ready_tasks(self) -> list[TaskTwinNode]:
        return [t for t in self.get().tasks.values() if t.status == "Ready"]

    def get_agent_workload(self) -> dict[str, int]:
        """Returns {agent_id: tasks_in_progress} for load balancing."""
        return {
            a.agent_id: (1 if a.current_task_id else 0)
            for a in self.get().agents.values()
        }

    def get_summary(self) -> dict[str, Any]:
        twin = self.get()
        tasks = list(twin.tasks.values())
        return {
            "last_sync": twin.last_sync,
            "total_files": len(twin.files),
            "total_tasks": len(tasks),
            "tasks_done": sum(1 for t in tasks if t.status == "Done"),
            "tasks_in_progress": sum(1 for t in tasks if t.status == "In Progress"),
            "tasks_blocked": sum(1 for t in tasks if t.status == "Blocked"),
            "agents_active": sum(1 for a in twin.agents.values() if a.status == "working"),
            "ci_status": twin.ci.last_run_status,
            "ci_coverage": twin.ci.coverage_pct,
            "ci_pass_rate": (
                twin.ci.passed_tests / (twin.ci.passed_tests + twin.ci.failed_tests)
                if (twin.ci.passed_tests + twin.ci.failed_tests) > 0 else 0.0
            ),
        }

    def _from_dict(self, data: dict) -> DigitalTwin:
        twin = DigitalTwin(
            version=data.get("version", "1.0.0"),
            repo_url=data.get("repo_url", ""),
            last_sync=data.get("last_sync", 0.0),
            embedding_store_path=data.get("embedding_store_path", ""),
            total_chunks=data.get("total_chunks", 0),
        )
        twin.files = {
            k: FileTwinNode(**v) for k, v in data.get("files", {}).items()
        }
        twin.agents = {
            k: AgentTwinNode(**v) for k, v in data.get("agents", {}).items()
        }
        twin.tasks = {
            k: TaskTwinNode(**v) for k, v in data.get("tasks", {}).items()
        }
        ci_data = data.get("ci", {})
        if ci_data:
            twin.ci = CIState(**ci_data)
        return twin
