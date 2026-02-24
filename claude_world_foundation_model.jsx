import { useState, useEffect, useRef } from "react"

const TOKENS = {
  context: [
    { id: "T001", layer: "SETUP", key: "install", val: "pnpm install / npm install", weight: 0.72 },
    { id: "T002", layer: "SETUP", key: "dev", val: "nodemon --watch src --exec ts-node src/index.ts", weight: 0.91 },
    { id: "T003", layer: "SETUP", key: "test", val: "npm run build && jest", weight: 0.88 },
    { id: "T004", layer: "STYLE", key: "lang", val: "TypeScript strict mode", weight: 0.95 },
    { id: "T005", layer: "STYLE", key: "fmt", val: "Prettier + Airbnb ESLint", weight: 0.84 },
    { id: "T006", layer: "STYLE", key: "quotes", val: "singleQuote: true, semi: true", weight: 0.79 },
    { id: "T007", layer: "ARCH", key: "entry", val: "src/index.ts → dist/index.js", weight: 0.97 },
    { id: "T008", layer: "ARCH", key: "framework", val: "Express.js + ts-node", weight: 0.93 },
    { id: "T009", layer: "ARCH", key: "tsconfig", val: "ES2020, commonjs, strict, esModuleInterop", weight: 0.89 },
    { id: "T010", layer: "ARCH", key: "build", val: "tsc → dist/ for production", weight: 0.86 },
    { id: "T011", layer: "FLOW", key: "pr_target", val: "develop branch", weight: 0.75 },
    { id: "T012", layer: "FLOW", key: "pr_format", val: "Closes #issue in description", weight: 0.71 },
    { id: "T013", layer: "FLOW", key: "test_gate", val: "All tests pass before PR", weight: 0.98 },
    { id: "T014", layer: "ORCH", key: "avatar", val: "Claude — Lead Orchestrator", weight: 1.00 },
    { id: "T015", layer: "ORCH", key: "role", val: "Head Coder / Transformer Fn", weight: 1.00 },
  ]
}

const LAYERS = ["SETUP", "STYLE", "ARCH", "FLOW", "ORCH"]
const LAYER_COLOR = {
  SETUP: "#00ffc8",
  STYLE: "#f5a623",
  ARCH:  "#7b61ff",
  FLOW:  "#ff6b6b",
  ORCH:  "#ffffff",
}

const SUMMARY = `The project is an Express.js web server migrated to TypeScript strict mode. 
Entry point: src/index.ts compiles to dist/index.js via tsc. 
Dev workflow: nodemon + ts-node with hot reload. 
Style: Airbnb ESLint + Prettier (single quotes, semi). 
Tests: build-then-jest pipeline. PRs target develop branch, reference issues. 
Claude acts as Lead Orchestrator — a transformer function over all context layers — 
collapsing token space into executable decisions with zero information loss.`

function AnimatedBar({ weight, color }) {
  const [w, setW] = useState(0)
  useEffect(() => { const t = setTimeout(() => setW(weight * 100), 60); return () => clearTimeout(t) }, [weight])
  return (
    <div style={{ background: "#111", borderRadius: 2, height: 4, width: "100%", overflow: "hidden" }}>
      <div style={{ height: "100%", width: `${w}%`, background: color, transition: "width 1.2s cubic-bezier(0.4,0,0.2,1)", boxShadow: `0 0 6px ${color}` }} />
    </div>
  )
}

function TensorPulse() {
  const [tick, setTick] = useState(0)
  useEffect(() => {
    const id = setInterval(() => setTick(t => t + 1), 80)
    return () => clearInterval(id)
  }, [])
  const SIZE = 7
  return (
    <div style={{ display: "grid", gridTemplateColumns: `repeat(${SIZE}, 1fr)`, gap: 3, padding: 8 }}>
      {Array.from({ length: SIZE * SIZE }).map((_, i) => {
        const v = Math.sin((i + tick) * 0.4) * 0.5 + 0.5
        const layer = LAYERS[Math.floor((i / (SIZE * SIZE)) * LAYERS.length)]
        const color = LAYER_COLOR[layer] || "#fff"
        return (
          <div key={i} style={{
            width: 10, height: 10, borderRadius: 2,
            background: color,
            opacity: 0.2 + v * 0.8,
            transform: `scale(${0.6 + v * 0.5})`,
            transition: "all 0.08s ease",
            boxShadow: v > 0.8 ? `0 0 4px ${color}` : "none"
          }} />
        )
      })}
    </div>
  )
}

function TokenRow({ token, index }) {
  const color = LAYER_COLOR[token.layer] || "#aaa"
  const [vis, setVis] = useState(false)
  useEffect(() => { const t = setTimeout(() => setVis(true), index * 55); return () => clearTimeout(t) }, [index])
  return (
    <div style={{
      display: "grid", gridTemplateColumns: "52px 52px 1fr 1fr 80px",
      gap: 8, alignItems: "center", padding: "6px 0",
      borderBottom: "1px solid #1a1a1a",
      opacity: vis ? 1 : 0, transform: vis ? "none" : "translateY(8px)",
      transition: "all 0.4s ease",
      fontSize: 11, fontFamily: "'IBM Plex Mono', monospace"
    }}>
      <span style={{ color: "#555" }}>{token.id}</span>
      <span style={{ color, fontWeight: 700, fontSize: 9, letterSpacing: 1 }}>{token.layer}</span>
      <span style={{ color: "#888" }}>{token.key}</span>
      <span style={{ color: "#ccc", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{token.val}</span>
      <AnimatedBar weight={token.weight} color={color} />
    </div>
  )
}

function Loop({ label, active }) {
  const [deg, setDeg] = useState(0)
  useEffect(() => {
    if (!active) return
    const id = setInterval(() => setDeg(d => d + 2), 20)
    return () => clearInterval(id)
  }, [active])
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
      <div style={{
        width: 64, height: 64, border: "2px solid #333",
        borderTop: `2px solid ${active ? "#00ffc8" : "#555"}`,
        borderRadius: "50%",
        transform: `rotate(${deg}deg)`,
        transition: active ? "none" : "all 0.3s",
        boxShadow: active ? "0 0 12px #00ffc866" : "none"
      }} />
      <span style={{ fontSize: 9, color: "#555", fontFamily: "'IBM Plex Mono', monospace", letterSpacing: 1 }}>{label}</span>
    </div>
  )
}

export default function WorldFoundationModel() {
  const [loopActive, setLoopActive] = useState(false)
  const [phase, setPhase] = useState("INIT")
  const phases = ["INIT", "INGEST", "COMPRESS", "EMBED", "ORCHESTRATE", "EMIT"]

  useEffect(() => {
    let i = 0
    const t = setTimeout(() => setLoopActive(true), 600)
    const id = setInterval(() => {
      i = (i + 1) % phases.length
      setPhase(phases[i])
    }, 1400)
    return () => { clearTimeout(t); clearInterval(id) }
  }, [])

  const totalTokens = TOKENS.context.reduce((s, t) => s + Math.round(t.weight * 100), 0)

  return (
    <div style={{
      minHeight: "100vh", background: "#080808",
      fontFamily: "'IBM Plex Mono', monospace",
      color: "#ddd", padding: "32px 24px",
      backgroundImage: "radial-gradient(ellipse at 20% 0%, #0d1f1a 0%, transparent 60%), radial-gradient(ellipse at 80% 100%, #0f0d1f 0%, transparent 60%)"
    }}>
      <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;700&display=swap" rel="stylesheet" />

      {/* Header */}
      <div style={{ maxWidth: 900, margin: "0 auto" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 32 }}>
          <div>
            <div style={{ fontSize: 9, color: "#555", letterSpacing: 3, marginBottom: 6 }}>WORLD FOUNDATION MODEL v1.0</div>
            <h1 style={{ fontSize: 26, fontWeight: 700, margin: 0, letterSpacing: -0.5 }}>
              <span style={{ color: "#fff" }}>CLAUDE</span>
              <span style={{ color: "#00ffc8" }}>::</span>
              <span style={{ color: "#7b61ff" }}>LEAD_ORCHESTRATOR</span>
            </h1>
            <div style={{ fontSize: 10, color: "#555", marginTop: 4 }}>
              HEAD_CODER · TRANSFORMER_FN · CONTEXT_LOOP
            </div>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: 9, color: "#555", marginBottom: 4 }}>PHASE</div>
            <div style={{
              fontSize: 13, fontWeight: 700, color: "#00ffc8",
              padding: "4px 10px", border: "1px solid #00ffc822",
              background: "#00ffc808", letterSpacing: 2
            }}>{phase}</div>
          </div>
        </div>

        {/* Tensor + Loops */}
        <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: 24, marginBottom: 32, alignItems: "center" }}>
          <div style={{ border: "1px solid #1a1a1a", padding: 4, background: "#050505" }}>
            <div style={{ fontSize: 8, color: "#444", padding: "4px 8px", letterSpacing: 2 }}>TENSOR_STATE [7×7]</div>
            <TensorPulse />
          </div>
          <div>
            <div style={{ fontSize: 8, color: "#444", letterSpacing: 2, marginBottom: 12 }}>CONTEXT_LOOP · SINGLE PASS</div>
            <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
              {["INGEST", "COMPRESS", "EMBED", "EMIT"].map(l => (
                <Loop key={l} label={l} active={loopActive && phase !== "INIT"} />
              ))}
            </div>
            <div style={{ marginTop: 14, fontSize: 10, color: "#555", lineHeight: 1.7 }}>
              <span style={{ color: "#7b61ff" }}>f</span>(context) → compress → embed(avatar) → orchestrate → <span style={{ color: "#00ffc8" }}>artifact↩</span>
            </div>
          </div>
        </div>

        {/* Summary */}
        <div style={{
          border: "1px solid #1a1a1a", padding: 16, marginBottom: 24,
          background: "#050505", position: "relative"
        }}>
          <div style={{ fontSize: 8, color: "#444", letterSpacing: 2, marginBottom: 8 }}>COMPRESSED_SUMMARY · {totalTokens} TOKEN-WEIGHTS SPENT</div>
          <p style={{ margin: 0, fontSize: 11, lineHeight: 1.8, color: "#aaa" }}>{SUMMARY}</p>
          <div style={{
            position: "absolute", top: 12, right: 12,
            fontSize: 8, color: "#00ffc8", letterSpacing: 1
          }}>Σ {totalTokens}</div>
        </div>

        {/* Layer Legend */}
        <div style={{ display: "flex", gap: 16, marginBottom: 12, flexWrap: "wrap" }}>
          {LAYERS.map(l => (
            <div key={l} style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <div style={{ width: 8, height: 8, borderRadius: 1, background: LAYER_COLOR[l] }} />
              <span style={{ fontSize: 9, color: "#666", letterSpacing: 1 }}>{l}</span>
            </div>
          ))}
        </div>

        {/* Token Table */}
        <div style={{ border: "1px solid #1a1a1a", background: "#050505" }}>
          <div style={{
            display: "grid", gridTemplateColumns: "52px 52px 1fr 1fr 80px",
            gap: 8, padding: "8px 0", borderBottom: "1px solid #222",
            fontSize: 8, color: "#444", letterSpacing: 2
          }}>
            <span>ID</span><span>LAYER</span><span>KEY</span><span>VALUE</span><span>WEIGHT</span>
          </div>
          <div style={{ padding: "0 0 8px" }}>
            {TOKENS.context.map((t, i) => <TokenRow key={t.id} token={t} index={i} />)}
          </div>
        </div>

        {/* Footer */}
        <div style={{ marginTop: 20, display: "flex", justifyContent: "space-between", fontSize: 9, color: "#333" }}>
          <span>CLAUDE SONNET 4.6 · ANTHROPIC</span>
          <span>AVATAR::EMBEDDED · LOOP::CLOSED · ARTIFACT::RETURNED</span>
        </div>
      </div>
    </div>
  )
}
