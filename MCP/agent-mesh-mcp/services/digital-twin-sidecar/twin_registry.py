from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TaskTwinNode:
    task_id: str
    name: str
    status: str
    assigned_agent: str = ""
    completion_pct: float = 0.0
    fossil_hashes: list[str] = field(default_factory=list)
    started_at: float = 0.0
    completed_at: float = 0.0


@dataclass
class AgentTwinNode:
    agent_id: str
    role: str
    current_task_id: str = ""
    tasks_completed: int = 0
    status: str = "idle"
    last_active: float = 0.0


@dataclass
class FileTwinNode:
    path: str
    last_modified: float


@dataclass
class CIState:
    last_run_sha: str = ""
    last_run_status: str = "unknown"
    passed_tests: int = 0
    failed_tests: int = 0
    coverage_pct: float = 0.0


@dataclass
class DigitalTwin:
    version: str = "1.0.0"
    last_sync: float = field(default_factory=time.time)
    files: dict[str, FileTwinNode] = field(default_factory=dict)
    agents: dict[str, AgentTwinNode] = field(default_factory=dict)
    tasks: dict[str, TaskTwinNode] = field(default_factory=dict)
    ci: CIState = field(default_factory=CIState)


class TwinRegistry:
    def __init__(self, state_file: Path, repo_root: Path):
        self.state_file = state_file
        self.repo_root = repo_root
        self._twin: DigitalTwin | None = None

    def load(self) -> DigitalTwin:
        if self.state_file.exists():
            raw = json.loads(self.state_file.read_text(encoding="utf-8"))
            self._twin = self._from_dict(raw)
        else:
            self._twin = DigitalTwin()
            self.sync_files()
            self.save()
        return self._twin

    def save(self) -> None:
        twin = self.get()
        twin.last_sync = time.time()
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(asdict(twin), indent=2), encoding="utf-8")

    def get(self) -> DigitalTwin:
        if self._twin is None:
            return self.load()
        return self._twin

    def sync_files(self) -> None:
        twin = self.get()
        for path in self.repo_root.rglob("*"):
            if not path.is_file():
                continue
            if ".git" in path.parts or "node_modules" in path.parts or "dist" in path.parts:
                continue
            if path.suffix not in {".py", ".ts", ".tsx", ".js", ".json", ".md", ".yml", ".yaml"}:
                continue
            rel = str(path.relative_to(self.repo_root))
            twin.files[rel] = FileTwinNode(path=rel, last_modified=path.stat().st_mtime)

    def assign_task(self, task_id: str, agent_id: str, task_name: str = "") -> TaskTwinNode:
        twin = self.get()
        task = twin.tasks.get(task_id)
        if task is None:
            task = TaskTwinNode(task_id=task_id, name=task_name or task_id, status="In Progress")
            twin.tasks[task_id] = task
        task.assigned_agent = agent_id
        task.status = "In Progress"
        task.started_at = task.started_at or time.time()

        agent = twin.agents.get(agent_id)
        if agent is None:
            agent = AgentTwinNode(agent_id=agent_id, role=agent_id)
            twin.agents[agent_id] = agent
        agent.current_task_id = task_id
        agent.status = "working"
        agent.last_active = time.time()
        return task

    def complete_task(self, task_id: str, fossil_hash: str = "") -> TaskTwinNode | None:
        twin = self.get()
        task = twin.tasks.get(task_id)
        if task is None:
            return None

        task.status = "Done"
        task.completion_pct = 100.0
        task.completed_at = time.time()
        if fossil_hash:
            task.fossil_hashes.append(fossil_hash)

        if task.assigned_agent and task.assigned_agent in twin.agents:
            agent = twin.agents[task.assigned_agent]
            agent.current_task_id = ""
            agent.status = "idle"
            agent.tasks_completed += 1
            agent.last_active = time.time()
        return task

    def get_tasks(self, status: str = "") -> list[dict[str, Any]]:
        tasks = list(self.get().tasks.values())
        if status:
            tasks = [t for t in tasks if t.status.lower() == status.lower()]
        return [asdict(t) for t in tasks]

    def get_summary(self) -> dict[str, Any]:
        twin = self.get()
        tasks = list(twin.tasks.values())
        passed = twin.ci.passed_tests
        failed = twin.ci.failed_tests
        pass_rate = (passed / (passed + failed)) if (passed + failed) else 0.0
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
            "ci_pass_rate": pass_rate,
        }

    @staticmethod
    def _from_dict(data: dict[str, Any]) -> DigitalTwin:
        twin = DigitalTwin(
            version=data.get("version", "1.0.0"),
            last_sync=float(data.get("last_sync", 0.0)),
        )

        twin.files = {
            key: FileTwinNode(**value) for key, value in data.get("files", {}).items()
        }
        twin.agents = {
            key: AgentTwinNode(**value) for key, value in data.get("agents", {}).items()
        }
        twin.tasks = {
            key: TaskTwinNode(**value) for key, value in data.get("tasks", {}).items()
        }
        if "ci" in data:
            twin.ci = CIState(**data["ci"])
        return twin
