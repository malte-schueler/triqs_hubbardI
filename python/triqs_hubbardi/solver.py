from pytriqs.gf import *
from pytriqs.atom_diag import *
from itertools import *
import numpy as np
from pytriqs.operators import Operator, c, c_dag, n

class Solver():
    
    def __init__(self, beta, gf_struct, n_iw=1025, n_tau=10001, n_l=30, n_w=500,w_min=-15,w_max=15,idelta=0.01):
        """
        Initialise the solver.
        Parameters
        ----------
        beta : scalar
               Inverse temperature.
        gf_struct : list of pairs [ (str,[int,...]), ...]
                    Structure of the Green's functions. It must be a
                    list of pairs, each containing the name of the
                    Green's function block as a string and a list of integer
                    indices.
                    For example: ``[ ('up', [0, 1, 2]), ('down', [0, 1, 2]) ]``.
        n_iw : integer, optional
               Number of Matsubara frequencies used for the Green's functions.
        n_tau : integer, optional
               Number of imaginary time points used for the Green's functions.
        """
        
        if isinstance(gf_struct,dict):
            print "WARNING: gf_struct should be a list of pairs [ (str,[int,...]), ...], not a dict"
            gf_struct = [ [k, v] for k, v in gf_struct.iteritems() ]
        
        g_w_list = []
        g_iw_list = []
        g_tau_list = []
        g_l_list = []

        name_list = [block for block, ind in gf_struct]
        for block, ind in gf_struct:
            g_w_list.append(GfReFreq(indices = ind, window = (w_min, w_max), n_points = n_w))
            g_iw_list.append(GfImFreq(indices = ind, beta = beta, n_points = n_iw))
            g_tau_list.append(GfImTime(indices = ind, beta = beta, n_points = n_tau))
            g_l_list.append(GfLegendre(indices = ind, beta = beta, n_points = n_l))
            
        self.G0_w = BlockGf(name_list = name_list, block_list = g_w_list)
        self.G0_iw = BlockGf(name_list = name_list, block_list = g_iw_list)
        self.G_tau = BlockGf(name_list = name_list, block_list = g_tau_list)        
        self.G_l = BlockGf(name_list = name_list, block_list = g_l_list)
        
        self.Sigma_iw = self.G0_iw.copy()
        self.Sigma_iw.zero()
        
        self.G_iw = self.G0_iw.copy()
        self.G_iw.zero()
        
        self.Sigma_w = self.G0_w.copy()
        self.Sigma_w.zero()
        
        self.G_w = self.G0_w.copy()
        self.G_w.zero()
        
        self.gf_struct = gf_struct
        
        self.n_iw = n_iw
        self.n_tau = n_tau
        self.n_l = n_l
        self.beta = beta
        
        self.n_w = n_w
        self.w_min = w_min
        self.w_max = w_max
        self.idelta = idelta
        
        self.fops = []
        for block, ind in gf_struct:
            for ii in ind:
                self.fops.append((block,ii))

        self.eal = dict()
        for block, ind in self.gf_struct:
            self.eal[block]= np.zeros((len(ind),len(ind)))
        
    def solve(self, **params_kw):
        """
        Solve the impurity problem: calculate G(iw) and Sigma(iw)
        Parameters
        ----------
        params_kw : dict {'param':value} that is passed to the core solver.
                     Two required :ref:`parameters <solve_parameters>` are
                        * `h_int` (:ref:`Operator object <triqslibs:operators>`): the local Hamiltonian of the impurity problem to be solved,
                        * `n_cycles` (int): number of measurements to be made.
                    Other parameters are 
                        * `calc_gtau` (bool): calculate G(tau)
                        * `calc_gw` (bool): calculate G(w) and Sigma(w)
                        * `calc_gl` (bool): calculate G(legendre)
                        * `calc_dm` (bool): calculate density matrix

        
        """

        
        
  
        h_int = params_kw['h_int']
        try:
            calc_gtau = params_kw['calc_gtau']
        except KeyError:
            calc_gtau = False
        
        try:
            calc_gw = params_kw['calc_gw']
        except KeyError:
            calc_gw = False

        try:
            calc_gl = params_kw['calc_gl']
        except KeyError:
            calc_gl = False

        try:
            calc_dm = params_kw['calc_dm']
        except KeyError:
            calc_dm = False
            
        Delta_iw = 0*self.G0_iw
        Delta_iw << iOmega_n
        Delta_iw -= inverse(self.G0_iw)

            
        for block, ind in self.gf_struct:
            a = Delta_iw[block].fit_tail()
            self.eal[block] = a[0][0]               
                
        G0_iw_F = 0*self.G_iw
        if calc_gw:
            G0_w_F = 0*self.G_w
        
        G0_iw_F << iOmega_n
        if calc_gw:
            G0_w_F << Omega
        
        for block, ind in self.gf_struct:
            G0_iw_F[block] -= self.eal[block]
            if calc_gw:
                G0_w_F[block] -= self.eal[block]
            
        G0_iw_F = inverse(G0_iw_F)
        if calc_gw:
            G0_w_F = inverse(G0_w_F)
        
        H_loc = 1.0*h_int
        for block, ind in self.gf_struct:
            for ii,ii_ind in enumerate(ind):
                for jj,jj_ind in enumerate(ind):
                    H_loc += self.eal[block][ii,jj]*c_dag(block,ii_ind)*c(block,jj_ind)

        self.ad = AtomDiag(H_loc, self.fops)
        
        self.G_iw = atomic_g_iw(self.ad, self.beta, self.gf_struct, self.n_iw )
        if calc_gw:
            self.G_w = atomic_g_w(self.ad, self.beta, self.gf_struct, (self.w_min,self.w_max), self.n_w, self.idelta)
        if calc_gtau:
            self.G_tau = atomic_g_tau(self.ad, self.beta, self.gf_struct, self.n_tau )
        if calc_gl:
            self.G_l = atomic_g_l(self.ad, self.beta, self.gf_struct, self.n_l )
        if calc_dm:
            self.dm = atomic_density_matrix(self.ad, self.beta)

        self.Sigma_iw = inverse(G0_iw_F) - inverse(self.G_iw)
        if calc_gw:
            self.Sigma_w = inverse(G0_w_F) - inverse(self.G_w)
