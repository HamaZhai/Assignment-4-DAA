"""Full-domain stress cases with analytic/independent expectations, one CPU per batch."""
import argparse
from collections import deque
import json
import random

from harness import build, environment, run_batch, save
from verify import validate

SEED = 4102027


def bitset_lcs(a, b):
    masks = {}
    for i, character in enumerate(b):
        masks[character] = masks.get(character, 0) | 1 << i
    state = 0
    for character in a:
        union = state | masks.get(character, 0)
        state = union & ~(union - ((state << 1) | 1))
    return state.bit_count()


def leaf_matching_size(n, edges):
    # Unit-weight tree independent set = n - maximum matching (bipartite theorem).
    # A maximum matching can contain any leaf edge; remove its two endpoints.
    adjacency = [[] for _ in range(n)]
    for u, v in edges:
        adjacency[u].append(v)
        adjacency[v].append(u)
    degree = list(map(len, adjacency))
    removed = [False] * n
    leaves = deque(u for u in range(n) if degree[u] == 1)
    matching = 0
    while leaves:
        leaf = leaves.popleft()
        if removed[leaf] or degree[leaf] != 1:
            continue
        neighbor = next(v for v in adjacency[leaf] if not removed[v])
        matching += 1
        removed[leaf] = removed[neighbor] = True
        for endpoint in (leaf, neighbor):
            for v in adjacency[endpoint]:
                if not removed[v]:
                    degree[v] -= 1
                    if degree[v] == 1:
                        leaves.append(v)
    return matching


def random_suffix_oracle(text):
    # C-level direct suffix ordering is independent of rank doubling.
    # Compare prefixes first, and materialize whole suffixes only inside tied buckets.
    # Prefixes distinguish nearly all random ASCII suffixes, keeping oracle memory small.
    buckets = {}
    for start in range(len(text)):
        buckets.setdefault(text[start:start + 16], []).append(start)
    sa = []
    for key in sorted(buckets):
        sa.extend(sorted(buckets[key], key=lambda i: text[i:]) if len(buckets[key]) > 1 else buckets[key])
    lcp = [0] * len(text)
    for rank in range(1, len(text)):
        a, b = sa[rank - 1], sa[rank]
        while a + lcp[rank] < len(text) and b + lcp[rank] < len(text) and \
                text[a + lcp[rank]] == text[b + lcp[rank]]:
            lcp[rank] += 1
    return {"sa": sa, "lcp": lcp, "length": max(lcp, default=0)}


def groups():
    rng = random.Random(SEED)
    random_a = "".join(rng.choices("abcd !~", k=1000))
    random_b = "".join(rng.choices("abcd !~", k=1000))
    yield "lcs", [
        ("equal-1000", {"task": "lcs", "a": "a" * 1000, "b": "a" * 1000}, 1000),
        ("reversed-blocks", {"task": "lcs", "a": "a" * 500 + "b" * 500,
                              "b": "b" * 500 + "a" * 500}, 500),
        ("random-1000", {"task": "lcs", "a": random_a, "b": random_b}, bitset_lcs(random_a, random_b))]
    n = 200
    depth = n.bit_length() - 1
    equal_cost = (n * (depth + 2) - 2 ** (depth + 1)) * 1000000000
    yield "merge", [
        ("equal-200-64-bit", {"task": "merge", "sizes": [1000000000] * n}, equal_cost),
        ("zero-200-skew-plan", {"task": "merge", "sizes": [0] * n}, 0),
        ("one-large-199-zero", {"task": "merge", "sizes": [0] * (n - 1) + [1000000000]}, 1000000000)]
    n = 100000
    chain = [[i - 1, i] for i in range(1, n)]
    star = [[0, i] for i in range(1, n)]
    random_edges = [[rng.randrange(i), i] for i in range(1, n)]
    yield "tree", [
        ("chain-100000-64-bit", {"task": "tree", "n": n, "weights": [1000000000] * n, "edges": chain},
         n // 2 * 1000000000),
        ("negative-chain-100000", {"task": "tree", "n": n, "weights": [-1000000000] * n, "edges": chain}, 0),
        ("star-100000-64-bit", {"task": "tree", "n": n, "weights": [1000000000] * n, "edges": star},
         (n - 1) * 1000000000),
        ("random-tree-matching-oracle", {"task": "tree", "n": n, "weights": [1] * n, "edges": random_edges},
         n - leaf_matching_size(n, random_edges))]
    yield "naive", [
        ("dense-3000", {"task": "naive", "text": "a" * 3000, "pattern": "a" * 1500}, list(range(1501))),
        ("late-mismatch-3000", {"task": "naive", "text": "a" * 3000, "pattern": "a" * 1499 + "b"}, []),
        ("empty-pattern-3000", {"task": "naive", "text": "~" * 3000, "pattern": ""}, list(range(3001)))]
    yield "kmp", [
        ("dense-200000-100000", {"task": "kmp", "text": "a" * 200000, "pattern": "a" * 100000}, list(range(100001))),
        ("late-mismatch-200000", {"task": "kmp", "text": "a" * 200000, "pattern": "a" * 99999 + "b"}, []),
        ("empty-pattern-200000", {"task": "kmp", "text": "a" * 200000, "pattern": ""}, list(range(200001)))]
    yield "rk", [
        ("dense-product-20000000", {"task": "rk", "text": "a" * 10000, "pattern": "a" * 2000}, list(range(8001))),
        ("collision-long-prefix", {"task": "rk", "text": "a" * 9998 + "dj", "pattern": "a" * 1998 + "ab"}, []),
        ("long-pattern-10000", {"task": "rk", "text": "a" * 2000, "pattern": "a" * 10000}, []),
        ("empty-pattern-10000", {"task": "rk", "text": "a" * 10000, "pattern": ""}, list(range(10001)))]
    n = 50000
    random_text = "".join(rng.choices("".join(map(chr, range(32, 127))), k=n))
    periodic_sa = list(range(n - 2, -1, -2)) + list(range(n - 1, -1, -2))
    periodic_lcp = [0] + list(range(2, n - 1, 2)) + [0] + list(range(1, n - 2, 2))
    yield "suffix", [
        ("equal-50000", {"task": "suffix", "text": "a" * n},
         {"sa": list(range(n - 1, -1, -1)), "lcp": list(range(n)), "length": n - 1}),
        ("periodic-50000", {"task": "suffix", "text": "ab" * (n // 2)},
         {"sa": periodic_sa, "lcp": periodic_lcp, "length": n - 2}),
        ("random-ascii-50000", {"task": "suffix", "text": random_text}, random_suffix_oracle(random_text))]
    dense_patterns = ["a" * i for i in range(1, 400)] + ["a"] * 9601
    assert len(dense_patterns) == 10000 and sum(map(len, dense_patterns)) <= 100000
    unique_patterns = ["".join(rng.choices("bcdefghijklmnopqrstuvwxyz !~", k=10)) for _ in range(10000)]
    deep_pattern = "a" * 100000
    yield "aho", [
        ("dense-duplicates-200000", {"task": "aho", "patterns": dense_patterns, "texts": ["a" * 200000]},
         [[200001 - len(pattern) for pattern in dense_patterns]]),
        ("deep-trie-100000", {"task": "aho", "patterns": [deep_pattern], "texts": ["a" * 200000, ""]}, [[100001], [0]]),
        ("wide-trie-100000-100-texts", {"task": "aho", "patterns": unique_patterns, "texts": ["a" * 2000] * 100},
         [[0] * 10000 for _ in range(100)]),
        ("maximum-duplicate-columns-reset", {"task": "aho", "patterns": ["a"] * 10000,
                                              "texts": ["a" * 2000] * 99 + [""]},
         [[2000] * 10000 for _ in range(99)] + [[0] * 10000])]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-build", action="store_true")
    args = parser.parse_args()
    if not args.no_build:
        build()
    report = {"seed": SEED, "environment": environment(), "groups": [],
              "memory_note": "5ms native-host peak working-set sampling; no 768 MiB container quota imposed"}
    for group, cases in groups():
        # Groups obey the 8 MiB output budget. The two huge Aho rows groups run independently.
        batches = [[case] for case in cases] if group == "aho" else [cases]
        for batch in batches:
            answers, metrics = run_batch([request for _, request, _ in batch])
            for (name, request, optimum), answer in zip(batch, answers):
                validate(request, answer, optimum)
            result = {"task": group, "passed": len(batch), "cases": [name for name, _, _ in batch], **metrics}
            report["groups"].append(result)
            print(json.dumps(result), flush=True)
    report["passed"] = sum(group["passed"] for group in report["groups"])
    report["failed"] = 0
    assert max(group["sampled_peak_working_set_mib"] for group in report["groups"]) < 768
    save("stress.json", report)
    print(f"PASS {report['passed']} stress cases")


if __name__ == "__main__":
    main()
