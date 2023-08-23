import math
import sys
import warnings

import numpy as np


def scan_dir(
    x0,
    direction,
    get_property,
    step_size=0.05,
    add_steps=10,
    max_steps=500,
    min_steps=5,
    grad_thresh=1e-2,
):
    assert step_size > 0.0, f"{step_size=} must be positive!"
    assert add_steps >= 0, f"{add_steps=} must must be positive!"
    assert max_steps > 0, f"{max_steps=} must be positive!"
    assert min_steps >= 0, f"{min_steps=} must be positive!"
    assert grad_thresh > 0.0, f"{grad_thresh} must be positive!"

    step = step_size * direction
    stop_in = add_steps
    xcur = x0 + step

    converged = False
    grad = np.nan
    prop_prev = None
    abs_grad_prev = None
    grad_decreased_already = False

    all_factors = np.arange(max_steps) + 1
    all_coords = np.empty((max_steps, *x0.shape))
    all_energies = list()
    all_properties = np.empty(max_steps)
    for i in range(max_steps):
        all_coords[i] = xcur
        # Calculate & store property
        energies, prop = get_property(xcur)
        all_properties[i] = prop
        all_energies.append(energies)

        # Determine gradient from finite differences
        if prop_prev is not None:
            grad = (prop - prop_prev) / step_size
            abs_grad = abs(grad)
        else:
            abs_grad = None

        if abs_grad_prev is not None:
            grad_decreased = abs_grad < abs_grad_prev
            grad_decreased_already = grad_decreased_already or grad_decreased
        else:
            grad_decreased = None
            grad_decreased_already = False
        print(f"{i=:03d}, property={prop: >12.4f}, {grad=: >12.4f}")
        sys.stdout.flush()

        # Break when the gradient already decreased once and increased
        # unexpectedly aftwards. But do at least 'min_steps' steps.
        if (
            (i >= min_steps)
            and grad_decreased_already
            and (grad_decreased is not None)
            and not grad_decreased
        ):
            print("Unexpected increase of abs(grad(property))! Breaking")
            break

        # Check gradient convergence; this check is skipped once convergence is indicated.
        if not converged and (converged := np.abs(grad) <= grad_thresh):
            print("Converged!")

        # If requested, we carry out additional steps, if requested.
        if add_steps and converged:
            stop_in -= 1

        # Break directly if converged and we don't want to do any additional steps.
        if converged and add_steps == 0:
            break
        elif add_steps and stop_in < 0:
            print("Did additional steps")
            break

        # Update variables
        xcur = xcur + step
        prop_prev = prop
        if abs_grad is not None:
            abs_grad_prev = abs_grad

    all_energies = np.array(all_energies)
    # Truncate arrays and drop empty part. This will also drop the last calculation
    # that lead to the break from the loop.
    return (
        all_factors[:i] * step_size,
        all_coords[:i],
        all_energies[:i],
        all_properties[:i],
    )


def scan(x0, direction, get_properties, **kwargs):
    dir_norm = np.linalg.norm(direction)
    if not math.isclose(dir_norm, 1.0):
        warnings.warn(f"norm(direction)={dir_norm:.6f} is not 1.0! Renormalizing.")
        direction = direction / dir_norm
    # Carry out calculation on initial geometry.
    ens0, prop0 = get_properties(x0)

    def get_property_changes(xi):
        """Get property changes w.r.t. initial geometry."""
        ens, prop = get_properties(xi)
        return ens, prop  # - prop0

    print("Positive direction")
    pos_dir = direction
    pos_facts, pos_coords, pos_ens, pos_props = scan_dir(
        x0, pos_dir, get_property_changes, **kwargs
    )
    print()

    print("Negative direction")
    neg_dir = -1.0 * direction
    neg_facts, neg_coords, neg_ens, neg_props = scan_dir(
        x0, neg_dir, get_property_changes, **kwargs
    )

    def concat(neg, init, pos):
        return np.concatenate((neg[::-1], [init], pos))

    all_facts = concat(-neg_facts, 0.0, pos_facts)
    all_coords = concat(neg_coords, x0, pos_coords)
    all_energies = concat(neg_ens, ens0, pos_ens)
    # When we consider the difference w.r.t. initial geometry then
    # the property is always 0.0.
    all_properties = concat(neg_props, prop0, pos_props)

    return all_facts, all_coords, all_energies, all_properties
