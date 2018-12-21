#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
@file   AnalysisTest.py

@author Lars Pastewka <lars.pastewka@imtek.uni-freiburg.de>

@date   17 Dec 2018

@brief  Tests for PyCo analysis tools; power-spectral density,
        autocorrelation function and variable bandwidth analysis

@section LICENCE

Copyright 2018 Lars Pastewka

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import unittest
import numpy as np

from PyCo.Topography import UniformNumpyTopography, NonuniformNumpyTopography, InterpolatedTopography
from PyCo.Topography.Nonuniform.PowerSpectrum import sinc, dsinc, power_spectrum

from tests.PyCoTest import PyCoTestCase


class PowerSpectrumTest(PyCoTestCase):
    def test_uniform(self):
        for periodic in [True, False]:
            for L in [1.3, 10.6]:
                for k in [2, 4]:
                    for n in [16, 128]:
                        x = np.arange(n) * L / n
                        h = np.sin(2 * np.pi * k * x / L)
                        t = UniformNumpyTopography(h, size=(L,), periodic=periodic)
                        q, C = t.power_spectrum_1D()

                        # The ms height of the sine is 1/2. The sum over the PSD (from -q to +q) is the ms height.
                        # Our PSD only contains *half* of the full PSD (on the +q branch, the -q branch is identical),
                        # therefore the sum over it is 1/4.
                        self.assertAlmostEqual(C.sum() / L, 1 / 4)

                        if periodic:
                            # The value at the individual wavevector must also equal 1/4. This is only exactly true
                            # for the periodic case. In the nonperiodic, this is convolved with the Fourier transform
                            # of the window function.
                            C /= L
                            r = np.zeros_like(C)
                            r[k] = 1 / 4
                            self.assertArrayAlmostEqual(C, r)

    @unittest.skip
    def test_nonuniform_on_uniform_grid(self):
        for L in [1.3, 10.6]:
            for k in [4, 8]:
                for n in [64]:
                    x = np.arange(n + 1) * L / n
                    h = np.sin(2 * np.pi * k * x / L)
                    t = NonuniformNumpyTopography(x, h)
                    q, C = t.power_spectrum_1D()

                    print('nu', C.sum() / L)

                    pad = 16
                    i = InterpolatedTopography(t, np.linspace(0, pad*x.max(), 4096))
                    qi, Ci = i.power_spectrum_1D(window='None')

                    q, C = power_spectrum(*t.points(), q=qi, window='None')

                    import matplotlib.pyplot as plt
                    #plt.loglog(qi[1:], pad*Ci[1:], 'k-')
                    plt.loglog(q[1:len(q)//8], abs(C[1:len(q)//8]-pad*Ci[1:len(q)//8]), 'r-')
                    plt.show()

                    #import matplotlib.pyplot as plt
                    #plt.plot(*i.points(), 'kx-')
                    #plt.show()

                    print('interp', Ci.sum() / L)

                    self.assertArrayAlmostEqual(C[1:len(q)//16], pad*Ci[1:len(q)//16])

                    # The ms height of the sine is 1/2. The sum over the PSD (from -q to +q) is the ms height.
                    # Our PSD only contains *half* of the full PSD (on the +q branch, the -q branch is identical),
                    # therefore the sum over it is 1/4.
                    #self.assertAlmostEqual(C.sum() / L, 1 / 4, places=2)

    def test_sum_triangles_gives_square(self):
        for a, b in [#(2.3, 1.2, 1.7),
                        #(1.5, 3.1, 3.1),
                        (0.5, 1.0),
                        (0.5, 0.5)]:
            q = np.linspace(0, 2 * np.pi / a, 1001)
            x = np.array([-a, a])
            h = np.array([b, b])
            _, C1 = power_spectrum(x, h, q=q, window='None')

            x = np.array([-a, a])
            h = np.array([0, b])
            _, C1 = power_spectrum(x, h, q=q, window='None')



    def test_invariance(self):
        for a, b, c in [#(2.3, 1.2, 1.7),
                        #(1.5, 3.1, 3.1),
                        (0.5, 1.0, 1.0),
                        (0.5, -0.5, 0.5)]:
            q = np.linspace(0, 2*np.pi/a, 1001)

            x = np.array([-a, a])
            h = np.array([b, c])
            print(x, h)
            t = NonuniformNumpyTopography(x, h)
            _, C1 = power_spectrum(*t.points(), q=q, window='None')

            x = np.array([-a, 0, a])
            h = np.array([b, (b+c)/2, c])
            print(x, h)
            t = NonuniformNumpyTopography(x, h)
            _, C2 = power_spectrum(*t.points(), q=q, window='None')

            x = np.array([-a, 0, a/2, a])
            h = np.array([b, (b+c)/2, (3*c+b)/4, c])
            print(x, h)
            t = NonuniformNumpyTopography(x, h)
            _, C3 = power_spectrum(*t.points(), q=q, window='None')

            import matplotlib.pyplot as plt
            plt.plot(q[1:], C1[1:], 'k-')
            plt.plot(q[1:], C2[1:], 'r-')
            plt.plot(q[1:], C3[1:], 'b-')
            plt.show()

    @unittest.skip
    def test_triangle(self):
        a = 2.3
        b = 1.2
        x = np.array([-a, a])
        h = np.array([-b, b])
        t = NonuniformNumpyTopography(x, h)
        i = InterpolatedTopography(t, np.linspace(x.min(), x.max(), 1024))

        qi, Ci = i.power_spectrum_1D(window='None')
        q, C = power_spectrum(*t.points(), q=qi, window='None')

        import matplotlib.pyplot as plt
        plt.loglog(qi[1:], Ci[1:], 'k-')
        plt.loglog(q[1:], C[1:], 'r-')
        plt.show()

    def test_dsinc(self):
        self.assertAlmostEqual(dsinc(0), 0)
        self.assertAlmostEqual(dsinc(np.pi)*np.pi, -1)
        self.assertAlmostEqual(dsinc(2*np.pi)*np.pi, 1 / 2)
        self.assertAlmostEqual(dsinc(3*np.pi)*np.pi, -1 / 3)

        dx = 1e-9
        for x in [0, 0.5e-6, 1e-6, 0.5, 1]:
            v1 = sinc(x + dx)
            v2 = sinc(x - dx)
            self.assertAlmostEqual(dsinc(x), (v1 - v2) / (2 * dx), places=5, msg='x = {}'.format(x))
