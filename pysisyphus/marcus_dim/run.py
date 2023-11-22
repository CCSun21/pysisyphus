# [1] https://doi.org/10.26434/chemrxiv-2022-253hc-v2
#     Identifying the Marcus dimension of electron transfer from
#     ab initio calculations
#     Šrut, Lear, Krewald, 2022 on chemrxiv
# [2] https://doi.org/10.1039/D3SC01402A
#     Identifying the Marcus dimension of electron transfer from
#     ab initio calculations
#     Šrut, Lear, Krewald, 2023, actual published version


from pathlib import Path
import os
import warnings

from distributed import LocalCluster
import matplotlib.pyplot as plt
import numpy as np
import psutil

from pysisyphus.constants import AU2EV
from pysisyphus.helpers_pure import get_state_label, highlight_text
from pysisyphus.marcus_dim.config import FIT_RESULTS_FN, SCAN_RESULTS_FN
from pysisyphus.marcus_dim.fit import epos_from_wf, fit_marcus_dim
from pysisyphus.marcus_dim.param import param_marcus
from pysisyphus.marcus_dim.scan import plot_scan, scan


_2EV = 2 / AU2EV


def run_scan(
    geom, marcus_dim, calc_getter, fragments, dummy_scan=False, cwd=".", **kwargs
):
    cwd = Path(cwd)
    # 2.) Scan along Marcus dimension
    print(highlight_text("Scan along Marcus Dimension"))
    pos_calc = calc_getter(base_name="scan_pos")
    neg_calc = calc_getter(base_name="scan_neg")

    has_all_energies = hasattr(pos_calc, "get_all_energies")
    if dummy_scan and not has_all_energies:
        warnings.warn(
            f"Calculator '{pos_calc}' does not implement 'get_all_energies()'! "
            f"Using dummy values for first excited state!'",
        )

    def get_properties(factor: int, coords_i: np.ndarray):
        # Use one of two different calculators, depending on the scan direction.
        calc = neg_calc if factor < 0 else pos_calc

        try:
            results = calc.get_all_energies(geom.atoms, coords_i)
            all_energies = results["all_energies"]
        except AttributeError as err:
            if not dummy_scan:
                raise err
            results = calc.get_energy(geom.atoms, coords_i)
            energy = results["energy"]
            all_energies = np.array((energy, energy + _2EV))
        energies = all_energies[:2]
        assert len(energies) == 2
        wf = calc.get_stored_wavefunction()
        tot_epos, alpha_epos = epos_from_wf(wf, fragments)
        return energies, alpha_epos

    scan_results_path = cwd / SCAN_RESULTS_FN
    scan_trj_path = cwd / "marcus_dim_scan.trj"
    scan_converged = False
    if scan_results_path.exists():
        scan_results = np.load(scan_results_path)
        print(f"Loaded scan data from '{scan_results_path}'.")
        scan_factors = scan_results["factors"]
        scan_coords = scan_results["coords"]
        scan_energies = scan_results["energies"]
        scan_properties = scan_results["properties"]
        try:
            scan_converged = bool(scan_results["scan_converged"])
        except KeyError:
            pass

    if not scan_converged:
        scan_factors, scan_coords, scan_energies, scan_properties = scan(
            coords_init=geom.cart_coords.copy(),
            direction=marcus_dim,
            get_properties=get_properties,
            **kwargs,
        )
        # Dump scan geometries into trj file
        xyzs = list()
        for sc, (se_gs, _) in zip(scan_coords, scan_energies):
            xyz = geom.as_xyz(cart_coords=sc, comment=f"{se_gs:.6f}")
            xyzs.append(xyz)
        with open(scan_trj_path, "w") as handle:
            handle.write("\n".join(xyzs))
    else:
        print("Skipping scan.")
    scan_fig, scan_axs = plot_scan(
        scan_factors, scan_energies, scan_properties, dummy_scan=dummy_scan
    )
    scan_fig.savefig(cwd / "scan.svg")
    plt.close(scan_fig)

    return scan_factors, scan_coords, scan_energies, scan_properties


def run_param(
    scan_factors: np.ndarray,
    scan_energies: np.ndarray,
    mult: int,
    cwd: os.PathLike = ".",
):
    cwd = Path(cwd)
    # 3.) Parametrization of Marcus model
    print(highlight_text("Parametrization of Marcus Model"))
    models = param_marcus(scan_factors, scan_energies)
    shifted_scan_energies = scan_energies - scan_energies.min()
    for para, model in models.items():
        print(f"Parametrization {para}: {model.pretty()}")
        fig, ax = model.plot(scan_factors)
        # Before adiabatic and diabatic states can be plotted side by side the sign of
        # scan_factors must be determined. Plotting should be done in  a way, to minimize
        # the difference between adiabatic energies from the model, and adiabatic energies
        # determined in the scan.
        G1, _ = model.G_adiabatic(scan_factors)
        # Determine sign that minimizes difference between parametrized adiabatic energies
        # and scanned energies.
        plus_diff = np.linalg.norm(G1 - shifted_scan_energies[:, 0])
        min_diff = np.linalg.norm(G1 - shifted_scan_energies[:, 0][::-1])
        sign = plus_diff if plus_diff < min_diff else -1

        for i, state in enumerate(shifted_scan_energies.T):
            label = get_state_label(mult, i)
            ax.plot(sign * scan_factors, state, label=f"${label}$")
            ax.legend()
        fig_fn = cwd / f"marcus_model_{para}.svg"
        fig.savefig(fig_fn)
        print(f"Saved plot of Marcus model to '{fig_fn}'")
    return models


def run_marcus_dim(
    geom,
    fragments,
    calc_getter,
    fit_kwargs=None,
    cluster=True,
    scan_kwargs=None,
    cwd=".",
    force=False,
    dummy_scan=False,
):
    """Fit Marucs dimension, scan along it and try to parametrize Marcus models."""
    if fit_kwargs is None:
        fit_kwargs = {}
    if scan_kwargs is None:
        scan_kwargs = {}
    fit_kwargs = fit_kwargs.copy()
    scan_kwargs = scan_kwargs.copy()
    cwd = Path(cwd)

    # 1.) Fit Marcus dimension
    print(highlight_text("Fitting of Marcus Dimension"))

    fit_results_path = cwd / FIT_RESULTS_FN
    rms_converged = False
    if fit_results_path.exists():
        md_results = np.load(fit_results_path)
        try:
            rms_converged = bool(md_results["rms_converged"])
        except KeyError:
            print("Could not determine if Marcus dimension already converged!")
    # When rms_converged is True md_results will always be present
    if not force and rms_converged:
        marcus_dim = md_results["marcus_dim"]
        print(f"Loaded Marcus dimension from '{fit_results_path}'. Skipping fit.")
        # TODO: report dimension?
    else:
        # Use scheduler/cluster/cluster_kwargs as in ChainOfStates.py?
        if cluster:
            n_workers = psutil.cpu_count(logical=False)
            scheduler = LocalCluster(n_workers=n_workers, threads_per_worker=1)
            fit_kwargs["scheduler"] = scheduler
        # Carry out fitting of Marcus dimension
        marcus_dim = fit_marcus_dim(geom, calc_getter, fragments, **fit_kwargs)
        if cluster:
            scheduler.close()
    print()

    # 2.) Scan along Marcus dimension
    scan_factors, scan_coords, scan_energies, scan_properties = run_scan(
        geom,
        marcus_dim,
        calc_getter,
        fragments,
        dummy_scan=dummy_scan,
        cwd=cwd,
        **scan_kwargs,
    )
    print()

    # 3.) Parametrization of Marcus model

    # Try to determine the multiplicity, for the creation of state labels as D_0, D_1, etc.
    # for the following plots.
    mult_calc = calc_getter()
    try:
        mult = mult_calc.mult
    except:
        mult = -1
    models = run_param(scan_factors, scan_energies, mult, cwd=cwd)
    return models
