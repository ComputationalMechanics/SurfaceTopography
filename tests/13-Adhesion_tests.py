#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
@file   10-Hertz_tests.py

@author Till Junge <till.junge@kit.edu>

@date   05 Oct 2015

@brief  Tests adhesion-free systems for accuracy and compares performance

@section LICENCE

 Copyright (C) 2015 Till Junge

PyCo is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License as
published by the Free Software Foundation, either version 3, or (at
your option) any later version.

PyCo is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public License
along with GNU Emacs; see the file COPYING. If not, write to the
Free Software Foundation, Inc., 59 Temple Place - Suite 330,
Boston, MA 02111-1307, USA.
"""

try:
    import unittest
    import numpy as np
    import time
    import math
    import PyCo.ReferenceSolutions.DMT as DMT
    import PyCo.ReferenceSolutions.JKR as JKR
    import PyCo.ReferenceSolutions.MaugisDugdale as MD
    from scipy.optimize import minimize_scalar
    from PyCo.ContactMechanics import ExpPotential
    from PyCo.SolidMechanics import (FreeFFTElasticHalfSpace,
                                     PeriodicFFTElasticHalfSpace)
    from PyCo.Surface import Sphere
    from PyCo.System import SystemFactory, SmoothContactSystem
except ImportError as err:
    import sys
    print(err)
    sys.exit(-1)

# -----------------------------------------------------------------------------
class AdhesionTest(unittest.TestCase):
    def setUp(self):
        # sphere radius:
        self.r_s = 10.0
        # contact radius
        self.r_c = .2
        # peak pressure
        self.p_0 = 2.5
        # equivalent Young's modulus
        self.E_s = 102.
        # work of adhesion
        self.w = 1.0
        # tolerance for optimizer
        self.tol = 1e-12
        # tolerance for contact area
        self.gap_tol = 1e-6

    def test_hard_wall_LBFGS(self):
        nx, ny = 128, 128
        sx = 10.0

        for ran in [0.05, 0.3]:
            substrate = FreeFFTElasticHalfSpace((nx, ny), self.E_s, (sx, sx))
            interaction = ExpPotential(self.w, ran)#, 0.1)
            surface = Sphere(self.r_s, (nx, ny), (sx, sx))
            ext_surface = Sphere(self.r_s, (2*nx, 2*ny), (2*sx, 2*sx),
                                 centre=(sx/2, sx/2))
            system = SmoothContactSystem(substrate, interaction, surface)

            disp0 = np.linspace(-self.r_s/100, self.r_s/50, 11)
            normal_force = []
            area = []
            for _disp0 in disp0:
                result = system.minimize_proxy(_disp0,
                                               lbounds=ext_surface.profile()+_disp0,
                                               tol=self.tol)
                u = result.x
                u.shape = ext_surface.shape
                f = substrate.evaluate_force(u)
                converged = result.success
                self.assertTrue(converged)

                gap = system.compute_gap(u, _disp0)

                normal_force += [-f.sum()]
                area += [(gap<self.gap_tol).sum()*system.area_per_pt]

            normal_force = np.array(normal_force)
            area = np.array(area)

            opt = minimize_scalar(lambda x: ((MD.load_and_displacement(np.sqrt(area/np.pi), self.r_s, self.E_s, self.w, x)[0]-normal_force)**2).sum(),
                                  bracket=(0.1*self.w/ran, 2*self.w/ran))
            cohesive_stress = opt.x

            residual = np.sqrt(((MD.load_and_displacement(np.sqrt(area/np.pi), self.r_s, self.E_s, self.w, cohesive_stress)[0]-normal_force)**2).mean())
            self.assertTrue(residual < 0.9)

if __name__ == '__main__':
    unittest.main()