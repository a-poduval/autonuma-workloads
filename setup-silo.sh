sudo apt update
sudo apt install libnuma-dev libpmem-dev libaio-dev libssl-dev
cd silo/silo
git apply ../../silo.patch
make dbtest -j20
