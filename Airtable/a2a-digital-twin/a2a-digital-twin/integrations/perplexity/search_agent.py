"""
integrations/perplexity/search_agent.py

Perplexity Search Agent — replaces/extends agents/researcher.py

Registers as both:
  1. An A2A agent (responds to AgentCard discovery + /tasks/send)
  2. An MCP tool (search_web, search_code_docs) on the MCP server

Architecture:
  - Query arrives via IntentEngine or direct MCP tool call
  - Agent embeds the query using vertical_tensor_slice
  - If NDP score of best repo chunk < REPO_THRESHOLD, falls through to Perplexity
  - Perplexity result is embedded, stored in artifact store, returned
  - All results include provenance (source: "repo" or "perplexity")

Integration with A2A_MCP:
  - Drop into agents/ as a peer to researcher.py
  - Register as MCP tool in mcp_extensions/claude_code_mcp_server.py
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import httpx

# Threshold below which we fall through to Perplexity
REPO_THRESHOLD = float(os.environ.get("PERPLEXITY_FALLTHROUGH_THRESHOLD", "0.72"))
PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY", "")
PERPLEXITY_MODEL = os.environ.get("PERPLEXITY_MODEL", "sonar-pro")


@dataclass
class SearchResult:
    query: str
    answer: str
    sources: list[dict[str, str]]
    source_type: str           # "repo" | "perplexity" | "hybrid"
    repo_score: float = 0.0
    citations: list[str] = field(default_factory=list)


async def search_perplexity(query: str, system_context: str = "") -> SearchResult:
    """
    Call Perplexity API with the query.
    Uses sonar-pro for research-grade answers with citations.
    """
    if not PERPLEXITY_API_KEY:
        return SearchResult(
            query=query,
            answer="[Perplexity API key not set — set PERPLEXITY_API_KEY]",
            sources=[],
            source_type="error",
        )

    messages = []
    if system_context:
        messages.append({
            "role": "system",
            "content": (
                "You are a technical research agent for the A2A_MCP codebase. "
                "Focus answers on Python, FastMCP, SQLAlchemy, and multi-agent systems. "
                f"Additional context: {system_context}"
            ),
        })
    messages.append({"role": "user", "content": query})

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://api.perplexity.ai/chat/completions",
            headers={
                "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": PERPLEXITY_MODEL,
                "messages": messages,
                "return_citations": True,
                "return_related_questions": False,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    choice = data["choices"][0]
    answer = choice["message"]["content"]
    citations = data.get("citations", [])
    sources = [{"url": c} for c in citations]

    return SearchResult(
        query=query,
        answer=answer,
        sources=sources,
        source_type="perplexity",
        citations=citations,
    )


class PerplexitySearchAgent:
    """
    Search agent that combines repo RAG (NDP) with Perplexity web search.

    Priority:
      1. Check repo embedding store via NDP — fast, free, grounded in your code
      2. If best NDP score < REPO_THRESHOLD, call Perplexity for web context
      3. If both available, return hybrid result

    Integration with existing IntentEngine:
      - This agent fits the 'researcher' slot in the 5-stage pipeline
      - Replace or wrap agents/researcher.py with this class
    """

    def __init__(self, slicer=None):
        """
        slicer: VerticalTensorSlicer instance (from rag/vertical_tensor_slice.py)
                If None, skips repo RAG and goes direct to Perplexity.
        """
        self.slicer = slicer

    async def research(
        self,
        query: str,
        agent_filter: str | None = None,
        top_k: int = 5,
    ) -> SearchResult:
        """
        Main entry point. Called by IntentEngine in the research stage.
        """
        repo_chunks: list[dict] = []
        best_score = 0.0

        # ── Step 1: Repo RAG via NDP ─────────────────────────────────────────
        if self.slicer is not None:
            repo_chunks = self.slicer.query(query, top_k=top_k, agent_filter=agent_filter)
            best_score = repo_chunks[0]["score"] if repo_chunks else 0.0

        # ── Step 2: Decide whether to call Perplexity ─────────────────────────
        needs_web = best_score < REPO_THRESHOLD or not self.slicer

        if not needs_web:
            # Repo is sufficient
            answer = "\n\n".join(
                f"[{r['file']} — score {r['score']:.3f}]\n{r['text']}"
                for r in repo_chunks
            )
            return SearchResult(
                query=query,
                answer=answer,
                sources=[{"file": r["file"]} for r in repo_chunks],
                source_type="repo",
                repo_score=best_score,
            )

        # ── Step 3: Perplexity for web knowledge ──────────────────────────────
        # Provide repo context to Perplexity so it focuses its answer
        repo_context = ""
        if repo_chunks:
            repo_context = "Relevant repo context:\n" + "\n".join(
                r["text"][:200] for r in repo_chunks[:3]
            )

        perp_result = await search_perplexity(query, system_context=repo_context)
        perp_result.repo_score = best_score
        perp_result.source_type = "hybrid" if repo_chunks else "perplexity"

        # Prepend any strong repo matches
        if repo_chunks and best_score > 0.5:
            perp_result.sources = (
                [{"file": r["file"]} for r in repo_chunks] + perp_result.sources
            )

        return perp_result

    def as_mcp_tool(self):
        """Returns a dict compatible with FastMCP tool registration."""
        return {
            "name": "search_web",
            "description": (
                "Search for technical information using Perplexity AI. "
                "First checks the A2A_MCP repo via semantic search (NDP), "
                "then falls through to Perplexity for web context if needed. "
                "Use for: documentation lookup, API references, architecture decisions."
            ),
            "fn": self._tool_fn,
        }

    async def _tool_fn(self, query: str, agent_filter: str = "") -> dict[str, Any]:
        result = await self.research(
            query, agent_filter=agent_filter or None
        )
        return {
            "ok": True,
            "query": result.query,
            "answer": result.answer,
            "source_type": result.source_type,
            "repo_score": result.repo_score,
            "sources": result.sources[:5],
            "citations": result.citations[:5],
        }


# ── A2A Agent Card (for agent discovery protocol) ────────────────────────────
PERPLEXITY_AGENT_CARD = {
    "name": "PerplexitySearchAgent",
    "description": "Research agent combining repo RAG with Perplexity web search",
    "version": "1.0.0",
    "url": "http://localhost:8000/agents/perplexity",
    "capabilities": {
        "streaming": False,
        "pushNotifications": False,
    },
    "skills": [
        {
            "id": "repo_search",
            "name": "Repo Semantic Search",
            "description": "NDP search over A2A_MCP embedding store",
            "inputModes": ["text"],
            "outputModes": ["text"],
        },
        {
            "id": "web_research",
            "name": "Perplexity Web Research",
            "description": "Real-time web search via Perplexity sonar-pro",
            "inputModes": ["text"],
            "outputModes": ["text"],
        },
    ],
}
