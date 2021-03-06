from jax.config import config
config.update("jax_enable_x64", True)
import jax.numpy as np

from tqdm import tqdm

from GaussianProcess.utils import transform_data, data_checker
from GaussianProcess.kernel import GaussianRBFKernel
from GaussianProcess import GPR


class BayesOpt(object):
    """Bayesian Optimization based on Gaussian Process.
    Args:
        f (function): function to optimize.
        initial_input (array-like):
            Initial position for Bayesian optimization.
            array shape (n_samples, n_features) or (n_samples,).
            Feature vectors or other representations of training data (also required for prediction).

        acq (function): Acquisition function.

        acq_optim (function or baysianoptim acquisition_optimizer class):
            Optimizer when searching for the maximum value of the acquisition function.

        initial_Y (array-like): Defaults to None.
            Y must be the same size as the number of data in X.
            The i-th index of Y must correspond to the i-th index of X.
        kernel (function or baysianoptim kernel class, optional):
            Kernel used in Gaussian Process Regression. Defaults to GaussKernel(h=1,a=1).

        alpha (float, optional):
            Regularization parameter. Defaults to 1e-6.

        maximize (bool, optional):
            If True, optimize to maximum. Defaults to False.

    Attributes:
        param_history (array-like) : History of parameters.
        value_history (array-like) : History of values.
        best_params (array) : Maximum/minimum parameter in the search history.
        best_value (array) : Maximum/minimum value in the search history.
        gpr (class) : Result of GP with search value as learning target
        kernel (function) : Kernel used in GP.
        alpha (float) : Regularization parameter.
        maximization (bool) : If True, optimize to maximum.
        n_trial (int) : Number of searches.
        acq (function) : Acquisition function.
    """

    def __init__(self, f, initial_input, acq, acq_optim, initial_Y=None, kernel=None, alpha=1e-6, maximize=False, function_input_unpacking=True):

        self.__objectivefunction = f
        self.__initial_X = transform_data(initial_input)
        self.__function_unpack = function_input_unpacking
        self.__initial_Y = self.__calculate_initialY(initial_Y)
        data_checker(self.__initial_X, self.__initial_Y)
        self.__maximize = maximize

        # init GPR
        if kernel is None:
            kernel = GaussianRBFKernel(h=1.0, a=1.0)
        self.__kernel = kernel
        self.__alpha = alpha
        self.__gpr = GPR(X_train=self.__initial_X,
                         Y_train=self.__initial_Y,
                         alpha=self.__alpha,
                         kernel=self.__kernel)
        self.__X_history = []
        self.__Y_history = []

        # best params
        self.__best_value = None
        self.__best_params = None

        # init acquuisition function
        self.__acq = acq
        self.__acq_optimizer = acq_optim

    def __calculate_initialY(self, initial_Y):
        if initial_Y is None:
            iniY = []
            for iniX in self.__initial_X:
                if self.__function_unpack:
                    iniY.append(self.__objectivefunction(*iniX.T))  # unpack list (like [x1,x2,...,xd]) to x1,x2,...,xd for function inputs by using '*' operator.

                else:
                    iniY.append(self.__objectivefunction(np.atleast_2d(iniX)))
            return np.array(iniY)
        else:
            if initial_Y.shape[0] != self.__initial_X.shape[0]:
                raise ValueError('Y must be the same size as the number of data in X.')
            return transform_data(initial_Y)

    def run_optim(self, max_iter, terminate_function=None):
        '''Run baysian optimization.
        Args:
            max_iter (int): exploration horizon, or number of acquisitions.

            terminate_function (function, optional):
                A function that receives iteration and the history of input and output, and returns a bool that terminates iteration.
                Defaults to None.
                Example:
                    def terminate_function(it, param_history, value_history):
                        if value_history.min()<1e-1:
                            return True
                        else:
                            return False

        '''

        with tqdm(total=max_iter) as bar:
            for i in range(max_iter):
                loc, acq_val = self.__acq_optimizer(gpr=self.__gpr, acq=self.__acq, it=i)
                if self.__function_unpack:
                    Y_obs = self.__objectivefunction(*loc.T)  # unpack list (like [x1,x2,...,xd]) to x1,x2,...,xd for function inputs by using '*' operator.
                else:
                    Y_obs = self.__objectivefunction(np.atleast_2d(loc))
                self.__gpr.append_data(np.atleast_2d(loc), Y_obs)
                self.__X_history.append(loc)
                self.__Y_history.append(Y_obs)

                if self.__maximize:
                    if self.__best_value is None or Y_obs > self.__best_value:
                        self.__best_value = Y_obs
                        self.__best_params = loc
                else:
                    if self.__best_value is None or Y_obs < self.__best_value:
                        self.__best_value = Y_obs
                        self.__best_params = loc

                post_str = f'param:{loc}, value:{Y_obs}, current best param:{self.__best_params}, current best_value:{self.__best_value}'
                bar.set_description_str('BayesOpt')
                bar.set_postfix_str(post_str)
                bar.update()
                if (terminate_function is not None) and (terminate_function(i, self.__X_history, self.__Y_history)):
                    print(f'break iter:{i}, current best param:{self.__best_params}, current best_value:{self.__best_value}')
                    break

    @property
    def param_history(self):
        return np.array(self.__X_history)

    @property
    def value_history(self):
        return np.array(self.__Y_history)

    @property
    def best_params(self):
        return self.__best_params

    @property
    def best_value(self):
        return self.__best_value

    @property
    def gpr(self):
        return self.__gpr

    @property
    def kernel(self):
        return self.__kernel

    @property
    def alpha(self):
        return self.__alpha

    @property
    def maximization(self):
        return self.__maximize

    @property
    def n_trial(self):
        return len(self.__Y_history)

    @property
    def acq(self):
        return self.__acq
