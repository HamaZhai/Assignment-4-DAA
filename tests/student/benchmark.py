"""Build Release and run the real C# benchmark pinned to one CPU; save raw samples."""
import json
import os
from pathlib import Path
import subprocess

import harness


def main():
    project = Path(__file__).resolve().parent / "benchmark/Benchmark.csproj"
    output = project.parent / "build"
    subprocess.run(["dotnet", "build", str(project), "-c", "Release", "--nologo", "-o", str(output)],
                   check=True, timeout=60)
    harness.COMMAND = ["dotnet", str(output / "Benchmark.dll")]
    previous = os.environ.get("DOTNET_TieredCompilation")
    os.environ["DOTNET_TieredCompilation"] = "0"
    try:
        answers, metrics = harness.run_batch([{}])  # Benchmark emits exactly one JSON report.
    finally:
        if previous is None:
            os.environ.pop("DOTNET_TieredCompilation", None)
        else:
            os.environ["DOTNET_TieredCompilation"] = previous
    result = answers[0]
    result["environment"] = harness.environment()
    result["process_metrics"] = metrics
    harness.save("benchmark.json", result)
    header = "| Case | n | m | Algorithm | Run 1 | Run 2 | Run 3 | Run 4 | Run 5 | Median |\n"
    table = header + "|---|---:|---:|---|---:|---:|---:|---:|---:|---:|\n"
    for row in result["rows"]:
        values = " | ".join(f"{x:.3f}" for x in row["microseconds_per_call"])
        table += (f"| {row['kind']} | {row['n']} | {row['m']} | {row['algorithm']} | {values} | "
                  f"{row['median_microseconds_per_call']:.3f} |\n")
    (harness.RESULTS / "benchmark.md").write_text(
        "Times in microseconds per call; each run is a measured 25-call block divided by 25.\n\n" + table,
        encoding="utf-8")
    print(table)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
