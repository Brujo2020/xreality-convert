"""Fail-closed, local records for optional paid/online processing.

The Image-to-3D pipeline is deliberately local-first.  This module does not
perform HTTP requests and does not know a vendor API.  It only provides the
durable *authority* a later provider adapter must present before it can make a
networked request.  A consent is bound to one sealed asset hash, one allowlisted
provider, one operation, an exact money ceiling, and an expiry.  Reservations,
reconciliation and a one-way job kill switch are local JSON evidence.

Amounts are integer micro-units (one millionth of a currency unit), avoiding
floating point accounting ambiguity.  Provider adapters must reserve before
they submit work and reconcile after receiving a billable outcome.
"""

from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import time
from typing import Any, Callable, Iterator, Mapping, Sequence

from buffalo_runtime import ContractError, atomic_write_json, canonical_json, make_read_only, safe_job_path


CLOUD_CONSENT_SCHEMA_VERSION = 1
MAX_RECORD_BYTES = 256 * 1024
_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._-]{0,95}$")
_CURRENCY = re.compile(r"^[A-Z]{3}$")


class CloudConsentError(ValueError):
    """Online work lacks local, explicit, verifiable authority."""


def _sha256(value: Any, code: str) -> str:
    if not isinstance(value, str):
        raise CloudConsentError(code)
    digest = value.removeprefix("sha256:").lower()
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise CloudConsentError(code)
    return digest


def _identifier(value: Any, code: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise CloudConsentError(code)
    return value


def _currency(value: Any) -> str:
    if not isinstance(value, str) or not _CURRENCY.fullmatch(value):
        raise CloudConsentError("invalid_currency")
    return value


def _micro_amount(value: Any, code: str) -> int:
    # bool is an int subclass but must never mean money.
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CloudConsentError(code)
    if value > 10**15:  # $1B in micro-units: deliberately bounded local input.
        raise CloudConsentError(code)
    return value


def _timestamp(value: Any, code: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CloudConsentError(code)
    result = float(value)
    if result <= 0 or result != result or result in (float("inf"), float("-inf")):
        raise CloudConsentError(code)
    return result


def _managed_job_dir(value: str | Path) -> Path:
    job_dir = Path(value).resolve()
    if job_dir.is_symlink() or not job_dir.is_dir():
        raise CloudConsentError("managed_job_missing")
    return job_dir


def _safe_child(job_dir: Path, relative: str) -> Path:
    try:
        return safe_job_path(job_dir, relative)
    except ContractError as exc:
        raise CloudConsentError("unsafe_cloud_record_path") from exc


def _record_id(payload: Mapping[str, Any]) -> str:
    return f"sha256:{hashlib.sha256(canonical_json(payload)).hexdigest()}"


def _copy_record(document: Mapping[str, Any], code: str) -> dict[str, Any]:
    try:
        clone = json.loads(canonical_json(dict(document)).decode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise CloudConsentError(code) from exc
    if not isinstance(clone, dict):
        raise CloudConsentError(code)
    return clone


def _write_new_read_only(path: Path, record: Mapping[str, Any], exists_code: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=False, indent=2).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise CloudConsentError(exists_code) from exc
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    make_read_only(path)


@contextmanager
def _locked(job_dir: Path) -> Iterator[None]:
    """Serialize budget decisions within one job without an external service."""
    lock_path = _safe_child(job_dir, ".cloud-consent.lock")
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _read_json(path: Path, code: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise CloudConsentError(code)
    try:
        if path.stat().st_size <= 0 or path.stat().st_size > MAX_RECORD_BYTES:
            raise CloudConsentError(code)
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CloudConsentError(code) from exc
    if not isinstance(document, dict):
        raise CloudConsentError(code)
    return document


def _verify_self_id(document: Mapping[str, Any], kind: str, code: str) -> dict[str, Any]:
    record = _copy_record(document, code)
    if record.get("kind") != kind or record.get("schema_version") != CLOUD_CONSENT_SCHEMA_VERSION:
        raise CloudConsentError(code)
    observed = record.pop("record_id", None)
    if observed != _record_id(record):
        raise CloudConsentError(code)
    return record


def _allowlist(allowed_providers: Sequence[str]) -> frozenset[str]:
    if isinstance(allowed_providers, (str, bytes)):
        raise CloudConsentError("provider_allowlist_required")
    values = frozenset(_identifier(provider, "invalid_allowed_provider") for provider in allowed_providers)
    if not values:
        raise CloudConsentError("provider_allowlist_required")
    return values


def create_consent(
    *,
    job_dir: str | Path,
    asset_sha256: str,
    provider: str,
    operation: str,
    max_cost_micros: int,
    currency: str,
    expires_at: float,
    allowed_providers: Sequence[str],
    clock: Callable[[], float] = time.time,
) -> dict[str, Any]:
    """Seal one immutable consent.  Consent creation never enables network I/O."""
    root = _managed_job_dir(job_dir)
    asset = _sha256(asset_sha256, "invalid_asset_sha256")
    checked_provider = _identifier(provider, "invalid_provider")
    if checked_provider not in _allowlist(allowed_providers):
        raise CloudConsentError("provider_not_allowlisted")
    checked_operation = _identifier(operation, "invalid_operation")
    ceiling = _micro_amount(max_cost_micros, "invalid_max_cost_micros")
    checked_currency = _currency(currency)
    now = _timestamp(clock(), "invalid_clock")
    expiry = _timestamp(expires_at, "invalid_expiry")
    if expiry <= now:
        raise CloudConsentError("consent_expired")
    payload = {
        "schema_version": CLOUD_CONSENT_SCHEMA_VERSION,
        "kind": "xreality_cloud_consent",
        "created_at": now,
        "asset_sha256": f"sha256:{asset}",
        "provider": checked_provider,
        "operation": checked_operation,
        "max_cost_micros": ceiling,
        "currency": checked_currency,
        "expires_at": expiry,
        "network": {"permitted": True, "adapter_must_recheck": True},
    }
    consent_id = _record_id(payload)
    record = dict(payload, record_id=consent_id)
    path = _safe_child(root, f"cloud-consents/{consent_id.removeprefix('sha256:')}.json")
    _write_new_read_only(path, record, "consent_already_exists")
    return record


def _consent_path(job_dir: Path, consent_id: str) -> Path:
    digest = _sha256(consent_id, "invalid_consent_id")
    return _safe_child(job_dir, f"cloud-consents/{digest}.json")


def verify_consent(
    *,
    job_dir: str | Path,
    consent_id: str,
    asset_sha256: str,
    provider: str,
    operation: str,
    allowed_providers: Sequence[str],
    now: float | None = None,
    clock: Callable[[], float] = time.time,
) -> dict[str, Any]:
    """Verify an unexpired authority for exactly one provider request."""
    root = _managed_job_dir(job_dir)
    _assert_not_killed(root)
    record = _verify_self_id(_read_json(_consent_path(root, consent_id), "consent_missing_or_invalid"), "xreality_cloud_consent", "consent_missing_or_invalid")
    if f"sha256:{_sha256(asset_sha256, 'invalid_asset_sha256')}" != record.get("asset_sha256"):
        raise CloudConsentError("consent_asset_mismatch")
    checked_provider = _identifier(provider, "invalid_provider")
    if checked_provider not in _allowlist(allowed_providers) or record.get("provider") != checked_provider:
        raise CloudConsentError("consent_provider_mismatch")
    if record.get("operation") != _identifier(operation, "invalid_operation"):
        raise CloudConsentError("consent_operation_mismatch")
    current = _timestamp(clock() if now is None else now, "invalid_clock")
    if current >= _timestamp(record.get("expires_at"), "consent_missing_or_invalid"):
        raise CloudConsentError("consent_expired")
    _micro_amount(record.get("max_cost_micros"), "consent_missing_or_invalid")
    _currency(record.get("currency"))
    return dict(record, record_id=consent_id)


def _kill_switch_path(job_dir: Path) -> Path:
    return _safe_child(job_dir, "cloud-kill-switch.json")


def _assert_not_killed(job_dir: Path) -> None:
    path = _kill_switch_path(job_dir)
    if path.exists():
        _verify_self_id(_read_json(path, "invalid_kill_switch"), "xreality_cloud_kill_switch", "invalid_kill_switch")
        raise CloudConsentError("cloud_kill_switch_engaged")


def engage_kill_switch(
    *, job_dir: str | Path, reason: str, clock: Callable[[], float] = time.time,
) -> dict[str, Any]:
    """Permanently block every cloud reservation in this job directory."""
    root = _managed_job_dir(job_dir)
    checked_reason = _identifier(reason, "invalid_kill_switch_reason")
    payload = {
        "schema_version": CLOUD_CONSENT_SCHEMA_VERSION,
        "kind": "xreality_cloud_kill_switch",
        "engaged_at": _timestamp(clock(), "invalid_clock"),
        "reason": checked_reason,
        "effect": "all_future_cloud_reservations_denied",
    }
    record = dict(payload, record_id=_record_id(payload))
    _write_new_read_only(_kill_switch_path(root), record, "cloud_kill_switch_already_engaged")
    return record


def _budget_path(job_dir: Path, consent_id: str) -> Path:
    digest = _sha256(consent_id, "invalid_consent_id")
    return _safe_child(job_dir, f"cloud-budgets/{digest}.json")


def _audit_path(job_dir: Path, consent_id: str, activity_id: str, action: str) -> Path:
    digest = _sha256(consent_id, "invalid_consent_id")
    return _safe_child(job_dir, f"cloud-audit/{digest}-{_identifier(activity_id, 'invalid_activity_id')}-{action}.json")


def _empty_budget(consent: Mapping[str, Any], consent_id: str) -> dict[str, Any]:
    return {
        "schema_version": CLOUD_CONSENT_SCHEMA_VERSION,
        "kind": "xreality_cloud_budget_state",
        "consent_id": consent_id,
        "max_cost_micros": consent["max_cost_micros"],
        "spent_micros": 0,
        "reserved_micros": 0,
        "reservations": {},
    }


def _load_budget(job_dir: Path, consent: Mapping[str, Any], consent_id: str) -> dict[str, Any]:
    path = _budget_path(job_dir, consent_id)
    if not path.exists():
        return _empty_budget(consent, consent_id)
    budget = _read_json(path, "invalid_budget_state")
    if (budget.get("schema_version") != CLOUD_CONSENT_SCHEMA_VERSION or budget.get("kind") != "xreality_cloud_budget_state" or
            budget.get("consent_id") != consent_id or budget.get("max_cost_micros") != consent.get("max_cost_micros")):
        raise CloudConsentError("invalid_budget_state")
    spent = _micro_amount(budget.get("spent_micros"), "invalid_budget_state")
    reserved = _micro_amount(budget.get("reserved_micros"), "invalid_budget_state")
    maximum = _micro_amount(budget.get("max_cost_micros"), "invalid_budget_state")
    if spent + reserved > maximum or not isinstance(budget.get("reservations"), dict):
        raise CloudConsentError("invalid_budget_state")
    return budget


def _write_budget(job_dir: Path, consent_id: str, budget: Mapping[str, Any]) -> None:
    atomic_write_json(_budget_path(job_dir, consent_id), _copy_record(budget, "invalid_budget_state"))


def _audit(job_dir: Path, consent_id: str, activity_id: str, action: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    if action not in {"reserved", "reconciled"}:
        raise CloudConsentError("invalid_audit_action")
    body = {
        "schema_version": CLOUD_CONSENT_SCHEMA_VERSION,
        "kind": "xreality_cloud_budget_audit",
        "consent_id": consent_id,
        "activity_id": activity_id,
        "action": action,
        **dict(payload),
    }
    record = dict(body, record_id=_record_id(body))
    _write_new_read_only(_audit_path(job_dir, consent_id, activity_id, action), record, "cloud_activity_already_recorded")
    return record


def reserve_budget(
    *,
    job_dir: str | Path,
    consent_id: str,
    asset_sha256: str,
    provider: str,
    operation: str,
    allowed_providers: Sequence[str],
    activity_id: str,
    amount_micros: int,
    clock: Callable[[], float] = time.time,
) -> dict[str, Any]:
    """Atomically reserve consent budget before an optional provider call."""
    root = _managed_job_dir(job_dir)
    activity = _identifier(activity_id, "invalid_activity_id")
    amount = _micro_amount(amount_micros, "invalid_reservation_amount")
    if amount <= 0:
        raise CloudConsentError("invalid_reservation_amount")
    with _locked(root):
        consent = verify_consent(job_dir=root, consent_id=consent_id, asset_sha256=asset_sha256, provider=provider,
                                 operation=operation, allowed_providers=allowed_providers, clock=clock)
        budget = _load_budget(root, consent, consent_id)
        reservations = budget["reservations"]
        if activity in reservations:
            raise CloudConsentError("cloud_activity_already_exists")
        if amount > budget["max_cost_micros"] - budget["spent_micros"] - budget["reserved_micros"]:
            raise CloudConsentError("cloud_budget_exceeded")
        at = _timestamp(clock(), "invalid_clock")
        reservations[activity] = {"reserved_micros": amount, "status": "reserved", "reserved_at": at}
        budget["reserved_micros"] += amount
        _audit(root, consent_id, activity, "reserved", {"at": at, "amount_micros": amount, "currency": consent["currency"]})
        _write_budget(root, consent_id, budget)
        return {"consent_id": consent_id, "activity_id": activity, "reserved_micros": amount,
                "currency": consent["currency"], "remaining_micros": budget["max_cost_micros"] - budget["spent_micros"] - budget["reserved_micros"]}


def reconcile_budget(
    *, job_dir: str | Path, consent_id: str, activity_id: str, actual_cost_micros: int,
    clock: Callable[[], float] = time.time,
) -> dict[str, Any]:
    """Close a reservation after a provider outcome; it can never exceed reserve."""
    root = _managed_job_dir(job_dir)
    activity = _identifier(activity_id, "invalid_activity_id")
    actual = _micro_amount(actual_cost_micros, "invalid_actual_cost")
    with _locked(root):
        _assert_not_killed(root)  # A killed job cannot silently continue billing.
        consent_document = _verify_self_id(_read_json(_consent_path(root, consent_id), "consent_missing_or_invalid"), "xreality_cloud_consent", "consent_missing_or_invalid")
        budget = _load_budget(root, consent_document, consent_id)
        reservation = budget["reservations"].get(activity)
        if not isinstance(reservation, dict) or reservation.get("status") != "reserved":
            raise CloudConsentError("cloud_reservation_missing_or_closed")
        reserved = _micro_amount(reservation.get("reserved_micros"), "invalid_budget_state")
        if actual > reserved:
            raise CloudConsentError("actual_cost_exceeds_reserved_budget")
        at = _timestamp(clock(), "invalid_clock")
        reservation.update({"status": "reconciled", "actual_cost_micros": actual, "reconciled_at": at})
        budget["reserved_micros"] -= reserved
        budget["spent_micros"] += actual
        _audit(root, consent_id, activity, "reconciled", {"at": at, "reserved_micros": reserved,
                                                            "actual_cost_micros": actual, "currency": consent_document["currency"]})
        _write_budget(root, consent_id, budget)
        return {"consent_id": consent_id, "activity_id": activity, "actual_cost_micros": actual,
                "currency": consent_document["currency"], "remaining_micros": budget["max_cost_micros"] - budget["spent_micros"] - budget["reserved_micros"]}
