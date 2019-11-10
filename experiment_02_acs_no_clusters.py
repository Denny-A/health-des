import datetime
import logging.config
import os
import numpy as np
import dept_des
import state_info

# basic paths
ps = os.path.sep
basic_path = "data" + ps + "acs_no_clusters" + ps
add_path = "data" + ps + "acs" + ps
surg_path = "data" + ps + "surgeries" + ps
dt_suffix = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")

# logging configuration
logging.config.fileConfig("logging.ini")
m_log = logging.getLogger("exp_2")
m_log.info("Starting experiment")

# reading paths clusters
n_clusters = 1
p_clusters = np.full(1, 1.0, dtype=float)
# reading states for clusters
states_pools = [state_info.load_state_pool(basic_path + "Transition_matrix.csv", basic_path)]
# creating ACS patients generator
acs_patients_gen = state_info.PatientGenerator(p_clusters, states_pools)
acs_event_gen = state_info.PatientsDayFlowGenerator(
    add_path + "Number_of_patients.txt", add_path + "Entrance_time.txt"
)
# creating background patients generator
background_surgery_gen = state_info.PatientsDayFlowGenerator(
    surg_path + "total_surgeries_per_day.txt", surg_path + "total_surgeries_time_in_day.txt"
)
background_surgery_duration_gen = state_info.RvFromData(
    np.loadtxt(surg_path + "total_surgeries_duration.txt").flatten()
)


# run series
def single_experiment_run(target_scale, bg_scale, n_surgery, queue, run_id):
    simulation_time = 2 * 30 * 24 * 60
    sim_res = dept_des.simulate_patients_flow(
        acs_patients_gen,
        acs_event_gen,
        n_surgery,
        background_surgery_gen,
        background_surgery_duration_gen,
        bg_scale,
        target_scale,
        simulation_time,
        use_queueing=queue,
    )
    sim_res.to_csv("logs" + ps + "sim-res-" + dt_suffix + ".csv")
    sim_stats = dept_des.get_queue_statistics(sim_res)
    sim_stats["BG_SCALE"] = bg_scale
    sim_stats["TARGET_SCALE"] = target_scale
    sim_stats["N_SURG"] = n_surgery
    m_log.info("#{}: {}".format(run_id, sim_stats))
    return sim_stats


run_res = single_experiment_run(1.0, 0.1, 2, False, 0)
