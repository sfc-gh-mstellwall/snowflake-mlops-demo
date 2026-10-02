from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "build" / "releases"

ALLOWLISTED_PATHS = (
    "jobs/train.py",
    "code_bundle.yml",
    "config/environments.yaml",
    "config/workflow.yaml",
    "project.yaml",
    "src/credit_default/__init__.py",
    "src/credit_default/contracts.py",
    "src/credit_default/evaluation.py",
    "src/credit_default/evidence.py",
    "src/credit_default/training.py",
    "src/credit_default/release.py",
    "src/credit_default/approval.py",
    "src/credit_default/monitoring.py",
)

EXCLUDED_NAME_PARTS = (
    ".ipynb_checkpoints",
    "__pycache__",
    ".venv",
    "memories",
    "versions/live",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def is_excluded(path: Path) -> bool:
    text = path.as_posix()
    return any(part in text for part in EXCLUDED_NAME_PARTS)


def collect_payload_files(project_dir: Path) -> list[Path]:
    files = []
    for relative in ALLOWLISTED_PATHS:
        path = project_dir / relative
        if not path.is_file():
            raise FileNotFoundError(f"Release payload is missing {relative}")
        if is_excluded(path.relative_to(project_dir)):
            raise ValueError(f"Allowlisted path is excluded: {relative}")
        files.append(path)
    return files


def build_release(
    project_dir: Path,
    output_dir: Path,
    release_id: str,
) -> dict:
    payload_dir = output_dir / release_id
    if payload_dir.exists():
        raise FileExistsError(f"Release directory already exists: {payload_dir}")
    payload_dir.mkdir(parents=True)

    files: list[dict[str, str]] = []
    for source in collect_payload_files(project_dir):
        relative = source.relative_to(project_dir).as_posix()
        destination = payload_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        files.append({"path": relative, "sha256": sha256_file(source)})

    manifest = {
        "release_id": release_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_root": str(project_dir),
        "files": files,
        "excluded": list(EXCLUDED_NAME_PARTS),
        "execute_from_notebook_cell": False,
        "create_from_workspace_live": False,
    }
    payload_hash = hashlib.sha256(
        json.dumps(files, sort_keys=True).encode("utf-8")
    ).hexdigest()
    manifest["payload_digest"] = payload_hash
    (payload_dir / "release_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an allowlisted Code Bundle payload")
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    manifest = build_release(PROJECT_DIR, args.output_dir, args.release_id)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
