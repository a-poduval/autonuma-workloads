#!/bin/bash

# Hard-coded values for node 2 of our system
# Set this to the local memory address range specified in dmesg for the CPU node closest to CXL memory
BASE=0x0000000100000000
MAX=0x00000017ffffffff

# Convert size string to bytes
convert_to_bytes() {
  local size=$1
  local bytes
  local block_size=$((512 * 1024 * 1024))
  case "$size" in
    *[Kk])
      bytes=$(( ${size%[Kk]} * 1024 ))
      ;;
    *[Mm])
      bytes=$(( ${size%[Mm]} * 1024 * 1024 ))
      ;;
    *[Gg])
      bytes=$(( ${size%[Gg]} * 1024 * 1024 * 1024 ))
      echo $bytes
      return
      ;;
    *)
      echo $size
      return
      ;;
  esac
  # Round up to nearest multiple of 512MB
  echo $(( (bytes + block_size - 1) / block_size * block_size ))
}

# Convert decimal to hex
dec_to_hex() {
  printf "0x%016x" "$1"
}

if [[ "$1" == "reset" ]]; then
  echo "Resetting memory range..."
  chmem -e ${BASE}-${MAX}
elif [[ "$1" == "set" && -n "$2" ]]; then
  SIZE_BYTES=$(convert_to_bytes "$2")
  BASE_DEC=$((0x${BASE#0x}))
  MAX_DEC=$((0x${MAX#0x}))
  END_DEC=$((BASE_DEC + SIZE_BYTES - 1))

  if (( END_DEC > MAX_DEC )); then
    echo "Error: Size exceeds maximum memory range."
    exit 1
  fi

  END_HEX=$(dec_to_hex "$END_DEC")
  echo "Offlining full range..."
  chmem -d ${BASE}-${MAX}
  echo "Onlining range ${BASE}-${END_HEX}..."
  chmem -e ${BASE}-${END_HEX}
else
  echo "Usage:"
  echo "  $0 set <size>   # e.g., 20G, 512M, 1024K, or bytes"
  echo "  $0 reset        # bring full range back online"
  exit 1
fi
