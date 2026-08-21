"""Bounded MLX runtime configuration for Apple Silicon.

The previous implementation allocated a synthetic 6-12 GB tensor as a
"memory pool". MLX already manages unified memory; that reservation competed
with Shape/Paint weights and increased memory pressure without accelerating
inference. This module only applies runtime controls exposed by MLX itself.
"""

import os
import platform
import subprocess


MIB = 1024 * 1024
GIB = 1024 * MIB


def _sysctl_int(name, default):
    try:
        result = subprocess.run(
            ["sysctl", "-n", name],
            capture_output=True,
            check=True,
            text=True,
        )
        return int(result.stdout.strip())
    except (OSError, ValueError, subprocess.SubprocessError):
        return default


def _sysctl_text(name, default):
    try:
        result = subprocess.run(
            ["sysctl", "-n", name],
            capture_output=True,
            check=True,
            text=True,
        )
        return result.stdout.strip() or default
    except (OSError, subprocess.SubprocessError):
        return default


class MacRuntimeOptimizer:
    """Configure bounded caches and expose measured hardware topology."""

    def __init__(self):
        self.apple_silicon = platform.system() == "Darwin" and platform.machine() == "arm64"
        self.total_memory = _sysctl_int("hw.memsize", 16 * GIB)
        self.performance_cores = _sysctl_int(
            "hw.perflevel0.physicalcpu", max(1, (os.cpu_count() or 4) // 2)
        )
        self.logical_cores = os.cpu_count() or self.performance_cores
        self.chip = _sysctl_text("machdep.cpu.brand_string", platform.machine())
        # The cache is expendable; keep it small so Shape can be released before
        # the 6-view Paint stage on unified-memory Macs. Electron supplies the
        # hardware plan before NumPy/MLX imports; this fallback also supports a
        # manually started server.
        default_cache_mib = 256 if self.total_memory <= 16 * GIB else 512 if self.total_memory <= 32 * GIB else 1024
        requested_cache_mib = int(os.environ.get("XREALITY_MLX_CACHE_MIB", default_cache_mib))
        self.cache_limit = max(128, min(1024, requested_cache_mib)) * MIB
        default_workers = max(1, min(4, self.logical_cores // 3))
        self.validation_workers = max(
            1, min(4, int(os.environ.get("XREALITY_VALIDATION_WORKERS", default_workers)))
        )
        self.scheduling = "metal-sequential-cpu-bounded"
        self.mlx_available = False

    def apply(self):
        if not self.apple_silicon:
            return self
        try:
            import mlx.core as mx

            mx.set_cache_limit(self.cache_limit)
            mx.reset_peak_memory()
            self.mlx_available = True
        except (ImportError, AttributeError, RuntimeError):
            self.mlx_available = False
        return self

    def clear_cache(self):
        if not self.mlx_available:
            return
        try:
            import mlx.core as mx

            mx.clear_cache()
        except (AttributeError, RuntimeError):
            pass

    def snapshot(self):
        metrics = {
            "chip": self.chip,
            "totalMemoryBytes": self.total_memory,
            "performanceCores": self.performance_cores,
            "logicalCores": self.logical_cores,
            "mlxCacheLimitBytes": self.cache_limit,
            "validationWorkers": self.validation_workers,
            "scheduling": self.scheduling,
            "mlxAvailable": self.mlx_available,
        }
        if self.mlx_available:
            try:
                import mlx.core as mx

                metrics.update(
                    {
                        "mlxActiveMemoryBytes": mx.get_active_memory(),
                        "mlxCacheMemoryBytes": mx.get_cache_memory(),
                        "mlxPeakMemoryBytes": mx.get_peak_memory(),
                    }
                )
            except (AttributeError, RuntimeError):
                pass
        return metrics


_optimizer = None


def get_m5_optimizer():
    global _optimizer
    if _optimizer is None:
        _optimizer = MacRuntimeOptimizer()
    return _optimizer


def apply_m5_optimizations():
    optimizer = get_m5_optimizer().apply()
    print(
        "MLX runtime: "
        f"{optimizer.chip}, cache={optimizer.cache_limit // MIB} MiB, "
        f"validation_workers={optimizer.validation_workers}"
    )
    return optimizer
