#for i in {1..12}
#do
#  ./pebs-perf-slowdown.sh xsbench $((6 * 1024 * i)) 8 xsbench-$((i * 6))GB
#done

./pebs-perf-slowdown.sh xsbench $((4 * 1024)) 8 xsbench-4GB
./pebs-perf-slowdown.sh xsbench $((32 * 1024)) 8 xsbench-32GB
./pebs-perf-slowdown.sh xsbench $((72 * 1024)) 8 xsbench-72GB

#for i in {1..12}
#do
#  ./pebs-perf-slowdown.sh liblinear $((6 * 1024 * i)) 8 liblinear-$((i * 6))GB
#done

./pebs-perf-slowdown.sh liblinear $((4 * 1024)) 8 liblinear-4GB
./pebs-perf-slowdown.sh liblinear $((32 * 1024)) 8 liblinear-32GB
./pebs-perf-slowdown.sh liblinear $((72 * 1024)) 8 liblinear-72GB

#for i in {1..12}
#do
#  ./pebs-perf-slowdown.sh silo $((6 * 1024 * i)) 8 silo-$((i * 6))GB
#done
./pebs-perf-slowdown.sh silo $((4 * 1024)) 8 silo-4GB
./pebs-perf-slowdown.sh silo $((32* 1024)) 8 silo-32GB
./pebs-perf-slowdown.sh silo $((72* 1024)) 8 silo-72GB

#for i in {1..12}
#do
# ./pebs-perf-slowdown.sh flexkvs $((6 * 1024 * i)) 8 flexkvs-$((i * 6))GB
#done
./pebs-perf-slowdown.sh flexkvs $((4 * 1024)) 8 flexkvs-4GB
./pebs-perf-slowdown.sh flexkvs $((32* 1024)) 8 flexkvs-32GB
./pebs-perf-slowdown.sh flexkvs $((72* 1024)) 8 flexkvs-72GB

#for i in {1..12}
#do
#  ./pebs-perf-slowdown.sh gapbs_bc $((4 * 1024 * i)) 8 gapbs_bc-$((i * 4))GB
#done
./pebs-perf-slowdown.sh gapbs_bc $((4 * 1024)) 8 gapbs_bc-4GB
./pebs-perf-slowdown.sh gapbs_bc $((16* 1024)) 8 gapbs_bc-16GB
./pebs-perf-slowdown.sh gapbs_bc $((40 * 1024)) 8 gapbs_bc-40GB

#for i in {1..12}
#do
#  ./pebs-perf-slowdown.sh gapbs_cc $((4 * 1024 * i)) 8 gapbs_bc-$((i * 4))GB
#done
./pebs-perf-slowdown.sh gapbs_cc $((4 * 1024)) 8 gapbs_cc-4GB
./pebs-perf-slowdown.sh gapbs_cc $((16* 1024)) 8 gapbs_cc-16GB
./pebs-perf-slowdown.sh gapbs_cc $((40 * 1024)) 8 gapbs_cc-40GB

#for i in {1..12}
#do
#  ./pebs-perf-slowdown.sh gapbs_pr $((4 * 1024 * i)) 8 gapbs_pr-$((i * 4))GB
#done
./pebs-perf-slowdown.sh gapbs_pr $((4 * 1024)) 8 gapbs_pr-4GB
./pebs-perf-slowdown.sh gapbs_pr $((16* 1024)) 8 gapbs_pr-16GB
./pebs-perf-slowdown.sh gapbs_pr $((40 * 1024)) 8 gapbs_pr-40GB

#for i in {1..9}
#do
#  ./pebs-perf-slowdown.sh merci $((2 * 1024 * i)) 8 merci-$((i * 2))GB
#done
./pebs-perf-slowdown.sh merci $((2 * 1024)) 8 merci-2GB
./pebs-perf-slowdown.sh merci $((6 * 1024)) 8 merci-6GB
./pebs-perf-slowdown.sh merci $((10 * 1024)) 8 merci-10GB
./pebs-perf-slowdown.sh merci $((14 * 1024)) 8 merci-14GB
#./pebs-perf-slowdown.sh merci $((18 * 1024)) 8 merci-18GB
./pebs-perf-slowdown.sh merci $((22 * 1024)) 8 merci-22GB
