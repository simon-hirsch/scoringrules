import typing as tp

from scoringrules.backend import backends
from scoringrules.core import crps

if tp.TYPE_CHECKING:
    from scoringrules.core.typing import Array, ArrayLike, Backend


def crps_ensemble(
    observations: "ArrayLike",
    forecasts: "Array",
    /,
    axis: int = -1,
    *,
    sorted_ensemble: bool = False,
    estimator: str = "pwm",
    backend: "Backend" = None,
) -> "Array":
    r"""Estimate the Continuous Ranked Probability Score (CRPS) for a finite ensemble.

    Parameters
    ----------
    observations: ArrayLike
        The observed values.
    forecasts: ArrayLike
        The predicted forecast ensemble, where the ensemble dimension is by default
        represented by the last axis.
    axis: int
        The axis corresponding to the ensemble. Default is the last axis.
    sorted_ensemble: bool
        Boolean indicating whether the ensemble members are already in ascending order.
        Default is False.
    estimator: str
        Indicates the CRPS estimator to be used.
    backend: str
        The name of the backend used for computations. Defaults to 'numba' if available, else 'numpy'.

    Returns
    -------
    crps: ArrayLike
        The CRPS between the forecast ensemble and obs.

    Examples
    --------
    >>> from scoringrules import crps
    >>> crps.ensemble(pred, obs)
    """
    B = backends.active if backend is None else backends[backend]
    observations, forecasts = map(B.asarray, (observations, forecasts))

    if estimator not in crps.estimator_gufuncs:
        raise ValueError(
            f"{estimator} is not a valid estimator. "
            f"Must be one of {crps.estimator_gufuncs.keys()}"
        )

    if axis != -1:
        forecasts = B.moveaxis(forecasts, axis, -1)

    if not sorted_ensemble and estimator not in ["nrg", "akr", "akr_circperm", "fair"]:
        forecasts = B.sort(forecasts, axis=-1)

    if backend == "numba":
        return crps.estimator_gufuncs[estimator](observations, forecasts)

    return crps.ensemble(observations, forecasts, estimator, backend=backend)


def twcrps_ensemble(
    observations: "ArrayLike",
    forecasts: "Array",
    v_func: tp.Callable[["ArrayLike"], "ArrayLike"],
    /,
    axis: int = -1,
    *,
    estimator: str = "pwm",
    sorted_ensemble: bool = False,
    backend: "Backend" = None,
) -> "Array":
    r"""Estimate the Threshold-Weighted Continuous Ranked Probability Score (twCRPS) for a finite ensemble.

    Computation is performed using the ensemble representation of the twCRPS in
    [Allen et al. (2022)](https://arxiv.org/abs/2202.12732):

    $$ \mathrm{twCRPS}(F_{ens}, y) = \frac{1}{M} \sum_{m = 1}^{M} |v(x_{m}) - v(y)| - \frac{1}{2 M^{2}} \sum_{m = 1}^{M} \sum_{j = 1}^{M} |v(x_{m}) - v(x_{j})|,$$

    where $F_{ens}(x) = \sum_{m=1}^{M} 1 \{ x_{m} \leq x \}/M$ is the empirical
    distribution function associated with an ensemble forecast $x_{1}, \dots, x_{M}$ with
    $M$ members, and $v$ is the chaining function used to target particular outcomes.

    Parameters
    ----------
    observations: ArrayLike
        The observed values.
    forecasts: ArrayLike
        The predicted forecast ensemble, where the ensemble dimension is by default
        represented by the last axis.
    v_func: tp.Callable
        Chaining function used to emphasise particular outcomes. For example, a function that
        only considers values above a certain threshold $t$ by projecting forecasts and observations
        to $[t, \inf)$.
    axis: int
        The axis corresponding to the ensemble. Default is the last axis.
    backend: str
        The name of the backend used for computations. Defaults to 'numba' if available, else 'numpy'.

    Returns
    -------
    twcrps: ArrayLike
        The twCRPS between the forecast ensemble and obs for the chosen chaining function.

    Examples
    --------
    >>> from scoringrules import crps
    >>> twcrps.ensemble(pred, obs)
    """
    observations, forecasts = map(v_func, (observations, forecasts))
    return crps_ensemble(
        observations,
        forecasts,
        axis=axis,
        sorted_ensemble=sorted_ensemble,
        estimator=estimator,
        backend=backend,
    )


def crps_quantile(
    observations: "ArrayLike",
    forecasts: "Array",
    alpha: "Array",
    /,
    axis: int = -1,
    *,
    backend: "Backend" = None,
) -> "Array":
    r"""Approximate the CRPS from quantile predictions via the Pinball Loss.

    It is based on the notation in [Berrisch & Ziel, 2022](https://arxiv.org/pdf/2102.00968)

    The CRPS can be approximated as the mean pinball loss for all
    quantile forecasts $F_q$ with level $q \in Q$:

    $$\text{quantileCRPS} = \frac{2}{|Q|} \sum_{q \in Q} PB_q$$

    where the pinball loss is defined as:

    $$\text{PB}_q = \begin{cases}
        q(y - F_q) &\text{if} & y \geq F_q  \\
        (1-q)(F_q - y) &\text{else.} &  \\
    \end{cases} $$

    Parameters
    ----------
    observations: ArrayLike
        The observed values.
    forecasts: Array
        The predicted forecast ensemble, where the ensemble dimension is by default
        represented by the last axis.
    alpha: Array
        The percentile levels. We expect the quantile array to match the axis (see below) of the forecast array.
    axis: int
        The axis corresponding to the ensemble. Default is the last axis.
    backend: str
        The name of the backend used for computations. Defaults to 'numba' if available, else 'numpy'.

    Returns
    -------
    qcrps: Array
        An array of CRPS scores for each forecast, which should be averaged to get meaningful values.

    Examples
    --------
    >>> import scoringrules as sr
    >>> sr.crps_quantile(obs, fct, alpha)
    """
    B = backends.active if backend is None else backends[backend]
    observations, forecasts, alpha = map(B.asarray, (observations, forecasts, alpha))

    if axis != -1:
        forecasts = B.moveaxis(forecasts, axis, -1)

    if not forecasts.shape[-1] == alpha.shape[-1]:
        raise ValueError("Expected matching length of forecasts and alpha values.")

    if B.name == "numba":
        return crps.quantile_pinball_gufunc(observations, forecasts, alpha)

    return crps.quantile_pinball(observations, forecasts, alpha, backend=backend)


def owcrps_ensemble(
    observations: "ArrayLike",
    forecasts: "Array",
    w_func: tp.Callable[["ArrayLike"], "ArrayLike"],
    /,
    axis: int = -1,
    *,
    estimator: tp.Literal["nrg"] = "nrg",
    backend: "Backend" = None,
) -> "Array":
    r"""Estimate the Outcome-Weighted Continuous Ranked Probability Score (owCRPS) for a finite ensemble.

    Computation is performed using the ensemble representation of the owCRPS in
    [Allen et al. (2022)](https://arxiv.org/abs/2202.12732):

    $$ \mathrm{owCRPS}(F_{ens}, y) = \frac{1}{M \bar{w}} \sum_{m = 1}^{M} |x_{m} - y|w(x_{m})w(y) - \frac{1}{2 M^{2} \bar{w}^{2}} \sum_{m = 1}^{M} \sum_{j = 1}^{M} |x_{m} - x_{j}|w(x_{m})w(x_{j})w(y),$$

    where $F_{ens}(x) = \sum_{m=1}^{M} 1\{ x_{m} \leq x \}/M$ is the empirical
    distribution function associated with an ensemble forecast $x_{1}, \dots, x_{M}$ with
    $M$ members, $w$ is the chosen weight function, and $\bar{w} = \sum_{m=1}^{M}w(x_{m})/M$.

    Parameters
    ----------
    observations: ArrayLike
        The observed values.
    forecasts: ArrayLike
        The predicted forecast ensemble, where the ensemble dimension is by default
        represented by the last axis.
    w_func: tp.Callable
        Weight function used to emphasise particular outcomes.
    axis: int
        The axis corresponding to the ensemble. Default is the last axis.
    backend: str
        The name of the backend used for computations. Defaults to 'numba' if available, else 'numpy'.

    Returns
    -------
    owcrps: ArrayLike
        The owCRPS between the forecast ensemble and obs for the chosen weight function.

    Examples
    --------
    >>> from scoringrules import crps
    >>> owcrps.ensemble(pred, obs)
    """
    B = backends.active if backend is None else backends[backend]

    if estimator != "nrg":
        raise ValueError(
            "Only the energy form of the estimator is available "
            "for the outcome-weighted CRPS."
        )
    if axis != -1:
        forecasts = B.moveaxis(forecasts, axis, -1)

    obs_weights, fct_weights = map(w_func, (observations, forecasts))

    if backend == "numba":
        return crps.estimator_gufuncs["ow" + estimator](
            observations, forecasts, obs_weights, fct_weights
        )

    observations, forecasts, obs_weights, fct_weights = map(
        B.asarray, (observations, forecasts, obs_weights, fct_weights)
    )
    return crps.ow_ensemble(
        observations, forecasts, obs_weights, fct_weights, backend=backend
    )


def vrcrps_ensemble(
    observations: "ArrayLike",
    forecasts: "Array",
    w_func: tp.Callable[["ArrayLike"], "ArrayLike"],
    /,
    axis: int = -1,
    *,
    estimator: tp.Literal["nrg"] = "nrg",
    backend: "Backend" = None,
) -> "Array":
    r"""Estimate the Vertically Re-scaled Continuous Ranked Probability Score (vrCRPS) for a finite ensemble.

    Computation is performed using the ensemble representation of the vrCRPS in
    [Allen et al. (2022)](https://arxiv.org/abs/2202.12732):

    \[
    \begin{split}
        \mathrm{vrCRPS}(F_{ens}, y) = & \frac{1}{M} \sum_{m = 1}^{M} |x_{m} - y|w(x_{m})w(y) - \frac{1}{2 M^{2}} \sum_{m = 1}^{M} \sum_{j = 1}^{M} |x_{m} - x_{j}|w(x_{m})w(x_{j}) \\
            & + \left( \frac{1}{M} \sum_{m = 1}^{M} |x_{m}| w(x_{m}) - |y| w(y) \right) \left( \frac{1}{M} \sum_{m = 1}^{M} w(x_{m}) - w(y) \right),
    \end{split}
    \]

    where $F_{ens}(x) = \sum_{m=1}^{M} 1 \{ x_{m} \leq x \}/M$ is the empirical
    distribution function associated with an ensemble forecast $x_{1}, \dots, x_{M}$ with
    $M$ members, $w$ is the chosen weight function, and $\bar{w} = \sum_{m=1}^{M}w(x_{m})/M$.

    Parameters
    ----------
    observations: ArrayLike
        The observed values.
    forecasts: ArrayLike
        The predicted forecast ensemble, where the ensemble dimension is by default
        represented by the last axis.
    w_func: tp.Callable
        Weight function used to emphasise particular outcomes.
    axis: int
        The axis corresponding to the ensemble. Default is the last axis.
    backend: str
        The name of the backend used for computations. Defaults to 'numba' if available, else 'numpy'.

    Returns
    -------
    vrcrps: ArrayLike
        The vrCRPS between the forecast ensemble and obs for the chosen weight function.

    Examples
    --------
    >>> from scoringrules import crps
    >>> vrcrps.ensemble(pred, obs)
    """
    B = backends.active if backend is None else backends[backend]

    if estimator != "nrg":
        raise ValueError(
            "Only the energy form of the estimator is available "
            "for the outcome-weighted CRPS."
        )
    if axis != -1:
        forecasts = B.moveaxis(forecasts, axis, -1)

    obs_weights, fct_weights = map(w_func, (observations, forecasts))

    if backend == "numba":
        return crps.estimator_gufuncs["vr" + estimator](
            observations, forecasts, obs_weights, fct_weights
        )

    observations, forecasts, obs_weights, fct_weights = map(
        B.asarray, (observations, forecasts, obs_weights, fct_weights)
    )
    return crps.vr_ensemble(
        observations, forecasts, obs_weights, fct_weights, backend=backend
    )


def crps_exponential(
    observation: "ArrayLike",
    rate: "ArrayLike",
    /,
    *,
    backend: "Backend" = None,
) -> "ArrayLike":
    r"""Compute the closed form of the CRPS for the exponential distribution.

    It is based on the following formulation from
    [Jordan et al. (2019)](https://www.jstatsoft.org/article/view/v090i12):

    $$\mathrm{CRPS}(F_{\lambda}, y) = |y| - \frac{2F_{\lambda}(y)}{\lambda} + \frac{1}{2 \lambda},$$

    where $F_{\lambda}$ is exponential distribution function with rate parameter $\lambda > 0$.

    Parameters
    ----------
    observation:
        The observed values.
    rate:
        Rate parameter of the forecast exponential distribution.

    Returns
    -------
    score:
        The CRPS between Exp(rate) and obs.

    Examples
    --------
    ```pycon
    >>> import scoringrules as sr
    >>> import numpy as np
    >>> sr.crps_exponential(0.8, 3.0)
    0.360478635526275
    >>> sr.crps_exponential(np.array([0.8, 0.9]), np.array([3.0, 2.0]))
    array([0.36047864, 0.24071795])
    ```
    """
    return crps.exponential(observation, rate, backend=backend)


def crps_normal(
    observation: "ArrayLike",
    mu: "ArrayLike",
    sigma: "ArrayLike",
    /,
    *,
    backend: "Backend" = None,
) -> "ArrayLike":
    r"""Compute the closed form of the CRPS for the normal distribution.

    It is based on the following formulation from
    [Geiting et al. (2005)](https://journals.ametsoc.org/view/journals/mwre/133/5/mwr2904.1.xml):

    $$ \mathrm{CRPS}(\mathcal{N}(\mu, \sigma), y) = \sigma \Bigl\{ \omega [\Phi(ω) - 1] + 2 \phi(\omega) - \frac{1}{\sqrt{\pi}} \Bigl\},$$

    where $\Phi(ω)$ and $\phi(ω)$ are respectively the CDF and PDF of the standard normal
    distribution at the normalized prediction error $\omega = \frac{y - \mu}{\sigma}$.

    Parameters
    ----------
    observations: ArrayLike
        The observed values.
    mu: ArrayLike
        Mean of the forecast normal distribution.
    sigma: ArrayLike
        Standard deviation of the forecast normal distribution.

    Returns
    -------
    crps: array_like
        The CRPS between Normal(mu, sigma) and obs.

    Examples
    --------
    >>> from scoringrules import crps
    >>> crps.normal(0.1, 0.4, 0.0)
    """
    return crps.normal(observation, mu, sigma, backend=backend)


def crps_lognormal(
    observation: "ArrayLike",
    mulog: "ArrayLike",
    sigmalog: "ArrayLike",
    backend: "Backend" = None,
) -> "ArrayLike":
    r"""Compute the closed form of the CRPS for the lognormal distribution.

    It is based on the formulation introduced by
    [Baran and Lerch (2015)](https://rmets.onlinelibrary.wiley.com/doi/full/10.1002/qj.2521)

    $$ \mathrm{CRPS}(\mathrm{log}\mathcal{N}(\mu, \sigma), y) =
    y [2 \Phi(y) - 1] - 2 \mathrm{exp}(\mu + \frac{\sigma^2}{2})
    \left[ \Phi(\omega - \sigma) + \Phi(\frac{\sigma}{\sqrt{2}}) \right]$$

    where $\Phi$ is the CDF of the standard normal distribution and
    $\omega = \frac{\mathrm{log}y - \mu}{\sigma}$.

    Note that mean and standard deviation are not the values for the distribution itself,
    but of the underlying normal distribution it is derived from.

    Parameters
    ----------
    observation:
        The observed values.
    mulog:
        Mean of the normal underlying distribution.
    sigmalog:
        Standard deviation of the underlying normal distribution.

    Returns
    -------
    crps: ArrayLike
        The CRPS between Lognormal(mu, sigma) and obs.

    Examples
    --------
    >>> from scoringrules import crps
    >>> crps.lognormal(0.1, 0.4, 0.0)
    """
    return crps.lognormal(observation, mulog, sigmalog, backend=backend)


def crps_logistic(
    observation: "ArrayLike",
    mu: "ArrayLike",
    sigma: "ArrayLike",
    /,
    *,
    backend: "Backend" = None,
) -> "ArrayLike":
    r"""Compute the closed form of the CRPS for the logistic distribution.

    It is based on the following formulation from
    [Jordan et al. (2019)](https://www.jstatsoft.org/article/view/v090i12):

    $$ \mathrm{CRPS}(\mathcal{L}(\mu, \sigma), y) = \sigma \left\{ \omega - 2 \log F(\omega) - 1 \right\}, $$

    where $F(\omega)$ is the CDF of the standard logistic distribution at the
    normalized prediction error $\omega = \frac{y - \mu}{\sigma}$.

    Parameters
    ----------
    observations: ArrayLike
        Observed values.
    mu: ArrayLike
        Location parameter of the forecast logistic distribution.
    sigma: ArrayLike
        Scale parameter of the forecast logistic distribution.

    Returns
    -------
    crps: array_like
        The CRPS for the Logistic(mu, sigma) forecasts given the observations.

    Examples
    --------
    >>> from scoringrules import crps
    >>> crps.logistic(0.1, 0.4, 0.0)
    """
    return crps.logistic(observation, mu, sigma, backend=backend)


__all__ = [
    "crps_ensemble",
    "twcrps_ensemble",
    "owcrps_ensemble",
    "vrcrps_ensemble",
    "crps_normal",
    "crps_lognormal",
    "crps_logistic",
]
