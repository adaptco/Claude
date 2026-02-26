#!/usr/bin/env python3
"""
Hardened physics_workflow_compiler.py

Features:
- argparse for CLI
- robust JSON file loading with clear errors
- safe YAML generation using PyYAML
- atomic writes to avoid partial files
- logging for diagnostics
- configurable input/output paths
"""

from pathlib import Path
import argparse
import json
import logging
import os
import sys
import tempfile

import yaml

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)


def load_json(path: Path):
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error("Required file not found: %s", path)
        raise
    except json.JSONDecodeError as e:
        logging.error("Invalid JSON in %s: %s", path, e)
        raise


def safe_write_yaml(obj, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Write to a temp file in the same directory then atomically replace
    fd, tmp_path = tempfile.mkstemp(dir=str(dest.parent))
    os.close(fd)
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                obj,
                f,
                sort_keys=False,
                allow_unicode=True,
                default_flow_style=False,
                indent=2,
            )
        os.replace(tmp_path, str(dest))
        logging.info("Wrote %s", dest)
    except Exception:
        logging.exception("Failed to write YAML to %s", dest)
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        raise


def build_workflow(name: str, curvature, threshold):
    job_name = f"notify-{name}"
    return {
        "name": f"generated-{name}",
        "on": ["workflow_dispatch"],
        "jobs": {
            job_name: {
                "runs-on": "ubuntu-latest",
                "steps": [
                    {
                        "name": "Notify",
                        "run": (
                            f"echo 'Route {name} curvature {curvature} "
                            f"exceeds threshold {threshold}'"
                        ),
                    }
                ],
            }
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Compile physics model into GitHub Actions workflows."
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=Path("agent_physics/physics_model.json"),
        help="Path to physics_model.json",
    )
    parser.add_argument(
        "--state",
        type=Path,
        default=Path("agent_physics/current_state.json"),
        help="Path to current_state.json",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(".github/workflows/generated"),
        help="Output directory for generated workflows",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Optional curvature threshold override",
    )
    args = parser.parse_args()

    try:
        model = load_json(args.model)
        load_json(args.state)  # validated for integrity; unused fields reserved
    except Exception:  # pylint: disable=broad-exception-caught
        logging.error("Aborting due to input file errors.")
        sys.exit(2)

    routes = model.get("routes") or []
    if not isinstance(routes, list):
        logging.error("Invalid model format: 'routes' must be a list.")
        sys.exit(3)

    args.out.mkdir(parents=True, exist_ok=True)

    generated_files = []
    try:
        for route in routes:
            name = route.get("name")
            if not name:
                logging.warning("Skipping route with missing name: %s", route)
                continue

            curvature = route.get("curvature")
            if curvature is None:
                logging.warning(
                    "Route %s missing curvature; defaulting to 0", name
                )
                curvature = 0

            threshold = (
                args.threshold
                if args.threshold is not None
                else route.get("threshold", 1.0)
            )

            workflow_obj = build_workflow(name, curvature, threshold)
            out_path = args.out / f"generated-{name}.yml"
            safe_write_yaml(workflow_obj, out_path)
            generated_files.append(str(out_path))

    except Exception:  # pylint: disable=broad-exception-caught
        logging.exception("Failed during workflow generation.")
        sys.exit(4)

    logging.info(
        "Generated %d workflow(s): %s",
        len(generated_files),
        ", ".join(generated_files),
    )
    print(json.dumps({"generated": generated_files}, ensure_ascii=False))


if __name__ == "__main__":
    main()
