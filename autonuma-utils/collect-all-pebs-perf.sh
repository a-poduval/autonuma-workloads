./pebs-perf-node.sh liblinear 1 8 liblinear-0GB
./pebs-perf-node.sh liblinear 1 4 liblinear-0GB
./pebs-perf-node.sh liblinear 1 2 liblinear-0GB
for i in {1..10}
do
  ./pebs-perf-slowdown.sh liblinear $((1024 * i * 6)) 8 liblinear-$((i * 6))GB
  ./pebs-perf-slowdown.sh liblinear $((1024 * i * 6)) 4 liblinear-$((i * 6))GB
  ./pebs-perf-slowdown.sh liblinear $((1024 * i * 6)) 2 liblinear-$((i * 6))GB
done
./pebs-perf-node.sh liblinear 0 8 liblinear-RSS
./pebs-perf-node.sh liblinear 0 4 liblinear-RSS
./pebs-perf-node.sh liblinear 0 2 liblinear-RSS

./pebs-perf-node.sh xsbench 1 8 xsbench-0GB
./pebs-perf-node.sh xsbench 1 4 xsbench-0GB
./pebs-perf-node.sh xsbench 1 2 xsbench-0GB
for i in {1..10}
do
  ./pebs-perf-slowdown.sh xsbench $((1024 * i * 7)) 8 xsbench-$((i * 7))GB
  ./pebs-perf-slowdown.sh xsbench $((1024 * i * 7)) 4 xsbench-$((i * 7))GB
  ./pebs-perf-slowdown.sh xsbench $((1024 * i * 7)) 2 xsbench-$((i * 7))GB
done
./pebs-perf-node.sh xsbench 0 8 xsbench-RSS
./pebs-perf-node.sh xsbench 0 4 xsbench-RSS
./pebs-perf-node.sh xsbench 0 2 xsbench-RSS

./pebs-perf-node.sh silo 1 8 silo-0GB
./pebs-perf-node.sh silo 1 4 silo-0GB
./pebs-perf-node.sh silo 1 2 silo-0GB
for i in {1..10}
do
  ./pebs-perf-slowdown.sh silo $((1024 * i * 7)) 8 silo-$((i * 7))GB
  ./pebs-perf-slowdown.sh silo $((1024 * i * 7)) 4 silo-$((i * 7))GB
  ./pebs-perf-slowdown.sh silo $((1024 * i * 7)) 2 silo-$((i * 7))GB
done
./pebs-perf-node.sh silo 0 8 silo-RSS
./pebs-perf-node.sh silo 0 4 silo-RSS
./pebs-perf-node.sh silo 0 2 silo-RSS

./pebs-perf-node.sh flexkvs 1 8 flexkvs-0GB
./pebs-perf-node.sh flexkvs 1 4 flexkvs-0GB
./pebs-perf-node.sh flexkvs 1 2 flexkvs-0GB
for i in {1..10}
do
  ./pebs-perf-slowdown.sh flexkvs $((1024 * i * 7)) 8 flexkvs-$((i * 7))GB
  ./pebs-perf-slowdown.sh flexkvs $((1024 * i * 7)) 4 flexkvs-$((i * 7))GB
  ./pebs-perf-slowdown.sh flexkvs $((1024 * i * 7)) 2 flexkvs-$((i * 7))GB
done
./pebs-perf-node.sh flexkvs 0 8 flexkvs-RSS
./pebs-perf-node.sh flexkvs 0 4 flexkvs-RSS
./pebs-perf-node.sh flexkvs 0 2 flexkvs-RSS

./pebs-perf-node.sh gapbs_bc 1 8 gapbs_bc-0GB
./pebs-perf-node.sh gapbs_bc 1 4 gapbs_bc-0GB
./pebs-perf-node.sh gapbs_bc 1 2 gapbs_bc-0GB
for i in {1..10}
do
  ./pebs-perf-slowdown.sh gapbs_bc $((1024 * i * 4)) 8 gapbs_bc-$((i * 4))GB
  ./pebs-perf-slowdown.sh gapbs_bc $((1024 * i * 4)) 4 gapbs_bc-$((i * 4))GB
  ./pebs-perf-slowdown.sh gapbs_bc $((1024 * i * 4)) 2 gapbs_bc-$((i * 4))GB
done
./pebs-perf-node.sh gapbs_bc 0 8 gapbs_bc-RSS
./pebs-perf-node.sh gapbs_bc 0 4 gapbs_bc-RSS
./pebs-perf-node.sh gapbs_bc 0 2 gapbs_bc-RSS

./pebs-perf-node.sh gapbs_cc 1 8 gapbs_cc-0GB
./pebs-perf-node.sh gapbs_cc 1 4 gapbs_cc-0GB
./pebs-perf-node.sh gapbs_cc 1 2 gapbs_cc-0GB
for i in {1..10}
do
  ./pebs-perf-slowdown.sh gapbs_cc $((1024 * i * 4)) 8 gapbs_cc-$((i * 4))GB
  ./pebs-perf-slowdown.sh gapbs_cc $((1024 * i * 4)) 4 gapbs_cc-$((i * 4))GB
  ./pebs-perf-slowdown.sh gapbs_cc $((1024 * i * 4)) 2 gapbs_cc-$((i * 4))GB
done
./pebs-perf-node.sh gapbs_cc 0 8 gapbs_cc-RSS
./pebs-perf-node.sh gapbs_cc 0 4 gapbs_cc-RSS
./pebs-perf-node.sh gapbs_cc 0 2 gapbs_cc-RSS

./pebs-perf-node.sh gapbs_pr 1 8 gapbs_pr-0GB
./pebs-perf-node.sh gapbs_pr 1 4 gapbs_pr-0GB
./pebs-perf-node.sh gapbs_pr 1 2 gapbs_pr-0GB
for i in {1..10}
do
  ./pebs-perf-slowdown.sh gapbs_pr $((1024 * i * 4)) 8 gapbs_pr-$((i * 4))GB
  ./pebs-perf-slowdown.sh gapbs_pr $((1024 * i * 4)) 4 gapbs_pr-$((i * 4))GB
  ./pebs-perf-slowdown.sh gapbs_pr $((1024 * i * 4)) 2 gapbs_pr-$((i * 4))GB
done
./pebs-perf-node.sh gapbs_pr 0 8 gapbs_pr-RSS
./pebs-perf-node.sh gapbs_pr 0 4 gapbs_pr-RSS
./pebs-perf-node.sh gapbs_pr 0 2 gapbs_pr-RSS

./pebs-perf-node.sh merci 1 8 merci-0MB
./pebs-perf-node.sh merci 1 4 merci-0MB
./pebs-perf-node.sh merci 1 2 merci-0MB
for i in {1..10}
do
  ./pebs-perf-slowdown.sh merci $((1280 * i * 2)) 8 merci-$((i * 2560))MB
  ./pebs-perf-slowdown.sh merci $((1280 * i * 2)) 4 merci-$((i * 2560))MB
  ./pebs-perf-slowdown.sh merci $((1280 * i * 2)) 2 merci-$((i * 2560))MB
done
./pebs-perf-node.sh merci 0 8 merci-RSS
./pebs-perf-node.sh merci 0 4 merci-RSS
./pebs-perf-node.sh merci 0 2 merci-RSS
