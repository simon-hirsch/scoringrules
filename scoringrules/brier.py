import numpy as np
from numpy.typing import NDArray

EPSILON = 1e-7


def brier_score(forecasts: NDArray, observations: NDArray):
    r"""
    Compute the Brier Score (BS).

    The BS is formulated as

    $$BS(f, y) = (f - y)^2,$$

    where $f \in [0, 1]$ is the predicted probability of an event and $y \in \{0, 1\}$ the actual outcome.

    Parameters
    ----------
    forecasts : NDArray
        Forecasted probabilities between 0 and 1.
    observations: NDArray
        Observed outcome, either 0 or 1.

    Returns
    -------
    brier_score : NDArray
        The computed Brier Score.

    """
    forecasts, observations = np.array(forecasts), np.asarray(observations)

    if (forecasts < 0.0).any() or (forecasts > (1.0 + EPSILON)).any():
        raise ValueError("Forecasted probabilities must be within 0 and 1.")

    if not set(np.unique(observations[~np.isnan(observations)])) <= {0, 1}:
        raise ValueError("Observations must be 0, 1, or NaN")

    return (forecasts - observations) ** 2
