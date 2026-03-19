# Profiler Options Guide

CIntent now supports three different profiling backends. Choose based on your needs:

## Profiler Comparison

| Profiler | Coverage | Overhead | Output Format | Best For |
|----------|----------|----------|---------------|----------|
| **py-spy** (default) | ~90-95% | 5-10% | speedscope JSON | General use, balanced |
| **perf** | ~99% | 10-15% | perf.data | System analysis, detailed |
| **uprobe** | 100% | 1-3% | CSV trace | Complete coverage, low overhead |

## Usage

### py-spy (Default - Sampling)

```yaml
- uses: clonedSemicolon/setup-cintent@main
  with:
    profiler: "py-spy"
    sample_rate: "1000"
```

**Pros:**
- Easy to use, no extra setup
- Speedscope format compatible with existing parsers
- Works on any Python version

**Cons:**
- May miss very fast function calls
- Sampling-based (not deterministic)

---

### perf (System-level Sampling)

```yaml
- uses: clonedSemicolon/setup-cintent@main
  with:
    profiler: "perf"
    sample_rate: "1000"
```

**Pros:**
- Better Python stack unwinding
- Integrated with Linux kernel
- Can profile native C extensions

**Cons:**
- Requires perf to be installed
- Output needs conversion to speedscope format
- Higher overhead than py-spy

**Note:** Perf output is in `.perf.data` format. You'll need to convert it:
```bash
perf script -i file.perf.data | speedscope -
```

---

### uprobe (eBPF Tracing - 100% Coverage)

```yaml
- uses: clonedSemicolon/setup-cintent@main
  with:
    profiler: "uprobe"
```

**Pros:**
- **Captures EVERY function call** (100% coverage)
- Very low overhead (1-3%)
- Deterministic (not sampling-based)
- No `sample_rate` needed

**Cons:**
- Requires Python debug symbols
- May generate very large log files
- Output format is CSV, needs conversion

**Note:** Uprobe output is CSV format:
```
timestamp,pid,event,function,file,line,duration_ns
```

---

## Recommendations

### For CI Testing (Default)
```yaml
- uses: clonedSemicolon/setup-cintent@main
  with:
    profiler: "py-spy"
    sample_rate: "1000"
```

### For Maximum Coverage
```yaml
- uses: clonedSemicolon/setup-cintent@main
  with:
    profiler: "uprobe"
```

### For System Analysis
```yaml
- uses: clonedSemicolon/setup-cintent@main
  with:
    profiler: "perf"
    sample_rate: "500"
```

## Sample Rate Guidelines

For `py-spy` and `perf`:

- **100** - Low overhead, long-running processes
- **500** - Balanced, good for most CI jobs
- **1000** - Default, captures most calls
- **5000** - High coverage, acceptable overhead
- **10000** - Maximum coverage, high overhead

For `uprobe`: sample_rate is ignored (captures all calls).
