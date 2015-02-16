#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#
# @file   common.py
#
# @author Till Junge <till.junge@kit.edu>
#
# @date   11 Feb 2015
#
# @brief  Bin for small common helper function and classes
#
# @section LICENCE
#
#  Copyright (C) 2015 Till Junge
#
# PyPyContact is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation, either version 3, or (at
# your option) any later version.
#
# PyPyContact is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GNU Emacs; see the file COPYING. If not, write to the
# Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.
#

import numpy as np

def compare_containers(x, y):
    """
    compares whether two containers have the same content regardless of their
    type. eg, compares [1, 2, 3] and (1, 2., 3.) as True
    Keyword Arguments:
    x -- 
    y -- 
    """
    if x != y:
        try:
            if not len(x) == len(y): return False
            for xitem, yitem in zip(x, y):
                if not xitem == yitem: return False
        except Exception:
            return False
    return True

def evaluate_gradient(fun, x, delta):
    """
    Don't actually use this function in production code, it's not efficient.
    Returns an approximation of the gradient evaluated using central
    differences.

    (grad f)_i = ((f(x+e_i*delta/2)-f(x-e_i*delta/2))/delta)

    Arguments:
    fun   -- function to be evaluated
    x     -- point of evaluation
    delta -- step width
    """
    x = np.array(x)
    grad = np.zeros_like(x).reshape(-1)
    for i, coord in enumerate(x.reshape(-1)):
        x_plus      = x.copy().reshape(-1)
        x_plus[i]  += .5*delta
        x_minus     = x.copy().reshape(-1)
        x_minus[i] -= .5*delta
        grad[i] = (fun(x_plus.reshape(x.shape))-fun(x_minus.reshape(x.shape)))/delta
    grad.shape = x.shape
    return grad

def mean_err(arr1, arr2):
    return abs(np.ravel(arr1-arr2)).mean()
