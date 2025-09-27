#!/bin/bash

git submodule init
git submodule update

sudo apt update
sudo apt install -y libnuma-dev libpmem-dev libaio-dev libssl-dev mpich libdb++-dev pcm msr-tools

# PEBS
cd scripts/PEBS_page_tracking/
git apply ../../patches/pebs.patch
make -j20
cd ../..

# flexkvs
cd flexkvs
git apply ../patches/flexkvs.patch
make -j20
cd ..

# GAPBS
cd gapbs
git apply ../patches/gapbs.patch
make bench-graphs -j20
make -j20
cd ..

# graph_500
cd graph500
git apply ../patches/graph500.patch
cd src
make -j20
cd ../..

# liblinear
cd liblinear-2.47
wget https://www.csie.ntu.edu.tw/~cjlin/libsvmtools/datasets/binary/kddb.bz2
bunzip2 kddb.bz2
wget https://www.csie.ntu.edu.tw/~cjlin/libsvmtools/datasets/binary/kdd12.xz
unxz kdd12.xz
rm kdd12.xz
make -j20
cd ..

# MERCI
cd MERCI
git apply ../patches/merci.patch
mkdir -p data/4_filtered/amazon_All
cd data/4_filtered/amazon_All
wget https://pages.cs.wisc.edu/~apoduval/MERCI/data/4_filtered/amazon_All/amazon_All_test_filtered.txt
wget https://pages.cs.wisc.edu/~apoduval/MERCI/data/4_filtered/amazon_All/amazon_All_train_filtered.txt
cd ../../..
mkdir -p data/5_patoh/amazon_All/partition_2748/
cd data/5_patoh/amazon_All/partition_2748/
wget https://pages.cs.wisc.edu/~apoduval/MERCI/data/5_patoh/amazon_All/partition_2748/amazon_All_train_filtered.txt.part.2748
cd ../../../..
# now in merci
cd 4_performance_evaluation/
mkdir bin
make -j20
cd ../..
# now in workloads

# silo
cd silo/silo
git apply ../../patches/silo.patch
make dbtest -j20
cd ../..

# XSBench
cd XSBench/openmp-threading
make -j20
cd ../..

# Setup the colloid kernel
sudo apt install -y build-essential libncurses-dev bison flex libssl-dev libelf-dev fakeroot dwarves
cd colloid
git apply ../colloid.patch
cd tpp/linux-6.3
cp /boot/config-$(uname -r) .config
make olddefconfig
scripts/config --disable SYSTEM_REVOCATION_KEYS
scripts/config --set-str CONFIG_LOCALVERSION "-colloid"
make -j32 bzImage
make -j32 modules
sudo make modules_install
sudo make install
cd ../memeater
make
cd ../tierinit
make
cd ../kswapdrst
make
#echo "Update FAR and LOCAL memory nodes in tierinit and memeater c files"
#echo "Don't forget to add the tierinit and kswapdrst modules and modprobe msr @reboot to the crontab"
#echo -n "For example "
#echo -n "@reboot insmod /mydata/colloid/tpp/tierinit/tierinit.ko"
#echo -n "@reboot insmod /mydata/colloid/tpp/kswapdrst/kswapdrst.ko"
#echo " or @reboot modprobe msr"
