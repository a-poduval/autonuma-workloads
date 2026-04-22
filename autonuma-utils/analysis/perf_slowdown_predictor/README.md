# perf_slowdown_predictor

This directory contains a modular parse/filter + train/predict workflow.

## Scope implemented now

- Recursive perf file matching by regex.
- Curated file selection via manifest CSV and explicit include-path.
- Runtime parsing from sibling logs.
- Tail-window filtering using runtime + safety margin.
- CSV outputs for file-level metadata and filtered epoch rows.
- Split labels in outputs (train/val/reference/predict or user-defined).
- Per-epoch feature extraction for total/unique/hotness/latency signals.
- Trainable remote-share model (ridge regression) with split-based training.
- Per-epoch predicted local/remote comparisons and per-file total comparisons.

## Not implemented yet

- Sequence models (LSTM) and reference-only generalization path.

Future work placeholders are in next_steps.py as comments only.

## Module map

- constants.py: event names, regex defaults, event code map.
- models.py: data classes.
- text_parsing.py: numeric/time token parsing.
- event_parsing.py: perf event token parsing and canonicalization.
- log_metrics.py: workload runtime/throughput extraction from logs.
- file_matching.py: regex validation and recursive file matching.
- perf_csv.py: perf CSV epoch collection and tail-window filtering.
- pipeline.py: one-file parse/filter orchestration.
- outputs.py: CSV writers.
- feature_engineering.py: epoch features + target derivation.
- model_ridge.py: remote-share regressor.
- evaluation.py: epoch/file metrics.
- prediction_outputs.py: prediction CSV writers.
- run_parse_filter.py: parse/filter CLI.
- run_train_predict.py: train + predict CLI for remote/local per epoch.
- __main__.py: package entrypoint.

## Run

From analysis directory:

python3 -m perf_slowdown_predictor <input_dir> --sort-by-path

## Simple workflow (recommended)

From this directory:

python3 main.py --train /path/to/train_logs --val /path/to/val_logs

Optional:

- add --reference /path/to/reference_logs
- add --manifest-csv selection_manifest.csv (manifest remains optional)

This writes outputs and model state to debug/ by default.

Predict with a directory or a single perf CSV:

python3 main.py --predict /path/to/log_dir_or_file

This writes prediction CSVs to debug/ and loads debug/model_state.json by default.

Curated manifest mode:

python3 -m perf_slowdown_predictor --manifest-csv selected_logs.csv --sort-by-path

Manifest CSV format:

- Required column: path
- Optional columns: split, tag, rss

Example rows:

- path,split,tag,rss
- ../../autonuma_logs/merci/merci-24GB_8t_perf.csv,reference,merci_ref,22GB
- ../../autonuma_logs/merci/merci-8GB_8t_perf.csv,train,merci_train_a,22GB
- ../../autonuma_logs/merci/merci-6GB_8t_perf.csv,val,merci_val,22GB

## Train/predict run

python3 -m perf_slowdown_predictor.run_train_predict --manifest-csv selection_manifest.csv --rss-source manifest --train-split train --sort-by-path

Outputs include:

- epoch-level predictions (actual vs predicted local/remote)
- file-level totals (actual vs predicted)
- split-level metrics
