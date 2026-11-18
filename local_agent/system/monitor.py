"""System Monitoring and Resource Inspection for NOVA — Phase 6.

Provides real-time system metrics using psutil: CPU, RAM, Disk,
running processes, and hardware/platform telemetry.
"""

from __future__ import annotations

import datetime
import logging
import platform
import sys
import time
from typing import Any, Dict, List, Optional

import psutil

logger = logging.getLogger(__name__)


class SystemMonitor:
    """Monitors system performance, resource utilization, and running processes."""

    @staticmethod
    def get_system_summary() -> Dict[str, Any]:
        """Comprehensive snapshot of hardware and resource metrics."""
        # CPU
        cpu_percent = psutil.cpu_percent(interval=0.1)
        cpu_count_logical = psutil.cpu_count(logical=True)
        cpu_count_physical = psutil.cpu_count(logical=False)

        # RAM
        vm = psutil.virtual_memory()
        ram_total_gb = round(vm.total / (1024 ** 3), 2)
        ram_avail_gb = round(vm.available / (1024 ** 3), 2)
        ram_used_gb = round(vm.used / (1024 ** 3), 2)

        # Boot time & uptime
        boot_time = psutil.boot_time()
        uptime_seconds = int(time.time() - boot_time)
        uptime_str = str(datetime.timedelta(seconds=uptime_seconds))

        return {
            "os": platform.system(),
            "os_release": platform.release(),
            "os_version": platform.version(),
            "architecture": platform.machine(),
            "python_version": sys.version.split()[0],
            "cpu": {
                "percent": cpu_percent,
                "cores_logical": cpu_count_logical,
                "cores_physical": cpu_count_physical,
            },
            "ram": {
                "total_gb": ram_total_gb,
                "available_gb": ram_avail_gb,
                "used_gb": ram_used_gb,
                "percent_used": vm.percent,
            },
            "uptime": uptime_str,
        }

    @staticmethod
    def get_disk_usage(path: Optional[str] = None) -> List[Dict[str, Any]]:
        """Report disk space for all mounted partitions or a specific target path."""
        results = []
        if path:
            try:
                usage = psutil.disk_usage(path)
                return [{
                    "target": path,
                    "total_gb": round(usage.total / (1024 ** 3), 2),
                    "used_gb": round(usage.used / (1024 ** 3), 2),
                    "free_gb": round(usage.free / (1024 ** 3), 2),
                    "percent_used": usage.percent,
                }]
            except Exception as e:
                logger.warning("Could not get disk usage for %s: %s", path, e)
                return []

        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
                results.append({
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "fstype": part.fstype,
                    "total_gb": round(usage.total / (1024 ** 3), 2),
                    "used_gb": round(usage.used / (1024 ** 3), 2),
                    "free_gb": round(usage.free / (1024 ** 3), 2),
                    "percent_used": usage.percent,
                })
            except (PermissionError, OSError):
                continue
        return results

    @staticmethod
    def list_processes(
        top_n: int = 15,
        sort_by: str = "memory",
        filter_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List running processes with PID, name, memory, and CPU metrics."""
        processes = []
        for proc in psutil.process_iter(["pid", "name", "username", "memory_percent", "cpu_percent"]):
            try:
                info = proc.info
                name = info.get("name") or ""
                if filter_name and filter_name.lower() not in name.lower():
                    continue

                mem = round(info.get("memory_percent") or 0.0, 2)
                cpu = round(info.get("cpu_percent") or 0.0, 1)

                processes.append({
                    "pid": info.get("pid"),
                    "name": name,
                    "user": info.get("username") or "",
                    "memory_percent": mem,
                    "cpu_percent": cpu,
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        # Sort
        key = "memory_percent" if sort_by == "memory" else "cpu_percent"
        processes.sort(key=lambda p: p.get(key, 0), reverse=True)
        return processes[:top_n]

    @staticmethod
    def get_process_info(pid: int) -> Dict[str, Any]:
        """Fetch detailed information for a specific process by PID."""
        try:
            p = psutil.Process(pid)
            with p.oneshot():
                return {
                    "pid": p.pid,
                    "name": p.name(),
                    "exe": p.exe() if hasattr(p, "exe") else "",
                    "status": p.status(),
                    "create_time": datetime.datetime.fromtimestamp(p.create_time()).isoformat(),
                    "num_threads": p.num_threads(),
                    "memory_mb": round(p.memory_info().rss / (1024 * 1024), 2),
                    "cpu_percent": p.cpu_percent(interval=0.05),
                }
        except psutil.NoSuchProcess:
            return {"pid": pid, "error": "Process not found"}
        except psutil.AccessDenied:
            return {"pid": pid, "error": "Access denied"}
