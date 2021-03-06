import numpy as np

from .base import Baseline
from rllab.regressors.gaussian_mlp_regressor import GaussianMLPRegressor


class GaussianMLPBaseline(Baseline):
    def __init__(self, env_spec, subsample_factor=1., num_seq_inputs=1, regressor_args=None, ):
        self._subsample_factor = subsample_factor
        if regressor_args is None:
            regressor_args = dict()

        self._regressor = GaussianMLPRegressor(
            input_shape=(env_spec.observation_space.flat_dim * num_seq_inputs,),
            output_dim=1,
            name="vf",
            **regressor_args
        )

    def fit(self, paths):
        # --
        # Subsample before fitting.
        if self._subsample_factor < 1:
            lst_rnd_idx = []
            for path in paths:
                # Subsample index
                path_len = len(path['returns'])
                rnd_idx = np.random.choice(path_len, int(np.ceil(path_len * self._subsample_factor)),
                                           replace=False)
                lst_rnd_idx.append(rnd_idx)
            observations = np.concatenate([p["obs"][idx] for p, idx in zip(paths, lst_rnd_idx)])
            returns = np.concatenate([p["returns"][idx] for p, idx in zip(paths, lst_rnd_idx)])
        else:
            observations = np.concatenate([p["obs"] for p in paths])
            returns = np.concatenate([p["returns"] for p in paths])
        self._regressor.fit(observations, returns.reshape((-1, 1)))

    def predict(self, path):
        return self._regressor.predict(path["obs"]).flatten()

    def get_param_values(self, **tags):
        return self._regressor.get_param_values(**tags)

    def set_param_values(self, flattened_params, **tags):
        self._regressor.set_param_values(flattened_params, **tags)
