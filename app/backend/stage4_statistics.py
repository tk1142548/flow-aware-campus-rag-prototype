"""Paired, reproducible statistics and evidence coverage observations."""
from __future__ import annotations

import itertools
import numpy as np


def retrieval_observation(hit_ids: list[str], relevant: set[str]) -> dict:
    if not relevant:
        raise ValueError('relevant evidence must not be empty')
    found = set(hit_ids)
    if len(found) != len(hit_ids):
        raise ValueError('duplicate retrieval hits')
    count = len(found & relevant)
    recall = count / len(relevant)
    return {'recall_at_k': recall, 'precision_at_k': count / len(found) if found else 0.0,
            'complete_evidence': count == len(relevant),
            'missing_evidence_ids': sorted(relevant - found),
            'retrieval_error': 'retrieval_miss' if count == 0 else ('partial_retrieval' if count < len(relevant) else 'none')}


def paired_analysis(left, right, item_ids, repetitions: int = 10000, seed: int = 0) -> dict:
    """Difference is right minus left; resample aligned pairs and whole items."""
    a, b = np.asarray(left, dtype=float), np.asarray(right, dtype=float)
    if a.ndim != 1 or a.shape != b.shape or not a.size or len(item_ids) != a.size:
        raise ValueError('paired inputs must be equally sized nonempty vectors')
    if not np.isfinite(a).all() or not np.isfinite(b).all() or repetitions < 100:
        raise ValueError('invalid metric or resampling count')
    delta = b-a; rng = np.random.default_rng(seed)
    sample = delta[rng.integers(0, delta.size, (repetitions, delta.size))].mean(axis=1)
    groups = sorted(set(item_ids))
    sums = np.asarray([sum(delta[i] for i, item in enumerate(item_ids) if item == group) for group in groups])
    counts = np.asarray([item_ids.count(group) for group in groups])
    selections = rng.integers(0, len(groups), (repetitions, len(groups)))
    cluster = sums[selections].sum(axis=1)/counts[selections].sum(axis=1)
    signs = rng.choice([-1, 1], (repetitions, len(delta)))
    null = (signs * delta).mean(axis=1)
    observed = float(delta.mean())
    p = (1 + np.count_nonzero(np.abs(null) >= abs(observed)-1e-12))/(repetitions+1)
    if len(groups) <= 16:
        cluster_signs = np.asarray(list(itertools.product((-1, 1), repeat=len(groups))))
        cluster_null = (cluster_signs * sums).sum(axis=1) / a.size
        cluster_p = float(np.mean(np.abs(cluster_null) >= abs(observed)-1e-12))
    else:
        cluster_signs = rng.choice([-1, 1], (repetitions, len(groups)))
        cluster_null = (cluster_signs * sums).sum(axis=1) / a.size
        cluster_p = float((1 + np.count_nonzero(np.abs(cluster_null) >= abs(observed)-1e-12))/(repetitions+1))
    return {'pair_count': int(a.size), 'item_cluster_count': len(groups), 'mean_difference': observed,
            'wins': int((delta>1e-12).sum()), 'losses': int((delta < -1e-12).sum()), 'ties': int((np.abs(delta)<=1e-12).sum()),
            'sample_bootstrap_ci95': np.quantile(sample, [0.025,0.975]).tolist(),
            'item_cluster_bootstrap_ci95': np.quantile(cluster, [0.025,0.975]).tolist(),
            'paired_sign_flip_p': float(p), 'item_cluster_sign_flip_p': cluster_p,
            'repetitions': repetitions, 'seed': seed}


def holm_adjust(p_values: list[float]) -> list[float]:
    order = sorted(range(len(p_values)), key=lambda i: p_values[i])
    result = [0.0]*len(order); previous = 0.0
    for rank, index in enumerate(order):
        previous = max(previous, min(1.0, (len(order)-rank)*p_values[index]))
        result[index] = previous
    return result
