#!/usr/bin/env python3

import pytest

from pysisyphus.calculators.PySCF import PySCF
from pysisyphus.helpers import geom_from_library
from pysisyphus.intcoords.augment_bonds import augment_bonds
from pysisyphus.testing import using
from pysisyphus.tsoptimizers.RSIRFOptimizer import RSIRFOptimizer


@using("pyscf")
@pytest.mark.parametrize(
    "augment, ref_cycle",
    [
        (True, 6),
        (False, 57),
    ]
)
def test_augment_coordinates_silyl(augment, ref_cycle):
    geom = geom_from_library("baker_ts/18_silyene_insertion.xyz",
                             coord_type="redund")

    opt_kwargs = {
        "thresh": "baker",
        "max_cycles": 100,
        "dump": True,
        "trust_radius": 0.3,
        "trust_max": 0.3,
    }
    calc_kwargs = {
        "charge": 0,
        "mult": 1,
        "pal": 4,
    }
    calc = PySCF(basis="321g", **calc_kwargs)

    geom.set_calculator(calc)

    # Check if additional coordiantes can be defined
    if augment:
        geom = augment_bonds(geom)

    opt = RSIRFOptimizer(geom, **opt_kwargs)
    opt.run()

    ref_en = -367.20778
    assert geom.energy == pytest.approx(ref_en)
    assert opt.cur_cycle == ref_cycle
