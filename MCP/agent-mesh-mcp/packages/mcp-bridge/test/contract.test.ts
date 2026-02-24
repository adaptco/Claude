import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, it } from "node:test";
import assert from "node:assert/strict";

import { SidecarClient } from "../src/index.js";

describe("OpenAPI contract", () => {
  it("defines all endpoints consumed by SidecarClient", () => {
    const repoRoot = resolve(fileURLToPath(new URL("../../..", import.meta.url)));
    const openapiPath = resolve(repoRoot, "services", "digital-twin-sidecar", "openapi.yaml");
    const doc = readFileSync(openapiPath, "utf-8");

    const requiredPathMethods = [
      "/health:\n    get:",
      "/v1/repo/search:\n    post:",
      "/v1/twin/state:\n    get:",
      "/v1/twin/tasks:\n    get:",
      "/v1/twin/task-assigned:\n    post:",
      "/v1/twin/task-completed:\n    post:",
    ];

    for (const marker of requiredPathMethods) {
      assert.ok(
        doc.includes(marker),
        `OpenAPI contract is missing required endpoint marker: ${marker}`
      );
    }
  });

  it("exports bridge methods expected by MCP server integration", () => {
    const client = new SidecarClient();
    assert.equal(typeof client.searchRepo, "function");
    assert.equal(typeof client.getTwinState, "function");
    assert.equal(typeof client.getTwinTasks, "function");
    assert.equal(typeof client.notifyTaskAssigned, "function");
    assert.equal(typeof client.notifyTaskCompleted, "function");
  });
});
