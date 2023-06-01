import time

import matplotlib.pyplot as plt
import numpy as np
from scipy.constants import c as speed_of_light, hbar, pi
from scipy.integrate import quad

from pysisyphus.constants import AU2EV, AU2J, AU2SEC


JOULE2EV = AU2EV / AU2J


def angfreq_au(wavenum):
    """Angular frequency in atomic units from wavenumber in cm⁻¹."""
    angfreq_si = speed_of_light * wavenum * 1e2 * 2 * pi
    return angfreq_si * AU2SEC


def nu2eV(wavenum):
    joule = hbar * (2 * pi) * speed_of_light * wavenum * 1e2
    return joule * JOULE2EV


def get_crossec_integrand(dE_exc: float, gamma: float, displs, nus):
    """
    dE_exc - excitation energy, in wavenumbers
    gamma - in wavenumbers
    """
    angfreq_exc = angfreq_au(dE_exc)
    angfreq_gamma = angfreq_au(gamma)
    minus_displs_half = (-(displs**2)) / 2
    angfreqs = angfreq_au(nus)
    imag_angfreqs = -1j * angfreqs

    def ovlp_term(t):
        exp_arg = minus_displs_half * (1 - np.exp(imag_angfreqs * t))
        return np.prod(np.exp(exp_arg))

    def integrand(t, dE_incident):
        """
        dE_inc - energy of incident photon, in wavenumbers
        """
        angfreq_incident = angfreq_au(dE_incident)
        return np.exp(
            1j * (angfreq_incident - angfreq_exc) * t - angfreq_gamma * t
        ) * ovlp_term(t)

    return integrand


def imdho_abs_cross_section(
    dEs_inc: np.ndarray,
    dE_exc: float,
    gamma: float,
    displs: np.ndarray,
    nus: np.ndarray,
    ithresh: float = 1e-6,
):
    integrand = get_crossec_integrand(dE_exc, gamma, displs, nus)

    tmax = -np.log(ithresh) / angfreq_au(gamma)
    print(f"tmax={tmax:.4f} au for Γ={gamma:.2f} cm⁻¹")

    tenth = dEs_inc.size // 10
    cross_secs = np.zeros_like(dEs_inc)
    for i, dE_inc in enumerate(dEs_inc):
        y, _ = quad(integrand, 0, tmax, args=(dE_inc,), complex_func=True, limit=500)
        cross_secs[i] = y.real
        if i % tenth == 0:
            print(i, y.real)
    # TODO: make normalization optional and also include electronic part
    cross_secs = cross_secs / cross_secs.max()
    return cross_secs
