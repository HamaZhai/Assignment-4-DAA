using System.Text.Json.Nodes;

public static class Algorithms
{
    public static JsonObject lcs(JsonObject input)
    {
        string a = input["a"]!.GetValue<string>();
        string b = input["b"]!.GetValue<string>();
        var lengths = new int[a.Length + 1, b.Length + 1];
        for (int i = 1; i <= a.Length; i++)
            for (int j = 1; j <= b.Length; j++)
                lengths[i, j] = a[i - 1] == b[j - 1]
                    ? lengths[i - 1, j - 1] + 1
                    : Math.Max(lengths[i - 1, j], lengths[i, j - 1]);

        int length = lengths[a.Length, b.Length];
        var sequence = new char[length];
        int row = a.Length, column = b.Length, remaining = length;
        while (row > 0 && column > 0)
        {
            if (a[row - 1] == b[column - 1])
            {
                sequence[--remaining] = a[row - 1];
                row--;
                column--;
            }
            else if (lengths[row - 1, column] >= lengths[row, column - 1])
                row--;
            else
                column--;
        }
        return new JsonObject { ["length"] = length, ["sequence"] = new string(sequence) };
    }

    public static JsonObject merge(JsonObject input)
    {
        JsonArray sizes = input["sizes"]!.AsArray();
        int n = sizes.Count;
        var plan = new JsonArray();
        if (n <= 1)
            return new JsonObject { ["cost"] = 0L, ["plan"] = plan };

        var prefix = new long[n + 1];
        for (int i = 0; i < n; i++)
            prefix[i + 1] = prefix[i] + sizes[i]!.GetValue<long>();
        var costs = new long[n, n];
        var splits = new int[n, n];
        for (int length = 2; length <= n; length++)
            for (int left = 0; left + length <= n; left++)
            {
                int right = left + length - 1;
                long totalSize = prefix[right + 1] - prefix[left];
                long best = long.MaxValue;
                for (int split = left; split < right; split++)
                {
                    long candidate = costs[left, split] + costs[split + 1, right] + totalSize;
                    if (candidate < best)
                    {
                        best = candidate;
                        splits[left, right] = split;
                    }
                }
                costs[left, right] = best;
            }

        void AppendPlan(int left, int right)
        {
            if (left == right) return;
            int split = splits[left, right];
            AppendPlan(left, split);
            AppendPlan(split + 1, right);
            plan.Add(new JsonArray(left, split, right));
        }
        AppendPlan(0, n - 1);
        return new JsonObject { ["cost"] = costs[0, n - 1], ["plan"] = plan };
    }

    public static JsonObject tree(JsonObject input)
    {
        int n = input["n"]!.GetValue<int>();
        var selected = new JsonArray();
        if (n == 0)
            return new JsonObject { ["weight"] = 0L, ["selected"] = selected };

        var head = new int[n];
        Array.Fill(head, -1);
        var target = new int[2 * (n - 1)];
        var next = new int[target.Length];
        int edgeIndex = 0;
        void AddEdge(int from, int to)
        {
            target[edgeIndex] = to;
            next[edgeIndex] = head[from];
            head[from] = edgeIndex++;
        }
        foreach (JsonNode? edge in input["edges"]!.AsArray())
        {
            int u = edge![0]!.GetValue<int>(), v = edge[1]!.GetValue<int>();
            AddEdge(u, v);
            AddEdge(v, u);
        }

        var parent = new int[n];
        var order = new int[n];
        parent[0] = -1;
        int orderCount = 1;
        for (int index = 0; index < orderCount; index++)
        {
            int u = order[index];
            for (int edge = head[u]; edge != -1; edge = next[edge])
            {
                int v = target[edge];
                if (v == parent[u]) continue;
                parent[v] = u;
                order[orderCount++] = v;
            }
        }

        var take = new long[n];
        var skip = new long[n];
        for (int u = 0; u < n; u++)
            take[u] = input["weights"]![u]!.GetValue<long>();
        for (int index = n - 1; index > 0; index--)
        {
            int u = order[index], p = parent[u];
            take[p] += skip[u];
            skip[p] += Math.Max(take[u], skip[u]);
        }

        var chosen = new bool[n];
        foreach (int u in order)
        {
            chosen[u] = (parent[u] == -1 || !chosen[parent[u]]) && take[u] > skip[u];
            if (chosen[u]) selected.Add(u);
        }
        return new JsonObject { ["weight"] = Math.Max(take[0], skip[0]), ["selected"] = selected };
    }

    public static JsonObject naive(JsonObject input)
    {
        string text = input["text"]!.GetValue<string>();
        string pattern = input["pattern"]!.GetValue<string>();
        var positions = new JsonArray();
        for (int start = 0; start <= text.Length - pattern.Length; start++)
        {
            int matched = 0;
            while (matched < pattern.Length && text[start + matched] == pattern[matched])
                matched++;
            if (matched == pattern.Length) positions.Add(start);
        }
        return new JsonObject { ["positions"] = positions };
    }

    public static JsonObject kmp(JsonObject input)
    {
        string text = input["text"]!.GetValue<string>();
        string pattern = input["pattern"]!.GetValue<string>();
        var positions = new JsonArray();
        if (pattern.Length == 0)
        {
            for (int start = 0; start <= text.Length; start++) positions.Add(start);
            return new JsonObject { ["positions"] = positions };
        }
        var prefix = new int[pattern.Length];
        for (int i = 1; i < pattern.Length; i++)
        {
            int border = prefix[i - 1];
            while (border > 0 && pattern[i] != pattern[border]) border = prefix[border - 1];
            if (pattern[i] == pattern[border]) border++;
            prefix[i] = border;
        }
        int matched = 0;
        for (int i = 0; i < text.Length; i++)
        {
            while (matched > 0 && text[i] != pattern[matched]) matched = prefix[matched - 1];
            if (text[i] == pattern[matched]) matched++;
            if (matched == pattern.Length)
            {
                positions.Add(i - pattern.Length + 1);
                matched = prefix[matched - 1];
            }
        }
        return new JsonObject { ["positions"] = positions };
    }

    public static JsonObject rk(JsonObject input)
    {
        string text = input["text"]!.GetValue<string>();
        string pattern = input["pattern"]!.GetValue<string>();
        int n = text.Length, m = pattern.Length;
        var positions = new JsonArray();
        if (m == 0)
        {
            for (int start = 0; start <= n; start++) positions.Add(start);
            return new JsonObject { ["positions"] = positions };
        }
        if (m > n) return new JsonObject { ["positions"] = positions };

        const long Base = 31, Modulus = 101;
        long highestPower = 1, patternHash = 0, windowHash = 0;
        for (int i = 0; i < m; i++)
        {
            patternHash = (patternHash * Base + pattern[i]) % Modulus;
            windowHash = (windowHash * Base + text[i]) % Modulus;
            if (i > 0) highestPower = highestPower * Base % Modulus;
        }
        for (int start = 0; start <= n - m; start++)
        {
            if (windowHash == patternHash)
            {
                int matched = 0;
                while (matched < m && text[start + matched] == pattern[matched]) matched++;
                if (matched == m) positions.Add(start);
            }
            if (start < n - m)
            {
                long remainder = (windowHash - text[start] * highestPower) % Modulus;
                if (remainder < 0) remainder += Modulus;
                windowHash = (remainder * Base + text[start + m]) % Modulus;
            }
        }
        return new JsonObject { ["positions"] = positions };
    }

    public static JsonObject suffix(JsonObject input)
    {
        string text = input["text"]!.GetValue<string>();
        int[] sa = BuildSuffixArray(text);
        int[] lcp = BuildLcp(text, sa);
        int bestLength = 0, bestStart = 0;
        var suffixes = new JsonArray();
        var prefixes = new JsonArray();
        for (int i = 0; i < sa.Length; i++)
        {
            suffixes.Add(sa[i]);
            prefixes.Add(lcp[i]);
            if (lcp[i] > bestLength)
            {
                bestLength = lcp[i];
                bestStart = sa[i];
            }
        }
        return new JsonObject
        {
            ["sa"] = suffixes, ["lcp"] = prefixes,
            ["repeated"] = text.Substring(bestStart, bestLength)
        };
    }

    private static int[] BuildSuffixArray(string text)
    {
        int n = text.Length;
        var sa = new int[n];
        if (n == 0) return sa;
        var ranks = new int[n];
        var newRanks = new int[n];
        var buffer = new int[n];
        int classes = 95;
        var counts = new int[Math.Max(n, classes) + 1];
        for (int i = 0; i < n; i++)
        {
            sa[i] = i;
            ranks[i] = text[i] - 32 + 1;
        }
        for (int width = 1; width < n; width *= 2)
        {
            SortRanks(sa, buffer, ranks, width, classes, counts);
            SortRanks(buffer, sa, ranks, 0, classes, counts);
            int newClasses = 1;
            newRanks[sa[0]] = newClasses;
            for (int i = 1; i < n; i++)
            {
                int a = sa[i - 1], b = sa[i];
                int secondA = a + width < n ? ranks[a + width] : 0;
                int secondB = b + width < n ? ranks[b + width] : 0;
                if (ranks[a] != ranks[b] || secondA != secondB) newClasses++;
                newRanks[b] = newClasses;
            }
            (ranks, newRanks) = (newRanks, ranks);
            classes = newClasses;
            if (classes == n) break;
        }
        return sa;
    }

    private static void SortRanks(int[] source, int[] destination, int[] ranks,
        int offset, int classes, int[] counts)
    {
        Array.Clear(counts, 0, classes + 1);
        foreach (int suffix in source)
            counts[suffix + offset < ranks.Length ? ranks[suffix + offset] : 0]++;
        int position = 0;
        for (int key = 0; key <= classes; key++)
        {
            int count = counts[key];
            counts[key] = position;
            position += count;
        }
        foreach (int suffix in source)
        {
            int key = suffix + offset < ranks.Length ? ranks[suffix + offset] : 0;
            destination[counts[key]++] = suffix;
        }
    }

    private static int[] BuildLcp(string text, int[] sa)
    {
        int n = text.Length;
        var inverse = new int[n];
        var lcp = new int[n];
        for (int rank = 0; rank < n; rank++) inverse[sa[rank]] = rank;
        int common = 0;
        for (int start = 0; start < n; start++)
        {
            int rank = inverse[start];
            if (rank == 0)
            {
                common = 0;
                continue;
            }
            int previous = sa[rank - 1];
            while (start + common < n && previous + common < n &&
                   text[start + common] == text[previous + common]) common++;
            lcp[rank] = common;
            if (common > 0) common--;
        }
        return lcp;
    }

    public static JsonObject aho(JsonObject input)
    {
        JsonArray patterns = input["patterns"]!.AsArray();
        JsonArray texts = input["texts"]!.AsArray();
        var rows = new JsonArray();
        if (texts.Count == 0) return new JsonObject { ["counts"] = rows };
        if (patterns.Count == 0)
        {
            foreach (JsonNode? unused in texts) rows.Add(new JsonArray());
            return new JsonObject { ["counts"] = rows };
        }

        const int AlphabetSize = 95;
        var transitions = new List<int[]> { new int[AlphabetSize] };
        var terminals = new int[patterns.Count];
        for (int index = 0; index < patterns.Count; index++)
        {
            int state = 0;
            foreach (char character in patterns[index]!.GetValue<string>())
            {
                int symbol = character - 32;
                if (transitions[state][symbol] == 0)
                {
                    transitions[state][symbol] = transitions.Count;
                    transitions.Add(new int[AlphabetSize]);
                }
                state = transitions[state][symbol];
            }
            terminals[index] = state;
        }

        int states = transitions.Count;
        var failure = new int[states];
        var breadthFirst = new int[states];
        int queued = 0;
        for (int symbol = 0; symbol < AlphabetSize; symbol++)
            if (transitions[0][symbol] != 0) breadthFirst[queued++] = transitions[0][symbol];
        for (int index = 0; index < queued; index++)
        {
            int state = breadthFirst[index];
            for (int symbol = 0; symbol < AlphabetSize; symbol++)
            {
                int child = transitions[state][symbol];
                if (child == 0)
                    transitions[state][symbol] = transitions[failure[state]][symbol];
                else
                {
                    failure[child] = transitions[failure[state]][symbol];
                    breadthFirst[queued++] = child;
                }
            }
        }

        var visits = new long[states];
        foreach (JsonNode? textNode in texts)
        {
            Array.Clear(visits);
            int state = 0;
            foreach (char character in textNode!.GetValue<string>())
            {
                state = transitions[state][character - 32];
                visits[state]++;
            }
            for (int index = queued - 1; index >= 0; index--)
            {
                int child = breadthFirst[index];
                visits[failure[child]] += visits[child];
            }
            var row = new JsonArray();
            foreach (int terminal in terminals) row.Add(visits[terminal]);
            rows.Add(row);
        }
        return new JsonObject { ["counts"] = rows };
    }
}
