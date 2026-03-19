# Profiler Options Guide

CIntent now supports four different profiling backends. Choose based on your needs:

## Profiler Comparison

| Profiler | Coverage | Overhead | Requires Root | Output Format | Best For |
|----------|----------|----------|---------------|---------------|----------|
| **py-spy** (default) | ~90-95% | 5-10% | No | speedscope JSON | General use, balanced |
| **perf** | ~99% | 10-15% | Yes | perf.data | System analysis, detailed |
| **uprobe** | 100% | 1-3% | Yes | CSV trace | Complete coverage, low overhead |
| **setprofile** | 100% | 5-8% | No | CSV trace | Complete coverage, no root needed |

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

### For Maximum Coverage (No Root Required) ⭐ **RECOMMENDED for GitHub Actions**
```yaml
- uses: clonedSemicolon/setup-cintent@main
  with:
    profiler: "setprofile"
```

---

## setprofile (sys.setprofile) - NEW!

**Uses Python's built-in `sys.setprofile()` for deterministic 100% coverage without needing root access or external tools.**

### Advantages
- ✅ **100% function call coverage** (deterministic, not sampling)
- ✅ **No root/sudo required** (works in restrictive environments)
- ✅ **Cross-platform** (Linux, macOS, Windows)
- ✅ **No external dependencies** (pure Python stdlib)
- ✅ **~5-8% overhead** (reasonable for CI)

### Output Format
CSV format: `timestamp_ns,event,function,filename,line`

```csv
1234567890123456789,call,test_function,/path/to/test.py,42
1234567890234567890,return,test_function,/path/to/test.py,42
```

### When to Use
- GitHub Actions or CI environments without root
- Need 100% coverage but uprobe is unavailable
- Cross-platform profiling (non-Linux)
- Development/debugging scenarios

---

## Updated Sample Rate Guidelines

For `py-spy` and `perf` only:
- **100** - Low overhead, long-running processes
- **500** - Balanced, good for most CI jobs
- **1000** - Default, captures most calls
- **5000** - High coverage, acceptable overhead
- **10000** - Maximum coverage, high overhead

For `uprobe` and `setprofile`: sample_rate is ignored (captures all calls).
