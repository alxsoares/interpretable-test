"""Module containing many types of two sample test algorithms"""

__author__ = "wittawat"

from abc import ABCMeta, abstractmethod
from freqopttest.data import TSTData
import matplotlib.pyplot as plt
import numpy as np
import freqopttest.util as util

import scipy.stats as stats
import theano
import theano.tensor as tensor
import theano.tensor.nlinalg as nlinalg
import theano.tensor.slinalg as slinalg

class TwoSampleTest(object):
    """Abstract class for two sample tests."""
    __metaclass__ = ABCMeta

    def __init__(self, alpha=0.01):
        """
        alpha: significance level of the test
        """
        self.alpha = alpha

    @abstractmethod
    def perform_test(self, tst_data):
        """perform the two-sample test and return values computed in a dictionary:
        {alpha: 0.01, pvalue: 0.0002, test_stat: 2.3, h0_rejected: True, ...}
        tst_data: an instance of TSTData
        """
        raise NotImplementedError()

    @abstractmethod
    def compute_stat(self, tst_data):
        """Compute the test statistic"""
        raise NotImplementedError()

    #@abstractmethod
    #def visual_test(self, tst_data):
    #    """Perform the test and plot the results. This is suitable for use 
    #    with IPython."""
    #    raise NotImplementedError()
    ##@abstractmethod
    #def pvalue(self):
    #   """Compute and return the p-value of the test"""
    #   raise NotImplementedError()

    #def h0_rejected(self):
    #    """Return true if the null hypothesis is rejected"""
    #    return self.pvalue() < self.alpha

class TSTFactory(object):
    """A factory to produce TwoSampleTest objects from string labels"""

    # MeanEmbeddingTest where the test_locs are drawn from a Gaussian fitted 
    # to the joint data x, y.
    MET_GAUSS = 'met_gauss'

    # MeanEmbeddingTest where test_locs are optimized

    def __init__(self):
        raise NotImplementedError('This factory cannot be instantiated.')

    @staticmethod
    def create(spec, tst_data):
        """tst_data: an instance of TSTData.  """ 
        pass


class HotellingT2Test(TwoSampleTest):
    """Two-sample test with Hotelling T-squared statistic.
    Techinical details follow "Applied Multivariate Analysis" of Neil H. Timm.
    See page 156.
    
    """
    def __init__(self, alpha=0.01):
        self.alpha = alpha 

    def perform_test(self, tst_data):
        """perform the two-sample test and return values computed in a dictionary:
        {alpha: 0.01, pvalue: 0.0002, test_stat: 2.3, h0_rejected: True, ...}
        tst_data: an instance of TSTData
        """
        d = tst_data.dim()
        chi2_stat = self.compute_stat(tst_data)
        pvalue = stats.chi2.sf(chi2_stat, d)
        alpha = self.alpha
        results = {'alpha': self.alpha, 'pvalue': pvalue, 'test_stat': chi2_stat,
                'h0_rejected': pvalue < alpha}
        return results

    def compute_stat(self, tst_data):
        """Compute the test statistic"""
        X, Y = tst_data.xy()
        #if X.shape[0] != Y.shape[0]:
        #    raise ValueError('Require nx = ny for now. Will improve if needed.')
        nx = X.shape[0]
        ny = Y.shape[0]
        mx = np.mean(X, 0)
        my = np.mean(Y, 0)
        mdiff = mx-my
        sx = np.cov(X.T)
        sy = np.cov(Y.T)
        s = sx/nx + sy/ny
        chi2_stat = np.linalg.solve(s, mdiff).dot(mdiff)
        return chi2_stat

class GammaMMDTest(TwoSampleTest):
    """MMD test by fitting a Gamma distribution to the test statistic (MMD^2) 
    The code is partially based on the code of Kacper Chwialkovski.
    """
    def __init__(self, kernel, alpha=0.01):
        """
        kernel: an instance of symmetric Kernel
        """
        self.alpha = alpha 
        self.kernel = kernel 

    def perform_test(self, tst_data):
        """perform the two-sample test and return values computed in a dictionary:
        {alpha: 0.01, pvalue: 0.0002, test_stat: 2.3, h0_rejected: True, ...}
        """
        X, Y = tst_data.xy()
        if X.shape[0] != Y.shape[0]:
            raise ValueError('Require sample size of X = size of Y')

        K = self.kernel.eval(X, X)
        L = self.kernel.eval(Y, Y)
        KL = self.kernel.eval(X, Y)

        n = X.shape[0]
        # test statistic
        test_stat = 1.0/n * np.sum(K + L - KL - KL.T)
        meanMMD = 2.0/n * (1.0 - 1.0/n*np.sum(np.diag(KL)))

        np.fill_diagonal(K, 0.0)
        np.fill_diagonal(L, 0.0)
        np.fill_diagonal(KL, 0.0)

        varMMD = 2.0/n/(n-1) * 1.0/n/(n-1) * np.sum((K + L - KL - KL.T)**2)
        # parameters of the fitted Gamma distribution
        al = meanMMD**2 / varMMD
        bet = varMMD*n / meanMMD
        pval = stats.gamma.sf(test_stat, al, scale=bet)
        results = {'alpha': self.alpha, 'pvalue': pval, 'test_stat': test_stat,
                'h0_rejected': pval < self.alpha}
        return results


    def compute_stat(self, tst_data):
        """Compute the test statistic"""
        raise NotImplementedError()

    def visual_test(self, tst_data):
        """Perform the test and plot the results. This is suitable for use 
        with IPython."""
        raise NotImplementedError()


class SmoothCFTest(TwoSampleTest):
    """Class for two-sample test using smooth characteristic functions.
    Use Gaussian kernel."""
    def __init__(self, test_freqs, gaussian_width, alpha=0.01):
        """
        :param test_freqs: J x d numpy array of J frequencies to test the difference
        gaussian_width: The width is used to divide the data. The test will be 
            equivalent if the data is divided beforehand and gaussian_width=1.
        """
        super(SmoothCFTest, self).__init__(alpha)
        self.test_freqs = test_freqs
        self.gaussian_width = gaussian_width

    @property
    def gaussian_width(self):
        # Gaussian width. Positive number.
        return self._gaussian_width
    
    @gaussian_width.setter
    def gaussian_width(self, width):
        if util.is_real_num(width) and float(width) > 0:
            self._gaussian_width = float(width)
        else:
            raise ValueError('gaussian_width must be a float > 0.')

    def compute_stat(self, tst_data):
        # test freqs or Gaussian width undefined 
        if self.test_freqs is None: 
            raise ValueError('test_freqs must be specified.')
        if self.gaussian_width is None:
            raise ValueError('gaussian_width > 0 must be specified.')

        X, Y = tst_data.xy()
        test_freqs = self.test_freqs
        gamma = self.gaussian_width
        n = X.shape[0]
        Z = SmoothCFTest.construct_z(X, Y, test_freqs, gamma)
        Sig = np.cov(Z.T)
        W = np.mean(Z, 0)
        # test statistic
        s = n*np.linalg.solve(Sig, W).dot(W)
        return s

    def perform_test(self, tst_data):
        """perform the two-sample test and return values computed in a dictionary:
        {alpha: 0.01, pvalue: 0.0002, test_stat: 2.3, h0_rejected: True, ...}
        tst_data: an instance of TSTData
        """
        stat = self.compute_stat(tst_data)
        J, d = self.test_freqs.shape
        # 2J degrees of freedom because of sin and cos
        pvalue = stats.chi2.sf(stat, 2*J)
        alpha = self.alpha
        results = {'alpha': self.alpha, 'pvalue': pvalue, 'test_stat': stat,
                'h0_rejected': pvalue < alpha}
        return results

    #def visual_test(self, tst_data):
    #    """Perform the test and plot the results. This is suitable for use 
    #    with IPython."""
    #    raise NotImplementedError()

    
    #---------------------------------

    @staticmethod
    def create_randn(tst_data, J, alpha=0.01, seed=19):
        """Create a SmoothCFTest whose test frequencies are drawn from 
        the standard Gaussian """

        rand_state = np.random.get_state()
        np.random.seed(seed)

        gamma = tst_data.mean_std()

        d = tst_data.dim()
        T = np.random.randn(J, d)
        np.random.set_state(rand_state)
        scf_randn = SmoothCFTest(T, gamma, alpha=alpha)
        return scf_randn

    @staticmethod 
    def construct_z(X, Y, test_freqs, gaussian_width):
        """Construct the features Z to be used for testing with T^2 statistics.
        Z is defined in Eq.14 of Chwialkovski et al., 2015 (NIPS). 

        test_freqs: J x d test frequencies
        
        Return a n x 2J numpy array. 2J because of sin and cos for each frequency.
        """
        if X.shape[0] != Y.shape[0]:
            raise ValueError('Sample size n must be the same for X and Y.')
        X = X/gaussian_width
        Y = Y/gaussian_width 
        n, d = X.shape
        J = test_freqs.shape[0]
        # inverse Fourier transform (upto scaling) of the unit-width Gaussian kernel 
        fx = np.exp(-np.sum(X**2, 1)/2)[:, np.newaxis]
        fy = np.exp(-np.sum(Y**2, 1)/2)[:, np.newaxis]
        # n x J
        x_freq = X.dot(test_freqs.T)
        y_freq = Y.dot(test_freqs.T)
        # zx: n x 2J
        zx = np.hstack((np.sin(x_freq)*fx, np.cos(x_freq)*fx))
        zy = np.hstack((np.sin(y_freq)*fy, np.cos(y_freq)*fy))
        z = zx-zy
        assert z.shape == (n, 2*J)
        return z

    @staticmethod 
    def construct_z_theano(Xth, Yth, Tth, gwidth_th):
        """Construct the features Z to be used for testing with T^2 statistics.
        Z is defined in Eq.14 of Chwialkovski et al., 2015 (NIPS). 
        Theano version.
        
        Return a n x 2J numpy array. 2J because of sin and cos for each frequency.
        """
        Xth = Xth/gwidth_th
        Yth = Yth/gwidth_th 
        # inverse Fourier transform (upto scaling) of the unit-width Gaussian kernel 
        fx = tensor.exp(-(Xth**2).sum(1)/2).reshape((-1, 1))
        fy = tensor.exp(-(Yth**2).sum(1)/2).reshape((-1, 1))
        # n x J
        x_freq = Xth.dot(Tth.T)
        y_freq = Yth.dot(Tth.T)
        # zx: n x 2J
        zx = tensor.concatenate([tensor.sin(x_freq)*fx, tensor.cos(x_freq)*fx], axis=1)
        zy = tensor.concatenate([tensor.sin(y_freq)*fy, tensor.cos(y_freq)*fy], axis=1)
        z = zx-zy
        return z

    @staticmethod
    def optimize_freqs_width(tst_data, n_test_freqs=10, max_iter=400,
            freqs_step_size=0.2, gwidth_step_size=0.01, batch_proportion=1.0,
            tol_fun=1e-3, seed=1):
        """Optimize the test frequencies and the Gaussian kernel width by 
        maximizing the test power. X, Y should not be the same data as used 
        in the actual test (i.e., should be a held-out set). 

        - max_iter: #gradient descent iterations
        - batch_proportion: (0,1] value to be multipled with nx giving the batch 
            size in stochastic gradient. 1 = full gradient ascent.
        - tol_fun: termination tolerance of the objective value
        
        Return (test_freqs, gaussian_width, info)
        """
        J = n_test_freqs
        """
        Optimize the empirical version of Lambda(T) i.e., the criterion used 
        to optimize the test locations, for the test based 
        on difference of mean embeddings with Gaussian kernel. 
        Also optimize the Gaussian width.

        :return a theano function T |-> Lambda(T)
        """
        d = tst_data.dim()
        # set the seed
        rand_state = np.random.get_state()
        np.random.seed(seed)

        # draw frequencies randomly from the standard Gaussian. 
        # TODO: Can we do better?
        T0 = np.random.randn(J, d)
        # reset the seed back to the original
        np.random.set_state(rand_state)

        func_z = SmoothCFTest.construct_z_theano
        # info = optimization info 
        T, gamma, info = optimize_T_gaussian_width(tst_data, T0, func_z, 
                max_iter=max_iter, T_step_size=freqs_step_size, 
                gwidth_step_size=gwidth_step_size, batch_proportion=batch_proportion,
                tol_fun=tol_fun)

        ninfo = {'test_freqs': info['Ts'], 'test_freqs0': info['T0'], 
                'gwidths': info['gwidths'], 'obj_values': info['obj_values']}
        return (T, gamma, ninfo  )

    @staticmethod
    def optimize_gwidth(tst_data, T, max_iter=400, 
            gwidth_step_size=0.1, batch_proportion=1.0, tol_fun=1e-3):
        """Optimize the Gaussian kernel width by 
        maximizing the test power, fixing the test frequencies to T. X, Y should
        not be the same data as used in the actual test (i.e., should be a
        held-out set). 

        - max_iter: #gradient descent iterations
        - batch_proportion: (0,1] value to be multipled with nx giving the batch 
            size in stochastic gradient. 1 = full gradient ascent.
        - tol_fun: termination tolerance of the objective value
        
        Return (gaussian_width, info)
        """

        func_z = SmoothCFTest.construct_z_theano
        # info = optimization info 
        gamma, info = optimize_gaussian_width(tst_data, T, func_z, 
                max_iter=max_iter, gwidth_step_size=gwidth_step_size,
                batch_proportion=batch_proportion, tol_fun=tol_fun)

        ninfo = {'test_freqs': T, 'gwidths': info['gwidths'], 'obj_values':
                info['obj_values']}
        return ( gamma, ninfo  )

class MeanEmbeddingTest(TwoSampleTest):
    """Class for two-sample test using squared difference of mean embeddings. 
    Use Gaussian kernel."""

    def __init__(self, test_locs, gaussian_width, alpha=0.01):
        """
        :param test_locs: J x d numpy array of J locations to test the difference
        gaussian_width: The width is used to divide the data. The test will be 
            equivalent if the data is divided beforehand and gaussian_width=1.
        """
        super(MeanEmbeddingTest, self).__init__(alpha)

        self.test_locs = test_locs
        self.gaussian_width = gaussian_width

    @property
    def gaussian_width(self):
        # Gaussian width. Positive number.
        return self._gaussian_width
    
    @gaussian_width.setter
    def gaussian_width(self, width):
        if util.is_real_num(width) and float(width) > 0:
            self._gaussian_width = float(width)
        else:
            raise ValueError('gaussian_width must be a float > 0. Was %s'%(str(width)))

    def perform_test(self, tst_data):
        stat = self.compute_stat(tst_data)
        J, d = self.test_locs.shape
        pvalue = stats.chi2.sf(stat, J)
        alpha = self.alpha
        results = {'alpha': self.alpha, 'pvalue': pvalue, 'test_stat': stat,
                'h0_rejected': pvalue < alpha}
        return results

    def compute_stat(self, tst_data):
        # test locations or Gaussian width undefined 
        if self.test_locs is None: 
            raise ValueError('test_locs must be specified.')
        if self.gaussian_width is None:
            raise ValueError('gaussian_width > 0 must be specified.')

        X, Y = tst_data.xy()
        test_locs = self.test_locs
        gamma = self.gaussian_width
        n = X.shape[0]
        g = MeanEmbeddingTest.asym_gauss_kernel(X, test_locs, gamma)
        h = MeanEmbeddingTest.asym_gauss_kernel(Y, test_locs, gamma)
        Z = g-h
        Sig = np.cov(Z.T)
        W = np.mean(Z, 0)
        # test statistic
        s = n*np.linalg.solve(Sig, W).dot(W)
        return s

    def visual_test(self, tst_data):
        results = self.perform_test(tst_data)
        s = results['test_stat']
        pval = results['pvalue']
        J = self.test_locs.shape[0]
        domain = np.linspace(stats.chi2.ppf(0.001, J), stats.chi2.ppf(0.9999, J), 200)
        plt.plot(domain, stats.chi2.pdf(domain, J), label='$\chi^2$ (df=%d)'%J)
        plt.stem([s], [stats.chi2.pdf(J, J)/2], 'or-', label='test stat')
        plt.legend(loc='best', frameon=True)
        plt.title('%s. p-val: %.3g. stat: %.3g'%(type(self).__name__, pval, s))
        plt.show()
    #===============================

    @staticmethod 
    def construct_z_theano(Xth, Yth, T, gaussian_width):
        """Construct the features Z to be used for testing with T^2 statistics.
        Z is defined in Eq.12 of Chwialkovski et al., 2015 (NIPS). 

        T: J x d test locations
        
        Return a n x J numpy array. 
        """
        g = MeanEmbeddingTest.asym_gauss_kernel_theano(Xth, T, gaussian_width)
        h = MeanEmbeddingTest.asym_gauss_kernel_theano(Yth, T, gaussian_width)
        # Z: nx x J
        Z = g-h
        return Z

    @staticmethod
    def asym_gauss_kernel_theano(X, test_locs, gamma):
        """Asymmetric kernel for the two sample test. Theano version.
        :return kernel matrix X.shape[0] x test_locs.shape[0]
        """
        T = test_locs
        n, d = X.shape
        X = X/gamma

        D2 = (X**2).sum(1).reshape((-1, 1)) - 2*X.dot(T.T) + tensor.sum(T**2, 1).reshape((1, -1))
        K = tensor.exp(-D2)
        return K

    @staticmethod
    def create_fit_gauss_heuristic(tst_data, n_test_locs, alpha=0.01, seed=1):
        """Construct a MeanEmbeddingTest where test_locs are drawn from a Gaussian
        fitted to the data x, y.          
        """
        rand_state = np.random.get_state()
        np.random.seed(seed)
        # fit a Gaussian in the middle of X, Y and draw sample to initialize T
        X, Y = tst_data.xy()
        xy = np.vstack((X, Y))
        mean_xy = np.mean(xy, 0)
        cov_xy = np.cov(xy.T)
        if cov_xy.ndim == 0:
            # 1d dataset. 
            cov_xy = np.array([[cov_xy]])
        T = np.random.multivariate_normal(mean_xy, cov_xy, n_test_locs)
        # Gaussian (asymmetric) kernel width is set to the average standard
        # deviations of x, y
        stdx = np.mean(np.std(X, 0))
        stdy = np.mean(np.std(Y, 0))
        gamma = (stdx + stdy)/2.0
        
        met = MeanEmbeddingTest(test_locs=T, gaussian_width=gamma, alpha=alpha)
        np.random.set_state(rand_state)
        return met

    @staticmethod
    def optimize_locs_width(tst_data, n_test_locs=10, max_iter=400, 
            locs_step_size=0.1, gwidth_step_size=0.01, batch_proportion=1.0, 
            tol_fun=1e-3, seed=1):
        """Optimize the test locations and the Gaussian kernel width by 
        maximizing the test power. X, Y should not be the same data as used 
        in the actual test (i.e., should be a held-out set). 

        - max_iter: #gradient descent iterations
        - batch_proportion: (0,1] value to be multipled with nx giving the batch 
            size in stochastic gradient. 1 = full gradient ascent.
        - tol_fun: termination tolerance of the objective value
        
        Return (test_locs, gaussian_width, info)
        """
        J = n_test_locs
        """
        Optimize the empirical version of Lambda(T) i.e., the criterion used 
        to optimize the test locations, for the test based 
        on difference of mean embeddings with Gaussian kernel. 
        Also optimize the Gaussian width.

        :return a theano function T |-> Lambda(T)
        """

        T0 = MeanEmbeddingTest.init_locs_randn(tst_data, n_test_locs, seed=seed)
        func_z = MeanEmbeddingTest.construct_z_theano
        # info = optimization info 
        T, gamma, info = optimize_T_gaussian_width(tst_data, T0, func_z, 
                max_iter=max_iter, T_step_size=locs_step_size, 
                gwidth_step_size=gwidth_step_size, batch_proportion=batch_proportion,
                tol_fun=tol_fun)

        ninfo = {'test_locs': info['Ts'], 'test_locs0': info['T0'], 
                'gwidths': info['gwidths'], 'obj_values': info['obj_values']}
        return (T, gamma, ninfo  )

    @staticmethod 
    def init_locs_randn(tst_data, n_test_locs, seed=1):
        """Fit a Gaussian to the merged data of the two samples and draw 
        n_test_locs points from the Gaussian"""
        # set the seed
        rand_state = np.random.get_state()
        np.random.seed(seed)

        X, Y = tst_data.xy()
        # fit a Gaussian in the middle of X, Y and draw sample to initialize T
        xy = np.vstack((X, Y))
        mean_xy = np.mean(xy, 0)
        cov_xy = np.cov(xy.T)
        T0 = np.random.multivariate_normal(mean_xy, cov_xy, n_test_locs)
        # reset the seed back to the original
        np.random.set_state(rand_state)
        return T0

    @staticmethod
    def optimize_gwidth(tst_data, T, max_iter=400, 
            gwidth_step_size=0.1, batch_proportion=1.0, tol_fun=1e-3):
        """Optimize the Gaussian kernel width by 
        maximizing the test power, fixing the test locations to T. X, Y should
        not be the same data as used in the actual test (i.e., should be a
        held-out set). 

        - max_iter: #gradient descent iterations
        - batch_proportion: (0,1] value to be multipled with nx giving the batch 
            size in stochastic gradient. 1 = full gradient ascent.
        - tol_fun: termination tolerance of the objective value
        
        Return (gaussian_width, info)
        """

        func_z = MeanEmbeddingTest.construct_z_theano
        # info = optimization info 
        gamma, info = optimize_gaussian_width(tst_data, T, func_z, 
                max_iter=max_iter, gwidth_step_size=gwidth_step_size,
                batch_proportion=batch_proportion, tol_fun=tol_fun)

        ninfo = {'test_locs': T, 'gwidths': info['gwidths'], 'obj_values':
                info['obj_values']}
        return ( gamma, ninfo  )


    @staticmethod
    def asym_gauss_kernel(X, test_locs, gamma):
        """Compute a X.shape[0] x test_locs.shape[0] Gaussian kernel matrix where
        the Gaussian width gamma will divide only the data X (not test_locs).
        This is defined as in Chwialkovski, 2015 (NIPS)
        """
        n, d = X.shape
        X = X/gamma
        D2 = np.sum(X**2, 1)[:, np.newaxis] - 2*X.dot(test_locs.T) + np.sum(test_locs**2, 1)
        K = np.exp(-D2)
        return K

    @staticmethod
    def heu_3gauss_test_locs(J):
        """Draw J test locations with a heuristic.
        The heuristic is to fit a Gaussian to each sample, and another Gaussian 
        in the center of the two. Then, draw test locations from the three Gaussians.
        """
        pass

# Used by SmoothCFTest and MeanEmbeddingTest
def optimize_gaussian_width(tst_data, T, func_z, max_iter=400, 
        gwidth_step_size=0.1, batch_proportion=1.0, 
        tol_fun=1e-3 ):
    """Optimize the Gaussian kernel width by maximizing the test power.
    This does the same thing as optimize_T_gaussian_width() without optimizing 
    T (T = test locations / test frequencies).

    Return (optimized Gaussian width, info)
    """

    X, Y = tst_data.xy()
    nx, d = X.shape
    # initialize Theano variables
    Tth = theano.shared(T, name='T')
    Xth = tensor.dmatrix('X')
    Yth = tensor.dmatrix('Y')
    it = theano.shared(1, name='iter')
    # square root of the Gaussian width. Use square root to handle the 
    # positivity constraint by squaring it later.
    gamma_sq_init = 1e-4 + tst_data.mean_std()**0.5
    gamma_sq_th = theano.shared(gamma_sq_init, name='gamma')

    #sqr(x) = x^2
    Z = func_z(Xth, Yth, Tth, tensor.sqr(gamma_sq_th))
    W = Z.sum(axis=0)/nx
    # covariance 
    Z0 = Z - W
    Sig = Z0.T.dot(Z0)/nx

    # gradient computation does not support solve()
    #s = slinalg.solve(Sig, W).dot(nx*W)
    s = nlinalg.matrix_inverse(Sig).dot(W).dot(W)*nx
    gra_gamma_sq = tensor.grad(s, gamma_sq_th)
    step_pow = 0.5
    max_gam_sq_step = 1.0
    func = theano.function(inputs=[Xth, Yth], outputs=s, 
           updates=[
              (it, it+1), 
              #(gamma_sq_th, gamma_sq_th+gwidth_step_size*gra_gamma_sq\
              #        /it**step_pow/tensor.sum(gra_gamma_sq**2)**0.5 ) 
              (gamma_sq_th, gamma_sq_th+gwidth_step_size*tensor.sgn(gra_gamma_sq) \
                      *tensor.minimum(tensor.abs_(gra_gamma_sq), max_gam_sq_step) \
                      /it**step_pow) 
              ] 
           )
    # //////// run gradient ascent //////////////
    S = np.zeros(max_iter)
    gams = np.zeros(max_iter)
    for t in range(max_iter):
        # stochastic gradient ascent
        ind = np.random.choice(nx, min(int(batch_proportion*nx), nx), replace=False)
        # record objective values 
        S[t] = func(X[ind, :], Y[ind, :])
        gams[t] = gamma_sq_th.get_value()**2

        # check the change of the objective values 
        if t >= 2 and abs(S[t]-S[t-1]) <= tol_fun:
            break

    S = S[:t]
    gams = gams[:t]

    # optimization info 
    info = {'T': T, 'gwidths': gams, 'obj_values': S}
    return (gams[-1], info  )




# Used by SmoothCFTest and MeanEmbeddingTest
def optimize_T_gaussian_width(tst_data, T0, func_z, max_iter=400, 
        T_step_size=0.05, gwidth_step_size=0.01, batch_proportion=1.0, 
        tol_fun=1e-3 ):
    """Optimize the T (test locations for MeanEmbeddingTest, frequencies for 
    SmoothCFTest) and the Gaussian kernel width by 
    maximizing the test power. X, Y should not be the same data as used 
    in the actual test (i.e., should be a held-out set). 
    Optimize the empirical version of Lambda(T) i.e., the criterion used 
    to optimize the test locations.

    - T0: Jxd numpy array. initial value of T,  where
      J = the number of test locations/frequencies
    - func_z: function that works on Theano variables 
        to construct features to be used for the T^2 test. 
        (X, Y, T, gaussian_width) |-> n x J'
    - max_iter: #gradient descent iterations
    - batch_proportion: (0,1] value to be multipled with nx giving the batch 
        size in stochastic gradient. 1 = full gradient ascent.
    - tol_fun: termination tolerance of the objective value
    
    Return (test_locs, gaussian_width, info)
    """

    X, Y = tst_data.xy()
    nx, d = X.shape
    # initialize Theano variables
    T = theano.shared(T0, name='T')
    Xth = tensor.dmatrix('X')
    Yth = tensor.dmatrix('Y')
    it = theano.shared(1, name='iter')
    # square root of the Gaussian width. Use square root to handle the 
    # positivity constraint by squaring it later.
    gamma_sq_init = 1e-4 + tst_data.mean_std()**0.5
    gamma_sq_th = theano.shared(gamma_sq_init, name='gamma')

    #sqr(x) = x^2
    Z = func_z(Xth, Yth, T, tensor.sqr(gamma_sq_th))
    W = Z.sum(axis=0)/nx
    # covariance 
    Z0 = Z - W
    Sig = Z0.T.dot(Z0)/nx

    # gradient computation does not support solve()
    #s = slinalg.solve(Sig, W).dot(nx*W)
    s = nlinalg.matrix_inverse(Sig).dot(W).dot(W)*nx
    gra_T, gra_gamma_sq = tensor.grad(s, [T, gamma_sq_th])
    step_pow = 0.5
    max_gam_sq_step = 1.0
    func = theano.function(inputs=[Xth, Yth], outputs=s, 
           updates=[
              (T, T+T_step_size*gra_T/it**step_pow/tensor.sum(gra_T**2)**0.5 ), 
              (it, it+1), 
              #(gamma_sq_th, gamma_sq_th+gwidth_step_size*gra_gamma_sq\
              #        /it**step_pow/tensor.sum(gra_gamma_sq**2)**0.5 ) 
              (gamma_sq_th, gamma_sq_th+gwidth_step_size*tensor.sgn(gra_gamma_sq) \
                      *tensor.minimum(tensor.abs_(gra_gamma_sq), max_gam_sq_step) \
                      /it**step_pow) 
              ] 
           )
           #updates=[(T, T+T_step_size*gra_T), (it, it+1), 
           #    (gamma_sq_th, gamma_sq_th+gwidth_step_size*gra_gamma_sq) ] )
                           #updates=[(T, T+0.1*gra_T), (it, it+1) ] )

    # //////// run gradient ascent //////////////
    S = np.zeros(max_iter)
    J = T0.shape[0]
    Ts = np.zeros((max_iter, J, d))
    gams = np.zeros(max_iter)
    for t in range(max_iter):
        # stochastic gradient ascent
        ind = np.random.choice(nx, min(int(batch_proportion*nx), nx), replace=False)
        # record objective values 
        try:
            S[t] = func(X[ind, :], Y[ind, :])
        except: 
            print 'Exception occurred during gradient descent. Stop optimization.'
            import traceback as tb 
            tb.print_exc()
            t = t -1
            break

        Ts[t] = T.get_value()
        gams[t] = gamma_sq_th.get_value()**2

        # check the change of the objective values 
        if t >= 2 and abs(S[t]-S[t-1]) <= tol_fun:
            break

    S = S[:t+1]
    Ts = Ts[:t+1]
    gams = gams[:t+1]

    # optimization info 
    info = {'Ts': Ts, 'T0':T0, 'gwidths': gams, 'obj_values': S}
    return (Ts[-1], gams[-1], info  )


