# binex clean

## Synopsis

```
binex clean cache [--older-than DAYS] [--dry-run]
```

## Description

Reclaims local disk space. Currently manages the [node cache](../workflows/format.md#node-caching).

## `binex clean cache`

Clears cached node results from the local store.

| Option | Type | Description |
|---|---|---|
| `--older-than` | `float` | Only clear entries older than this many days |
| `--dry-run` | flag | Report how much is stored without deleting |

```bash
# See how much cache is stored
$ binex clean cache --dry-run
42 cache entries stored; would clear entries.

# Clear everything
$ binex clean cache
Cleared 42 cache entries.

# Clear only stale entries
$ binex clean cache --older-than 7
Cleared 9 cache entries older than 7.0 days.
```

Cache entries are pointers to the artifacts a run already produced, so clearing
them frees the cache index without touching run history. A node whose cached
artifact has been pruned simply re-executes on the next run.

## See also

- [Node Caching](../workflows/format.md#node-caching) — how caching works and how to enable it
- [`binex run`](run.md) — `--cache` / `--offline` flags
