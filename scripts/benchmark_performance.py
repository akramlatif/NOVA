"""NOVA Performance & Resource Profiler.

Benchmarks RAM consumption, CPU overhead, SQLite database latency, and
system budget compliance against NOVA's 8 GB RAM target machine.
"""

import os
import sys
import time
import json
import psutil
import sqlite3
import tempfile
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from local_agent.config import load_config
from local_agent.system.monitor import SystemMonitor
from local_agent.memory.manager import MemoryManager


def benchmark_ram_footprint():
    """Measure resident set size (RSS) memory of current process."""
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    rss_mb = round(mem_info.rss / (1024 * 1024), 2)
    vms_mb = round(mem_info.vms / (1024 * 1024), 2)
    return {"rss_mb": rss_mb, "vms_mb": vms_mb}


def benchmark_sqlite_latency(n_iterations: int = 200):
    """Benchmark raw SQLite write and read latency in milliseconds."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE benchmark (id INTEGER PRIMARY KEY, key TEXT, val TEXT)")

        # Write benchmark
        t0 = time.perf_counter()
        with conn:
            for i in range(n_iterations):
                conn.execute("INSERT INTO benchmark (key, val) VALUES (?, ?)", (f"k_{i}", f"val_{i}"))
        write_time_total = time.perf_counter() - t0
        avg_write_ms = round((write_time_total / n_iterations) * 1000, 3)

        # Read benchmark
        t0 = time.perf_counter()
        for i in range(n_iterations):
            conn.execute("SELECT val FROM benchmark WHERE key = ?", (f"k_{i}",)).fetchone()
        read_time_total = time.perf_counter() - t0
        avg_read_ms = round((read_time_total / n_iterations) * 1000, 3)

        conn.close()
        return {
            "iterations": n_iterations,
            "avg_write_ms": avg_write_ms,
            "avg_read_ms": avg_read_ms,
            "total_time_sec": round(write_time_total + read_time_total, 4),
        }
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def benchmark_memory_manager_throughput():
    """Benchmark episodic memory write, search, and recall operations."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        mgr = MemoryManager(db_path=db_path)
        t0 = time.perf_counter()
        for i in range(50):
            mgr.remember(key=f"pref_{i}", content=f"User prefers setting {i} for automation", category="preference")
        write_elapsed = time.perf_counter() - t0

        t0 = time.perf_counter()
        results = mgr.recall("automation setting 10")
        recall_elapsed = time.perf_counter() - t0

        return {
            "entries_stored": 50,
            "store_total_sec": round(write_elapsed, 4),
            "store_avg_ms": round((write_elapsed / 50) * 1000, 2),
            "recall_latency_ms": round(recall_elapsed * 1000, 2),
            "recall_found": len(results),
        }
    finally:
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except Exception:
                pass


def main():
    print("=" * 60)
    print("  NOVA Phase 11 — Security & Performance Assessment Profiler")
    print("=" * 60)

    # 1. System hardware snapshot
    summary = SystemMonitor.get_system_summary()
    print(f"\n[Hardware Target Profile]")
    print(f"  CPU Cores (Logical):  {summary['cpu']['cores_logical']}")
    print(f"  Total RAM:            {summary['ram']['total_gb']} GB")
    print(f"  Available RAM:        {summary['ram']['available_gb']} GB ({100 - summary['ram']['percent_used']}% free)")
    print(f"  OS:                   {summary['os']} {summary['os_release']} ({summary['architecture']})")

    # 2. Process Memory Footprint
    mem = benchmark_ram_footprint()
    print(f"\n[Process Memory Footprint]")
    print(f"  Resident Set (RAM):   {mem['rss_mb']} MB (Budget target: < 150 MB for core agent)")
    print(f"  Virtual Memory:       {mem['vms_mb']} MB")
    budget_ok = mem["rss_mb"] < 250
    print(f"  Budget Compliance:    {'[PASS] Within 8 GB limits' if budget_ok else '[WARN] High memory'}")

    # 3. Database Performance
    db_metrics = benchmark_sqlite_latency(200)
    print(f"\n[SQLite Storage Latency (200 ops)]")
    print(f"  Average Write:        {db_metrics['avg_write_ms']} ms / op")
    print(f"  Average Read:         {db_metrics['avg_read_ms']} ms / op")

    # 4. Memory Manager Latency
    mem_mgr = benchmark_memory_manager_throughput()
    print(f"\n[Memory Manager Latency]")
    print(f"  Store 50 Memories:    {mem_mgr['store_total_sec']}s ({mem_mgr['store_avg_ms']} ms / entry)")
    print(f"  Semantic Recall:      {mem_mgr['recall_latency_ms']} ms")

    results = {
        "timestamp": time.time(),
        "hardware": summary,
        "ram_footprint": mem,
        "sqlite_benchmark": db_metrics,
        "memory_manager_benchmark": mem_mgr,
    }

    output_path = PROJECT_ROOT / "docs" / "benchmark_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\n[OK] Benchmark completed. Results saved to docs/benchmark_results.json")
    print("=" * 60)


if __name__ == "__main__":
    main()
