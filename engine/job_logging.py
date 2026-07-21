import json
import time


def append_job_log(log_dir, job_id, event, **fields):
    log_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "job_id": job_id,
        "event": event,
        "created_at": time.time(),
        **fields,
    }
    path = log_dir / f"{job_id}.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    return path
