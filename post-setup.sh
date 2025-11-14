#!/bin/bash

cd colloid/tpp/linux-6.3/tools/perf/
make -j$(nproc)
sudo mkdir -p /lib/linux-tools/$(uname -r)
sudo cp perf /lib/linux-tools/$(uname -r)
cd ../../../memeater
make
cd ../tierinit
make
cd ../kswapdrst
make
