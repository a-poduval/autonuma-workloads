#!/bin/bash

# Function to display usage instructions
usage() {
    echo "Usage: $0 workload [-f config_file.yaml]"
    echo "  workload           Name of the workload to run (e.g., gapbs-pr)"
    echo "  -f config_file.yaml    (Optional) YAML configuration file for workload parameters"
    exit 1
}

start_pebs() {
    echo "Starting PEBS"
    local output_file="$1"
    local sampling_period=50
    local epoch_size=$((500 * 1000))

    # Check if the pipe exists, delete it if it does
    if [ -p "$PEBS_PIPE" ]; then
        rm "$PEBS_PIPE"
    fi

    # Create a new named pipe (FIFO)
    mkfifo "$PEBS_PIPE"

    sudo "${PEBS_PATH}/bin/pebs_periodic_reads.x" "$sampling_period" "$epoch_size" "$output_file" "$PEBS_PIPE" &

    echo $!
}

stop_pebs() {
    echo "Stopping PEBS"
    sudo echo "q" > $PEBS_PIPE
    sudo rm -f $PEBS_PIPE
}

main() {
    # Ensure at least one argument (workload) is provided
    if [ "$#" -lt 1 ]; then
        usage
    fi

    CUR_PATH="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
    PEBS_PATH=$CUR_PATH/scripts/PEBS_page_tracking
    PEBS_PIPE="/tmp/pebs_pipe"
    WORKLOAD_SCRIPT_PATH=$CUR_PATH/scripts/workloads

    WORKLOAD=$1
    shift
    # Process additional command-line options using getopts
    while getopts "f:" opt; do
        case ${opt} in
            f)
                CONFIG_FILE="$OPTARG"
                ;;
            *)
                usage
                ;;
        esac
    done

    echo "Workload: ${WORKLOAD}"
    [ -n "${CONFIG_FILE}" ] && echo "Using configuration file: ${CONFIG_FILE}"

    # Construct the expected workload script path.
    WORKLOAD_SCRIPT="${WORKLOAD_SCRIPT_PATH}/${WORKLOAD}.sh"
    if [ ! -f "${WORKLOAD_SCRIPT}" ]; then
        echo "ERROR: Workload script ${WORKLOAD_SCRIPT} not found."
        exit 1
    fi

    # Source the workload script.
    source "${WORKLOAD_SCRIPT}"

    # Expect the workload script to define run, build, and config functions 
    if ! declare -f "run_${WORKLOAD}" > /dev/null; then
        echo "ERROR: Function run_${WORKLOAD} not defined in ${WORKLOAD_SCRIPT}"
        exit 1
    fi

    if ! declare -f "build_${WORKLOAD}" > /dev/null; then
        echo "ERROR: Function build_${WORKLOAD} not defined in ${WORKLOAD_SCRIPT}"
        exit 1
    fi

    if ! declare -f "config_${WORKLOAD}" > /dev/null; then
        echo "ERROR: Function config_${WORKLOAD} not defined in ${WORKLOAD_SCRIPT}"
        exit 1
    fi

    
    #Set config
    config_${WORKLOAD} ${CONFIG_FILE}
    
    #Build workload
    build_${WORKLOAD}
    
    # Call the workload function, passing the config file (if any).
    start_pebs ${WORKLOAD}_samples.dat
    run_${WORKLOAD} #"${CONFIG_FILE}"
    stop_pebs
}

main $@
