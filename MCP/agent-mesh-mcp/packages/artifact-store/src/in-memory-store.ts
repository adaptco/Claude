import type {
  Artifact,
  ArtifactId,
  ArtifactStore,
  AgentId,
  FossilRecord,
  FossilEventType,
} from "@agent-mesh/core";
import { randomUUID, createHash } from "crypto";

function cosine(a: number[], b: number[]): number {
  let dot = 0, na = 0, nb = 0;
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i];
    na  += a[i] * a[i];
    nb  += b[i] * b[i];
  }
  return na === 0 || nb === 0 ? 0 : dot / (Math.sqrt(na) * Math.sqrt(nb));
}

export class InMemoryArtifactStore implements ArtifactStore {
  private readonly artifacts = new Map<ArtifactId, Artifact>();
  private readonly fossilChain: FossilRecord[] = [];
  private lastHash = "genesis";

  async put(
    input: Omit<Artifact, "id" | "createdAt" | "status">
  ): Promise<Artifact> {
    const artifact: Artifact = {
      ...input,
      id: randomUUID(),
      status: "draft",
      createdAt: Date.now(),
    };
    this.artifacts.set(artifact.id, artifact);
    return artifact;
  }

  async get(id: ArtifactId): Promise<Artifact | null> {
    return this.artifacts.get(id) ?? null;
  }

  async seal(id: ArtifactId, sealedBy: AgentId): Promise<Artifact> {
    const artifact = this.artifacts.get(id);
    if (!artifact) throw new Error(`Artifact ${id} not found`);
    if (artifact.status === "sealed") throw new Error(`Artifact ${id} already sealed`);

    const sealed: Artifact = { ...artifact, status: "sealed", sealedAt: Date.now() };
    this.artifacts.set(id, sealed);

    await this.fossil({
      event: "artifact_sealed",
      agentId: sealedBy,
      taskTreeId: artifact.taskTreeId,
      payload: { artifactId: id },
      chainHash: "", // computed inside fossil()
    });

    return sealed;
  }

  async query(vector: number[], topK = 5): Promise<Artifact[]> {
    const results: { artifact: Artifact; score: number }[] = [];
    for (const artifact of this.artifacts.values()) {
      if (!artifact.embedding || artifact.embedding.length === 0) continue;
      results.push({ artifact, score: cosine(vector, artifact.embedding) });
    }
    return results
      .sort((a, b) => b.score - a.score)
      .slice(0, topK)
      .map((r) => r.artifact);
  }

  async fossil(
    input: Omit<FossilRecord, "fossilId" | "sealedAt" | "chainHash"> & { chainHash?: string }
  ): Promise<FossilRecord> {
    const sealedAt = Date.now();
    const chainHash = createHash("sha256")
      .update(this.lastHash + sealedAt + JSON.stringify(input.payload))
      .digest("hex");

    const record: FossilRecord = {
      fossilId: randomUUID(),
      event: input.event,
      agentId: input.agentId,
      taskTreeId: input.taskTreeId,
      payload: input.payload,
      sealedAt,
      chainHash,
    };

    this.lastHash = chainHash;
    this.fossilChain.push(record);
    return record;
  }

  async fossils(): Promise<FossilRecord[]> {
    return [...this.fossilChain];
  }

  /** Verify the entire fossil chain for integrity */
  verifyChain(): { valid: boolean; brokenAt?: number } {
    let prev = "genesis";
    for (let i = 0; i < this.fossilChain.length; i++) {
      const f = this.fossilChain[i];
      const expected = createHash("sha256")
        .update(prev + f.sealedAt + JSON.stringify(f.payload))
        .digest("hex");
      if (expected !== f.chainHash) return { valid: false, brokenAt: i };
      prev = f.chainHash;
    }
    return { valid: true };
  }

  snapshot() {
    return {
      artifactCount: this.artifacts.size,
      fossilCount: this.fossilChain.length,
      chainValid: this.verifyChain().valid,
    };
  }
}
