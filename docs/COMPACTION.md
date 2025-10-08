# Background Compaction

## Overview

KVStore includes **automatic background compaction** to reclaim disk space from deleted entries. Since the data file is append-only, deleted entries remain until compaction runs.

## How It Works

### Compaction Logic

The background thread periodically checks if compaction is needed:

1. **Wake up** every `COMPACTION_INTERVAL` seconds (default: 1 hour)
2. **Check file size** - If file < `COMPACTION_MIN_FILE_SIZE`, skip compaction
3. **Calculate dead space ratio** - `dead_ratio = 1 - (live_data_size / total_file_size)`
4. **Compare threshold** - If `dead_ratio < COMPACTION_THRESHOLD`, skip compaction
5. **Start compaction** if both conditions are met
6. **Return to step 1** after completion or skip

### Compaction Process

**Phase 1 - Snapshot** (with read lock):
- Copy current index
- Record old file size

**Phase 2 - Copy** (minimal locking):
- Create temporary file
- Copy only active entries
- Read with brief read locks

**Phase 3 - Swap** (with write lock):
- Copy entries added during compaction
- Atomic file swap
- Update index with new offsets

**Phase 4 - Cleanup**:
- Keep backup file (data.db.old)
- Report statistics

## Configuration

Settings in `kvstore/utils/config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `COMPACTION_ENABLED` | `True` | Enable automatic compaction |
| `COMPACTION_INTERVAL` | `3600` (1 hour) | Seconds between checks |
| `COMPACTION_THRESHOLD` | `0.3` (30%) | Minimum dead space ratio |
| `COMPACTION_MIN_FILE_SIZE` | `10 MB` | Minimum file size |

**Compaction triggers when:**
1. File size ≥ `COMPACTION_MIN_FILE_SIZE`
2. Dead space ratio ≥ `COMPACTION_THRESHOLD`

**Dead space formula:** `dead_ratio = 1 - (live_data_size / total_file_size)`

## Summary

✅ **Automatic** - Runs in background without intervention  
✅ **Efficient** - Minimal impact on concurrent operations  
✅ **Configurable** - Tune thresholds for your workload  
✅ **Safe** - Atomic swaps with backup retention  
✅ **Observable** - Detailed logging and metrics  
✅ **Production-ready** - Tested with concurrent loads  
✅ **Replica-aware** - Disabled on replicas automatically

Background compaction ensures optimal disk usage automatically!

