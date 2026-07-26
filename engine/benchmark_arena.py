"""Local, provider-neutral primitives for sealed and blind 3D benchmarks."""

import argparse
import hashlib
import json
from pathlib import Path


def canonical_json(value):
    def validate(node):
        if isinstance(node, float):
            raise ValueError("floating_point_not_allowed")
        if isinstance(node, dict):
            for key, child in node.items():
                if not isinstance(key, str):
                    raise ValueError("non_string_key")
                validate(child)
        elif isinstance(node, list):
            for child in node:
                validate(child)
        elif node is not None and not isinstance(node, (str, int, bool)):
            raise ValueError("unsupported_json_value")

    validate(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha256(payload):
    return hashlib.sha256(payload).hexdigest()


def _asset_path(root, relative_path):
    if not isinstance(relative_path, str) or not relative_path:
        raise ValueError("invalid_asset_path")
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("unsafe_asset_path")
    candidate = root / relative
    if candidate.is_symlink() or not candidate.is_file():
        raise ValueError("missing_or_unsafe_asset")
    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("unsafe_asset_path") from exc
    return candidate


def _merkle_root(leaves):
    level = [
        hashlib.sha256(path.encode("utf-8") + b"\0" + bytes.fromhex(digest)).digest()
        for path, digest in leaves
    ]
    if not level:
        raise ValueError("empty_corpus")
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [
            hashlib.sha256(level[index] + level[index + 1]).digest()
            for index in range(0, len(level), 2)
        ]
    return level[0].hex()


def seal_corpus(corpus_directory):
    root = Path(corpus_directory)
    manifest_path = _asset_path(root, "corpus.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schemaVersion") != 1 or not isinstance(manifest.get("items"), list):
        raise ValueError("invalid_corpus_manifest")

    item_ids = set()
    asset_paths = {"corpus.json"}
    for item in manifest["items"]:
        item_id = item.get("id") if isinstance(item, dict) else None
        assets = item.get("assets") if isinstance(item, dict) else None
        if not isinstance(item_id, str) or not item_id or item_id in item_ids:
            raise ValueError("invalid_or_duplicate_item_id")
        if not isinstance(assets, list) or not assets:
            raise ValueError("missing_item_assets")
        item_ids.add(item_id)
        asset_paths.update(assets)

    files = []
    for relative_path in sorted(asset_paths):
        asset = _asset_path(root, relative_path)
        files.append({
            "path": relative_path,
            "sizeBytes": asset.stat().st_size,
            "sha256": _sha256(asset.read_bytes()),
        })
    leaves = [(entry["path"], entry["sha256"]) for entry in files]
    identity = {
        "schemaVersion": 1,
        "manifestSha256": _sha256(canonical_json(manifest)),
        "merkleRoot": _merkle_root(leaves),
        "files": files,
        "itemCount": len(item_ids),
    }
    identity["corpusId"] = _sha256(canonical_json(identity))
    return identity


def blind_candidate_order(benchmark_spec_id, item_id, seed, manifest_ids):
    if len(set(manifest_ids)) != len(manifest_ids) or not manifest_ids:
        raise ValueError("invalid_candidate_manifest_ids")
    ordered = sorted(
        manifest_ids,
        key=lambda manifest_id: _sha256(
            f"{benchmark_spec_id}:{item_id}:{seed}:{manifest_id}".encode("utf-8")
        ),
    )
    return [
        {"label": f"candidate-{index:02d}", "manifestId": manifest_id}
        for index, manifest_id in enumerate(ordered, start=1)
    ]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Xreality local benchmark arena")
    subparsers = parser.add_subparsers(dest="command", required=True)
    seal_parser = subparsers.add_parser("seal")
    seal_parser.add_argument("corpus_directory")
    args = parser.parse_args(argv)
    if args.command == "seal":
        print(json.dumps(seal_corpus(args.corpus_directory), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
