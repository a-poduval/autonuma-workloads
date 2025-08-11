#!/bin/bash

# Function to display usage instructions
usage() {
    echo "Usage: $0 benchmark_suite workload [-f config_file.yaml]"
    echo "  -b                          Benchmark suite"
    echo "  -w                          Workload"
    echo "  -o                          Output directory"
    echo "  -f config_file.yaml         (Optional) YAML configuration file for workload parameters"
    echo "  -i instrumentation          Instrumentation tool: 'pebs', 'damon' (default: none)"
    echo "  -s Damon Sampling Rate      Default: 5000 (microseconds) or 5ms"
    echo "  -a Damon Aggregate Rate     Default: 100ms"
    echo "  -n Min # of Damon regions  (Optional)"
    echo "  -m Max # of Damon regions  (Optional)"
    echo "  -x Damon auto access_bp    (Optional)"
    echo "  -y Damon auto aggrs        (Optional)"
    exit 1
}

start_damo() {
    local output_file="$1"
    local proc_pid="$2"
    local sampling_period="$3"
    local agg_period="$4"
    local min_num_region="$5"
    local max_num_region="$6"

    echo "Min ${min_num_region}"
    echo "Max ${max_num_region}"

    if [ -z "$min_num_region" ]; then
        sudo env "PATH=$PATH" damo record -s ${sampling_period} -a ${agg_period} -o $output_file $proc_pid &
    else
        sudo env "PATH=$PATH" damo record --monitoring_nr_regions_range ${min_num_region} ${max_num_region} -s ${sampling_period} -a ${agg_period} -o $output_file $proc_pid &
    fi
}

start_damo_autotune() {
    local output_file="$1"
    local proc_pid="$2"
    local sampling_period="$3"
    local agg_period="$4"
    local min_num_region="$5"
    local max_num_region="$6"

    echo "Min ${min_num_region}"
    echo "Max ${max_num_region}"

    if [ -z "$DAMON_AUTO_AGGRS" ]; then
        $DAMON_AUTO_ACCESS_BP=4
        $DAMON_AUTO_AGGRS=100
    fi

    echo "access_bp ${DAMON_AUTO_ACCESS_BP}"
    echo "AGGRS ${DAMON_AUTO_AGGRS}"

    if [ -z "$min_num_region" ]; then
        sudo env "PATH=$PATH" damo record --monitoring_intervals_goal ${DAMON_AUTO_ACCESS_BP} ${DAMON_AUTO_AGGRS} 2000 8000000 -s ${sampling_period} -a ${agg_period} -o $output_file $proc_pid &
    else
        sudo env "PATH=$PATH" damo record --monitoring_intervals_goal ${DAMON_AUTO_ACCESS_BP} ${DAMON_AUTO_AGGRS} 2000 8000000 --monitoring_nr_regions_range ${min_num_region} ${max_num_region} -s ${sampling_period} -a ${agg_period} -o $output_file $proc_pid &
    fi
}

stop_damo() {
    local output_file="$1"
    local text_output_file="${output_file%.dat}.damon.txt"
    local text_region_output_file="${output_file%.dat}.region.damon.txt"
    sudo env "PATH=$PATH" damo stop #Looks Like damo ends on its own

    #Without sleep, heatmap command sometimes fails.
    sleep 10
    sudo env "PATH=$PATH" damo report heatmap --output raw --input $output_file --resol 1000 1000 --draw_range all \
        > $text_output_file
    sleep 10
    sudo env "PATH=$PATH" damo report access --raw_form --raw_number --input $output_file > $text_region_output_file
}

start_pebs() {
    echo "Starting PEBS"
    local output_file="$1"
    local sampling_period=$2 #Record sample after N events
    local epoch_size=$((1000 * 1000)) # How often to aggregate samples

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

sys_init() {
    # Disable SMT # TODO: No longer disabling as Hemem needs it, separate out into a separate config
    #echo off | sudo tee /sys/devices/system/cpu/smt/control
    # Disable randomized va space
    echo 0 | sudo tee /proc/sys/kernel/randomize_va_space
    # Drop page cache
    sync
    echo 3 | sudo tee /proc/sys/vm/drop_caches
}

sys_cleanup(){
    # Re-enable randomized va space
    echo 2 | sudo tee /proc/sys/kernel/randomize_va_space
    # Re-enable SMT # TODO: No longer disabling as Hemem needs it, separate out into a separate config
    #echo on | sudo tee /sys/devices/system/cpu/smt/control
}

extract_policy() {
    local path="$1"
    case $(basename "$path") in
        libhemem.so) echo "libhemem" ;;
        libhemem-lru.so) echo "libhemem-lru" ;;
        libhemem-baseline.so) echo "libhemem-baseline" ;;
        *) echo "unknown" ;;
    esac
}

# DAMON Auto tune params
DAMON_AUTO_ACCESS_BP=""
DAMON_AUTO_AGGRS=""

main() {

    . ./scripts/parse_args.sh $@
    print_cmd_args

    # Ensure at least one argument (workload) is provided
    if [ "$#" -lt 1 ]; then
        usage
    fi

    #Change if needed
    CUR_PATH="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
    DAMO_PATH=$CUR_PATH/scripts/damo
    PEBS_PATH=$CUR_PATH/scripts/PEBS_page_tracking
    PEBS_PIPE="/tmp/pebs_pipe"

    export PATH=$DAMO_PATH:$PATH

    WORKLOAD_SCRIPT_PATH=$CUR_PATH/scripts/workloads

    SUITE=$_arg_suite
    WORKLOAD=$_arg_workload
    CONFIG_FILE=$_arg_config_file
    INSTRUMENT=$_arg_instrument
    OUTPUT_DIR=$_arg_output_dir

    SAMPLING_RATE=$_arg_sampling_rate
    AGG_RATE=$_arg_aggregate_rate

    MIN_NUM_DAMO=$_arg_min_damon
    MAX_NUM_DAMO=$_arg_max_damon

    DAMON_AUTO_ACCESS_BP=$_arg_auto_access_bp
    DAMON_AUTO_AGGRS=$_arg_auto_aggrs


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

    hemem_policy=$(extract_policy "$HEMEMPOL")

    # Source the workload script.
    source "${SUITE_SCRIPT}"

    # Expect the workload script to define run, run_strace, build, and config functions
    if ! declare -f "run_${SUITE}" > /dev/null; then
        echo "ERROR: Function run_${SUITE} not defined in ${SUITE_SCRIPT}"
        exit 1
    fi

    if ! declare -f "run_strace_${SUITE}" > /dev/null; then
        echo "ERROR: Function run_strace_${SUITE} not defined in ${SUITE_SCRIPT}"
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
            sys_init

            echo "Running with PEBS."
            start_pebs ${OUTPUT_DIR}/${SUITE}_${WORKLOAD}_${SAMPLING_RATE}_samples.dat $SAMPLING_RATE
            # Run command should set $workload_pid variable.
            run_${SUITE} ${WORKLOAD} #"${CONFIG_FILE}"
            #run_strace_${SUITE} ${WORKLOAD} #"${CONFIG_FILE}"
            tail --pid=$workload_pid -f /dev/null
            stop_pebs

            sys_cleanup
            ;;

        damon)
            sys_init

            echo "Running with DAMON."
            if [ -z "$MAX_NUM_DAMO" ] && [ -z "$MIN_NUM_DAMO" ]; then

                if [ -z "$DAMON_AUTO_AGGRS" ]; then
                    DAMO_FILE=${OUTPUT_DIR}/${SUITE}_${WORKLOAD}_${SAMPLING_RATE}_${AGG_RATE}_damon.dat
                else
                    DAMO_FILE=${OUTPUT_DIR}/${SUITE}_${WORKLOAD}_${SAMPLING_RATE}_${AGG_RATE}_${DAMON_AUTO_ACCESS_BP}bp_${DAMON_AUTO_AGGRS}agg_damon.dat
                fi

                # Run command should set $workload_pid variable.
                run_${SUITE} ${WORKLOAD} #"${CONFIG_FILE}"
                #run_strace_${SUITE} ${WORKLOAD} #"${CONFIG_FILE}"
                start_damo_autotune ${DAMO_FILE} $workload_pid $SAMPLING_RATE $AGG_RATE
            else
                if [ -z "$MAX_NUM_DAMO" ]; then
                    MAX_NUM_DAMO=$MIN_NUM_DAMO
                elif [ -z "$MIN_NUM_DAMO" ]; then
                    MIN_NUM_DAMO=$MAX_NUM_DAMO
                fi

                if [ -z "$DAMON_AUTO_AGGRS" ]; then
                    DAMO_FILE=${OUTPUT_DIR}/${SUITE}_${WORKLOAD}_${SAMPLING_RATE}_${AGG_RATE}_${MIN_NUM_DAMO}r_${MAX_NUM_DAMO}r_damon.dat
                else
                    DAMO_FILE=${OUTPUT_DIR}/${SUITE}_${WORKLOAD}_${SAMPLING_RATE}_${AGG_RATE}_${MIN_NUM_DAMO}r_${MAX_NUM_DAMO}r_${DAMON_AUTO_ACCESS_BP}bp_${DAMON_AUTO_AGGRS}agg_damon.dat
                fi
                # Run command should set $workload_pid variable. # TODO: Support case when not using Hemem again
                /usr/bin/time -v -o ${OUTPUT_DIR}/${WORKLOAD}_${policy}_time.txt \
                run_${SUITE} ${WORKLOAD} #"${CONFIG_FILE}"
                #run_strace_${SUITE} ${WORKLOAD} #"${CONFIG_FILE}"
                start_damo_autotune ${DAMO_FILE} $workload_pid $SAMPLING_RATE $AGG_RATE $MIN_NUM_DAMO $MAX_NUM_DAMO
            fi

            tail --pid=$workload_pid -f /dev/null
            stop_damo ${DAMO_FILE}

            sys_cleanup
            ;;
        "")
            sys_init

            run_${SUITE} ${WORKLOAD} #"${CONFIG_FILE}"
            #run_strace_${SUITE} ${WORKLOAD} #"${CONFIG_FILE}"
            tail --pid=$workload_pid -f /dev/null

            sys_cleanup
            ;;
        *)
            echo "ERROR: Unknown instrumentation option '$INSTRUMENT'. Valid options are 'pebs' or 'damon'."
            exit 1
            ;;
    esac

    #$CUR_PATH/largest_vma.sh -i memory_regions.csv -o $CUR_PATH/results/results_${SUITE}/${SUITE}_${WORKLOAD}_vma.csv
    #cp memory_regions.csv $CUR_PATH/results/results_${SUITE}/${SUITE}_${WORKLOAD}_smaps_ts.csv
    #python coalesce_smap.py memory_regions.csv
    #mv smap_deduplicated.csv $CUR_PATH/results/results_${SUITE}/${SUITE}_${WORKLOAD}_vma.csv
    #mv ${SUITE}_${WORKLOAD}_strace.log $CUR_PATH/results/results_${SUITE}/

    clean_${SUITE}
}

main $@
