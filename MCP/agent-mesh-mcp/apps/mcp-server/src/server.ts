import * as z from "zod/v3";

import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { BridgeError } from "@agent-mesh/mcp-bridge";

import { createRuntime } from "./runtime.js";

const runtime = createRuntime({
  sidecarBaseUrl: process.env.SIDECAR_BASE_URL ?? "http://127.0.0.1:8090",
});

const server = new McpServer({
  name: "agent-mesh-mcp",
  version: "0.1.0",
});

function okResult(payload: unknown) {
  const structuredContent =
    typeof payload === "object" && payload !== null && !Array.isArray(payload)
      ? (payload as Record<string, unknown>)
      : { value: payload };
  return {
    content: [{ type: "text" as const, text: JSON.stringify(payload, null, 2) }],
    structuredContent,
  };
}

function errorResult(payload: unknown) {
  const structuredContent =
    typeof payload === "object" && payload !== null && !Array.isArray(payload)
      ? (payload as Record<string, unknown>)
      : { value: payload };
  return {
    content: [{ type: "text" as const, text: JSON.stringify(payload, null, 2) }],
    structuredContent,
    isError: true,
  };
}

server.registerTool(
  "agents.list",
  {
    description: "List all registered agents and their capabilities.",
    inputSchema: {},
  },
  async () => okResult({ ok: true, agents: runtime.listAgents() })
);

server.registerTool(
  "agents.send",
  {
    description: "Send an AgentMessage to a specific agent via the consent router.",
    inputSchema: {
      to: z.string(),
      type: z.enum(["task", "query", "artifact"]),
      payload: z.record(z.unknown()),
      taskTreeId: z.string().optional(),
    },
  },
  async ({ to, type, payload, taskTreeId }) => {
    const reply = await runtime.sendMessage({ to, type, payload, taskTreeId });
    return okResult({ ok: true, reply });
  }
);

server.registerTool(
  "artifacts.seal",
  {
    description: "Seal a draft artifact, making it immutable.",
    inputSchema: {
      artifactId: z.string(),
      sealedBy: z.string().optional(),
    },
  },
  async ({ artifactId, sealedBy }) => {
    const artifact = await runtime.sealArtifact(artifactId, sealedBy);
    return okResult({ ok: true, artifact });
  }
);

server.registerTool(
  "artifacts.query",
  {
    description: "Semantic vector search over the in-memory artifact store.",
    inputSchema: {
      text: z.string(),
      topK: z.number().int().min(1).max(50).optional(),
    },
  },
  async ({ text, topK }) => {
    const artifacts = await runtime.queryArtifacts(text, topK ?? 5);
    return okResult({ ok: true, artifacts });
  }
);

server.registerTool(
  "fossils.list",
  {
    description: "Return the full tamper-evident fossil chain.",
    inputSchema: {},
  },
  async () => okResult({ ok: true, fossils: await runtime.listFossils() })
);

server.registerTool(
  "agents.spawn",
  {
    description: "Route a task to a selected or semantically-ranked agent and return the agent reply.",
    inputSchema: {
      task: z.string(),
      agentId: z.string().optional(),
      taskTreeId: z.string().optional(),
    },
  },
  async ({ task, agentId, taskTreeId }) => {
    const result = await runtime.spawnAgent({ task, agentId, taskTreeId });
    return okResult({ ok: true, ...result });
  }
);

server.registerTool(
  "repo.search",
  {
    description: "Search the repository using sidecar embeddings and normalized dot product ranking.",
    inputSchema: {
      query: z.string(),
      topK: z.number().int().min(1).max(50).optional(),
      agentFilter: z.string().optional(),
    },
  },
  async ({ query, topK, agentFilter }) => {
    try {
      const result = await runtime.repoSearch(query, topK ?? 8, agentFilter ?? "");
      return okResult(result);
    } catch (err) {
      if (err instanceof BridgeError && err.code === "SIDECAR_UNAVAILABLE") {
        return okResult({
          ok: false,
          error: {
            code: err.code,
            message: err.message,
          },
        });
      }
      if (err instanceof BridgeError) {
        return errorResult({
          ok: false,
          error: {
            code: err.code,
            message: err.message,
            failClosed: true,
          },
        });
      }
      throw err;
    }
  }
);

server.registerTool(
  "twin.get_state",
  {
    description: "Get digital twin summary state from the sidecar.",
    inputSchema: {},
  },
  async () => {
    try {
      return okResult(await runtime.twinState());
    } catch (err) {
      if (err instanceof BridgeError && err.code === "SIDECAR_UNAVAILABLE") {
        return okResult({ ok: false, error: { code: err.code, message: err.message } });
      }
      if (err instanceof BridgeError) {
        return errorResult({
          ok: false,
          error: { code: err.code, message: err.message, failClosed: true },
        });
      }
      throw err;
    }
  }
);

server.registerTool(
  "twin.get_tasks",
  {
    description: "List twin tasks and optionally filter by status.",
    inputSchema: {
      status: z.string().optional(),
    },
  },
  async ({ status }) => {
    try {
      return okResult(await runtime.twinTasks(status ?? ""));
    } catch (err) {
      if (err instanceof BridgeError && err.code === "SIDECAR_UNAVAILABLE") {
        return okResult({ ok: false, error: { code: err.code, message: err.message } });
      }
      if (err instanceof BridgeError) {
        return errorResult({
          ok: false,
          error: { code: err.code, message: err.message, failClosed: true },
        });
      }
      throw err;
    }
  }
);

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((err) => {
  const message = err instanceof Error ? err.stack ?? err.message : String(err);
  process.stderr.write(`${message}\n`);
  process.exit(1);
});
