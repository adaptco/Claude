from __future__ import annotations

import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from twin_registry import TwinRegistry
from vertical_tensor_slice import EmbeddingIndex


class RepoSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    topK: int = Field(default=8, ge=1, le=50)
    agentFilter: str = ""


class TaskAssignedRequest(BaseModel):
    taskId: str = Field(min_length=1)
    agentId: str = Field(min_length=1)
    taskName: str = ""


class TaskCompletedRequest(BaseModel):
    taskId: str = Field(min_length=1)
    fossilHash: str = ""


def _default_repo_root() -> Path:
    env = os.environ.get("SIDECAR_REPO_ROOT", "")
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parents[2]


def _default_state_file() -> Path:
    env = os.environ.get("TWIN_STATE_FILE", "")
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parent / "data" / "twin_state.json"


def _default_store_file() -> Path:
    env = os.environ.get("EMBEDDING_STORE_FILE", "")
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parent / "data" / "embedding_store.npz"


def create_app(
    repo_root: Path | None = None,
    state_file: Path | None = None,
    store_file: Path | None = None,
) -> FastAPI:
    repo_root = (repo_root or _default_repo_root()).resolve()
    state_file = (state_file or _default_state_file()).resolve()
    store_file = (store_file or _default_store_file()).resolve()

    twin = TwinRegistry(state_file=state_file, repo_root=repo_root)
    twin.load()
    index = EmbeddingIndex(repo_root=repo_root, store_path=store_file)

    app = FastAPI(
        title="Digital Twin Sidecar",
        version="1.0.0",
        description="A2A-inspired repo search and twin observability sidecar",
    )

    @app.get("/health")
    def health() -> dict:
        return {
            "ok": True,
            "repoRoot": str(repo_root),
            "stateFile": str(state_file),
            "storeFile": str(store_file),
        }

    @app.post("/v1/repo/search")
    def repo_search(payload: RepoSearchRequest) -> dict:
        try:
            results = index.search(
                query=payload.query,
                top_k=payload.topK,
                agent_filter=payload.agentFilter,
            )
            return {"ok": True, "results": results, "count": len(results)}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"repo search failed: {exc}") from exc

    @app.get("/v1/twin/state")
    def twin_state() -> dict:
        return {"ok": True, "state": twin.get_summary()}

    @app.get("/v1/twin/tasks")
    def twin_tasks(status: str = Query(default="")) -> dict:
        return {"ok": True, "tasks": twin.get_tasks(status=status)}

    @app.post("/v1/twin/task-assigned")
    def task_assigned(payload: TaskAssignedRequest) -> dict:
        task = twin.assign_task(payload.taskId, payload.agentId, payload.taskName)
        twin.save()
        return {"ok": True, "task": task.__dict__}

    @app.post("/v1/twin/task-completed")
    def task_completed(payload: TaskCompletedRequest) -> dict:
        task = twin.complete_task(payload.taskId, payload.fossilHash)
        twin.save()
        if task is None:
            return {"ok": False, "error": "task not found"}
        return {"ok": True, "task": task.__dict__}

    return app


if __name__ == "__main__":
    host = os.environ.get("SIDECAR_HOST", "127.0.0.1")
    port = int(os.environ.get("SIDECAR_PORT", "8090"))
    uvicorn.run(create_app(), host=host, port=port)
