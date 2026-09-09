import numpy as np
from scipy.signal import correlate


def to_mono_float32(audio):
    """Convert an audio block to a one-dimensional float32 array."""
    data = np.asarray(audio)
    if data.ndim > 1:
        data = np.mean(data, axis=1)
    return data.astype(np.float32, copy=False).reshape(-1)


def normalized_similarity(data, template):
    """Return the best zero-mean normalized correlation in ``data``."""
    data = np.asarray(data, dtype=np.float32).reshape(-1)
    template = np.asarray(template, dtype=np.float32).reshape(-1)
    window_size = template.size

    if window_size == 0 or data.size < window_size:
        return 0.0

    centered_template = template - np.mean(template)
    template_energy = float(np.dot(centered_template, centered_template))
    if template_energy <= np.finfo(np.float32).eps:
        return 0.0

    # FFT correlation avoids the O(n*m) cost of np.correlate. Window energy
    # makes scores comparable even when the template appears inside a longer block.
    correlation = correlate(data, centered_template, mode="valid", method="fft")
    data64 = data.astype(np.float64, copy=False)
    cumulative = np.concatenate(([0.0], np.cumsum(data64)))
    cumulative_sq = np.concatenate(([0.0], np.cumsum(data64 * data64)))
    window_sum = cumulative[window_size:] - cumulative[:-window_size]
    window_sq_sum = cumulative_sq[window_size:] - cumulative_sq[:-window_size]
    window_energy = window_sq_sum - (window_sum * window_sum / window_size)
    denominator = np.sqrt(np.maximum(window_energy, 0.0) * template_energy)

    scores = np.divide(
        correlation,
        denominator,
        out=np.zeros_like(correlation, dtype=np.float64),
        where=denominator > np.finfo(np.float64).eps,
    )
    if scores.size == 0:
        return 0.0
    return float(np.clip(np.max(scores), 0.0, 1.0))
