import { createServer } from "node:http";
import { afterEach, describe, it } from "node:test";
import assert from "node:assert/strict";

import { BridgeError, SidecarClient } from "../src/index.js";

interface RunningServer {
  baseUrl: string;
  close: () => Promise<void>;
}

async function startJsonServer(
  handler: (method: string, path: string, body: unknown) => unknown
): Promise<RunningServer> {
  const server = createServer(async (req, res) => {
    const chunks: Uint8Array[] = [];
    for await (const chunk of req) chunks.push(chunk as Uint8Array);
    const raw = Buffer.concat(chunks).toString("utf-8");
    const body = raw ? JSON.parse(raw) : undefined;
    const payload = handler(req.method ?? "GET", req.url ?? "/", body);
    res.setHeader("content-type", "application/json");
    res.end(JSON.stringify(payload));
  });

  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", () => resolve()));
  const address = server.address();
  assert.ok(address && typeof address !== "string");
  return {
    baseUrl: `http://127.0.0.1:${address.port}`,
    close: () => new Promise<void>((resolve, reject) => server.close((err) => (err ? reject(err) : resolve()))),
  };
}

let currentServer: RunningServer | undefined;

afterEach(async () => {
  if (currentServer) {
    await currentServer.close();
    currentServer = undefined;
  }
});

describe("SidecarClient", () => {
  it("searches repo and validates response schema", async () => {
    currentServer = await startJsonServer((_method, path) => {
      if (path === "/v1/repo/search") {
        return {
          ok: true,
          results: [{ key: "README.md:0", file: "README.md", score: 0.9, text: "hello" }],
          count: 1,
        };
      }
      return { ok: true };
    });

    const client = new SidecarClient({ baseUrl: currentServer.baseUrl, timeoutMs: 2000 });
    const result = await client.searchRepo("hello");
    assert.equal(result.ok, true);
    assert.equal(result.count, 1);
    assert.equal(result.results[0]?.file, "README.md");
  });

  it("returns unavailable error deterministically when sidecar is down", async () => {
    const client = new SidecarClient({ baseUrl: "http://127.0.0.1:1", timeoutMs: 100 });
    await assert.rejects(
      client.getTwinState(),
      (err: unknown) => err instanceof BridgeError && err.code === "SIDECAR_UNAVAILABLE"
    );
  });

  it("fails closed on malformed sidecar payloads", async () => {
    currentServer = await startJsonServer((_method, path) => {
      if (path === "/v1/repo/search") {
        return { ok: true, results: "invalid", count: 1 };
      }
      return { ok: true };
    });
    const client = new SidecarClient({ baseUrl: currentServer.baseUrl });
    await assert.rejects(
      client.searchRepo("x"),
      (err: unknown) => err instanceof BridgeError && err.code === "SIDECAR_MALFORMED_RESPONSE"
    );
  });
});
