# Student verification and benchmark

Run from the repository root with Python 3.12+ and the .NET SDK capable of targeting net8.0:

```sh
python tests/student/run_all.py
```

The runner performs the unchanged official setup/check commands, independent small-case
verification, full-domain stress tests and a real Release benchmark. It stops on failure.
No third-party Python packages or NuGet dependencies are required.

Individual commands:

```sh
python tools/run.py --language CSharp --setup
python tools/run.py --language CSharp --check
python tests/student/verify.py
python tests/student/stress.py
python tests/student/benchmark.py
```

`verify.py` and `stress.py` accept `--no-build` after an up-to-date official build.
`edge_cases.json` contains 40 named fixtures (search fixtures expand into all three methods).
`verify.py` generates exhaustive binary cases and fixed-seed random cases, validates required
JSON types (including rejecting Boolean-as-integer), and checks complete witnesses.
Its oracles enumerate subsequences, adjacent merge sequences and independent vertex sets;
string oracles use direct slice equality and direct suffix ordering.

`stress.py` checks the full published size limits. It uses closed forms, a bitset LCS oracle,
leaf maximum matching for a random unit-weight tree, and direct suffix ordering for random
ASCII. Every stress response also passes witness/schema checks. Each child is pinned to
one available logical CPU and has a 20-second timeout and an 8-MiB output check. Memory is
sampled on the host, not limited by a container. Large Aho outputs run in separate batches.

`benchmark/Benchmark.csproj` links the actual `CSharp/source/Algorithms.cs`; it does not
copy the search implementation. The benchmark uses seed 4102026, random/repetitive cases,
three increasing (n,m) pairs, correctness before timing, 20 warm-up calls per configuration,
then five samples of 25 calls each. The method call and result DOM construction are timed;
input generation, JSON parsing/serialization and explicit pre-sample GC are excluded.
Tiered JIT is disabled, method order rotates, and all methods use identical input objects.

Recorded evidence is in `results/`:

| File | Contents |
|---|---|
| `official.log`, `official.json` | Real official setup/check output and status |
| `edge_results.json` | Each expanded fixture, expected value and actual complete response |
| `verification.json` | Counts, fixed seed, request digest, environment and source digest |
| `stress.json` | Checked cases, elapsed times, output bytes and sampled memory |
| `benchmark.json` | Original block timings, per-call means, medians, generator and environment |
| `benchmark.md` | Readable five-run benchmark table in microseconds per call |

Re-running overwrites the result files with new real measurements. Timing values vary by
machine and load. See `ANALYSIS.md` for proofs, boundaries, interpretation and limitations.
