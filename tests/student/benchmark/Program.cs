using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text.Json;
using System.Text.Json.Nodes;

// A separate executable benchmarks the actual submission methods, never a copy.
const int Seed = 4102026;
const int WarmupCalls = 20;
const int Samples = 5;
const int CallsPerSample = 25;
var algorithms = new (string Name, Func<JsonObject, JsonObject> Run)[]
{
    ("naive", Algorithms.naive), ("kmp", Algorithms.kmp), ("rk", Algorithms.rk)
};
var rng = new Random(Seed);
var rows = new List<object>();
long checksum = 0;

foreach (string kind in new[] { "random", "repetitive" })
foreach ((int n, int m) in new[] { (300, 75), (1000, 250), (3000, 750) })
{
    string text = kind == "random"
        ? new string(Enumerable.Range(0, n).Select(_ => "abcd"[rng.Next(4)]).ToArray())
        : new string('a', n);
    int chosenStart = kind == "random" ? rng.Next(n - m + 1) : 0;
    string pattern = text.Substring(chosenStart, m);
    var request = new JsonObject { ["text"] = text, ["pattern"] = pattern };

    // Independent trusted oracle is outside the timing region. Built-in exact
    // search is used ONLY by this benchmark, never by the submission algorithms.
    var expected = new List<int>();
    int next = 0;
    while (next <= n - m)
    {
        int found = text.IndexOf(pattern, next, StringComparison.Ordinal);
        if (found < 0) break;
        expected.Add(found);
        next = found + 1;
    }
    void Check(JsonObject answer)
    {
        int[] actual = answer["positions"]!.AsArray().Select(x => x!.GetValue<int>()).ToArray();
        if (!actual.SequenceEqual(expected)) throw new InvalidOperationException("Incorrect search result");
    }
    foreach (var algorithm in algorithms) Check(algorithm.Run(request));
    foreach (var algorithm in algorithms)
        for (int call = 0; call < WarmupCalls; call++) Check(algorithm.Run(request));

    var milliseconds = algorithms.Select(_ => new List<double>()).ToArray();
    for (int sample = 0; sample < Samples; sample++)
        // Rotate method order to reduce fixed-order bias.
        for (int offset = 0; offset < algorithms.Length; offset++)
        {
            int index = (sample + offset) % algorithms.Length;
            GC.Collect();
            GC.WaitForPendingFinalizers();
            GC.Collect();
            long started = Stopwatch.GetTimestamp();
            for (int call = 0; call < CallsPerSample; call++)
            {
                JsonObject answer = algorithms[index].Run(request);
                checksum += answer["positions"]!.AsArray().Count;
                GC.KeepAlive(answer);
            }
            milliseconds[index].Add(Stopwatch.GetElapsedTime(started).TotalMilliseconds);
            Check(algorithms[index].Run(request));
        }

    for (int index = 0; index < algorithms.Length; index++)
    {
        double[] micros = milliseconds[index].Select(ms => ms * 1000 / CallsPerSample).ToArray();
        rows.Add(new
        {
            kind, n, m, seed = Seed, algorithm = algorithms[index].Name,
            pattern_start = chosenStart, expected_matches = expected.Count,
            text_sha256 = Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(
                System.Text.Encoding.ASCII.GetBytes(text))).ToLowerInvariant(),
            raw_sample_milliseconds = milliseconds[index],
            microseconds_per_call = micros, median_microseconds_per_call = micros.Order().ElementAt(Samples / 2),
            correct_outputs_checked = true
        });
    }
}
Console.WriteLine(JsonSerializer.Serialize(new
{
    seed = Seed, warmup_calls_per_configuration = WarmupCalls, samples = Samples,
    calls_per_sample = CallsPerSample, checksum,
    runtime = RuntimeInformation.FrameworkDescription, os = RuntimeInformation.OSDescription,
    architecture = RuntimeInformation.ProcessArchitecture.ToString(),
    processor_count = Environment.ProcessorCount, stopwatch_frequency = Stopwatch.Frequency,
    tiered_compilation = Environment.GetEnvironmentVariable("DOTNET_TieredCompilation"),
    scope = "Public method call including JsonObject extraction and result DOM allocation; checksum/KeepAlive; " +
            "excludes input generation, parsing, serialization, correctness checks, explicit pre-sample GC and compilation. " +
            "Natural GC inside each measured block is included. Each raw sample times 25 real calls.",
    generator = "System.Random(seed=4102026), random text iid uniform over abcd; pattern sampled from that text. " +
                "Repetitive text=a^n and pattern=a^m.",
    rows
}));
