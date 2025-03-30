#!/bin/bash

#Change if needed
DAMO_PATH='/mydata/damo'
export PATH=$DAMO_PATH:$PATH

# Function to display usage instructions
usage() {
    echo "Usage: $0 workload [-f config_file.yaml]"
    echo "  workload                    Name of the workload to run (e.g., pr)"
    echo "  -b                          Benchmark suite"
    echo "  -w                          Workload"
    echo "  -o                          Output directory"
    echo "  -f config_file.yaml         (Optional) YAML configuration file for workload parameters"
    echo "  -i instrumentation          Instrumentation tool: 'pebs', 'damon' (default: none)"
    echo "  -s Damon Sampling Rate      Microseconds (default: 5000)"
    exit 1
}

start_damo() {
    local output_file="$1"
    local proc_pid="$2"
    local sampling_period="$3"

    sudo env "PATH=$PATH" damo record -s ${sampling_period} -o $output_file $proc_pid &
}

stop_damo() {
    local output_file="$1"
    local text_output_file="${output_file%.dat}.damon.txt"
    #sudo env "PATH=$PATH" damo stop #Looks Like damo ends on its own

    #Without sleep, heatmap command sometimes fails.
    sleep 1
    sudo env "PATH=$PATH" damo report heatmap --output raw --input $output_file > $text_output_file 
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
    SAMPLING_RATE=5000

    # Process additional command-line options using getopts
    while getopts "f:b:w:o:i:s:" opt; do
        case ${opt} in
            f)
                CONFIG_FILE="$OPTARG"
                ;;
            b)
                SUITE="$OPTARG"
                ;;
            w)
                WORKLOAD="$OPTARG"
                ;;
            o)
                OUTPUT_DIR="$OPTARG"
                ;;
            i)
                INSTRUMENT="$OPTARG"
                ;;
            s)
                SAMPLING_RATE="$OPTARG"
                ;;
            *)
                usage
                ;;
        esac
    done
    
    #Check that suite and workload have been provided 
    if [ -z "$SUITE" ] || [ -z "$WORKLOAD" ] || [ -z "$OUTPUT_DIR" ]; then
        usage
    fi

    echo "Workload: ${WORKLOAD}"
    [ -n "${CONFIG_FILE}" ] && echo "Using configuration file: ${CONFIG_FILE}"

    # Construct the expected workload script path.
    SUITE_SCRIPT="${WORKLOAD_SCRIPT_PATH}/${SUITE}.sh"
    if [ ! -f "${SUITE_SCRIPT}" ]; then
        echo "ERROR: Workload script ${SUITE_SCRIPT} not found."
        exit 1
    fi

    # Create the output directory if it doesn't exist
    if [ ! -d "$OUTPUT_DIR" ]; then
        echo "Output directory does not exist. Creating: $OUTPUT_DIR"
        mkdir -p "$OUTPUT_DIR"
        if [ $? -ne 0 ]; then
            echo "ERROR: Failed to create output directory."
            exit 1
        fi
    fi

    # Source the workload script.
    source "${SUITE_SCRIPT}"

    # Expect the workload script to define run, build, and config functions 
    if ! declare -f "run_${SUITE}" > /dev/null; then
        echo "ERROR: Function run_${SUITE} not defined in ${SUITE_SCRIPT}"
        exit 1
    fi

    if ! declare -f "build_${SUITE}" > /dev/null; then
        echo "ERROR: Function build_${SUITE} not defined in ${SUITE_SCRIPT}"
        exit 1
    fi

    if ! declare -f "config_${SUITE}" > /dev/null; then
        echo "ERROR: Function config_${SUITE} not defined in ${SUITE_SCRIPT}"
        exit 1
    fi

    if ! declare -f "clean_${SUITE}" > /dev/null; then
        echo "ERROR: Function clean_${SUITE} not defined in ${SUITE_SCRIPT}"
        exit 1
    fi
    
    # Set config
    config_${SUITE} ${CONFIG_FILE} ${WORKLOAD}
    
    # Build workload
    build_${SUITE} ${WORKLOAD}
    
    # Call the workload function, passing the config file (if any).
    case "$INSTRUMENT" in
        # PEBS starts before workload, damo starts after.
        pebs)
            echo 0 | sudo tee /proc/sys/kernel/randomize_va_space

            echo "Running with PEBS."
            start_pebs ${OUTPUT_DIR}/${SUITE}_${WORKLOAD}_samples.dat
            # Run command should set $workload_pid variable.
            run_${SUITE} ${WORKLOAD} #"${CONFIG_FILE}"
            tail --pid=$workload_pid -f /dev/null
            stop_pebs

            echo 2 | sudo tee /proc/sys/kernel/randomize_va_space
            ;;

        damon)
            echo 0 | sudo tee /proc/sys/kernel/randomize_va_space

            echo "Running with DAMON."
            # Run command should set $workload_pid variable.
            run_${SUITE} ${WORKLOAD} #"${CONFIG_FILE}"
            start_damo ${OUTPUT_DIR}/${SUITE}_${WORKLOAD}_${SAMPLING_RATE}_damon.dat $workload_pid $SAMPLING_RATE
            tail --pid=$workload_pid -f /dev/null
            stop_damo ${OUTPUT_DIR}/${SUITE}_${WORKLOAD}_damon.dat

            echo 2 | sudo tee /proc/sys/kernel/randomize_va_space
            ;;
        "")
            echo 0 | sudo tee /proc/sys/kernel/randomize_va_space

            run_${SUITE} ${WORKLOAD} #"${CONFIG_FILE}"
            tail --pid=$workload_pid -f /dev/null

            echo 2 | sudo tee /proc/sys/kernel/randomize_va_space
            ;;
        *)
            echo "ERROR: Unknown instrumentation option '$INSTRUMENT'. Valid options are 'pebs' or 'damon'."
            exit 1
            ;;
        esac

    clean_${SUITE}
}

main $@
