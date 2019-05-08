#!/usr/bin/env python3

from pathlib import Path
from pprint import pprint
import time

import cloudpickle

from pysisyphus.calculators.XTB import XTB
from pysisyphus.helpers import geom_from_library
from pysisyphus.optimizers.RFOptimizer import RFOptimizer
from pysisyphus.optimizers.RSRFOptimizer import RSRFOptimizer


GEOMS = {
    "artemisin.xyz": (0, 1),
    "avobenzone.xyz": (0, 1),
    "azadirachtin.xyz": (0, 1),
    "bisphenol_a.xyz": (0, 1),
    "cetirizine.xyz": (0, 1),
    "codeine.xyz": (0, 1),
    "diisobutyl_phthalate.xyz": (0, 1),
    "easc.xyz": (0, 1),
    "estradiol.xyz": (0, 1),
    "inosine.xyz": (1, 1),
    "maltose.xyz": (0, 1),
    "mg_porphin.xyz": (0, 1),
    "ochratoxin_a.xyz": (0, 1),
    "penicillin_v.xyz": (0, 1),
    "raffinose.xyz": (0, 1),
    "sphingomyelin.xyz": (0, 1),
    "tamoxifen.xyz": (0, 1),
    "vitamin_c.xyz": (0, 1),
    "zn_edta.xyz": (-2, 1)
}


def test_birkholz():
    base_path = Path("birkholz")
    results = dict()
    tot_cycles = 0
    fails = 0
    start = time.time()
    # GEOMS = { "bisphenol_a.xyz": (0, 1), }
    for xyz_fn, (charge, mult) in GEOMS.items():
        print(xyz_fn, charge, mult)
        geom = geom_from_library(base_path / xyz_fn, coord_type="redund")
        xtb = XTB(charge=charge, mult=mult, pal=4)
        geom.set_calculator(xtb)

        opt_kwargs_base = {
            "max_cycles": 150,
            "thresh": "gau",
            "trust_radius": 0.5,
            "trust_update": True,
            "hess_update": "bfgs",
        }
        rsrfo_kwargs = opt_kwargs_base.copy()
        rsrfo_kwargs.update({
            "max_micro_cycles": 1,
        })
        opt = RSRFOptimizer(geom, **rsrfo_kwargs)
        opt.run()

        # rfo_kwargs = opt_kwargs_base.copy()
        # opt = RFOptimizer(geom, **rfo_kwargs)
        # opt.run()

        converged = opt.is_converged
        cycles = opt.cur_cycle+1
        results[xyz_fn] = (converged, cycles)
        pprint(results)

        if converged:
            tot_cycles += cycles
        else:
            fails += 1
        print()
    end = time.time()
    print()

    print(f"Total runtime: {end-start:.1f} s")
    pprint(results)
    print(f"Total cycles: {tot_cycles}")
    print(f"Fails: {fails}")

    opt_kwargs["time"] = time.time()
    to_pickle = (results, opt_kwargs, type(opt))
    hash_ = hash(frozenset(opt_kwargs.items()))
    pickle_fn = f"results_{hash_}.pickle"
    with open(pickle_fn, "wb") as handle:
        cloudpickle.dump(to_pickle, handle)
    print(f"Save pickled results to {pickle_fn}")


if __name__ == "__main__":
    test_birkholz()
