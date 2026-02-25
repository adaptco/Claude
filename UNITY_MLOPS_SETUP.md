# Unity Autonomous MLOps Setup

This guide explains how to use `mlops_unity_pipeline.py` to run a fully automated Unity → RL training pipeline.

## What this pipeline provides

1. LLM-assisted Unity C# behavior generation.
2. Unity build artifact creation (extensible to real headless Unity builds).
3. ML-Agents training orchestration for 24/7 workloads.
4. Model registration metadata compatible with Vertex AI workflows.
5. Cron-based scheduling for hourly/nightly continuous training.

## Quick start

### 1) Install dependencies

```bash
pip install mlagents==1.0.0 pyyaml croniter
```

`croniter` is optional at runtime (the module has a built-in fallback parser), but recommended for full cron expression support.

### 2) Create a single training job

```python
import asyncio
from mlops_unity_pipeline import (
    UnityAssetSpec,
    RLTrainingConfig,
    TrainingJob,
    UnityMLOpsOrchestrator,
)

async def main():
    orchestrator = UnityMLOpsOrchestrator()

    asset = UnityAssetSpec(
        asset_id="test-001",
        name="SimpleAgent",
        asset_type="behavior",
        description="Reach target position",
    )

    config = RLTrainingConfig(
        algorithm="PPO",
        max_steps=100_000,
        num_envs=8,
        time_scale=20.0,
    )

    result = await orchestrator.execute_training_job(
        TrainingJob(job_id="test-job", asset_spec=asset, rl_config=config)
    )
    print(f"Model: {result.trained_model_path}")

asyncio.run(main())
```

### 3) Run recurring schedules

```python
import asyncio
from mlops_unity_pipeline import (
    UnityMLOpsOrchestrator,
    TrainingScheduler,
    TrainingSchedule,
    UnityAssetSpec,
    RLTrainingConfig,
)

async def run_forever():
    orchestrator = UnityMLOpsOrchestrator()
    scheduler = TrainingScheduler(orchestrator)

    schedule = TrainingSchedule(
        schedule_id="nightly",
        cron_expression="0 2 * * *",  # 2AM UTC daily
        asset_specs=[
            UnityAssetSpec(
                asset_id="nav-001",
                name="NavigationAgent",
                asset_type="behavior",
                description="Navigate to waypoint while avoiding obstacles",
            )
        ],
        rl_config=RLTrainingConfig(algorithm="PPO", max_steps=1_000_000),
    )

    scheduler.add_schedule(schedule)
    await scheduler.run_forever()

asyncio.run(run_forever())
```

## Vertex AI integration

Set `VERTEX_MODEL_REGISTRY_URI` to persist model registration metadata with a production URI:

```bash
export VERTEX_MODEL_REGISTRY_URI="projects/my-project/locations/us-central1/models"
```

The orchestrator always writes local registry records under:

```text
artifacts/mlops/registry/*.json
```

## Extending to real infrastructure

- Replace `build_unity_environment` with a headless Unity CLI build command.
- Replace `train_agent` placeholder model generation with `mlagents-learn` execution.
- Inject your own async notifier into `webhook_notifier` for Slack/Discord/HTTP callbacks.
- Configure Kubernetes CronJobs for horizontal scaling.

You can also pass command hooks directly to the orchestrator:

```python
orchestrator = UnityMLOpsOrchestrator(
    unity_build_command=["/opt/unity/Editor/Unity", "-batchmode", "-quit"],
    mlagents_train_command=["python", "scripts/run_mlagents_train.py"],
)
```

When `mlagents_train_command` is used, these environment variables are provided:

- `UNITY_BUILD_PATH`
- `MLAGENTS_CONFIG_PATH`
- `MLAGENTS_OUTPUT_MODEL`

## Offline RL workflow

1. Collect demonstration files (`.demo`) with ML-Agents.
2. Set `demo_path` in `RLTrainingConfig`.
3. Adjust trainer settings for BC/offline warm start.
4. Optionally fine-tune online using the built Unity environment.

## Monitoring recommendations

- Track run metrics in TensorBoard.
- Add custom evaluation episodes post-training.
- Export model cards and registry metadata per run.
