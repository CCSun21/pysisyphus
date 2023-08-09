import warnings

try:
    import ase

    HAVE_ASE = True
except ModuleNotFoundError:
    HAVE_ASE = False
import numpy as np

from pysisyphus.constants import BOHR2ANG as Bohr
from pysisyphus.elem_data import INV_ATOMIC_NUMBERS as chemical_symbols

"""
The 'Grid' class and the 'plot' function are directly copied from
gpaw commit 8b893bc47c5d37a9085540179406460df01682ec.
gpaw is licensed under GPLv3.
"""


class Grid:
    def __init__(self, i, j):
        self.grid = np.zeros((i, j), np.int8)
        self.grid[:] = ord(" ")
        self.depth = np.zeros((i, j))
        self.depth[:] = 1e10

    def put(self, c, i, j, depth=1e9):
        if depth < self.depth[i, j]:
            self.grid[i, j] = ord(c)
            self.depth[i, j] = depth


def plot(atoms) -> str:
    """Ascii-art plot of the atoms."""

    #   y
    #   |
    #   .-- x
    #  /
    # z

    if atoms.cell.handedness != 1:
        # See example we can't handle in test_ascii_art()
        return ""

    cell_cv = atoms.get_cell()
    if atoms.cell.orthorhombic:
        plot_box = True
    else:
        atoms = atoms.copy()
        atoms.cell = [1, 1, 1]
        atoms.center(vacuum=2.0)
        cell_cv = atoms.get_cell()
        plot_box = False

    cell = np.diagonal(cell_cv) / Bohr
    positions = atoms.get_positions() / Bohr
    numbers = atoms.get_atomic_numbers()

    s = 1.3
    nx, ny, nz = nxyz = (s * cell * (1.0, 0.25, 0.5) + 0.5).astype(int)
    sx, sy, sz = nxyz / cell
    grid = Grid(nx + ny + 4, nz + ny + 1)
    positions = (positions % cell + cell) % cell
    ij = np.dot(positions, [(sx, 0), (sy, sy), (0, sz)])
    ij = np.around(ij).astype(int)
    for a, Z in enumerate(numbers):
        symbol = chemical_symbols[Z]
        i, j = ij[a]
        depth = positions[a, 1]
        for n, c in enumerate(symbol):
            grid.put(c, i + n + 1, j, depth)
    if plot_box:
        k = 0
        for i, j in [(1, 0), (1 + nx, 0)]:
            grid.put("*", i, j)
            grid.put(".", i + ny, j + ny)
            if k == 0:
                grid.put("*", i, j + nz)
            grid.put(".", i + ny, j + nz + ny)
            for y in range(1, ny):
                grid.put("/", i + y, j + y, y / sy)
                if k == 0:
                    grid.put("/", i + y, j + y + nz, y / sy)
            for z in range(1, nz):
                if k == 0:
                    grid.put("|", i, j + z)
                grid.put("|", i + ny, j + z + ny)
            k = 1
        for i, j in [(1, 0), (1, nz)]:
            for x in range(1, nx):
                if k == 1:
                    grid.put("-", i + x, j)
                grid.put("-", i + x + ny, j + ny)
            k = 0
    return "\n".join(
        ["".join([chr(x) for x in line]) for line in np.transpose(grid.grid)[::-1]]
    )


def plot_wrapper(geom) -> str:
    """ASCII representation of pysisyphus.Geometry object.

    Thin wrapper around gpaw's outplot.plot() function."""
    if not HAVE_ASE:
        warnings.warn("Geometry-ASCII plot requires ASE (python -m pip install ase)!")
        return ""

    # Export Geometry object to ase.Atoms object w/ autogenerated cell.
    atoms = geom.as_ase_atoms(vacuum=2.0)
    return plot(atoms)
