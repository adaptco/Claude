"""End-to-end Unity MLOps orchestration for asset generation and RL training.

This module provides a pragmatic, testable pipeline skeleton that can be wired into
real Unity, ML-Agents, and Vertex AI infrastructure.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional
from uuid import uuid4

try:
    from croniter import croniter
except ImportError:  # pragma: no cover - exercised in environments without croniter.
    croniter = None



@dataclass(frozen=True)
class UnityAssetSpec:
    """Specifies a Unity asset/behavior to generate and train."""

    asset_id: str
    name: str
    asset_type: str
    description: str
    observation_space: Dict[str, Any] = field(default_factory=dict)
    action_space: Dict[str, Any] = field(default_factory=dict)
    generation_hints: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RLTrainingConfig:
    """Training settings for Unity ML-Agents."""

    algorithm: str = "PPO"
    max_steps: int = 1_000_000
    num_envs: int = 16
    time_scale: float = 20.0
    behavior_name: str = "AgentBehavior"
    learning_rate: float = 3e-4
    batch_size: int = 1024
    demo_path: Optional[str] = None


@dataclass(frozen=True)
class TrainingJob:
    """A single trainable job that binds an asset spec and RL config."""

    job_id: str
    asset_spec: UnityAssetSpec
    rl_config: RLTrainingConfig
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class TrainingResult:
    """Result metadata returned after a training run."""

    job_id: str
    status: str
    generated_code_path: str
    unity_build_path: str
    trained_model_path: str
    model_registry_uri: Optional[str]
    metrics: Dict[str, Any] = field(default_factory=dict)


class UnityMLOpsOrchestrator:
    """Coordinates generation, build, training, and registry publication."""

    def __init__(
        self,
        workspace_dir: str | Path = "artifacts/mlops",
        llm_code_generator: Optional[Callable[[UnityAssetSpec], Awaitable[str]]] = None,
        webhook_notifier: Optional[Callable[[str, Dict[str, Any]], Awaitable[None]]] = None,
        unity_build_command: Optional[List[str]] = None,
        mlagents_train_command: Optional[List[str]] = None,
    ) -> None:
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.llm_code_generator = llm_code_generator
        self.webhook_notifier = webhook_notifier
        self.unity_build_command = unity_build_command
        self.mlagents_train_command = mlagents_train_command

    async def execute_training_job(self, job: TrainingJob) -> TrainingResult:
        """Run the full pipeline for a single job."""

        job_dir = self.workspace_dir / job.job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        code_path = await self.generate_unity_code(job.asset_spec, job_dir)
        build_path = await self.build_unity_environment(job.asset_spec, code_path, job_dir)
        model_path, metrics = await self.train_agent(job, build_path, job_dir)
        registry_uri = await self.register_model(job, model_path, metrics)

        result = TrainingResult(
            job_id=job.job_id,
            status="completed",
            generated_code_path=str(code_path),
            unity_build_path=str(build_path),
            trained_model_path=str(model_path),
            model_registry_uri=registry_uri,
            metrics=metrics,
        )
        await self._notify("training.completed", {"job_id": job.job_id, "result": result.__dict__})
        return result

    async def generate_unity_code(self, spec: UnityAssetSpec, job_dir: Path) -> Path:
        output = job_dir / f"{spec.name}.cs"
        if self.llm_code_generator:
            code = await self.llm_code_generator(spec)
        else:
            code = self._default_code_template(spec)
        output.write_text(code, encoding="utf-8")
        await self._notify("generation.completed", {"asset_id": spec.asset_id, "code_path": str(output)})
        return output

    async def build_unity_environment(self, spec: UnityAssetSpec, code_path: Path, job_dir: Path) -> Path:
        build_dir = job_dir / "Build"
        build_dir.mkdir(parents=True, exist_ok=True)
        build_marker = build_dir / f"{spec.name}.build.json"
        payload = {
            "asset_id": spec.asset_id,
            "asset_type": spec.asset_type,
            "generated_code": str(code_path),
            "built_at": datetime.now(timezone.utc).isoformat(),
        }
        build_marker.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        if self.unity_build_command:
            await asyncio.to_thread(
                subprocess.run,
                [*self.unity_build_command, str(code_path), str(build_dir)],
                check=True,
                cwd=str(job_dir),
            )

        await self._notify("build.completed", {"asset_id": spec.asset_id, "build_path": str(build_marker)})
        return build_marker

    async def train_agent(self, job: TrainingJob, build_path: Path, job_dir: Path) -> tuple[Path, Dict[str, Any]]:
        run_dir = job_dir / "training"
        run_dir.mkdir(parents=True, exist_ok=True)

        # Emit ML-Agents YAML config for reproducible training.
        trainer_config = {
            "behaviors": {
                job.rl_config.behavior_name: {
                    "trainer_type": job.rl_config.algorithm.lower(),
                    "hyperparameters": {
                        "learning_rate": job.rl_config.learning_rate,
                        "batch_size": job.rl_config.batch_size,
                    },
                    "max_steps": job.rl_config.max_steps,
                    "time_horizon": 64,
                    "summary_freq": 10_000,
                }
            }
        }
        config_path = run_dir / "trainer_config.json"
        config_path.write_text(json.dumps(trainer_config, indent=2), encoding="utf-8")

        model_path = run_dir / f"{job.asset_spec.name}.onnx"

        if self.mlagents_train_command:
            env = os.environ.copy()
            env["UNITY_BUILD_PATH"] = str(build_path)
            env["MLAGENTS_CONFIG_PATH"] = str(config_path)
            env["MLAGENTS_OUTPUT_MODEL"] = str(model_path)
            await asyncio.to_thread(
                subprocess.run,
                self.mlagents_train_command,
                check=True,
                cwd=str(job_dir),
                env=env,
            )
            if not model_path.exists():
                raise RuntimeError("mlagents command completed without writing MLAGENTS_OUTPUT_MODEL")
        else:
            # Write a deterministic placeholder model artifact when external binaries
            # are not available in CI/local dev.
            model_path.write_bytes(b"unity-mlagents-placeholder-model")

        metrics = {
            "algorithm": job.rl_config.algorithm,
            "max_steps": job.rl_config.max_steps,
            "num_envs": job.rl_config.num_envs,
            "time_scale": job.rl_config.time_scale,
            "build_source": str(build_path),
            "reward_mean": 0.0,
        }
        metrics_path = run_dir / "metrics.json"
        metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

        await self._notify("training.completed", {"job_id": job.job_id, "model_path": str(model_path)})
        return model_path, metrics

    async def register_model(self, job: TrainingJob, model_path: Path, metrics: Dict[str, Any]) -> Optional[str]:
        """Register model metadata. Set VERTEX_MODEL_REGISTRY_URI to activate."""

        registry_uri = os.getenv("VERTEX_MODEL_REGISTRY_URI")
        registry_dir = self.workspace_dir / "registry"
        registry_dir.mkdir(parents=True, exist_ok=True)
        local_record = registry_dir / f"{job.job_id}.json"
        local_record.write_text(
            json.dumps(
                {
                    "job_id": job.job_id,
                    "asset_id": job.asset_spec.asset_id,
                    "model_path": str(model_path),
                    "vertex_registry_uri": registry_uri,
                    "metrics": metrics,
                    "registered_at": datetime.now(timezone.utc).isoformat(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        await self._notify("registry.completed", {"job_id": job.job_id, "record": str(local_record)})
        return registry_uri

    async def _notify(self, event_name: str, payload: Dict[str, Any]) -> None:
        if self.webhook_notifier:
            await self.webhook_notifier(event_name, payload)

    @staticmethod
    def _default_code_template(spec: UnityAssetSpec) -> str:
        safe_name = "".join(ch for ch in spec.name if ch.isalnum() or ch == "_") or "GeneratedAgent"
        return (
            "using UnityEngine;\n"
            "using Unity.MLAgents;\n"
            "using Unity.MLAgents.Actuators;\n"
            "using Unity.MLAgents.Sensors;\n\n"
            f"public class {safe_name} : Agent {{\n"
            f"    // Auto-generated from spec: {spec.description}\n"
            "    public override void CollectObservations(VectorSensor sensor) { }\n"
            "    public override void OnActionReceived(ActionBuffers actions) { }\n"
            "}\n"
        )


def _next_cron_time(cron_expression: str, base: datetime) -> datetime:
    """Compute next UTC run for a basic 5-field cron expression.

    Supported tokens: `*` or exact integer values.
    """

    if croniter is not None:
        return croniter(cron_expression, base).get_next(datetime)

    fields = cron_expression.strip().split()
    if len(fields) != 5:
        raise ValueError(f"Expected 5 cron fields, got: {cron_expression!r}")

    minute_f, hour_f, day_f, month_f, weekday_f = fields

    allowed = {
        "minute": _expand_cron_field(minute_f, 0, 59),
        "hour": _expand_cron_field(hour_f, 0, 23),
        "day": _expand_cron_field(day_f, 1, 31),
        "month": _expand_cron_field(month_f, 1, 12),
        "weekday": _expand_cron_field(weekday_f.replace("7", "0"), 0, 6),
    }

    candidate = base.astimezone(timezone.utc).replace(second=0, microsecond=0) + timedelta(minutes=1)
    for _ in range(525600):  # up to 1 year search
        if (
            candidate.minute in allowed["minute"]
            and candidate.hour in allowed["hour"]
            and candidate.day in allowed["day"]
            and candidate.month in allowed["month"]
            and (candidate.isoweekday() % 7) in allowed["weekday"]
        ):
            return candidate
        candidate += timedelta(minutes=1)

    raise ValueError(f"Unable to resolve next run for cron expression: {cron_expression}")


def _expand_cron_field(token: str, minimum: int, maximum: int) -> set[int]:
    """Expand one cron field supporting wildcards, ranges, and steps."""

    values: set[int] = set()
    for part in token.split(","):
        part = part.strip()
        if not part:
            continue

        step = 1
        if "/" in part:
            base, step_text = part.split("/", 1)
            part = base
            step = int(step_text)
            if step <= 0:
                raise ValueError(f"Invalid step '{step_text}' in cron token '{token}'")

        if part == "*":
            start, end = minimum, maximum
        elif "-" in part:
            start_text, end_text = part.split("-", 1)
            start, end = int(start_text), int(end_text)
        else:
            start = end = int(part)

        if start < minimum or end > maximum or start > end:
            raise ValueError(f"Out-of-range cron value '{part}' expected [{minimum}, {maximum}]")

        values.update(range(start, end + 1, step))

    if not values:
        raise ValueError(f"Unable to parse cron field '{token}'")
    return values



@dataclass(frozen=True)
class TrainingSchedule:
    """Cron-driven schedule that emits training jobs."""

    schedule_id: str
    cron_expression: str
    asset_specs: List[UnityAssetSpec]
    rl_config: RLTrainingConfig


class TrainingScheduler:
    """Simple asynchronous scheduler for recurring training jobs."""

    def __init__(self, orchestrator: UnityMLOpsOrchestrator, poll_interval_s: float = 1.0) -> None:
        self.orchestrator = orchestrator
        self.poll_interval_s = poll_interval_s
        self._schedules: Dict[str, TrainingSchedule] = {}
        self._next_run: Dict[str, datetime] = {}
        self._active_tasks: set[asyncio.Task[Any]] = set()
        self._stop_event = asyncio.Event()

    def add_schedule(self, schedule: TrainingSchedule) -> None:
        self._schedules[schedule.schedule_id] = schedule
        base = datetime.now(timezone.utc)
        self._next_run[schedule.schedule_id] = _next_cron_time(schedule.cron_expression, base)

    def remove_schedule(self, schedule_id: str) -> None:
        self._schedules.pop(schedule_id, None)
        self._next_run.pop(schedule_id, None)

    async def run_forever(self) -> None:
        self._stop_event.clear()
        while not self._stop_event.is_set():
            now = datetime.now(timezone.utc)
            for schedule_id, schedule in list(self._schedules.items()):
                due = self._next_run.get(schedule_id)
                if due and now >= due:
                    self._dispatch_schedule(schedule)
                    self._next_run[schedule_id] = _next_cron_time(schedule.cron_expression, now)
            await asyncio.sleep(self.poll_interval_s)

    async def run_once(self) -> None:
        now = datetime.now(timezone.utc)
        for schedule_id, schedule in list(self._schedules.items()):
            due = self._next_run.get(schedule_id)
            if due and now >= due:
                self._dispatch_schedule(schedule)
                self._next_run[schedule_id] = _next_cron_time(schedule.cron_expression, now)
        await self._drain_finished_tasks()

    async def shutdown(self) -> None:
        self._stop_event.set()
        if self._active_tasks:
            await asyncio.gather(*self._active_tasks, return_exceptions=True)

    def _dispatch_schedule(self, schedule: TrainingSchedule) -> None:
        for spec in schedule.asset_specs:
            job = TrainingJob(job_id=f"{schedule.schedule_id}-{uuid4().hex[:8]}", asset_spec=spec, rl_config=schedule.rl_config)
            task = asyncio.create_task(self.orchestrator.execute_training_job(job))
            self._active_tasks.add(task)
            task.add_done_callback(self._active_tasks.discard)

    async def _drain_finished_tasks(self) -> None:
        done = [task for task in self._active_tasks if task.done()]
        if done:
            await asyncio.gather(*done, return_exceptions=True)
