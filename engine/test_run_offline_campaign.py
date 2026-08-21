import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from offline_campaign import EXPECTED_CASE_IDS, REQUIRED_GATES, seal_case_report
from offline_corpus_preflight import build_preflight_manifest, write_preflight_manifest
from stage_supervisor import StageLimits, StageWorkerError


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_offline_campaign.py"
SPEC = importlib.util.spec_from_file_location("run_offline_campaign", SCRIPT)
runner = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(runner)


def _inventory():
    return {
        case_id: {
            "case_id": case_id,
            "delivery_intent": "preview",
            "source_identity_stratum": "real",
            "legal": {
                "license": {"status": "verified", "reference": "test-license"},
                "consent": {"status": "verified", "reference": "test-consent"},
            },
            "evidence": {"sufficiency": "sufficient", "reference": "test-capture"},
            "observed_view_count": 1,
            "inputs": [{
                "relative_path": f"inputs/{case_id}.png", "kind": "image",
                "identity_stratum": "real", "observed": True,
            }],
        }
        for case_id in EXPECTED_CASE_IDS
    }


def _write_inputs(root, inventory):
    for case in inventory.values():
        path = root / case["inputs"][0]["relative_path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((case["case_id"] + " input").encode("utf-8"))


def _report(campaign_id, case_id, asset_hash):
    return seal_case_report({
        "schema_version": 1,
        "campaign_id": campaign_id,
        "case_id": case_id,
        "execution": {"offline": True, "network_allowed": False},
        "asset": {"sha256": asset_hash},
        "gates": {
            gate: {"status": "pass", "evidence_class": "measured", "asset_sha256": asset_hash}
            for gate in REQUIRED_GATES
        },
        "metrics": {
            "latency_seconds": {"status": "measured", "value": 0.25},
            "peak_memory_bytes": {"status": "measured", "value": 1024},
        },
    })


class _WritingSupervisor:
    def __init__(self, snapshot, *, campaign_id, hashes, calls, fail_case=None):
        self.snapshot = snapshot
        self.campaign_id = campaign_id
        self.hashes = hashes
        self.calls = calls
        self.fail_case = fail_case

    def run(self, command, *, cwd, environment=None, limits=StageLimits()):
        self.calls.append({"command": list(command), "cwd": cwd, "environment": environment, "limits": limits})
        case_id, output = command[1], Path(command[2])
        if case_id == self.fail_case:
            raise StageWorkerError("nonzero_exit")
        output.write_text(json.dumps(_report(self.campaign_id, case_id, self.hashes[case_id])), encoding="utf-8")
        return {"stdout": "mocked", "stderr": "", "elapsed_seconds": 0.0}


class RunOfflineCampaignTests(unittest.TestCase):
    def _setup(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        corpus = root / "corpus"
        repository = root / "repository"
        workspace = root / "workspace"
        corpus.mkdir()
        repository.mkdir()
        workspace.mkdir()
        inventory = _inventory()
        _write_inputs(corpus, inventory)
        preflight = build_preflight_manifest(campaign_id="buffalo-runner-v1", corpus_root=corpus, cases=inventory)
        preflight_path = write_preflight_manifest(manifest=preflight, destination=root / "preflight.json")
        hashes = {case["case_id"]: case["asset"]["sha256"] for case in preflight["cases"]}
        return temporary, corpus, repository, workspace, preflight, preflight_path, hashes

    def test_runs_exact_30_cases_sequentially_offline_and_finalizes_only_sealed_reports(self):
        temporary, corpus, repository, workspace, preflight, preflight_path, hashes = self._setup()
        with temporary:
            calls = []
            result = runner.run_offline_campaign(
                preflight_path=preflight_path,
                corpus_root=corpus,
                repository_root=repository,
                workspace_root=workspace,
                command_template="mock-worker {case_id} {output_path} {input_path}",
                limits=StageLimits(timeout_seconds=7, network_allowed=False),
                snapshot=lambda: {"free_percent": 99.0, "swap_used_mb": 0.0},
                supervisor_factory=lambda snapshot: _WritingSupervisor(
                    snapshot, campaign_id=preflight["campaign_id"], hashes=hashes, calls=calls,
                ),
            )
            self.assertEqual([call["command"][1] for call in calls], list(EXPECTED_CASE_IDS))
            self.assertTrue(all(call["limits"].network_allowed is False for call in calls))
            self.assertTrue(all(call["environment"] is None for call in calls))
            self.assertEqual(result["final"]["report_count"], 30)
            self.assertTrue(result["final"]["aggregate"]["passed"])
            self.assertEqual(result["completed_cases"][0]["status"], "sealed")

    def test_rejects_unsealed_worker_output_before_repository_accepts_it(self):
        temporary, corpus, repository, workspace, preflight, preflight_path, hashes = self._setup()
        with temporary:
            class UnsealedSupervisor(_WritingSupervisor):
                def run(self, command, **kwargs):
                    self.calls.append({"command": list(command)})
                    Path(command[2]).write_text('{"not":"sealed"}', encoding="utf-8")
                    return {"elapsed_seconds": 0.0}

            with self.assertRaisesRegex(runner.OfflineCampaignRunnerError, "case_report_seal_invalid:product-ceramic-mug"):
                runner.run_offline_campaign(
                    preflight_path=preflight_path, corpus_root=corpus, repository_root=repository,
                    workspace_root=workspace, command_template="mock-worker {case_id} {output_path}",
                    snapshot=lambda: {"free_percent": 99.0, "swap_used_mb": 0.0},
                    supervisor_factory=lambda snapshot: UnsealedSupervisor(
                        snapshot, campaign_id=preflight["campaign_id"], hashes=hashes, calls=[],
                    ),
                )

    def test_worker_failure_stops_before_a_later_case_and_command_is_never_a_shell(self):
        temporary, corpus, repository, workspace, preflight, preflight_path, hashes = self._setup()
        with temporary:
            calls = []
            with self.assertRaisesRegex(runner.OfflineCampaignRunnerError, "case_worker_failed:product-glass-bottle:nonzero_exit"):
                runner.run_offline_campaign(
                    preflight_path=preflight_path, corpus_root=corpus, repository_root=repository,
                    workspace_root=workspace, command_template="mock-worker {case_id} {output_path} ';' echo no-shell",
                    snapshot=lambda: {"free_percent": 99.0, "swap_used_mb": 0.0},
                    supervisor_factory=lambda snapshot: _WritingSupervisor(
                        snapshot, campaign_id=preflight["campaign_id"], hashes=hashes, calls=calls,
                        fail_case="product-glass-bottle",
                    ),
                )
            self.assertEqual([call["command"][1] for call in calls], list(EXPECTED_CASE_IDS[:2]))
            self.assertIn(";", calls[0]["command"][-3])

    def test_rejects_tampered_preflight_and_templates_without_case_or_output_contracts(self):
        temporary, corpus, repository, workspace, preflight, preflight_path, hashes = self._setup()
        with temporary:
            bad = json.loads(preflight_path.read_text(encoding="utf-8"))
            bad["cases"][0]["asset"]["sha256"] = "sha256:" + "0" * 64
            tampered = preflight_path.parent / "tampered.json"
            tampered.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaisesRegex(runner.OfflineCampaignRunnerError, "preflight_manifest_seal_invalid"):
                runner.run_offline_campaign(
                    preflight_path=tampered, corpus_root=corpus, repository_root=repository,
                    command_template="worker {case_id} {output_path}",
                )
            with self.assertRaisesRegex(runner.OfflineCampaignRunnerError, "missing_fields"):
                runner.parse_command_template("worker {case_id}")
            with self.assertRaisesRegex(runner.OfflineCampaignRunnerError, "field_invalid"):
                runner.parse_command_template("worker {case_id.__class__} {output_path}")


if __name__ == "__main__":
    unittest.main()
