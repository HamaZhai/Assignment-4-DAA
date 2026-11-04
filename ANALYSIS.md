# Assignment 4 — Dynamic Programming and String Processing

## Environment and reproduction

Selected language: **CSharp** in `submission.json`. The supplied application targets
**net8.0** and ran on **.NET 8.0.26**, x64. The available build SDK is **9.0.313**;
it compiled the unchanged net8.0 project successfully. Python is **3.12.2**.
The host is Windows 11, build 26300, with an Intel Core i7-13620H and 16 logical
processors and 16961822720 bytes of OS-reported physical RAM (about 15.80 GiB).
Exact physical RAM and environment details are captured in
`tests/student/results/benchmark.json`. Tests and benchmark children are pinned
to one available logical CPU, with `DOTNET_PROCESSOR_COUNT=1`.

All commands below run from the repository root:

```sh
python tools/run.py --language CSharp --setup
python tools/run.py --language CSharp --check
python tests/student/verify.py --no-build
python tests/student/stress.py --no-build
python tests/student/benchmark.py
```

One command repeats the complete sequence and saves the official output:

```sh
python tests/student/run_all.py
```

Without `--no-build`, verification and stress scripts build the application
themselves. A direct build and JSONL example run are:

```sh
dotnet build CSharp/source/App.csproj --nologo -o CSharp/build
dotnet CSharp/build/App.dll
python tools/run.py --language CSharp --input examples/lcs.jsonl
```

The direct `dotnet` command reads requests from stdin until EOF. The final
example command uses the supplied fixture. The launcher builds in its supplied
default configuration; the separate benchmark builds in Release. No extra
NuGet or Python packages are required. The recorded local checks passed;
GitHub-hosted Actions and private grading checks have not been run in this
session. No new commit, push or Moodle submission has been made.

## Architecture, folders and execution flow

This is a stateless algorithm service with the template's public signatures.
The application remains small enough that introducing an interface hierarchy,
service container or message bus would add indirection without a dependency
to replace. The required `Algorithms` class is a collection of independent
handlers; there is no shared mutable state or algorithm-to-algorithm dependency.

| Location | Responsibility |
|---|---|
| `CSharp/source/Program.cs` | Existing entry point: parse each JSON line, dispatch one task, serialize one result |
| `CSharp/source/Algorithms.cs` | Eight required handlers and private suffix-construction helpers |
| `CSharp/source/App.csproj` | Supplied net8.0 build definition, unchanged |
| `submission.json` | Language selection |
| `tools/`, `tests/public.json` | Supplied launcher, validator and public cases, unchanged |
| `tests/student/verify.py`, `edge_cases.json` | Independent oracles and explicit boundary fixtures |
| `tests/student/stress.py` | Large-domain correctness checks |
| `tests/student/harness.py` | JSONL subprocess transport, affinity, timeout and host memory measurement |
| `tests/student/benchmark/` and `benchmark.py` | Direct measurement of the real search handlers |
| `tests/student/results/` | Actual evidence, raw measurements and environment/source digests |

Execution starts at the supplied top-level `Program.cs`. For each input line it
constructs a request object, selects a handler, receives a new result object and
writes exactly one JSON line. Each handler owns and releases its local state;
the next request starts independently. Only the dispatcher knows all task names.
The algorithms contain no console output. Input validity follows the official
contract: printable ASCII 32–126, nonempty Aho patterns and valid trees.

To extend the service, add a handler and a dispatch case, then add contract
fixtures and an independent oracle. Existing algorithm implementations need
no rewrite. A different suffix implementation can replace its private helper
without changing JSON transport. Each test family can run independently.
The public API and supplied infrastructure are preserved; `Program.cs` and
`App.csproj` required no changes.

## Algorithm explanations

### 1. LCS: prefix dynamic programming

**State and bases.** `lengths[i,j]` is the optimum length for `a[0..i)` and
`b[0..j)`. Row zero and column zero are zero because an empty prefix has no
nonempty common subsequence. Indices are prefix lengths, not character starts.

**Transition and order.** Rows and columns increase from one. Equal final
characters give `lengths[i-1,j-1]+1`. On a mismatch take
`max(lengths[i-1,j], lengths[i,j-1])`. All dependencies have smaller prefixes.

**Correctness.** With equal final characters, an optimum can end in that
character: if an optimum does not use both final positions, its last copy of
that character can be moved to these positions, or the character can be
appended if neither final character was used. Removing the common last
character leaves an optimum for smaller prefixes. Conversely any smaller
common subsequence can be extended. With unequal final characters, no common
subsequence uses both as its last character; it omits at least one, so one
of the two smaller-prefix optima is sufficient. Induction establishes the table.

**Reconstruction and ties.** Start at `(n,m)`. Equal characters are written
backwards into a character buffer; move diagonally. On mismatch move to a
predecessor with the same optimum, preferring the preceding row on a tie.
Each diagonal step removes one required character, preserving its order in
both strings. The resulting string has exactly the optimal length.

**Cost.** Time and auxiliary table space are O((n+1)(m+1)), including empty
inputs; backtracking is O(n+m). The input has O(n+m) characters and the result
uses O(ell+1) output space for LCS length ell, including its construction buffer.

**Boundaries.** `("tea_time","team")` must return length 4 and `"team"`,
detecting accidental substring logic. Empty left/right/both, repeated `a`s
and `ABCBDAB`/`BDCABA` cover bases and non-unique witnesses. Every returned
sequence is checked as a subsequence of both inputs, not just by length.

### 2. Ordered adjacent merging: interval dynamic programming

**State and bases.** `costs[l,r]` is the minimum cost of reducing the closed
original interval `[l,r]` to one block. A singleton costs zero. With zero or
one input blocks return cost zero and no operations. A `long` prefix sum
gives `sum(l,r)=prefix[r+1]-prefix[l]` in O(1).

**Transition and order.** For each interval length from 2 through n, try every
last split `k` in `[l,r)`:

```text
costs[l,r] = min_k(costs[l,k] + costs[k+1,r] + sum(l,r))
```

Store the first minimizing split. Both child intervals are shorter and already
computed. Prefix sums, DP costs and candidate additions all use `long`.

**Correctness.** Adjacent merging preserves closed original intervals. The
last merge of `[l,r]` must combine some `[l,k]` with `[k+1,r]` and pay the full
interval sum. Replacing either child plan by a cheaper plan would improve the
whole plan, so an optimum has optimal child plans. Conversely each tried split
and its two optimal child plans produce a legal complete plan. Induction by
interval length proves minimality.

**Reconstruction.** Visit the saved left child, right child, then append
`[l,k,r]`. At emission time both adjacent blocks exist. Induction also gives
exactly n-1 operations. Ties choose the smallest k. Reconstruction recursion
is bounded by 199 frames beyond the root at n=200; the unbounded tree case
uses no recursion.

**Cost.** O(n^3) time and O(n^2) auxiliary storage for n>=1; O(1) for n=0.
Input and output are O(n+1). Plan generation takes O(n) time/stack. A very
loose cost bound is `(n-1)*sum(sizes) <= 3.98e13`, safely within signed 64 bits.

**Boundaries.** `[1,100,1]` costs 203; merging the two separated 1s is illegal.
Four blocks of size 1e9 cost 8e9, detecting `int` overflow. Zero blocks permit
many optima. Tests simulate the live block collection and sum costs in plan
order, rejecting parent-first operations even if their numeric total is right.

### 3. Tree independent set: iterative take/skip DP

**State and bases.** Root the tree at vertex 0. `take[u]` is the best weight in
u's rooted subtree when u is selected; `skip[u]` is the best weight when u is
excluded. Initially `take[u]=weights[u]`, `skip[u]=0`. An empty tree returns
zero and an empty list. A leaf therefore has these same two states, even for
negative weights.

**Transitions and order.** Store undirected adjacency in `head`, `target`,
`next` arrays. An iterative parent-first traversal creates `parent` and
`order`; every child follows its parent. Scan this order backwards and add:

```text
take[parent[u]] += skip[u]
skip[parent[u]] += max(take[u], skip[u])
```

The child is complete before its contribution is added. For a valid tree,
skipping the parent edge is enough to visit every vertex once. There is no
recursive call or call-stack dependence on tree height.

**Correctness.** If u is taken, each child must be skipped. If u is skipped,
each child subtree independently chooses its better state. Tree edges are the
only conflicts, so combining these choices is both feasible and optimal by
subtree induction. `max(take[0],skip[0])` is the global optimum. Skip permits
the empty set, ensuring that all-negative inputs have optimum zero.

**Reconstruction.** Traverse parent-first order. A selected parent forces
exclusion. Otherwise select u only if `take[u]>skip[u]`; ties choose skip.
The decisions attain the corresponding DP value, no vertex repeats, and no
edge has two selected endpoints. Vertex order in the output is unrestricted.

**Cost.** O(n+1) time and auxiliary memory, with O(n+1) input and at most
O(n+1) output. Arrays, including adjacency, are linear. `long` is used for
both DP states; absolute sums are bounded by 1e14.

**Boundaries.** Empty/single/negative/zero/tied examples check reconstruction
and empty-set semantics. A 100000-vertex chain checks stack safety, and the
1e9-weight star has weight 99999000000000. Small random trees are relabelled
and have shuffled edges, so root 0 is not always the generator's root.

### 4a. Naive exact search

**Invariant, bases and order.** Try each start in increasing order from 0
through n-m inclusive. `matched` is the length of the verified common prefix
between the pattern and the window at that start. Compare the next character
until mismatch or completion. For m=0 the zero-comparison test succeeds at
every boundary 0..n; if m>n the start loop is empty.

**Correctness and output.** Every possible complete window is tried and is
reported exactly when all its characters agree. Incrementing the start by
one retains overlaps and gives strictly increasing, unique positions.
No separate reconstruction is needed: each accepted start is its witness.

**Cost.** O(n*m+n+1) time, O(1) auxiliary memory, O(z+1) output memory.
Input storage is O(n+m+1). The empty-pattern result takes O(n+1) time/space.

**Boundaries.** `aaaaa`/`aaa` gives `[0,1,2]`; empty/empty gives `[0]`.
Case, spaces, punctuation and the final valid start are tested independently.

### 4b. KMP: prefix function and fallback

**State and bases.** `prefix[i]` is the length of the longest proper prefix
of `pattern[0..i]` that is also a suffix. `prefix[0]=0`. Handle an empty
pattern by returning all boundaries before any indexing. In the text scan,
`matched` is the length of the longest retained pattern prefix matching a
suffix of the consumed text; it is always less than m before a comparison.

**Updates and order.** Build prefix entries left to right. On mismatch replace
the border by `prefix[border-1]` until extension is possible or it is zero.
Apply the same fallback in the text scan. Extend on equality. At a full match,
emit `i-m+1`, then set `matched=prefix[m-1]` to retain overlaps.

**Correctness.** Any shorter possible matched prefix after mismatch must be
a border of the already matched prefix. The prefix chain enumerates these
borders from longest to shortest; all other lengths are impossible. Thus
fallback loses no match. A full match is emitted only after all characters
have matched. Retaining its longest proper border preserves exactly the
possible continuation for overlapping matches. Text indices only advance,
so emitted positions are strictly increasing.

**Cost.** Prefix building and scanning have amortized O(m+n) comparisons:
each successful extension increases the retained length by one and fallback
decreases it. Including output, time is O(n+m+z+1), auxiliary memory O(m+1),
output O(z+1), and input O(n+m+1).

**Boundaries.** `ababababacababaca`/`ababaca` gives `[4,10]`, exercising repeated
fallback. Periodic overlap and a 200000-character text with a 100000-character
pattern exercise both fallback after a match and the full KMP domain.

### 4c. Rabin–Karp: rolling hash with exact verification

**Invariant and bases.** For window characters c[0..m), maintain
`H = sum(ASCII(c[j])*31^(m-1-j)) mod 101`. `highestPower=31^(m-1) mod 101`.
The leftmost character has the highest exponent. Initial hashes are computed
left to right by multiply-and-add. Empty patterns return all boundaries and
m>n returns no starts before a window is formed.

**Rolling update.** Remove the outgoing leading term, normalize the remainder,
multiply by 31 and append the next character:

```text
remainder = (H - ASCII(outgoing)*highestPower) % 101
if remainder < 0: remainder += 101
Hnext = (remainder*31 + ASCII(incoming)) % 101
```

Subtracting and shifting gives exactly the polynomial for the next window.
All hash arithmetic uses `long`. C# `%` can return a negative value, so the
normalization step is essential. Starts increase by one, including overlaps.

**Collisions and correctness.** Unequal hashes imply unequal strings; equal
hashes are only candidates. Compare real characters at every equal-hash
window and emit only if all m agree. In particular,
`H("ab")=(97*31+98)%101=75` and `H("dj")=(100*31+106)%101=75`.
For text `abdj`, pattern `ab`, the answer is `[0]`, never `[0,2]`.
Conversely equal strings always hash equally and pass verification, so there
are neither false positives nor false negatives. There is no probabilistic
correctness assumption. `zab`/`ab` also detects missing normalization: removing
the first `z` term produces a negative intermediate remainder.

**Cost.** For 1<=m<=n and c equal-hash candidate windows, time is
O(n+m+c*m); exact comparisons may stop early, but c*m is a safe bound.
The worst case is quadratic, for example long equal-character strings and
patterns where every window is a genuine match. A bound covering empty and
oversized patterns is O(n*m+n+m+1). The rolling implementation uses O(1)
auxiliary memory and O(z+1) output, apart from O(n+m+1) input storage.

### 5. Suffix array: prefix doubling and Kasai LCP

**Doubling state and bases.** `sa` contains only starts 0..n-1. Initially
`ranks[i]=ASCII(text[i])-32+1`, ranking one-character prefixes. Rank zero
represents a missing half of a suffix; no sentinel character or extra suffix
is appended. Empty input returns empty arrays; a singleton has `sa=[0]`.

**Doubling update and order.** At width w=1,2,4,..., sort starts by
`(ranks[i], i+w<n ? ranks[i+w] : 0)`. A stable counting sort on the second
key followed by a stable counting sort on the first key orders the pairs.
`SortRanks` builds frequencies, converts them to starting positions and
places starts in source order. Equal pairs receive equal new ranks; unequal
adjacent pairs increase the rank. Swap the rank buffers. Stop when all
classes are distinct or the compared length covers the string.

**Doubling correctness.** If ranks preserve equality and order for prefixes
of length w, the pair represents exactly the order for prefixes of length
2w, with the missing part smaller than any printable character. Induction
preserves this invariant. Distinct ranks already determine complete suffix
order because their first differing compared prefix determines that order.
Otherwise doubling eventually covers every suffix. The result is a sorted
permutation of exactly the nonempty suffix starts.

**Kasai state, updates and bases.** Construct inverse ranks. Scan text starts
i=0..n-1 and compare with the lexicographic predecessor `sa[inverse[i]-1]`.
Reuse `common`, extend it while characters agree, store it in `lcp[rank]`,
then decrement it by at most one. Rank zero has LCP zero and resets `common`
to zero. LCP array length is n, including the leading zero.

**Kasai correctness and amortization.** If two ordered suffixes share h
characters, removing their first characters preserves their ordering and
leaves at least h-1 common characters. The next suffix's immediate predecessor
lies no farther away in lexicographic order, so it shares at least that
prefix too. Thus the carried length never skips a mismatch. Extending finds
the exact adjacent LCP. Total extensions are O(n), since each iteration
decreases the carried length by at most one and it can never exceed n.

**Longest repeat reconstruction.** Save the first rank with the largest LCP
and return that prefix of its suffix. Suffixes sharing any fixed prefix form
a contiguous interval in sorted order. Any repeated substring therefore
appears in an adjacent LCP, and any adjacent LCP is a real repeat at two
distinct starts. Taking the maximum is optimal. Ties retain the first maximum;
overlapping occurrences are allowed. If all LCPs are zero, return `""`.

**Cost.** Each counting-sort round is O(n+classes), with classes<=max(95,n),
and there are O(log(n+1)) rounds. Doubling is O(n log(n+1)) time and Kasai
O(n), using O(n+1) auxiliary memory. Input is O(n+1); sa, lcp and the repeated
substring use O(n+1) output. Only the chosen repeat is extracted as a string;
production code never materializes all suffix strings.

**Boundaries.** `aaaa` yields sa `[3,2,1,0]`, lcp `[0,1,2,3]`, repeat `aaa`.
This detects reversed short-suffix order and missing overlap. Empty, singleton,
distinct strings, banana and tied repeats check the full schema. Equal,
periodic and random printable-ASCII strings of length 50000 test scale.

### 6. Aho–Corasick: failure automaton and visit aggregation

**States and bases.** Each trie state represents a dictionary prefix. State
zero is the root. Store one 95-entry transition row per actual state in a
`List<int[]>`; zero initially means no edge. Insertion creates only missing
children. `terminals[i]` is the state for dictionary position i. Duplicate
strings share that state but retain separate entries in `terminals`.
Patterns are nonempty under the contract, so the root is never a terminal.

**Failure construction and order.** Queue root children with failure zero.
In breadth-first order, a real child on c receives
`failure[child]=transition[failure[state],c]`. Missing transitions are filled
from that same failure row. Every failure target has smaller depth and is
already complete. Root's missing transitions stay at root. The saved queue
is also a parent-before-child order in the failure tree.

**Scanning invariant and correctness.** The current state is the longest
suffix of the consumed text that is a trie prefix. A direct edge extends it;
failure transitions choose the longest extendable shorter suffix. Thus each
text character moves to exactly the correct new state. Increment the visit
counter for that state, once per character. A pattern matches at that end
position exactly when its terminal occurs on this state's failure chain.

**Aggregation, duplicates and independent texts.** Process saved BFS order
backwards, adding `visits[child]` to `visits[failure[child]]`. All descendant
contributions arrive before their ancestor is propagated, so each terminal
gets exactly the number of text ends where its pattern matches. This counts
suffix-pattern matches and overlaps without listing individual matches or
copying inherited terminal lists. Emit `visits[terminals[i]]` in dictionary
order: duplicates obtain equal counts as separate columns. All visit counters
are `long`. Clear the visit array and reset state to zero before EVERY text.
The automaton is request-local and is rebuilt for a new dictionary.

**Empty cases and output.** No texts returns `counts=[]`. An empty dictionary
returns one empty row per text without scanning it. An empty text returns
one zero per pattern. Rows preserve text order and columns preserve dictionary
order. There is no witness reconstruction because the required output is counts.

**Cost.** Let L be total dictionary length including duplicates, p its size,
S actual trie states, q number of texts and T their total length. Construction
is O(L+95*S+p) time, O(95*S+p) auxiliary space; rows are allocated only for
actual states, even when many patterns are duplicates. Each text takes
O(|text|+S+p) time including clearing, reverse propagation and row creation.
Total time is O(L+95*S+p+T+q*(S+p)). Output is O(q*(p+1)+1), input
O(L+T+p+q+1). No-text and no-pattern shortcuts can use less space/time.
No complexity claim hides a factor equal to the number of individual matches.

**Boundaries.** Patterns `["he","she","he","e"]` in two successive `sheshe`
texts each yield `[2,2,2,2]`, followed by an empty text yielding all zeros.
`["a","aa","aaa","aa"]` in `aaaa` yields `[4,3,2,3]`. Dense stress cases
combine 10000 dictionary entries and 200000 characters; a separate 100000-deep
trie and a large wide trie cover construction and failure propagation.

## Verification evidence

The unchanged public checks passed **44/44 cases**, plus **88/88 responses**
in the repeated mixed batch, and setup ping passed. The baseline starter had
only ping passing because all eight methods were placeholders. The completed
implementation has no remaining TODO or NotImplementedException in selected
algorithm source. See `tests/student/results/official.log` and `official.json`.

### Independent small cases and witnesses

`verify.py` passed **5815 requests in one persistent mixed-task process**.
It expands 40 named fixtures to 60 requests, places those before and after
generated requests, and shuffles generated tasks with seed 4102026. Output
line counts, object/field types and integer arrays are checked. In Python,
`type(x) is int` rejects Booleans, which otherwise compare equal to 0/1.

| Command | Passed requests | Independent expected result |
|---|---:|---|
| lcs | 1133 | Enumerate subsequences of the shorter input; test subsequence membership |
| merge | 536 | Enumerate possible next adjacent merges, memoizing block tuples |
| tree | 172 | Enumerate all vertex subsets and reject adjacent selections |
| naive | 1125 | Compare direct Python slices at every possible start |
| kmp | 1125 | Same independent slice oracle, including empty boundaries |
| rk | 1125 | Same independent slice oracle, including real hash collisions |
| suffix | 427 | Direct small suffix-string sort and direct adjacent LCP comparisons |
| aho | 172 | Direct slice equality for every pattern/text, preserving duplicates |

Exhaustive cases cover every binary LCS pair up to length 4 (961), every
0/1/2 block tuple up to length 5 (364), binary search texts up to length 5
and patterns up to length 3 (2835 algorithm requests), and all binary suffix
texts up to length 7 (255). Additional random cases cover all printable ASCII,
arbitrary vertex labels, negative/large weights and repeated independent texts.
The merge oracle enumerates next actions rather than reproducing interval DP;
the LCS oracle enumerates subsequences rather than another prefix DP.

Witness validation independently checks both LCS subsequence relations and
length, merge live intervals/chronology/operation count/recomputed cost, and
tree selected-ID uniqueness/range/independence/recomputed weight. Suffix
validation checks full arrays and two real occurrences of an optimal repeat.
Comparing the three search implementations is therefore not the sole oracle.

All 60 expanded boundary fixtures have their complete expected and actual
responses in `tests/student/results/edge_results.json`; the generated suite's
seed, case counts, request SHA-256 and implementation source SHA-256 are in
`verification.json`. The following are representative actual checked cases:

| Command | Fixture in `tests/student/edge_cases.json` | Expected | Actual evidence | Defect detected |
|---|---|---|---|---|
| lcs | `lcs-subsequence` | length 4, `team` | Matching complete witness in `edge_results.json` | Confusing subsequence and substring |
| lcs | `lcs-ties` | any valid length-4 witness | Valid optimal witness | Requiring a specific tied answer |
| merge | `merge-adjacency` | 203 with valid live-block plan | Cost and chronological simulation passed | Arbitrary greedy merging |
| merge | `merge-64-bit` | 8000000000 | Exact cost and plan passed | 32-bit overflow |
| tree | `tree-negative` | 0, empty selection | Exact optimum and valid set | Forcing a nonempty set |
| tree | `tree-64-bit` | 4000000000 | Exact weight and independent set | Overflow or conflicting vertices |
| all searches | `search-empty-pattern` | `[0,1,2,3]` | All three agree with oracle | Missing final empty boundary |
| all searches | `search-overlap` | `[0,1,2]` | All three exact arrays passed | Advancing by pattern length |
| rk | `rk-collision` | `[0]` for `abdj`/`ab` | Exact `[0]` | Treating hash equality as proof |
| rk | `rk-negative-remainder` | `[1]` for `zab`/`ab` | Exact `[1]` | Missing modulo normalization |
| suffix | `suffix-all-equal` | sa `[3,2,1,0]`, lcp `[0,1,2,3]`, repeat length 3 | All arrays and witness passed | Wrong sentinel/order/LCP/overlap |
| aho | `aho-suffix-duplicates-reset` | rows `[2,2,2,2]`, `[2,2,2,2]`, zeros, `[1,0,1,1]` | Complete matrix passed | Suffix loss, duplicate loss or stale counts |

### Full-domain stress

`stress.py` passed **27/27 cases** under a 20-second timeout per batch.
Every child was pinned to one logical CPU, with an 8-MiB output-size check.
The exact batch times, output bytes and sampled peak working-set figures are
recorded in `tests/student/results/stress.json`. In the recorded final run,
the slowest batch was the four-tree batch at **0.933 seconds**; the largest
sampled peak working set was **165.79 MiB**. The largest output batch was
4970213 bytes, below 8 MiB. Official setup/check builds both completed with
zero warnings and zero errors within the 60-second compilation timeout.

| Task | Cases | Scale and independent checks |
|---|---:|---|
| lcs | 3 | 1000x1000 equal, reversed blocks and random; bitset LCS oracle for random |
| merge | 3 | n=200, equal 1e9 weights, all zeros, one large block; analytic optima and full plan simulation |
| tree | 4 | n=100000 chain, negative chain, star and random tree; witnesses checked in every case |
| naive | 3 | n=3000 dense matches, late mismatch and empty pattern |
| kmp | 3 | n=200000, m=100000; dense matches, late mismatch and empty pattern |
| rk | 4 | n*m=20000000, dense matches, shared-prefix collision, maximum pattern length and empty pattern |
| suffix | 3 | n=50000 equal, periodic and random ASCII, checking every sa/lcp entry and repeat |
| aho | 4 | Dense matches/duplicates, 100000-deep trie, total length 100000 wide dictionary, 100 texts and 10000 columns |

For n equal-sized merge blocks of weight w, an optimal balanced binary merge
tree has external path length `n*(floor(log2(n))+2)-2^(floor(log2(n))+1)`;
for n=200,w=1e9 the expected cost is 1544000000000. A prefix-code tree with
leaf depths differing by more than one can be improved by balancing, which
establishes the formula; an alphabetic balanced tree realizes it. The random
unit-weight tree's optimum is checked as `n - maximum matching size`: a tree
is bipartite, and greedy leaf-edge elimination finds a maximum matching,
independently of the submitted take/skip recurrence. For random large suffix
strings, the oracle sorts direct 16-character prefixes then full suffixes
only inside tied buckets; it never uses rank doubling.

Memory measurement samples native-host process working sets every 5 ms and
uses the OS-reported peak where available. It includes runtime, parsed JSON
and serialized output; it is not an auxiliary-memory measurement or an enforced
768-MiB Linux cgroup quota. Large Aho outputs run in separate batches to respect
8 MiB. These measurements demonstrate the tested local workload, not all
possible official group compositions. Official grading runs on a different
environment, and passing these tests does not establish a guaranteed score.

## Search comparison

The actual benchmark links the submitted `Algorithms.cs` into the separate
net8.0 Release project in `tests/student/benchmark/`. No search algorithm is
copied. Reproduce with `python tests/student/benchmark.py`.

**Inputs.** `(n,m)` increases through `(300,75)`, `(1000,250)`, `(3000,750)`.
All are in the common official domain, including RK's product limit. Use
`System.Random(4102026)` to draw random text uniformly from `abcd`, then draw
a valid start and extract the pattern from that exact text. Thus each random
case has at least one match. Repetitive cases use `a^n` and `a^m`, yielding
n-m+1 overlapping matches. The same request object goes to all three methods.
The artifact records the sampled start and text SHA-256 for each case.

**Correctness before timing.** An independent ordinal `IndexOf` oracle finds
all starts, advancing by one to retain overlaps. The benchmark checks each
algorithm against this oracle before warm-up and after every sample. Built-in
search is used only in the benchmark oracle, never the submitted algorithms.
All 18 configurations passed. Separate correctness fixtures include the
`ab`/`dj` collision in both directions.

**Timing scope and warm-up.** Tiered compilation is disabled for the benchmark
process (`DOTNET_TieredCompilation=0`), with 20 warm-up calls for each method
and input configuration after correctness verification. Then take five real
measurement samples per configuration, each containing 25 complete calls.
Compilation, process startup, input generation, input JSON parsing, output
serialization, correctness checks and explicit pre-sample garbage collection
are outside the timer. Timed work includes request-field extraction, algorithm
work, result JSON DOM allocation, a checksum update and `GC.KeepAlive`.
Natural garbage collection inside a sample is included. Before each sample
run a full GC outside the timer. Rotate algorithm order across samples.
All methods use identical boundaries. Stopwatch frequency and actual runtime
are saved in the report. There are 90 measured blocks / 2250 measured calls;
the five samples are within one warmed process, not separate cold startups.

**Raw measurements.** `tests/student/results/benchmark.json` preserves every
original 25-call block duration in milliseconds, each normalized microseconds
per call, and each five-sample median. `benchmark.md` presents all five runs.
The table below contains those real normalized measurements; rounding is only
for display. These are per-call block means, not individual-call latencies.

Times are **microseconds per call**; all rows passed the independent output
check, and all use seed 4102026 and the generators described above.

| Case | n | m | Algorithm | Run 1 | Run 2 | Run 3 | Run 4 | Run 5 | Median |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|
| random | 300 | 75 | naive | 1.108 | 0.592 | 0.680 | 0.560 | 0.684 | 0.680 |
| random | 300 | 75 | kmp | 1.404 | 1.104 | 0.916 | 0.748 | 0.780 | 0.916 |
| random | 300 | 75 | rk | 2.332 | 2.068 | 2.200 | 2.096 | 2.100 | 2.100 |
| random | 1000 | 250 | naive | 1.192 | 1.388 | 1.220 | 1.136 | 1.296 | 1.220 |
| random | 1000 | 250 | kmp | 2.584 | 2.068 | 2.356 | 2.432 | 2.344 | 2.356 |
| random | 1000 | 250 | rk | 6.176 | 6.152 | 6.320 | 7.628 | 6.248 | 6.248 |
| random | 3000 | 750 | naive | 3.432 | 3.596 | 2.844 | 3.676 | 3.568 | 3.568 |
| random | 3000 | 750 | kmp | 6.448 | 8.672 | 6.208 | 5.484 | 6.884 | 6.448 |
| random | 3000 | 750 | rk | 17.824 | 17.764 | 28.540 | 17.768 | 19.952 | 17.824 |
| repetitive | 300 | 75 | naive | 19.808 | 15.528 | 17.588 | 15.492 | 16.044 | 16.044 |
| repetitive | 300 | 75 | kmp | 8.944 | 8.840 | 9.380 | 9.948 | 9.240 | 9.240 |
| repetitive | 300 | 75 | rk | 19.148 | 19.876 | 17.048 | 18.428 | 22.716 | 19.148 |
| repetitive | 1000 | 250 | naive | 115.876 | 95.520 | 96.008 | 102.940 | 107.368 | 102.940 |
| repetitive | 1000 | 250 | kmp | 49.704 | 30.432 | 28.956 | 30.512 | 33.420 | 30.512 |
| repetitive | 1000 | 250 | rk | 117.948 | 113.576 | 121.812 | 130.840 | 122.552 | 121.812 |
| repetitive | 3000 | 750 | naive | 735.068 | 806.704 | 761.848 | 722.364 | 725.440 | 735.068 |
| repetitive | 3000 | 750 | kmp | 109.896 | 140.924 | 117.408 | 110.608 | 246.344 | 117.408 |
| repetitive | 3000 | 750 | rk | 1015.428 | 938.072 | 896.124 | 920.028 | 963.692 | 938.072 |

**Interpretation.** On these random inputs, early mismatches make naive
comparison inexpensive; KMP pays for its prefix table and RK pays for modular
rolling hashes. The observed random-case ordering is compatible with all
three theoretical bounds. On repetitive inputs, naive and exact RK compare
many full windows, while KMP reuses its prefix information. Result DOM
allocation is included for all three and contributes substantially when z
is large. Small microsecond timings are sensitive to scheduling, cache state
and clock/CPU frequency variation; raw samples show this variation.

The small modulus 101 makes accidental candidates common (roughly one hash
bucket in 101 under a uniform-hash heuristic, not a correctness guarantee).
Equal-character texts are more extreme: every true match is a candidate and
needs exact verification. These results describe this intentionally small
hash and these distributions. They do not generalize to all production hash
schemes, prove an asymptotic bound or rank algorithms on every input.

## Review findings, limitations and submission status

The eight original unimplemented handlers were replaced. Reconstruction is
included for all optimization tasks. Specific failure modes addressed are
parent-before-child merge plans, signed-weight empty-set handling, recursive
tree stack overflow, KMP overlap loss, RK collisions/negative remainder,
suffix sentinel leakage and Aho suffix/duplicate/reset errors. These were
risks checked by tests, not a claim that each was an observed intermediate bug.
The first completed implementation passed both public and independent suites.
A local capture issue with non-English .NET build diagnostics was corrected
in `run_all.py` by setting the CLI UI language for recorded official runs.

No known correctness failure remains in the tested official domain. Local
builds use SDK 9 targeting net8.0 and .NET 8 runtime; an actual SDK-8/Linux
Actions run has not been performed here. The supplied workflow installs
Python 3.12 and .NET 8 and selects CSharp via `submission.json`; it is unchanged.
Other-language starter placeholders intentionally remain as supplied; only
the selected C# implementation is the submission. Build/bin/obj and Python
cache directories are ignored by the existing `.gitignore` and are not
submission content. No final commit URL exists yet; the student must review
the diff and explicitly authorize any later commit/push. Moodle is untouched.

## Sources and AI Assistance

The primary materials used for this assignment were the official course resources provided in the [repository for Assignment 4](https://github.com/RZhaniya/daa-assignment-4-archive), including the README file, the assignment specification, algorithm contracts, grading criteria, testing recommendations, and submission instructions.

No third-party algorithm implementations or external algorithm libraries were used.

The **OpenAI Codex** model was utilized to develop additional test cases, create independent "oracles" for testing, and assist in drafting the technical documentation found in the `ANALYSIS.md` file.

**ChatGPT** was used to clarify assignment requirements, assist in designing additional tests, and gain a better understanding of the course material and the algorithms themselves.

I personally implemented the algorithms, verified the implementations, conducted testing, analyzed the results, and ensured the assignment functions correctly. All code and documentation generated with the help of AI have been reviewed and verified.

Benchmark results were obtained through actual execution rather than being estimated values. Performance metrics may vary depending on the runtime environment and system state.

Final editing, verification, and submission of the assignment remain my responsibility.
