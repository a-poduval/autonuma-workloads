for i in {1..28}
do
  ./memeater-autonuma.sh liblinear $((1024 * i)) 16 liblinear-${i}GB
  ./memeater-autonuma.sh liblinear $((1024 * i)) 8 liblinear-${i}GB
done

for i in {1..20}
do
  ./memeater-autonuma.sh silo $((1024 * i)) 16 silo-${i}GB
  ./memeater-autonuma.sh silo $((1024 * i)) 8 silo-${i}GB
done

for i in {1..40}
do
 ./memeater-autonuma.sh flexkvs $((1024 * i)) 16 flexkvs-${i}GB
 ./memeater-autonuma.sh flexkvs $((1024 * i)) 8 flexkvs-${i}GB
done

for i in {1..32}
do
  ./memeater-autonuma.sh gapbs_bc $((1024 * i)) 16 gapbs_bc-${i}GB
  ./memeater-autonuma.sh gapbs_bc $((1024 * i)) 8 gapbs_bc-${i}GB
done

for i in {1..32}
do
  ./memeater-autonuma.sh gapbs_pr $((1024 * i)) 16 gapbs_pr-${i}GB
  ./memeater-autonuma.sh gapbs_pr $((1024 * i)) 8 gapbs_pr-${i}GB
done

for i in {1..28}
do
  ./memeater-autonuma.sh merci $((1024 * i)) 16 merci-${i}GB
  ./memeater-autonuma.sh merci $((1024 * i)) 8 merci-${i}GB
done
