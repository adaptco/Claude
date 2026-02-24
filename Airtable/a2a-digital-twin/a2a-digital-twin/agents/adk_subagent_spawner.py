"""
agents/adk_subagent_spawner.py

A2A ADK (Agent Development Kit) integration for A2A_MCP.

This extends the existing IntentEngine's 5-stage pipeline with:
  1. Agent Cards — each agent self-describes via /.well-known/agent.json
  2. A2A task protocol — agents accept tasks at /tasks/send
  3. Subagent spawning from MCPHub using NDP-based capability routing
  4. Digital Twin registration on spawn

How it fits in the existing repo:
  - Drop this file in agents/
  - In orchestrator/intent_engine.py, replace direct agent instantiation
    with spawn_agent() from this module
  - MCPHub in orchestrator/main.py becomes the A2A discovery registry

The A2A protocol used here is google-deepmind/a2a-sdk compatible.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Awaitable

import httpx

from digital_twin.twin_registry import TwinRegistry


# ── Agent Card (A2A discovery contract) ──────────────────────────────────────
@dataclass
class AgentCapability:
    streaming: bool = False
    pushNotifications: bool = False
    stateTransitionHistory: bool = True   # fossil chain


@dataclass
class AgentSkill:
    id: str
    name: str
    description: str
    inputModes: list[str] = field(default_factory=lambda: ["text"])
    outputModes: list[str] = field(default_factory=lambda: ["text"])


@dataclass
class AgentCard:
    """
    A2A Agent Card — served at GET /.well-known/agent.json
    Each agent in agents/ gets one of these.
    """
    name: str
    description: str
    url: str
    version: str = "1.0.0"
    capabilities: AgentCapability = field(default_factory=AgentCapability)
    skills: list[AgentSkill] = field(default_factory=list)
    provider: dict = field(default_factory=lambda: {
        "organization": "ADAPTCO",
        "url": "https://github.com/adaptco-main/A2A_MCP",
    })

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


# ── Pre-defined Agent Cards for A2A_MCP agents ───────────────────────────────
AGENT_CARDS: dict[str, AgentCard] = {
    "managing_agent": AgentCard(
        name="ManagingAgent",
        description="High-level orchestration. Decomposes goals into tasks and assigns to specialists.",
        url="http://localhost:8001/agents/managing",
        skills=[AgentSkill("task_decomposition", "Task Decomposition",
                           "Break complex goals into atomic Airtable tasks")],
    ),
    "orchestration_agent": AgentCard(
        name="OrchestrationAgent",
        description="Workflow coordination. Manages the 5-stage IntentEngine pipeline.",
        url="http://localhost:8001/agents/orchestration",
        skills=[AgentSkill("pipeline_coordination", "Pipeline Coordination",
                           "Route tasks through Manager→Orchestrator→Architect→Coder→Tester")],
    ),
    "architecture_agent": AgentCard(
        name="ArchitectureAgent",
        description="System design decisions. Uses repo RAG to ground architectural choices.",
        url="http://localhost:8001/agents/architecture",
        skills=[AgentSkill("system_design", "System Design",
                           "Design subsystems grounded in existing A2A_MCP patterns")],
    ),
    "coder": AgentCard(
        name="CoderAgent",
        description="Code generation. Writes Python conforming to A2A_MCP patterns.",
        url="http://localhost:8001/agents/coder",
        skills=[AgentSkill("code_generation", "Code Generation",
                           "Write Python code using Claude Code MCP tools")],
    ),
    "tester": AgentCard(
        name="TesterAgent",
        description="Quality validation. Runs pytest, verifies fossil chain, checks coverage.",
        url="http://localhost:8001/agents/tester",
        skills=[AgentSkill("testing", "Testing", "pytest + fossil chain verification")],
    ),
    "researcher": AgentCard(
        name="PerplexityResearchAgent",
        description="Research. NDP repo search + Perplexity web fallthrough.",
        url="http://localhost:8001/agents/researcher",
        skills=[
            AgentSkill("repo_search", "Repo RAG", "NDP over embedding store"),
            AgentSkill("web_research", "Web Research", "Perplexity sonar-pro"),
        ],
    ),
    "digital_twin": AgentCard(
        name="DigitalTwinAgent",
        description="Live mirror of repo state. Tracks tasks, agents, CI, and file embeddings.",
        url="http://localhost:8001/agents/twin",
        skills=[AgentSkill("twin_sync", "Twin Sync", "Sync repo state to twin_state.json")],
    ),
}


# ── A2A Task Protocol ─────────────────────────────────────────────────────────
@dataclass
class A2ATask:
    """Represents a task sent via the A2A protocol."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    message: dict = field(default_factory=dict)   # {role, parts: [{text}]}
    status: str = "submitted"                     # submitted | working | completed | failed
    artifacts: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass
class A2ATaskResult:
    task_id: str
    status: str
    output: str
    artifacts: list[dict] = field(default_factory=list)
    fossil_hash: str = ""


# ── Subagent Spawner ──────────────────────────────────────────────────────────
class A2ASubagentSpawner:
    """
    Spawns subagents from the MCPHub using A2A protocol.

    Two modes:
      1. In-process: directly instantiate agent classes (for single-machine dev)
      2. Remote: send HTTP tasks to agent URLs (for distributed deployment)

    The spawner uses NDP routing to select the best agent for a task.
    """

    def __init__(
        self,
        slicer=None,
        twin: TwinRegistry | None = None,
        mode: str = "in-process",
    ):
        self.slicer = slicer
        self.twin = twin or TwinRegistry()
        self.mode = mode
        self._agent_handlers: dict[str, Callable[[A2ATask], Awaitable[A2ATaskResult]]] = {}

    def register_handler(
        self,
        agent_id: str,
        handler: Callable[[A2ATask], Awaitable[A2ATaskResult]],
    ) -> None:
        """Register an in-process agent handler."""
        self._agent_handlers[agent_id] = handler
        card = AGENT_CARDS.get(agent_id)
        if card and self.twin:
            self.twin.register_agent(agent_id, agent_id, f"prompt:{agent_id}")

    async def spawn(
        self,
        task_text: str,
        agent_id: str | None = None,
        session_id: str = "",
        metadata: dict | None = None,
    ) -> A2ATaskResult:
        """
        Spawn a subagent for a task.
        If agent_id is None, uses NDP routing to pick the best agent.
        """
        if agent_id is None:
            agent_id = self._route_by_ndp(task_text)

        task = A2ATask(
            session_id=session_id or str(uuid.uuid4()),
            message={"role": "user", "parts": [{"text": task_text}]},
            metadata=metadata or {},
        )

        if self.twin:
            self.twin.assign_task(agent_id, task.id)

        if self.mode == "in-process" and agent_id in self._agent_handlers:
            result = await self._agent_handlers[agent_id](task)
        elif self.mode == "remote":
            result = await self._send_remote(agent_id, task)
        else:
            result = A2ATaskResult(
                task_id=task.id,
                status="failed",
                output=f"No handler registered for agent: {agent_id}",
            )

        if self.twin and result.status == "completed":
            self.twin.complete_task(task.id, result.fossil_hash)

        return result

    def _route_by_ndp(self, task_text: str) -> str:
        """
        Use NDP to route task to best-matching agent.
        Falls back to 'managing_agent' if slicer not available.
        """
        if self.slicer is None:
            return "managing_agent"

        agent_prompts = {
            agent_id: card.description
            for agent_id, card in AGENT_CARDS.items()
        }
        best_agent, score = self.slicer.route_to_agent(task_text, agent_prompts)
        print(f"[A2A Router] NDP routing → {best_agent} (score={score:.3f})")
        return best_agent

    async def _send_remote(self, agent_id: str, task: A2ATask) -> A2ATaskResult:
        """Send task to remote agent via A2A HTTP protocol."""
        card = AGENT_CARDS.get(agent_id)
        if not card:
            return A2ATaskResult(task.id, "failed", f"Unknown agent: {agent_id}")

        url = f"{card.url}/tasks/send"
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                resp = await client.post(url, json=asdict(task))
                resp.raise_for_status()
                data = resp.json()
                return A2ATaskResult(
                    task_id=data.get("id", task.id),
                    status=data.get("status", {}).get("state", "completed"),
                    output=data.get("status", {}).get("message", {}).get("parts", [{}])[0].get("text", ""),
                    artifacts=data.get("artifacts", []),
                )
            except Exception as e:
                return A2ATaskResult(task.id, "failed", str(e))

    def get_agent_card(self, agent_id: str) -> dict | None:
        card = AGENT_CARDS.get(agent_id)
        return asdict(card) if card else None

    def list_agents(self) -> list[dict]:
        return [
            {
                "agent_id": aid,
                "name": card.name,
                "url": card.url,
                "skills": [s.id for s in card.skills],
                "status": self.twin.get().agents.get(aid, {}).status
                if self.twin and aid in self.twin.get().agents else "unregistered",
            }
            for aid, card in AGENT_CARDS.items()
        ]
