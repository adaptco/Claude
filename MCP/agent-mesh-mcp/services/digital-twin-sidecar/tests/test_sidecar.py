from __future__ import annotations

from pathlib import Path
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app


def _seed_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "README.md").write_text("# Demo\nThis is a twin sidecar test.\n", encoding="utf-8")
    src = repo / "packages" / "core"
    src.mkdir(parents=True, exist_ok=True)
    (src / "types.ts").write_text(
        "export type AgentId = string;\nexport interface AgentMessage { from: AgentId; to: AgentId; }\n",
        encoding="utf-8",
    )


def test_health_and_repo_search(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    state_file = tmp_path / "state.json"
    store_file = tmp_path / "store.npz"
    _seed_repo(repo)

    app = create_app(repo_root=repo, state_file=state_file, store_file=store_file)
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["ok"] is True

    search = client.post("/v1/repo/search", json={"query": "AgentMessage", "topK": 3})
    assert search.status_code == 200
    body = search.json()
    assert body["ok"] is True
    assert isinstance(body["results"], list)
    assert body["count"] == len(body["results"])
    if body["results"]:
        assert body["results"][0]["score"] >= body["results"][-1]["score"]


def test_twin_assign_complete_and_filter(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    state_file = tmp_path / "state.json"
    store_file = tmp_path / "store.npz"
    _seed_repo(repo)

    app = create_app(repo_root=repo, state_file=state_file, store_file=store_file)
    client = TestClient(app)

    assign = client.post(
        "/v1/twin/task-assigned",
        json={"taskId": "task-1", "agentId": "orchestrator", "taskName": "Initial task"},
    )
    assert assign.status_code == 200
    assert assign.json()["ok"] is True

    state = client.get("/v1/twin/state").json()["state"]
    assert state["tasks_in_progress"] == 1

    completed = client.post(
        "/v1/twin/task-completed",
        json={"taskId": "task-1", "fossilHash": "abc123"},
    )
    assert completed.status_code == 200
    assert completed.json()["ok"] is True

    done_tasks = client.get("/v1/twin/tasks", params={"status": "done"}).json()["tasks"]
    assert len(done_tasks) == 1
    assert done_tasks[0]["task_id"] == "task-1"
    assert done_tasks[0]["fossil_hashes"] == ["abc123"]
