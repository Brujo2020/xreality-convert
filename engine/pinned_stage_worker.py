"""Fail-closed launcher for offline stages with sealed local dependencies.

``StageSupervisor`` protects the host while a worker runs.  This module adds
the prerequisite that a worker is *not even spawned* until its stage manifest
has been loaded from owner-controlled storage and every declared local byte is
verified.  It intentionally has no downloader, network client, or fallback to
an unpinned executable.

The caller explicitly declares both the supply-chain entries a stage requires
and the verified script/artifact used to launch it.  This prevents a valid
model manifest from being used as a decorative check while a different helper
script is executed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence

from stage_supervisor import StageLimits, StageSupervisor
from supply_chain_registry import (
    SupplyChainError,
    VerifiedFile,
    VerifiedSupplyChainEntry,
    load_and_verify_manifest,
)


class PinnedStageWorkerError(ValueError):
    """The requested stage cannot safely be started."""


@dataclass(frozen=True)
class PinnedStageReceipt:
    """Immutable provenance returned only after a supervised launch succeeds."""

    manifest_hash: str
    scope: str
    entry_ids: tuple[str, ...]
    launcher_entry_id: str
    launcher_relative_path: str

    def as_dict(self) -> dict[str, object]:
        return {
            "manifest_hash": self.manifest_hash,
            "scope": self.scope,
            "entry_ids": list(self.entry_ids),
            "launcher_entry_id": self.launcher_entry_id,
            "launcher_relative_path": self.launcher_relative_path,
            "network_allowed": False,
        }


def _required_entry_ids(value: Sequence[str]) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or not value:
        raise PinnedStageWorkerError("pinned_stage_expected_entries_required")
    ids = tuple(value)
    if any(not isinstance(entry_id, str) or not entry_id for entry_id in ids):
        raise PinnedStageWorkerError("pinned_stage_entry_id_invalid")
    if len(set(ids)) != len(ids):
        raise PinnedStageWorkerError("pinned_stage_entry_id_duplicate")
    return ids


def _entry_files(entry: VerifiedSupplyChainEntry) -> tuple[VerifiedFile, ...]:
    return (entry.artifact, *entry.scripts)


def _verified_launcher(entry: VerifiedSupplyChainEntry, relative_path: str) -> VerifiedFile:
    if not isinstance(relative_path, str) or not relative_path:
        raise PinnedStageWorkerError("pinned_stage_launcher_path_invalid")
    for verified_file in _entry_files(entry):
        if verified_file.relative_path == relative_path:
            return verified_file
    raise PinnedStageWorkerError("pinned_stage_launcher_unpinned")


def _command_uses_launcher(command: Sequence[str], launcher: VerifiedFile) -> None:
    if isinstance(command, (str, bytes)) or not isinstance(command, Sequence) or not command:
        raise PinnedStageWorkerError("pinned_stage_command_invalid")
    if any(not isinstance(part, str) or not part for part in command):
        raise PinnedStageWorkerError("pinned_stage_command_invalid")

    expected = launcher.local_path.resolve(strict=True)
    for part in command:
        # A command token can be a flag or a non-path argument.  Only compare
        # path-like tokens; paths that do not exist are intentionally not
        # resolved here, because an output argument may be created by worker.
        candidate = Path(part)
        if candidate.is_absolute() or "/" in part or "\\" in part:
            try:
                if candidate.resolve(strict=True) == expected:
                    return
            except OSError:
                continue
    raise PinnedStageWorkerError("pinned_stage_launcher_not_in_command")


def _require_offline_limits(limits: StageLimits) -> StageLimits:
    if not isinstance(limits, StageLimits):
        raise PinnedStageWorkerError("pinned_stage_limits_invalid")
    if limits.network_allowed:
        raise PinnedStageWorkerError("pinned_stage_network_forbidden")
    # Recreate the immutable object so the no-network decision is explicit at
    # the composition boundary, rather than merely relying on a caller default.
    return StageLimits(
        timeout_seconds=limits.timeout_seconds,
        poll_seconds=limits.poll_seconds,
        minimum_free_percent=limits.minimum_free_percent,
        maximum_swap_growth_mb=limits.maximum_swap_growth_mb,
        network_allowed=False,
    )


class PinnedStageWorker:
    """Verify a stage's sealed supply chain before delegating to a watchdog."""

    def __init__(
        self,
        memory_snapshot: Callable[[], Mapping[str, float | None]],
        *,
        supervisor_factory: Callable[[Callable[[], Mapping[str, float | None]]], StageSupervisor] = StageSupervisor,
    ):
        self._memory_snapshot = memory_snapshot
        self._supervisor_factory = supervisor_factory

    def run(
        self,
        command: Sequence[str],
        *,
        cwd: str | Path,
        manifest_path: str | Path,
        local_root: str | Path,
        expected_scope: str,
        expected_entry_ids: Sequence[str],
        launcher_entry_id: str,
        launcher_relative_path: str,
        environment: Mapping[str, str] | None = None,
        limits: StageLimits = StageLimits(),
    ) -> dict[str, object]:
        """Run an attested local worker, or fail before creating a subprocess.

        ``manifest_path`` must be an owner-controlled, non-writable sealed
        declaration.  ``load_and_verify_manifest`` validates every declared
        artifact and script, so a corrupt unused entry also prevents launch.
        ``launcher_relative_path`` must name a verified file belonging to the
        selected required entry and must occur verbatim as a command path.
        """
        required_ids = _required_entry_ids(expected_entry_ids)
        if not isinstance(launcher_entry_id, str) or launcher_entry_id not in required_ids:
            raise PinnedStageWorkerError("pinned_stage_launcher_entry_invalid")
        if not isinstance(expected_scope, str) or not expected_scope:
            raise PinnedStageWorkerError("pinned_stage_scope_invalid")
        offline_limits = _require_offline_limits(limits)

        try:
            verified = load_and_verify_manifest(
                manifest_path,
                local_root=local_root,
                expected_scope=expected_scope,
            )
            selected = tuple(verified.by_id(entry_id) for entry_id in required_ids)
        except SupplyChainError as exc:
            raise PinnedStageWorkerError(f"pinned_stage_supply_chain_rejected:{exc}") from exc

        launcher = _verified_launcher(
            next(entry for entry in selected if entry.entry_id == launcher_entry_id),
            launcher_relative_path,
        )
        _command_uses_launcher(command, launcher)

        # StageSupervisor deterministically injects HF/Transformers offline
        # settings and strips proxy variables.  Passing a false-only limits
        # object makes network permission impossible through this launcher.
        result = self._supervisor_factory(self._memory_snapshot).run(
            command,
            cwd=cwd,
            environment=environment,
            limits=offline_limits,
        )
        receipt = PinnedStageReceipt(
            manifest_hash=verified.manifest_hash,
            scope=verified.scope,
            entry_ids=tuple(entry.entry_id for entry in selected),
            launcher_entry_id=launcher_entry_id,
            launcher_relative_path=launcher.relative_path,
        )
        return {"worker": result, "supply_chain": receipt.as_dict()}


__all__ = ["PinnedStageReceipt", "PinnedStageWorker", "PinnedStageWorkerError"]
