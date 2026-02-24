import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { createServer } from "node:http";

import { createRuntime, dot, selectBestAgent } from "../src/runtime.js";

describe("runtime routing helpers", () => {
  it("computes dot product correctly", () => {
    assert.equal(dot([1, 2, 3], [4, 5, 6]), 32);
  });

  it("selects the best agent by similarity score", () => {
    const result = selectBestAgent(
      [1, 0, 0],
      [
        { agentId: "a", vector: [0.1, 0.9, 0] },
        { agentId: "b", vector: [0.7, 0.1, 0] },
        { agentId: "c", vector: [0.2, 0, 0.8] },
      ]
    );
    assert.equal(result.agentId, "b");
    assert.equal(result.score, 0.7);
  });

  it("spawns with explicit agent id and bypasses ranking", async () => {
    const runtime = createRuntime({ sidecarBaseUrl: "http://127.0.0.1:1" });
    const result = await runtime.spawnAgent({
      task: "summarize architecture and route tasks",
      agentId: "specialist",
      taskTreeId: "tree-explicit",
    });
    assert.equal(result.selectedAgent, "specialist");
    assert.equal(result.reply.to, "mcp-client");
  });

  it("spawns without agent id and still succeeds when sidecar is down", async () => {
    const runtime = createRuntime({ sidecarBaseUrl: "http://127.0.0.1:1" });
    const result = await runtime.spawnAgent({
      task: "plan and orchestrate multi-step implementation",
      taskTreeId: "tree-ranked",
    });
    assert.ok(["orchestrator", "specialist", "gatekeeper"].includes(result.selectedAgent));
    assert.equal(typeof result.score, "number");
    assert.equal(result.reply.to, "mcp-client");
  });

  it("writes assignment and completion updates to sidecar when available", async () => {
    const calls: Array<{ path: string; body: unknown }> = [];
    const server = createServer(async (req, res) => {
      const chunks: Uint8Array[] = [];
      for await (const chunk of req) chunks.push(chunk as Uint8Array);
      const raw = Buffer.concat(chunks).toString("utf-8");
      const body = raw ? JSON.parse(raw) : undefined;
      calls.push({ path: req.url ?? "", body });
      res.setHeader("content-type", "application/json");
      res.end(JSON.stringify({ ok: true }));
    });
    await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", () => resolve()));
    const address = server.address();
    assert.ok(address && typeof address !== "string");

    const runtime = createRuntime({ sidecarBaseUrl: `http://127.0.0.1:${address.port}` });
    await runtime.spawnAgent({
      task: "verify sidecar write-through",
      taskTreeId: "tree-sidecar",
      agentId: "orchestrator",
    });
    await new Promise<void>((resolve, reject) => server.close((err) => (err ? reject(err) : resolve())));

    assert.ok(calls.some((item) => item.path === "/v1/twin/task-assigned"));
    assert.ok(calls.some((item) => item.path === "/v1/twin/task-completed"));
  });
});
