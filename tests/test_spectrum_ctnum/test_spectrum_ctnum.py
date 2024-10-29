from matplotlib.testing.decorators import image_comparison
import numpy as np

from pysisyphus.constants import NU2AU
from pysisyphus.helpers import geom_loader
from pysisyphus.drivers.spectrum_ctnum import ct_number_plot


@image_comparison(
    baseline_images=["spectrum_ctnum"],
    remove_text=True,
    extensions=["png"],
    style="mpl20",
)
def test_spectrum_ctnum(this_dir):
    data_dir = this_dir / "data"
    fn = data_dir / "combined.xyz"
    geom = geom_loader(fn)

    omegas = np.load(data_dir / "omegas.npy")
    nstates, nfrags2 = omegas.shape
    nfrags = int(nfrags2**0.5)
    ct_numbers = omegas.reshape(nstates, nfrags, nfrags)
    states = np.loadtxt(data_dir / "states")
    nstates = len(states)

    # exc_ens = states[:, 1] * NU2AU  # from wavenumbers to atomic units
    gs_energy = -1368.40370329
    all_energies = np.full(nstates + 1, gs_energy)
    all_energies[1:] += states[:, 1] * NU2AU  # from wavenumbers to atomic units
    foscs = states[:, 3]  # Oscillator strengths
    # Disable graphviz, as the reference image was created without it
    fig = ct_number_plot(
        geom.atoms,
        geom.cart_coords,
        all_energies,
        foscs,
        ct_numbers,
        try_graphviz=False,
    )
    # import matplotlib.pyplot as plt

    # plt.show()
