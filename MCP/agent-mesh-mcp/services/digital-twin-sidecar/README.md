# digital-twin-sidecar

Python sidecar service for phase-one A2A integration.

## Endpoints

- `GET /health`
- `POST /v1/repo/search`
- `GET /v1/twin/state`
- `GET /v1/twin/tasks`
- `POST /v1/twin/task-assigned`
- `POST /v1/twin/task-completed`

See `openapi.yaml` for the contract consumed by `@agent-mesh/mcp-bridge`.

## Run

```bash
python app.py
```
