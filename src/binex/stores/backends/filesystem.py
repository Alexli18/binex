"""Filesystem-based artifact store backend."""

from __future__ import annotations

import json
from pathlib import Path

from binex.models.artifact import Artifact


class FilesystemArtifactStore:
    """Store artifacts as JSON files in {base_path}/{run_id}/{artifact_id}.json."""

    def __init__(self, base_path: str) -> None:
        self._base_path = Path(base_path)
        self._index: dict[str, tuple[str, str]] = {}  # artifact_id -> (run_id, path)

    @staticmethod
    def _sanitize_component(name: str) -> str:
        """Reject path components containing traversal sequences."""
        if ".." in name or "/" in name or "\\" in name:
            raise ValueError(
                f"Invalid path component: {name!r} (must not contain '..', '/' or '\\\\')"
            )
        return name

    def _artifact_path(self, run_id: str, artifact_id: str) -> Path:
        safe_run = self._sanitize_component(run_id)
        safe_art = self._sanitize_component(artifact_id)
        return self._base_path / safe_run / f"{safe_art}.json"

    async def store(self, artifact: Artifact) -> None:
        path = self._artifact_path(artifact.run_id, artifact.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = artifact.model_dump(mode="json")
        path.write_text(json.dumps(data, indent=2, default=str))
        self._index[artifact.id] = (artifact.run_id, str(path))

    async def get(self, artifact_id: str) -> Artifact | None:
        self._sanitize_component(artifact_id)
        # Check in-memory index first
        entry = self._index.get(artifact_id)
        if entry is not None:
            path = Path(entry[1])
            if path.exists():
                data = json.loads(path.read_text())
                return Artifact.model_validate(data)

        # Scan filesystem for the artifact
        if self._base_path.exists():
            for f in self._base_path.rglob(f"{artifact_id}.json"):
                data = json.loads(f.read_text())
                return Artifact.model_validate(data)

        return None

    async def list_by_run(self, run_id: str) -> list[Artifact]:
        self._sanitize_component(run_id)
        run_dir = self._base_path / run_id
        if not run_dir.exists():
            return []
        results: list[Artifact] = []
        for f in run_dir.glob("*.json"):
            data = json.loads(f.read_text())
            results.append(Artifact.model_validate(data))
        return results

    async def get_lineage(self, artifact_id: str) -> list[Artifact]:
        result: list[Artifact] = []
        visited: set[str] = set()
        queue = [artifact_id]
        while queue:
            current_id = queue.pop(0)
            if current_id in visited:
                continue
            visited.add(current_id)
            art = await self.get(current_id)
            if art is None:
                continue
            if current_id != artifact_id:
                result.append(art)
            queue.extend(art.lineage.derived_from)
        return result


__all__ = ["FilesystemArtifactStore"]
