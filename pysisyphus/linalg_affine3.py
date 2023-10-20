"""
Affine transformations in 3d.

Based on code given by Emőd Kovács in

    Rotation about an arbitrary axis and reflection through an arbitrary plane
"""


import numpy as np


def svd_plane_normal(coords3d):
    """Normal vector of best-fit plane for coords3d."""
    centroid = coords3d.mean(axis=0)
    *_, vh = np.linalg.svd(coords3d - centroid[None, :])
    normal = vh.T[:, -1]
    return normal


def plane_normal(coords3d, thresh=1e-6):
    """Normal vector of plane given by 3 points."""
    assert coords3d.shape == (3, 3)
    a, b, c = coords3d
    vec1 = a - b
    vec1 /= np.linalg.norm(vec1)
    vec2 = a - c
    vec2 /= np.linalg.norm(vec2)
    assert vec1.dot(vec2) >= thresh
    normal = np.cross(vec1, vec2)
    normal /= np.linalg.norm(normal)
    return normal


def augment_vector(vec):
    assert vec.size == 3
    avec = np.empty(4)
    avec[:3] = vec
    avec[3] = 1.0
    return avec


def augment_vectors(vecs):
    rows, cols = vecs.shape
    assert cols == 3
    avecs = np.empty((rows, 4))
    avecs[:, :3] = vecs
    avecs[:, 3] = 1.0
    return avecs


def augment_matrix(mat, b=None):
    """Augment 3x3 matrix to 4x4."""
    assert mat.shape == (3, 3)
    if b is None:
        b = np.zeros(3)
    assert b.shape == (3,)
    amat = np.zeros((4, 4))
    amat[:3, :3] = mat
    amat[:3, 3] = b
    amat[3, 3] = 1
    return amat


def translation_matrix(vec):
    """Augmented translation matrix."""
    return augment_matrix(np.eye(3), b=vec)


def inv_translation_matrix(vec):
    """Inverse of augmented translation matrix."""
    return augment_matrix(np.eye(3), b=-vec)


def householder_reflection_matrix(normal):
    """Householder reflection matrix."""
    return np.eye(normal.size) - 2 * np.outer(normal, normal)


def reflection_matrix(normal, point):
    """Reflection through plane containing 'point' and normal vector 'normal'."""
    nx, ny, nz = normal
    d = (-normal * point).sum()

    b = -2 * normal * d
    R = np.diag(1 - 2 * normal**2)
    R[1, 0] = R[0, 1] = -2 * nx * ny
    R[2, 0] = R[0, 2] = -2 * nx * nz
    R[1, 2] = R[2, 1] = -2 * ny * nz
    R = augment_matrix(R, b)
    return R


def reflect_coords(R, coords3d):
    acoords3d = augment_vectors(coords3d)
    racoords3d = acoords3d @ R.T
    return racoords3d[:, :3]


def rotation_matrix_for_vec_align(
    vec1: np.ndarray, vec2: np.ndarray, thresh: float = 1e-8
) -> np.ndarray:
    """Returns rotation matrix that rotates vec1 onto vec2.

    Code adapted from https://math.stackexchange.com/a/476311

    (R @ vec1) and vec2 are parallel.

    Parameters
    ----------
    vec1
        3d vector.
    vec2
        3d vector.
    thresh
        Positive floating point for detecting parallel vectors.

    Returns
    -------
    R
        3x3 rotation matrix that rotates vec1 onto vec2.
    """
    assert thresh > 0.0
    vec1_norm = np.linalg.norm(vec1)
    assert vec1_norm >= thresh, f"Norm of vec1 is below {thresh=:.4e}!"
    vec2_norm = np.linalg.norm(vec2)
    assert vec2_norm >= thresh, f"Norm of vec2 is below {thresh=:.4e}!"
    vec1 = vec1 / vec1_norm
    vec2 = vec2 / vec2_norm
    cosine = vec1.dot(vec2)
    R = np.eye(3)
    # Shortcuts when vectors are already
    # ... parallel, dot product is ~ 1.0
    if abs(cosine - 1.0) <= thresh:
        return R
    # ... antiparallel, dot product is ~ -1.0
    elif abs(cosine + 1.0) <= thresh:
        return -R

    v1, v2, v3 = np.cross(vec1, vec2)
    vx = np.array(
        (
            (0, -v3, v2),
            (v3, 0, -v1),
            (-v2, v1, 0),
        )
    )
    quot = 1 / (1 + cosine)
    # Identity matrix was already assigned before to R
    R = R + vx + vx @ vx * quot
    return R
