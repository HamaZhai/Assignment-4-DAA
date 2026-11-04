"""Reproduce official checks, independent verification, stress and search benchmark."""
import json
import os
import re
import subprocess
import sys
import time

from harness import RESULTS, ROOT, environment, save


def main():
    RESULTS.mkdir(exist_ok=True)
    official = []
    logs = []
    for mode in ("--setup", "--check"):
        command = [sys.executable, "tools/run.py", "--language", "CSharp", mode]
        start = time.perf_counter()
        completed = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8",
                                                         "DOTNET_CLI_UI_LANGUAGE": "en-US"}, timeout=180)
        print(completed.stdout, flush=True)
        logs.append("COMMAND: " + " ".join(command) + "\n" + completed.stdout)
        official.append({"command": command[1:], "returncode": completed.returncode,
                         "elapsed_seconds": time.perf_counter() - start,
                         "public_pass_lines": len(re.findall(r"^PASS public ", completed.stdout, re.MULTILINE)),
                         "setup_passed": "PASS setup: ping" in completed.stdout,
                         "mixed_88_requests_passed": "PASS state reset: two complete batches in one process" in completed.stdout})
        (RESULTS / "official.log").write_text("\n".join(logs), encoding="utf-8")
        assert completed.returncode == 0
    assert official[0]["setup_passed"]
    assert official[1]["public_pass_lines"] == 44 and official[1]["mixed_88_requests_passed"]
    save("official.json", {"runs": official, "environment": environment()})
    for script, arguments in (("verify.py", ["--no-build"]), ("stress.py", ["--no-build"]), ("benchmark.py", [])):
        subprocess.run([sys.executable, str(ROOT / "tests/student" / script), *arguments], cwd=ROOT,
                       check=True, timeout=180)
    print("PASS official 44/44 + mixed 88/88; independent and stress suites; real benchmark recorded")


if __name__ == "__main__":
    main()
