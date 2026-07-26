import shutil
import time


def free_bytes(path):
    return shutil.disk_usage(path).free


def has_free_space(path, required_bytes):
    return free_bytes(path) >= required_bytes


def format_gb(value):
    return round(value / (1024**3), 1)


def cleanup_old_temporaries(root, older_than_seconds, now=None):
    current_time = time.time() if now is None else now
    removed = []
    for path in root.iterdir():
        if not path.is_file():
            continue
        if not (path.name.endswith(".png") or path.name.endswith("-prepared.png")):
            continue
        if current_time - path.stat().st_mtime < older_than_seconds:
            continue
        try:
            path.unlink()
        except OSError:
            continue
        removed.append(path.name)
    return removed
