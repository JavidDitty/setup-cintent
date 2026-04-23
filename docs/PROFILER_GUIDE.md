# Profiler Options Guide

CIntent now supports five different profiling backends. Choose based on your needs:

## Profiler Comparison

| Profiler | Coverage | Overhead | Requires Root | Output Format | Best For |
|----------|----------|----------|---------------|---------------|----------|
| **sysmonitor** (default) | 100% | 2-3% | No | CSV trace | **Recommended**: full coverage, low overhead |
| **py-spy** | ~90-95% | 5-10% | No | speedscope JSON | General use, balanced |
| **perf** | ~99% | 10-15% | Yes | perf.data | System analysis, detailed |
| **uprobe** | 100% | 1-3% | Yes | CSV trace | Complete coverage, eBPF-based |
| **setprofile** | 100% | 5-8% | No | CSV trace | Complete coverage, legacy fallback |

## Usage

### sysmonitor (Default - sys.monitoring PEP 669)

```yaml
- uses: clonedSemicolon/setup-cintent@main
  with:
    profiler: "sysmonitor"
```

**Pros:**
- **100% function call coverage** (deterministic, not sampling)
- **Very low overhead (~2-3%)** — C-level callback dispatch in the interpreter
- **No root/sudo required**
- Automatically disables monitoring for non-workspace code objects (zero future cost for stdlib/library calls)
- Only fires for Python functions (PY_START/PY_RETURN), skips C extension calls
- Falls back to sys.setprofile on Python < 3.12

**Cons:**
- Requires Python 3.12+ for full performance benefit (falls back to setprofile otherwise)

**Note:** `sample_rate` is ignored (captures all calls deterministically).

---

### py-spy (Sampling)

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

### For CI Testing (Default) ⭐ RECOMMENDED
```yaml
- uses: clonedSemicolon/setup-cintent@main
  with:
    profiler: "sysmonitor"
```

### For Maximum Coverage (eBPF, root required)
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

### For Legacy / Older Python
```yaml
- uses: clonedSemicolon/setup-cintent@main
  with:
    profiler: "setprofile"
```

## Sample Rate Guidelines

For `py-spy` and `perf`:

- **100** - Low overhead, long-running processes
- **500** - Balanced, good for most CI jobs
- **1000** - Default, captures most calls
- **5000** - High coverage, acceptable overhead
- **10000** - Maximum coverage, high overhead

For `uprobe`: sample_rate is ignored (captures all calls).

---

## sysmonitor (sys.monitoring PEP 669) - DEFAULT ⭐

**Uses Python 3.12+'s `sys.monitoring` API (PEP 669) for deterministic 100% coverage with very low overhead.**

### Why sysmonitor?

The key innovation is the `DISABLE` mechanism: when the callback sees a non-workspace
function (stdlib, pip packages, etc.), it returns `sys.monitoring.DISABLE` which
**permanently removes the callback for that code object**. This means:
- **First call** to any stdlib function: 1 callback (to classify it)
- **All subsequent calls**: **zero overhead**

Additionally, `PY_START` / `PY_RETURN` only fire for Python functions — C extension
calls are skipped entirely.

### Advantages
- ✅ **100% function call coverage** (deterministic, not sampling)
- ✅ **~2-3% overhead** (C-level dispatch + DISABLE optimisation)
- ✅ **No root/sudo required**
- ✅ **No external dependencies** (pure Python stdlib)
- ✅ **Automatic fallback** to sys.setprofile on Python < 3.12

### Output Format
CSV format: `timestamp_ns,event,function,filename,line`

```csv
1234567890123456789,call,test_function,/path/to/test.py,42
1234567890234567890,return,test_function,/path/to/test.py,42
```

### When to Use
- **Default for all CI profiling** (GitHub Actions, etc.)
- Need 100% coverage with minimal performance impact
- Python 3.12+ target projects (best performance)
- Any environment — no root, no special kernel features required

---

## setprofile (sys.setprofile) - Legacy

**Uses Python's built-in `sys.setprofile()` for deterministic 100% coverage. Superseded by sysmonitor for Python 3.12+.**

### Advantages
- ✅ **100% function call coverage** (deterministic, not sampling)
- ✅ **No root/sudo required**
- ✅ **Cross-platform** (Linux, macOS, Windows)
- ✅ **Works on all Python versions** (3.6+)

### Disadvantages
- ⚠️ **~5-8% overhead** — pure-Python callback on every call/return
- ⚠️ Fires for C calls too (`c_call`, `c_return`), adding unnecessary cost

### When to Use
- Python < 3.12 targets where sysmonitor is unavailable
- Cross-platform profiling on older Python

---

## Sample Rate Guidelines

For `py-spy` and `perf` only:
- **100** - Low overhead, long-running processes
- **500** - Balanced, good for most CI jobs
- **1000** - Default, captures most calls
- **5000** - High coverage, acceptable overhead
- **10000** - Maximum coverage, high overhead

For `sysmonitor`, `uprobe`, and `setprofile`: sample_rate is ignored (captures all calls).
