"""Independent exhaustive/random oracles plus witness/schema checks. Python stdlib only."""
import argparse
from collections import Counter
from functools import lru_cache
import hashlib
import itertools
import json
from pathlib import Path
import random

from harness import build, environment, run_batch, save

SEED = 4102026


def integer(value):
    assert type(value) is int


def integer_list(value):
    assert type(value) is list
    for item in value:
        integer(item)


def positions(text, pattern):
    # Independent oracle: Python slice equality, including empty pattern.
    return [i for i in range(len(text) - len(pattern) + 1) if text[i:i + len(pattern)] == pattern]


def subsequence(sequence, text):
    iterator = iter(text)
    return all(any(c == wanted for c in iterator) for wanted in sequence)


def lcs_oracle(a, b):
    # Enumerate subsequences, not a second copy of the submitted prefix DP.
    if len(a) > len(b):
        a, b = b, a
    for size in range(len(a), -1, -1):
        for indices in itertools.combinations(range(len(a)), size):
            if subsequence("".join(a[i] for i in indices), b):
                return size


@lru_cache(None)
def merge_oracle(blocks):
    # Enumerate legal next adjacent merges, not interval splits.
    if len(blocks) <= 1:
        return 0
    return min(blocks[i] + blocks[i + 1] + merge_oracle(
        blocks[:i] + (blocks[i] + blocks[i + 1],) + blocks[i + 2:])
        for i in range(len(blocks) - 1))


def tree_oracle(weights, edges):
    best = 0
    for mask in range(1 << len(weights)):
        if not any(mask >> u & 1 and mask >> v & 1 for u, v in edges):
            best = max(best, sum(w for u, w in enumerate(weights) if mask >> u & 1))
    return best


def suffix_oracle(text):
    # Small tests intentionally materialize suffixes, unlike production code.
    sa = sorted(range(len(text)), key=lambda i: text[i:])
    lcp = [0] * len(text)
    for rank in range(1, len(text)):
        a, b = sa[rank - 1], sa[rank]
        while b + lcp[rank] < len(text) and a + lcp[rank] < len(text) and \
                text[a + lcp[rank]] == text[b + lcp[rank]]:
            lcp[rank] += 1
    return {"sa": sa, "lcp": lcp, "length": max(lcp, default=0)}


def expected(request):
    task = request["task"]
    if task == "lcs":
        return lcs_oracle(request["a"], request["b"])
    if task == "merge":
        return merge_oracle(tuple(request["sizes"]))
    if task == "tree":
        return tree_oracle(request["weights"], request["edges"])
    if task in ("naive", "kmp", "rk"):
        return positions(request["text"], request["pattern"])
    if task == "suffix":
        return suffix_oracle(request["text"])
    if task == "aho":
        return [[len(positions(text, pattern)) for pattern in request["patterns"]]
                for text in request["texts"]]
    raise AssertionError(task)


def validate(request, answer, optimum):
    task = request["task"]
    if task == "lcs":
        integer(answer["length"])
        assert type(answer["sequence"]) is str
        assert answer["length"] == len(answer["sequence"]) == optimum
        assert subsequence(answer["sequence"], request["a"])
        assert subsequence(answer["sequence"], request["b"])
    elif task == "merge":
        integer(answer["cost"])
        assert answer["cost"] == optimum
        assert type(answer["plan"]) is list
        n = len(request["sizes"])
        assert len(answer["plan"]) == max(0, n - 1)
        live = {(i, i): size for i, size in enumerate(request["sizes"])}
        cost = 0
        for operation in answer["plan"]:
            integer_list(operation)
            assert len(operation) == 3
            left, split, right = operation
            assert 0 <= left <= split < right < n
            assert (left, split) in live and (split + 1, right) in live
            size = live.pop((left, split)) + live.pop((split + 1, right))
            live[left, right] = size
            cost += size
        assert cost == answer["cost"]
        assert live == ({(0, n - 1): sum(request["sizes"])} if n else {})
    elif task == "tree":
        integer(answer["weight"])
        integer_list(answer["selected"])
        selected = set(answer["selected"])
        assert len(selected) == len(answer["selected"])
        assert all(0 <= u < request["n"] for u in selected)
        assert not any(u in selected and v in selected for u, v in request["edges"])
        assert sum(request["weights"][u] for u in selected) == answer["weight"] == optimum
    elif task in ("naive", "kmp", "rk"):
        integer_list(answer["positions"])
        assert answer["positions"] == optimum
    elif task == "suffix":
        integer_list(answer["sa"])
        integer_list(answer["lcp"])
        assert answer["sa"] == optimum["sa"] and answer["lcp"] == optimum["lcp"]
        repeat = answer["repeated"]
        assert type(repeat) is str and len(repeat) == optimum["length"]
        if repeat:
            assert len(positions(request["text"], repeat)) >= 2
    elif task == "aho":
        assert type(answer["counts"]) is list
        for row in answer["counts"]:
            integer_list(row)
        assert answer["counts"] == optimum
    else:
        raise AssertionError(task)


def cases():
    fixtures = json.loads(Path(__file__).with_name("edge_cases.json").read_text(encoding="utf-8"))
    fixed = []
    for fixture in fixtures:
        inputs = ([{"task": task, **fixture["search"]} for task in ("naive", "kmp", "rk")]
                  if "search" in fixture else [fixture["input"]])
        for request in inputs:
            oracle = expected(request)
            if fixture["expected"] is not None:
                assert oracle == fixture["expected"], fixture["name"]
            fixed.append((fixture["name"] + ":" + request["task"], request, oracle))
    generated = []

    def add(request, name="generated"):
        generated.append((name, request, expected(request)))

    binary = ["".join(chars) for n in range(6) for chars in itertools.product("ab", repeat=n)]
    for a in binary[:31]:
        for b in binary[:31]:
            add({"task": "lcs", "a": a, "b": b}, "exhaustive-lcs")
    for n in range(6):
        for sizes in itertools.product(range(3), repeat=n):
            add({"task": "merge", "sizes": list(sizes)}, "exhaustive-merge")
    for text in binary:
        for pattern in binary[:15]:
            for task in ("naive", "kmp", "rk"):
                add({"task": task, "text": text, "pattern": pattern}, "exhaustive-search")
    for n in range(8):
        for chars in itertools.product("ab", repeat=n):
            add({"task": "suffix", "text": "".join(chars)}, "exhaustive-suffix")

    rng = random.Random(SEED)
    ascii_alphabet = "".join(map(chr, range(32, 127)))
    for index in range(160):
        alphabet = "ab !~" if index % 2 else ascii_alphabet
        text = "".join(rng.choices(alphabet, k=rng.randrange(0, 65)))
        pattern = (text[rng.randrange(len(text)):][:rng.randrange(10)] if text and index % 3 == 0
                   else "".join(rng.choices(alphabet, k=rng.randrange(15))))
        for task in ("naive", "kmp", "rk"):
            add({"task": task, "text": text, "pattern": pattern}, "random-search")
        add({"task": "suffix", "text": text}, "random-suffix")
        add({"task": "lcs", "a": "".join(rng.choices("abc", k=rng.randrange(11))),
             "b": "".join(rng.choices("abc", k=rng.randrange(11)))}, "random-lcs")
        add({"task": "merge", "sizes": [rng.choice([0, 1, 7, 1000000000])
                                           for _ in range(rng.randrange(8))]}, "random-merge")
        n = rng.randrange(13)
        labels = list(range(n))
        rng.shuffle(labels)
        edges = [[labels[u], labels[rng.randrange(u)]] for u in range(1, n)]
        rng.shuffle(edges)
        weights = [rng.choice([-1000000000, -9, 0, 1, 7, 1000000000]) for _ in range(n)]
        add({"task": "tree", "n": n, "weights": weights, "edges": edges}, "random-tree")
        patterns = ["".join(rng.choices(alphabet, k=rng.randrange(1, 9)))
                    for _ in range(rng.randrange(14))]
        if patterns:
            patterns += [patterns[0], patterns[0][-1:]]
        texts = [text, text, "", "".join(patterns)] if index % 5 else []
        add({"task": "aho", "patterns": patterns, "texts": texts}, "random-aho")
    rng.shuffle(generated)
    # Repeated fixed requests at both ends exercise reset after arbitrary mixed requests.
    return fixed, fixed + generated + fixed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-build", action="store_true")
    args = parser.parse_args()
    if not args.no_build:
        build()
    fixed, all_cases = cases()
    requests = [request for _, request, _ in all_cases]
    answers, metrics = run_batch(requests)
    for (name, request, optimum), answer in zip(all_cases, answers):
        try:
            validate(request, answer, optimum)
        except (AssertionError, KeyError, TypeError):
            save("failure.json", {"name": name, "input": request, "expected": optimum, "actual": answer})
            raise
    save("edge_results.json", [{"name": name, "input": request, "expected": optimum, "actual": answer,
                                "passed": True}
                               for (name, request, optimum), answer in zip(fixed, answers)])
    summary = {"seed": SEED, "passed": len(all_cases), "failed": 0,
               "per_task": dict(Counter(x["task"] for x in requests)),
               "families": dict(Counter(name.split(":")[0] for name, _, _ in all_cases)),
               "request_sha256": hashlib.sha256(json.dumps(requests, sort_keys=True).encode()).hexdigest(),
               "metrics": metrics, "environment": environment()}
    save("verification.json", summary)
    print(json.dumps({key: summary[key] for key in ("passed", "failed", "per_task", "metrics")}, indent=2))


if __name__ == "__main__":
    main()
