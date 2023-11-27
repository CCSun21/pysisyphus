# [1] https://doi.org/10.1039/D3SC01402A
#     Identifying the Marcus dimension of electron transfer from
#     ab initio calculations
#     Šrut, Lear, Krewald, 2023


import functools
import math
import os
import warnings

import numpy as np
import sympy as sym

from pysisyphus.constants import BOHR2ANG, NU2AU
import pysisyphus.marcus_dim.types as mdtypes


def solve_marcus(R, Vab, dG=None, en_exc_min=None):
    """Fit Marcus-Hush model to given parameters R, Vab, dG and en_exc_min.
    Either dG or en_exc_min is mandatory.

    All argument should be given in atomic units (Hartree and Bohr).

    Quartic extension is described here:
        https://www.science.org/doi/epdf/10.1126/science.278.5339.846
    This is not yet implemented!"""

    assert (dG is not None) or (
        en_exc_min is not None
    ), "Either 'dG' or 'en_exc_min' must be given!"
    f, d = sym.symbols("f d", real=True)
    # Equation 1 is the same for both parametrizations; either eq. (5b) or (6b)
    eq1 = (
        d / 2
        - 1 / 2 * ((d**2 * f - sym.sqrt(d**4 * f**2 - 4 * Vab**2)) / (d * f))
        - R
    )

    nan = math.nan

    def inner(eq2):
        # Solve equation system using sympy
        results = sym.solve([eq1, eq2], d, f, dict=True)
        # Class III systems with only one minimum can't be solved, but we
        # return a model nonetheless.
        if len(results) == 0:
            fval = nan
            dval = nan
            reorg_en = nan
            dG = nan
        elif len(results) == 1:
            res = results[0]
            fval = res[f]
            dval = res[d]
            reorg_en = fval * dval**2
            dG = (dval**2 * fval - 2 * Vab) ** 2 / (4 * dval**2 * fval)
        else:
            raise Exception("Solving equations yielded more than one result!")
        return mdtypes.MarcusModel(
            reorg_en=float(reorg_en),
            dG=float(dG),
            coupling=float(Vab),
            R=float(R),
            f=float(fval),
            d=float(dval),
        )

    results = dict()
    # Depending on whether dG and/or en_exc_min we can try to run both parametrizations.
    # Use parametrization A
    if dG is not None:
        # Eq. (5c) in SI of [1]
        eq2_a = (d**2 * f - 2 * Vab) ** 2 / (4 * d**2 * f) - dG
        results["a"] = inner(eq2_a)
    # Use parametrization B
    if en_exc_min is not None:
        # Eq. (6c) in SI of [1]
        eq2_b = d**2 * f - en_exc_min
        results["b"] = inner(eq2_b)
    return results


def solve_marcus_wavenums_and_ang(R, Vab, dG=None, en_exc_min=None):
    """Wrapper for solve_marcus that accepts wavenumbers and Ångstrom."""
    kwargs = {
        "R": R / BOHR2ANG,
        "Vab": Vab * NU2AU,
        "dG": dG * NU2AU if dG is not None else None,
        "en_exc_min": en_exc_min * NU2AU if en_exc_min is not None else None,
    }
    return solve_marcus(**kwargs)


def find_minima(arr):
    assert (arr.ndim == 1) and (len(arr) >= 3)
    first_min = [0] if arr[0] < arr[1] else []
    last_min = [len(arr) - 1] if arr[-1] < arr[-2] else []
    inner_mins = [i for i in range(1, arr.size) if arr[i - 1] > arr[i] < arr[i + 1]]
    return first_min + inner_mins + last_min


@functools.singledispatch
def param_marcus(coordinate: np.ndarray, energies: np.ndarray):
    """Parametrize Marcus model with results from scan along Marcus dimension."""
    assert coordinate.ndim == 1, (
        "Parametrization requires a 1d coordinate, e.g. an "
        "array collecting displacement along the Marcus dimension!"
    )
    assert (
        energies.ndim == 2
    ), "Parametrization requires potential energy curves of 2 states!"

    energies = energies - energies.min()
    # Excitation energy at adiabatic minimum
    min_inds = find_minima(energies[:, 0])  # Search minima in lower state
    if len(min_inds) == 2:
        ind0, ind1 = min_inds
        adia_min_ind = ind0 if energies[ind0, 0] < energies[ind1, 0] else ind1
        energies_between_mins = energies[ind0 : ind1 + 1]
        # Determine index of barrier in lower state
        barr_ind = energies_between_mins[:, 0].argmax()
        barr_ind += ind0
    elif len(min_inds) == 1:
        warnings.warn(
            "Found class III system or scan is not yet finished. "
            "Parametrizing Marcus model is not possible!"
        )
        adia_min_ind = barr_ind = min_inds[0]
    else:
        raise Exception("How did I get here?!")

    adia_min_ens = energies[adia_min_ind]
    en_exc_min = adia_min_ens[1] - adia_min_ens[0]
    barr_ens = energies[barr_ind]
    en_exc_barr = barr_ens[1] - barr_ens[0]

    # Electronic coupling
    Vab = en_exc_barr / 2
    # Distance R between adiabatic minimum and top of barrier
    R = abs(coordinate[barr_ind] - coordinate[adia_min_ind])
    # Barrier height ΔG
    dG = energies[barr_ind, 0]

    return solve_marcus(R, Vab, dG=dG, en_exc_min=en_exc_min)


@param_marcus.register
def _(path: os.PathLike):
    data = np.load(path)
    factors = data["factors"]
    energies = data["energies"]
    return param_marcus(factors, energies)
