# Page Tiering Predictor (Milestones 1-5)

This directory contains the first five implementation slices:

- Milestone 1: fast C17 text handler for PEBS traces.
- Phase 2: per-page PFN table with streaming page-state tracking.
- Phase 3: reuse-distance bookkeeping counters and running averages.
- Phase 4: fast-tier threshold prediction, confusion counters, and RSS-domain extrapolation.
- Phase 5: NUMA usage log integration, steady-state split, and optional promotion.

## Current scope

- Read a trace file line by line.
- Parse event class (`local_dram_*` or `remote_dram_*`).
- Extract address and PFN (`address >> 12`).
- Track page state keyed by PFN in an in-memory hash table.
- Record per-page access count, last timestamp, and last global access index.
- Track dual unique counters: actual-label based and predicted-placeholder based.
- Compute per-access reuse distance from global and unique counters.
- Maintain online means for reuse distance and timestamp deltas.
- Predict local/remote for observed accesses using reuse-distance vs fast-tier page budget.
- Optionally integrate `*_numa_meminfo.csv` logs to detect fast-tier steady state.
- Split observed PEBS events/new pages into before-steady and after-steady phases.
- Optional remote->local promotion based on running median reuse distance.
- Produce observed-domain prediction/confusion metrics and RSS-extrapolated metrics.
- Skip malformed or non-matching lines and count them.
- Print summary counters.

Policy for unobserved RSS pages: model one synthetic first-touch local access per
unobserved page (cold pages that can be allocated hot before eventual demotion).

## Build

```bash
make
```

## Run

```bash
./page_tiering_text_handler /path/to/trace.txt
```

Required arguments:

- `--fast-size` or `-f` : fast tier size (bytes or `K/M/G/T` suffix)
- `--rss-size` or `-r` : workload RSS (bytes or `K/M/G/T` suffix)

Optional arguments:

- `--numa-log` or `-n` : explicit NUMA memory log CSV path
- `--fast-node` or `-N` : fast node index for NUMA columns (default: 0)
- `--enable-promotion` : enable remote->local promotion

NUMA log inference (when `--numa-log` is not provided):

- If trace file name matches `*_script.txt`, the tool looks for
	`*_numa_meminfo.csv` in the same directory.
- Example:
	`flexkvs-72GB_8t_script.txt` -> `flexkvs-72GB_8t_numa_meminfo.csv`

## Example

```bash
./page_tiering_text_handler \
	/mydata/ztier/autonuma-workloads/3.autonuma_logs/silo/silo-6GB_8t_script.txt \
	--fast-size 8G \
	--rss-size 72G \
	--fast-node 0 \
	--enable-promotion
```

## Output fields

- Input file
- Fast tier size (bytes/pages)
- Workload RSS (bytes/pages)
- NUMA log integration summary (when available):
	- PEBS and NUMA timestamp spans (`last - first`)
	- aligned steady-state timestamp in PEBS time domain
	- fast/slow node used-memory growth before and after steady state
	- PEBS events/new-pages before and after steady state
	- PEBS new-page coverage before and after steady state
- Parser ingestion summary (total/parsed/ignored/malformed/timestamped)
- Observed PEBS access-level metrics:
	- Actual local/remote accesses
	- Predicted local/remote accesses
	- Predicted local but actual remote
	- Predicted remote but actual local
	- Unique pages tracked
- Phase 3 diagnostics:
	- Reuse-distance sample count and means
	- Time-delta sample count and mean
	- promotion count and running median reuse (when promotion is enabled)
- RSS extrapolated policy-level metrics:
	- Observed pages, unobserved pages
	- Synthetic first-touch local accesses
	- Extrapolated predicted/actual local/remote counts
	- Extrapolated confusion counts
