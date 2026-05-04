#!/bin/bash

#for i in {1..12}
#do
# ./memeater-damon.sh flexkvs $((1024 * 6 * i)) 16 flexkvs-$((i * 6))GB
# ./memeater-damon.sh flexkvs $((1024 * 6 * i)) 8 flexkvs-$((i * 6))GB
# ./memeater-damon.sh flexkvs $((1024 * 6 * i)) 4 flexkvs-$((i * 6))GB
#done
#
#for i in {1..12}
#do
#  ./memeater-damon.sh gapbs_bc $((1024 * 4 * i)) 16 gapbs_bc-$((i * 4))GB
#  ./memeater-damon.sh gapbs_bc $((1024 * 4 * i)) 8 gapbs_bc-$((i * 4))GB
#  ./memeater-damon.sh gapbs_bc $((1024 * 4 * i)) 4 gapbs_bc-$((i * 4))GB
#done
#
for i in {1..12}
do
  ./memeater-damon.sh gapbs_cc $((1024 * 4 * i)) 16 gapbs_cc-$((i * 4))GB
  ./memeater-damon.sh gapbs_cc $((1024 * 4 * i)) 8 gapbs_cc-$((i * 4))GB
  ./memeater-damon.sh gapbs_cc $((1024 * 4 * i)) 4 gapbs_cc-$((i * 4))GB
done

for i in {1..12}
do
  ./memeater-damon.sh gapbs_pr $((1024 * 4 * i)) 16 gapbs_pr-$((i * 4))GB
  ./memeater-damon.sh gapbs_pr $((1024 * 4 * i)) 8 gapbs_pr-$((i * 4))GB
  ./memeater-damon.sh gapbs_pr $((1024 * 4 * i)) 4 gapbs_pr-$((i * 4))GB
done

for i in {1..12}
do
  ./memeater-damon.sh liblinear $((1024 * 5 * i)) 16 liblinear-$((i * 5))GB
  ./memeater-damon.sh liblinear $((1024 * 5 * i)) 8 liblinear-$((i * 5))GB
  ./memeater-damon.sh liblinear $((1024 * 5 * i)) 4 liblinear-$((i * 5))GB
done

for i in {1..12}
do
  ./memeater-damon.sh merci $((1024 * 2 * i)) 16 merci-$((i * 2))GB
  ./memeater-damon.sh merci $((1024 * 2 * i)) 8 merci-$((i * 2))GB
  ./memeater-damon.sh merci $((1024 * 2 * i)) 4 merci-$((i * 2))GB
done

for i in {1..12}
do
  ./memeater-damon.sh silo $((1024 * 6 * i)) 16 silo-$((i * 6))GB
  ./memeater-damon.sh silo $((1024 * 6 * i)) 8 silo-$((i * 6))GB
  ./memeater-damon.sh silo $((1024 * 6 * i)) 4 silo-$((i * 6))GB
done

for i in {1..12}
do
  ./memeater-damon.sh xsbench $((1024 * 6 * i)) 16 xsbench-$((i * 6))GB
  ./memeater-damon.sh xsbench $((1024 * 6 * i)) 8 xsbench-$((i * 6))GB
  ./memeater-damon.sh xsbench $((1024 * 6 * i)) 4 xsbench-$((i * 6))GB
done
