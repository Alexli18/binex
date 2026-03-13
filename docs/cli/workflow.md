# workflow

Workflow versioning and inspection commands.

## `binex workflow version`

Display the schema version of a workflow YAML file.

```bash
binex workflow version <workflow_file>
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `workflow_file` | yes | Path to workflow YAML file |

### Output

```
Workflow: simple-pipeline
Version: 1
```

If the workflow has no `version` field:

```
Workflow: legacy-flow
Version: 1 (default — no version field found)
```

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `2` | File not found |

---

## `binex workflow diff`

Compare workflow definitions used in two different runs. Shows a unified diff of the normalized YAML snapshots stored at run time.

```bash
binex workflow diff <run_id_1> <run_id_2>
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `run_id_1` | yes | First run ID |
| `run_id_2` | yes | Second run ID |

### Output

If workflows differ:

```
--- run:run_abc123
+++ run:run_def456
@@ -1,3 +1,3 @@
-name: pipeline-v1
+name: pipeline-v2
 nodes:
   a:
```

If workflows are identical:

```
Workflows are identical (no diff).
```

### Error messages

| Message | Meaning |
|---------|---------|
| `Error: Run '<id>' not found.` | Run ID does not exist in the store |
| `Error: One or both runs have no workflow snapshot.` | Runs were created before snapshot support |
| `Error: Snapshot data missing.` | Snapshot hash exists but content is gone |

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success (including "identical" case) |

---

## How workflow snapshots work

Every `binex run` automatically stores a normalized snapshot of the workflow definition in the SQLite database. The snapshot is:

1. **Normalized** — `yaml.dump(sort_keys=True)` with `source_path` excluded
2. **Hashed** — SHA256 of the normalized YAML content
3. **Deduplicated** — identical workflows share the same snapshot (by hash)

This allows comparing the exact workflow used in any two runs, even if the original YAML file has been modified since.
