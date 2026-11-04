"""Shared process transport and environment capture; no algorithm oracles here."""
import ctypes
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
RESULTS = Path(__file__).resolve().parent / "results"
COMMAND = ["dotnet", str(ROOT / "CSharp/build/App.dll")]


def save(name, value):
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / name).write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def build():
    subprocess.run(["dotnet", "build", str(ROOT / "CSharp/source/App.csproj"),
                    "--nologo", "-o", str(ROOT / "CSharp/build")], check=True, timeout=60)


def environment():
    details = {"recorded_at": datetime.now(timezone(timedelta(hours=5))).isoformat(),
            "os": platform.platform(), "python": platform.python_version(),
            "processor": platform.processor(), "logical_cpus": os.cpu_count(),
            "dotnet_runtimes": subprocess.check_output(["dotnet", "--list-runtimes"], text=True).strip(),
            "dotnet_sdk": subprocess.check_output(["dotnet", "--version"], text=True).strip()}
    if os.name == "nt":
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
            details["cpu_model"] = winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()

        class MemoryStatus(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
                (name, ctypes.c_ulonglong) for name in
                ("physical", "available_physical", "page", "available_page", "virtual", "available_virtual", "extended")]
        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        assert ctypes.WinDLL("kernel32").GlobalMemoryStatusEx(ctypes.byref(status))
        details["physical_ram_bytes"] = status.physical
    elif Path("/proc/meminfo").exists():
        details["physical_ram_bytes"] = int(Path("/proc/meminfo").read_text().splitlines()[0].split()[1]) * 1024
    details["submission_source_sha256"] = hashlib.sha256(
        (ROOT / "CSharp/source/Algorithms.cs").read_bytes()).hexdigest()
    return details


def run_batch(requests, timeout=20):
    """Time JSONL process startup + execution + transport; validation is outside timing.

    Pin the child to one available CPU. Sample its resident/working-set peak at 5ms.
    These native-host samples are not a Linux container memory-limit measurement.
    """
    payload = "".join(json.dumps(x, separators=(",", ":")) + "\n" for x in requests)
    started = time.perf_counter()
    child = subprocess.Popen(COMMAND, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, encoding="utf-8",
                             env={**os.environ, "DOTNET_PROCESSOR_COUNT": "1"})
    if os.name == "nt":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t),
                                                  ctypes.POINTER(ctypes.c_size_t)]
        kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        allowed, system = ctypes.c_size_t(), ctypes.c_size_t()
        assert kernel.GetProcessAffinityMask(int(child._handle), ctypes.byref(allowed), ctypes.byref(system))
        assert kernel.SetProcessAffinityMask(int(child._handle), allowed.value & -allowed.value)
    elif hasattr(os, "sched_setaffinity"):
        os.sched_setaffinity(child.pid, {min(os.sched_getaffinity(child.pid))})

    peak_bytes = [0]
    stop = threading.Event()

    def sample_memory():
        if os.name == "nt":
            class Counters(ctypes.Structure):
                _fields_ = [("cb", ctypes.c_ulong), ("faults", ctypes.c_ulong)] + [
                    (name, ctypes.c_size_t) for name in
                    ("peak", "working", "peak_pool", "pool", "peak_nonpaged", "nonpaged", "page", "peak_page")]
            psapi = ctypes.WinDLL("psapi")
            psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(Counters), ctypes.c_ulong]
            counters = Counters()
            counters.cb = ctypes.sizeof(counters)
            while not stop.is_set():
                if psapi.GetProcessMemoryInfo(int(child._handle), ctypes.byref(counters), counters.cb):
                    peak_bytes[0] = max(peak_bytes[0], counters.peak)
                stop.wait(0.005)
        elif Path(f"/proc/{child.pid}/status").exists():
            while not stop.is_set():
                try:
                    for line in Path(f"/proc/{child.pid}/status").read_text().splitlines():
                        if line.startswith("VmHWM:"):
                            peak_bytes[0] = max(peak_bytes[0], int(line.split()[1]) * 1024)
                except FileNotFoundError:
                    break
                stop.wait(0.005)

    sampler = threading.Thread(target=sample_memory, daemon=True)
    sampler.start()
    try:
        stdout, stderr = child.communicate(payload, timeout=timeout)
    except subprocess.TimeoutExpired:
        child.kill()
        child.communicate()
        raise
    finally:
        stop.set()
        sampler.join()
    elapsed = time.perf_counter() - started
    assert child.returncode == 0, (child.returncode, stderr[:4000])
    assert not stderr, f"Unexpected stderr: {stderr[:4000]}"
    assert len(stdout.encode("utf-8")) <= 8 * 1024 * 1024, "Output exceeds official 8 MiB cap"
    lines = stdout.splitlines()
    assert len(lines) == len(requests), (len(lines), len(requests))
    answers = [json.loads(line) for line in lines]
    assert all(type(answer) is dict for answer in answers)
    return answers, {"elapsed_seconds": elapsed, "output_bytes": len(stdout.encode("utf-8")),
                     "sampled_peak_working_set_mib": peak_bytes[0] / 1024**2,
                     "cpu_affinity": "one available logical CPU", "timeout_seconds": timeout}
