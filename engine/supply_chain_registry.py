"""Local, offline and fail-closed supply-chain manifest verification.

This module deliberately has no downloader and no network client.  It binds a
model weight, installed skill, or helper script to a HTTPS source repository,
an immutable full Git commit, a recognised license identifier, and bytes that
already exist under one managed local root (a sealed job or engine config).

The manifest is content addressed as well.  Consequently a caller cannot
quietly change a source URL, license, path, or hash after review and retain a
previous approval.  Loading a manifest additionally rejects writable or
symlinked files; verification rejects symlinks in every artifact path segment.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
from types import MappingProxyType
from typing import Any, Mapping
from urllib.parse import urlparse


SUPPLY_CHAIN_SCHEMA_VERSION = 1
SUPPLY_CHAIN_KIND = "xreality_local_supply_chain_manifest"
MAX_MANIFEST_BYTES = 512 * 1024
MAX_ARTIFACT_BYTES = 32 * 1024 * 1024 * 1024
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_-]{0,95}$")
_LICENSE = re.compile(r"^[A-Za-z0-9.-]{2,100}$")
_KINDS = frozenset({"model", "skill", "script"})
_SCOPES = frozenset({"job", "config"})

# Deliberately small and explicit.  New licensing terms require a conscious
# local policy update rather than silently accepting a free-form label.
ALLOWED_LICENSE_IDS = frozenset({
    "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "CC-BY-4.0",
    "CC-BY-SA-4.0", "GPL-3.0-only", "Hunyuan3D-2.1-Community-License",
    "LGPL-3.0-only", "MIT", "MPL-2.0", "OpenRAIL++-M",
})


class SupplyChainError(ValueError):
    """A manifest or a local artifact is not trustworthy enough to execute."""


@dataclass(frozen=True)
class VerifiedFile:
    """A byte-verified file below the explicitly selected managed root."""

    relative_path: str
    sha256: str
    local_path: Path


@dataclass(frozen=True)
class VerifiedSupplyChainEntry:
    entry_id: str
    kind: str
    source_repo: str
    source_commit: str
    license_id: str
    artifact: VerifiedFile
    scripts: tuple[VerifiedFile, ...]


@dataclass(frozen=True)
class VerifiedSupplyChainManifest:
    scope: str
    manifest_hash: str
    entries: tuple[VerifiedSupplyChainEntry, ...]

    def by_id(self, entry_id: str) -> VerifiedSupplyChainEntry:
        for entry in self.entries:
            if entry.entry_id == entry_id:
                return entry
        raise SupplyChainError("supply_chain_entry_not_found")


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: Mapping[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value)).hexdigest()


def _without_self_hash(value: Mapping[str, Any]) -> dict[str, Any]:
    copy = deepcopy(dict(value))
    copy.pop("self_hash", None)
    return copy


def _require_identifier(value: Any, reason: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise SupplyChainError(reason)
    return value


def _require_hash(value: Any, reason: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise SupplyChainError(reason)
    return value


def _require_repo(value: Any) -> str:
    if not isinstance(value, str) or len(value) > 500:
        raise SupplyChainError("source_repo_invalid")
    parsed = urlparse(value)
    if (
        parsed.scheme != "https" or not parsed.netloc or parsed.username is not None
        or parsed.password is not None or parsed.query or parsed.fragment
        or not parsed.path or parsed.path.endswith("/")
    ):
        raise SupplyChainError("source_repo_invalid")
    parts = PurePosixPath(parsed.path).parts
    if len(parts) < 3 or any(part in {"", ".", ".."} for part in parts):
        raise SupplyChainError("source_repo_invalid")
    # Canonical spelling prevents equivalent-but-different URLs being approved.
    if value != f"https://{parsed.netloc}{parsed.path}":
        raise SupplyChainError("source_repo_not_canonical")
    return value


def _require_relative_path(value: Any, reason: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 400 or "\\" in value:
        raise SupplyChainError(reason)
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise SupplyChainError(reason)
    return path.as_posix()


def _require_license(value: Any) -> str:
    if not isinstance(value, str) or _LICENSE.fullmatch(value) is None or value not in ALLOWED_LICENSE_IDS:
        raise SupplyChainError("license_id_not_allowed")
    return value


def _validate_file_claim(value: Any, *, reason: str) -> dict[str, str]:
    if not isinstance(value, Mapping) or set(value) != {"path", "sha256"}:
        raise SupplyChainError(reason)
    return {
        "path": _require_relative_path(value.get("path"), f"{reason}_path"),
        "sha256": _require_hash(value.get("sha256"), f"{reason}_sha256"),
    }


def _normalize_entry(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) not in ({"id", "kind", "source", "license_id", "artifact"}, {"id", "kind", "source", "license_id", "artifact", "scripts"}):
        raise SupplyChainError("supply_chain_entry_invalid")
    entry_id = _require_identifier(value.get("id"), "supply_chain_entry_id_invalid")
    kind = value.get("kind")
    if kind not in _KINDS:
        raise SupplyChainError("supply_chain_entry_kind_invalid")
    source = value.get("source")
    if not isinstance(source, Mapping) or set(source) != {"repo", "commit"}:
        raise SupplyChainError("supply_chain_source_invalid")
    repo = _require_repo(source.get("repo"))
    commit = source.get("commit")
    if not isinstance(commit, str) or _COMMIT.fullmatch(commit) is None:
        raise SupplyChainError("supply_chain_source_commit_unpinned")
    scripts: list[dict[str, str]] = []
    raw_scripts = value.get("scripts", [])
    if not isinstance(raw_scripts, list):
        raise SupplyChainError("supply_chain_scripts_invalid")
    seen_scripts: set[str] = set()
    for raw_script in raw_scripts:
        checked = _validate_file_claim(raw_script, reason="supply_chain_script_invalid")
        if checked["path"] in seen_scripts:
            raise SupplyChainError("supply_chain_script_duplicate")
        seen_scripts.add(checked["path"])
        scripts.append(checked)
    return {
        "id": entry_id,
        "kind": kind,
        "source": {"repo": repo, "commit": commit},
        "license_id": _require_license(value.get("license_id")),
        "artifact": _validate_file_claim(value.get("artifact"), reason="supply_chain_artifact_invalid"),
        "scripts": sorted(scripts, key=lambda item: item["path"]),
    }


def normalize_manifest(manifest: Mapping[str, Any], *, require_self_hash: bool = True) -> dict[str, Any]:
    """Strictly validate the declaration and return its canonical form.

    This function intentionally accepts no user-chosen verification paths.  A
    caller must separately supply one local managed root to ``verify_manifest``.
    """
    expected = {"schema_version", "kind", "scope", "entries", "self_hash"}
    if not isinstance(manifest, Mapping) or set(manifest) != expected:
        raise SupplyChainError("supply_chain_manifest_fields_invalid")
    if manifest.get("schema_version") != SUPPLY_CHAIN_SCHEMA_VERSION or manifest.get("kind") != SUPPLY_CHAIN_KIND:
        raise SupplyChainError("supply_chain_schema_unsupported")
    scope = manifest.get("scope")
    if scope not in _SCOPES:
        raise SupplyChainError("supply_chain_scope_invalid")
    entries_value = manifest.get("entries")
    if not isinstance(entries_value, list) or not entries_value:
        raise SupplyChainError("supply_chain_entries_required")
    entries = [_normalize_entry(item) for item in entries_value]
    entry_ids = [item["id"] for item in entries]
    all_paths = [item["artifact"]["path"] for item in entries]
    for item in entries:
        all_paths.extend(script["path"] for script in item["scripts"])
    if len(set(entry_ids)) != len(entry_ids):
        raise SupplyChainError("supply_chain_entry_duplicate")
    if len(set(all_paths)) != len(all_paths):
        raise SupplyChainError("supply_chain_path_duplicate")
    normalized = {
        "schema_version": SUPPLY_CHAIN_SCHEMA_VERSION,
        "kind": SUPPLY_CHAIN_KIND,
        "scope": scope,
        "entries": sorted(entries, key=lambda item: item["id"]),
    }
    if require_self_hash:
        self_hash = manifest.get("self_hash")
        if not isinstance(self_hash, Mapping) or set(self_hash) != {"algorithm", "value"} or self_hash.get("algorithm") != "sha256":
            raise SupplyChainError("supply_chain_self_hash_invalid")
        claimed = _require_hash(self_hash.get("value"), "supply_chain_self_hash_invalid")
        if claimed != _digest(normalized):
            raise SupplyChainError("supply_chain_manifest_tampered")
        normalized["self_hash"] = {"algorithm": "sha256", "value": claimed}
    return normalized


def seal_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Return a deterministic self-hashed manifest ready for owner-only storage."""
    candidate = _without_self_hash(manifest)
    candidate["self_hash"] = {"algorithm": "sha256", "value": "sha256:" + "0" * 64}
    normalized = normalize_manifest(candidate, require_self_hash=False)
    normalized["self_hash"] = {"algorithm": "sha256", "value": _digest(normalized)}
    # Verify the output through the same strict route used for external input.
    return normalize_manifest(normalized)


def verify_manifest_seal(manifest: Mapping[str, Any]) -> bool:
    try:
        normalize_manifest(manifest)
    except SupplyChainError:
        return False
    return True


def _managed_root(root_value: str | Path) -> Path:
    root = Path(root_value)
    if root.is_symlink() or not root.is_dir():
        raise SupplyChainError("supply_chain_root_invalid")
    return root.resolve(strict=True)


def _local_regular_file(root: Path, relative_path: str) -> Path:
    candidate = root.joinpath(*PurePosixPath(relative_path).parts)
    # Reject any symlink, including an innocent-looking parent that resolves
    # back under root.  The declared bytes must be physically job/config local.
    cursor = root
    for part in PurePosixPath(relative_path).parts:
        cursor = cursor / part
        try:
            mode = cursor.lstat().st_mode
        except OSError as exc:
            raise SupplyChainError("supply_chain_artifact_missing") from exc
        if stat.S_ISLNK(mode):
            raise SupplyChainError("supply_chain_artifact_symlink")
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise SupplyChainError("supply_chain_artifact_missing") from exc
    if resolved.parent != root and root not in resolved.parents:
        raise SupplyChainError("supply_chain_artifact_outside_root")
    mode = resolved.stat().st_mode
    if not stat.S_ISREG(mode):
        raise SupplyChainError("supply_chain_artifact_not_regular")
    if resolved.stat().st_size > MAX_ARTIFACT_BYTES:
        raise SupplyChainError("supply_chain_artifact_too_large")
    return resolved


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise SupplyChainError("supply_chain_artifact_unreadable") from exc
    return "sha256:" + digest.hexdigest()


def _verify_file(root: Path, claim: Mapping[str, str]) -> VerifiedFile:
    path = _local_regular_file(root, claim["path"])
    actual = _sha256_file(path)
    if actual != claim["sha256"]:
        raise SupplyChainError("supply_chain_artifact_hash_mismatch")
    return VerifiedFile(relative_path=claim["path"], sha256=actual, local_path=path)


def verify_manifest(manifest: Mapping[str, Any], *, local_root: str | Path, expected_scope: str | None = None) -> VerifiedSupplyChainManifest:
    """Verify only bytes already under ``local_root``; never performs I/O online."""
    normalized = normalize_manifest(manifest)
    if expected_scope is not None and expected_scope not in _SCOPES:
        raise SupplyChainError("supply_chain_scope_invalid")
    if expected_scope is not None and normalized["scope"] != expected_scope:
        raise SupplyChainError("supply_chain_scope_mismatch")
    root = _managed_root(local_root)
    verified_entries: list[VerifiedSupplyChainEntry] = []
    for entry in normalized["entries"]:
        artifact = _verify_file(root, entry["artifact"])
        scripts = tuple(_verify_file(root, script) for script in entry["scripts"])
        verified_entries.append(VerifiedSupplyChainEntry(
            entry_id=entry["id"], kind=entry["kind"],
            source_repo=entry["source"]["repo"], source_commit=entry["source"]["commit"],
            license_id=entry["license_id"], artifact=artifact, scripts=scripts,
        ))
    return VerifiedSupplyChainManifest(
        scope=normalized["scope"], manifest_hash=normalized["self_hash"]["value"],
        entries=tuple(verified_entries),
    )


def load_and_verify_manifest(manifest_path: str | Path, *, local_root: str | Path, expected_scope: str | None = None) -> VerifiedSupplyChainManifest:
    """Load an owner-controlled local manifest and verify its declared bytes."""
    path = Path(manifest_path)
    if path.suffix.lower() != ".json" or path.is_symlink() or not path.is_file():
        raise SupplyChainError("supply_chain_manifest_missing")
    try:
        mode = path.stat().st_mode
        size = path.stat().st_size
    except OSError as exc:
        raise SupplyChainError("supply_chain_manifest_missing") from exc
    if not stat.S_ISREG(mode) or size <= 0 or size > MAX_MANIFEST_BYTES:
        raise SupplyChainError("supply_chain_manifest_invalid")
    # Other writers could replace an approved declaration between checks.
    if mode & 0o022:
        raise SupplyChainError("supply_chain_manifest_mutable")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SupplyChainError("supply_chain_manifest_invalid") from exc
    if not isinstance(document, Mapping):
        raise SupplyChainError("supply_chain_manifest_invalid")
    return verify_manifest(document, local_root=local_root, expected_scope=expected_scope)


__all__ = [
    "ALLOWED_LICENSE_IDS", "SUPPLY_CHAIN_KIND", "SUPPLY_CHAIN_SCHEMA_VERSION",
    "SupplyChainError", "VerifiedFile", "VerifiedSupplyChainEntry",
    "VerifiedSupplyChainManifest", "load_and_verify_manifest", "normalize_manifest",
    "seal_manifest", "verify_manifest", "verify_manifest_seal",
]
