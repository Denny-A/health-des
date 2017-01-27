import pandas as pd
import simpy
import scipy.stats.mstats
import numpy as np


def patient(env, patient_id, starting_state, states_pool, surgery_resource, logger):
    """Processing patients through the pool of states with queueing for states N* and I*"""
    state = starting_state
    while not states_pool[state].is_final:
        logger.append({'ID': patient_id, 'TIME': env.now, 'STATE': state,
                       'DIRECTION': 'IN', 'QUEUE_TIME': 0, 'QUEUE_LENGTH': 0})
        # print(env.now, logger[-1])
        surgery_state = state[0] in ['N', 'I']
        time_before_queue = env.now
        queue_length = 0
        if surgery_state:
            queue_length = len(surgery_resource.queue)
            request = surgery_resource.request()
            yield request
        time_in_queue = env.now - time_before_queue
        duration = int(states_pool[state].generate_duration())
        yield env.timeout(duration)
        if surgery_state:
            surgery_resource.release(request)
        logger.append({'ID': patient_id, 'TIME': env.now, 'STATE': state,
                       'DIRECTION': 'OUT', 'QUEUE_TIME': time_in_queue, 'QUEUE_LENGTH': queue_length})
        # print(env.now, logger[-1])
        state = states_pool[state].generate_next_state()
    logger.append({'ID': patient_id, 'TIME': env.now, 'STATE': state,
                   'DIRECTION': 'IN', 'QUEUE_TIME': 0, 'QUEUE_LENGTH': 0})


def background_surgery_process(env, surgery_resource, duration, logger):
    """Processing request to surgery room"""
    logger.append({'ID': -1, 'TIME': env.now, 'STATE': 'IXX', 'DIRECTION': 'IN',
                   'QUEUE_TIME': 0, 'QUEUE_LENGTH': 0})
    time_before_queue = env.now
    request = surgery_resource.request()
    yield request
    yield env.timeout(duration)
    surgery_resource.release(request)
    logger.append({'ID': -1, 'TIME': env.now, 'STATE': 'IXX', 'DIRECTION': 'OUT',
                   'QUEUE_TIME': env.now - time_before_queue, 'QUEUE_LENGTH': 0})


def generate_day_sequence(per_day_gen, time_in_day_gen, scale=1.0):
    """Generating sequence of requests within 24h"""
    seq = [0, 24*60]
    n = per_day_gen.rvs()
    for i in range(int(n * scale)):
        seq.append(int(time_in_day_gen.rvs()))
    seq.sort()
    return seq


def background_emitter(env, surgery_resource, logger,
                       surgery_bg_event_generator, surgery_bg_time_generator, surgery_bg_scale):
    """Generating daily activity in surgery room"""
    while True:
        seq = surgery_bg_event_generator.generate_day_sequence(scale=surgery_bg_scale)
        # print('Background surgery sequence for day: ', seq)
        for i in range(1, len(seq) - 1):
            yield env.timeout(seq[i] - seq[i - 1])
            env.process(background_surgery_process(env, surgery_resource, int(surgery_bg_time_generator.rvs()), logger))
        yield env.timeout(seq[-1] - seq[-2])


def target_emitter(env, target_event_generator, target_patient_generator, surgery_resource, logger):
    """Emitting patients with inter-patients time by span generator"""
    counter = 0
    while True:
        seq = target_event_generator.generate_day_sequence()
        # print('Planned sequence for day: ', seq)
        for i in range(1, len(seq) - 1):
            yield env.timeout(seq[i] - seq[i - 1])
            pat_state, pat_pool = target_patient_generator.get_patient()
            env.process(patient(env, counter, pat_state, pat_pool, surgery_resource, logger))
            counter += 1
            # print(str(env.now) + ': emitting new patient #' + str(counter) + ' at ' + str(seq[i]))
        yield env.timeout(seq[-1] - seq[-2])


def simulate_patients_flow(target_patient_generator, target_event_generator,
                           surgery_rooms_n, surgery_bg_event_generator, surgery_bg_time_generator, surgery_bg_scale,
                           simulation_time):
    """Run main simulation cycle"""
    log_track = []
    env = simpy.Environment()
    res = simpy.Resource(env, capacity=surgery_rooms_n)
    env.process(target_emitter(env, target_event_generator, target_patient_generator, res, log_track))
    env.process(background_emitter(env, res, log_track,
                                   surgery_bg_event_generator, surgery_bg_time_generator, surgery_bg_scale))
    env.run(until=simulation_time)
    return pd.DataFrame(log_track, columns=log_track[0].keys())


def get_queue_statistics(sim_res):
    """Basic stats for queue witing time"""
    mask = [st[0] in ['N', 'I'] for st in sim_res.STATE] & (sim_res.DIRECTION == 'OUT') & (sim_res.ID >= 0)
    mask_with_queue = mask & (sim_res.QUEUE_TIME > 0)
    qq = scipy.stats.mstats.mquantiles(sim_res[mask_with_queue].QUEUE_TIME)
    return {'PART': mask_with_queue.sum() / mask.sum(),
            'MIN': sim_res[mask_with_queue].QUEUE_TIME.min(),
            'MAX': sim_res[mask_with_queue].QUEUE_TIME.max(),
            'AVG': np.average(sim_res[mask_with_queue].QUEUE_TIME),
            'Q1': qq[0], 'Q2': qq[1], 'Q3': qq[2],
            'MAX_QUEUE_LENGTH': sim_res[mask_with_queue].QUEUE_LENGTH.max()}