#!/usr/bin/env python3

# [1  ] https://aip.scitation.org/doi/pdf/10.1063/1.3514202?class=pdf
#       Original EulerPC
#       Hratchian, Schlegel, 2010
# [2  ] https://aip.scitation.org/doi/pdf/10.1063/1.1724823?class=pdf
#       Original HPC
#       Hratchian, Schlegel, 2004
# [3  ] https://pubs.rsc.org/en/content/articlepdf/2017/cp/c7cp03722h
#       EulerPC re-implementation
#       Meisner, Kästner, 2017
# [3.1] http://www.rsc.org/suppdata/c7/cp/c7cp03722h/c7cp03722h1.pdf
#       Corresponding SI
# [4  ] https://aip.scitation.org/doi/pdf/10.1063/1.3593456?class=pdf
#       Hratchian, Frisch, 2011
# [6  ] https://aip.scitation.org/doi/10.1063/1.3593456<Paste>
#       Hratchian, Frisch
#	Further improvements; not implemented

import numpy as np

from pysisyphus.helpers import rms
from pysisyphus.irc.DWI import DWI
from pysisyphus.irc.IRC import IRC
from pysisyphus.optimizers.hessian_updates import bfgs_update, bofill_update


class EulerPC(IRC):

    def __init__(self, *args, hessian_recalc=None, hessian_update="bofill",
                 max_pred_steps=500, rms_grad_thresh=1e-4, dump_dwi=False, **kwargs):
        # Use a tighter criterion
        kwargs["rms_grad_thresh"] = rms_grad_thresh
        super().__init__(*args, **kwargs)

        self.hessian_recalc = hessian_recalc
        self.hessian_update = {
            "bfgs": bfgs_update,
            "bofill": bofill_update,
        }
        self.hessian_update_func = self.hessian_update[hessian_update]
        self.max_pred_steps = int(max_pred_steps)
        self.dump_dwi = dump_dwi

    def prepare(self, *args, **kwargs):
        super().prepare(*args, **kwargs)

        # Initialize the distance weighted interpolator with the data
        # from the initial displacement.
        self.dwi = DWI()
        mw_grad = self.mw_gradient
        energy = self.energy
        self.mw_H = self.geometry.mass_weigh_hessian(self.ts_hessian)

        dx = self.mw_coords - self.ts_mw_coords
        dg = mw_grad - self.ts_mw_gradient
        dH, key = self.hessian_update_func(self.ts_hessian, dx, dg)
        self.log(f"Did {key} hessian update.")
        self.mw_H += dH
        self.dwi.update(self.mw_coords, energy, mw_grad, self.mw_H.copy())

    def get_integration_length_func(self, init_mw_coords):
        def get_integration_length(cur_mw_coords):
            """Returns length of integration path done in mass-weighted coordinates
            in un-mass-weighted coordinates."""
            return np.linalg.norm((cur_mw_coords - init_mw_coords) / self.m_sqrt)
        return get_integration_length

    def step(self):
        ##################
        # PREDICTOR STEP #
        ##################

        mw_grad = self.mw_gradient
        energy = self.energy

        if self.cur_cycle > 0:
            if self.hessian_recalc and (self.cur_cycle % self.hessian_recalc == 0):
                self.mw_H = self.mw_hessian
                self.log("Calculated excact hessian")
            else:
                dx = self.mw_coords - self.irc_mw_coords[-2]
                dg = mw_grad - self.irc_mw_gradients[-2]
                dH, key = self.hessian_update_func(self.mw_H, dx, dg)
                self.mw_H += dH
                self.log(f"Did {key} hessian update before predictor step.")
            self.dwi.update(self.mw_coords.copy(), energy, mw_grad, self.mw_H.copy())

        # Create a copy of the inital coordinates for the determination
        # of the actual step size in the predictor Euler integration.
        init_mw_coords = self.mw_coords.copy()

        get_integration_length = self.get_integration_length_func(init_mw_coords)

        # Calculate predictor Euler-integeration step length. We do the integration
        # in mass-weighted coordinates, but we want to integrate until we achieve
        # a given step length in un-mass-weighted coordinates.
        # Converting the step from mass-weighted coordinates to un-mass-weighted
        # coordinates will reduce its norm as we dive the step vector by sqrt(m).
        #
        # So the problem is to determine a appropriate step-length for the
        # integration. [3] proposes just using Δs/250 with a maximum of 500 steps, so
        # something like Δs/(max_steps / 2). It seems we can't use this because (at
        # least for the systems I tested) this will lead to a step length that is too
        # small, so the predictor Euler-integration will fail to converge in the
        # prescribed number of cycles. This is because this calculation does not take
        # into account the mass-weighting. The step length may be appropriate for
        # integrations in un-mass-weighted coordinates, but not when using mass-weighted
        # coordinates.
        # We determine a conversion factor from comparing the magnitudes (norms) of
        # the mass-weighted and un-mass-weighted gradients. This takes into account
        # which atoms are actually moving, so it should be a good guess.
        norm_mw_grad = np.linalg.norm(mw_grad)
        norm_grad = np.linalg.norm(self.unweight_vec(mw_grad))
        conv_fact = norm_grad / norm_mw_grad
        conv_fact = max(2, conv_fact)
        self.log(f"Un-weighted / mass-weighted conversion factor {conv_fact:.4f}")
        euler_step_length = self.step_length / (self.max_pred_steps / conv_fact)

        def taylor_gradient(step):
            """Return gradient from Taylor expansion of energy to 2nd order."""
            return mw_grad + self.mw_H @ step

        # These variables will hold the coordinates and gradients along
        # the Euler integration and will be updated frequently.
        euler_mw_coords = self.mw_coords.copy()
        euler_mw_grad = mw_grad.copy()
        self.log(f"Predictor-Euler-integration with Δs={euler_step_length:.6f} "
                 f"for up to {self.max_pred_steps} steps")
        prev_cur_length = 0.
        for i in range(self.max_pred_steps):
            # Calculate step length in non-mass-weighted coordinates
            cur_length = get_integration_length(euler_mw_coords)
            if i % 50 == 0:
                diff = cur_length - prev_cur_length
                self.log(f"\t{i:03d}: {cur_length:.4f} Δ={diff:.4f}")
                prev_cur_length = cur_length

            # Check if we achieved the desired step length.
            if cur_length >= self.step_length:
                self.log( "Predictor-Euler integration converged with "
                         f"Δs={cur_length:.4f} (desired Δs={self.step_length:.4f}) "
                         f"after {i+1} steps!"
                )
                break
            step_ = euler_step_length * -euler_mw_grad / np.linalg.norm(euler_mw_grad)
            euler_mw_coords += step_
            # Determine actual step by comparing the current and the initial coordinates
            euler_step = euler_mw_coords - init_mw_coords
            euler_mw_grad = taylor_gradient(euler_step)
        else:
            self.log(f"Predictor-Euler integration dit not converge in {i+1} "
                     f"steps. Δs={cur_length:.4f}."
            )

            # Check if we are already sufficiently converged. If so signal
            # convergence.
            self.mw_coords = euler_mw_coords

            # Use rms of gradient from taylor expansion for convergence check.
            euler_grad = self.unweight_vec(euler_mw_grad)
            rms_grad = rms(euler_grad)

            # Or check true gradient? But this would need an additional calculation,
            # so I disabled it for now.
            # rms_grad = rms(self.gradient)

            if rms_grad <= 5*self.rms_grad_thresh:
                self.log("Sufficient convergence achieved on rms(grad)")
                self.converged = True
                return
        self.log("")

        # Calculate energy and gradient at new predicted geometry. Update the
        # hessian accordingly. These results will be added to the DWI for use
        # in the corrector step.
        self.mw_coords = euler_mw_coords
        self.log("Calculating energy and gradient at predictor step.")
        mw_grad = self.mw_gradient
        energy = self.energy

        # Hessian update
        dx = self.mw_coords - self.irc_mw_coords[-1]
        dg = mw_grad - self.irc_mw_gradients[-1]
        dH, key = self.hessian_update_func(self.mw_H, dx, dg)
        self.mw_H += dH
        self.log(f"Did {key} hessian update after predictor step.\n")
        self.dwi.update(self.mw_coords.copy(), energy, mw_grad, self.mw_H.copy())

        corrected_mw_coords = self.corrector_step(
                                init_mw_coords,
                                self.step_length,
                                self.dwi
        )
        self.mw_coords = corrected_mw_coords

    def corrector_step(self, init_mw_coords, step_length, dwi):
        ##################
        # CORRECTOR STEP #
        ##################

        get_integration_length = self.get_integration_length_func(init_mw_coords)

        if self.dump_dwi:
            dwi.dump(f"dwi_{self.cur_direction}_{self.cur_cycle:0{self.cycle_places}d}.h5")

        self.log("Starting mBS integration using Richardson extrapolation")
        errors = list()
        richardson = dict()
        for k in range(15):
            points = 20*(2**k)
            corr_step_length = step_length / (points - 1)
            cur_coords = init_mw_coords.copy()
            k_coords = list()
            cur_length = 0

            # Integrate until the desired spacing is reached
            while True:
                k_coords.append(cur_coords.copy())
                if abs(step_length - cur_length) < .5*corr_step_length:
                    self.log(f"\tk={k:02d} points={points: >4d} "
                             f"step_length={corr_step_length:.4f} Δs={cur_length:.4f}")
                    break

                energy, gradient = dwi.interpolate(cur_coords, gradient=True)
                cur_coords += corr_step_length * -gradient/np.linalg.norm(gradient)
                # cur_length += corr_step_length
                cur_length = get_integration_length(cur_coords)

                # Check for oscillation
                try:
                    prev_coords = k_coords[-2]
                    osc_norm = np.linalg.norm(cur_coords - prev_coords)
                    # TODO: Handle this by restarting everything with a smaller stepsize?
                    # Check 10.1039/c7cp03722h SI
                    if osc_norm <= corr_step_length:
                        self.log( "\tDetected oscillation in Corrector-Euler "
                                 f"integration for k={k:02d} and {points} points.\n"
                                  "\tAborting corrector integration!")
                        return prev_coords
                except IndexError:
                    pass
            richardson[(k, 0)] = cur_coords

            # Refine using Richardson extrapolation
            # Set additional values using Richard extrapolation
            for j in range(1, k+1):
                richardson[(k, j)] = ((2**j) * richardson[(k, j-1)] - richardson[(k-1, j-1)]) \
                                     / (2**j-1)
            # Can only be done after the second successful integration
            if k > 0:
                # Error estimate according to Numerical Recipes Eq. (17.3.9).
                # We compare the last two entries/columns in the current row.
                # RMS error
                error = np.sqrt(np.mean((richardson[(k,k)] - richardson[(k,k-1)])**2))
                errors.append(error)
                if error <= 1e-5:
                    self.log(f"mBS integration converged (error={error:.4e})!")
                    break
        else:
            raise Exception("Richardson did not converge!")
        
        self.log(f"Returning corrected mass-weighted coordinates from richardson[({k},{k})]")
        return richardson[(k,k)]
