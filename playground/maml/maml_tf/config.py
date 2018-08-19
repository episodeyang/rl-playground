import multiprocessing
from params_proto import cli_parse, Proto

ALLOWED_ALGS = "rl_algs.PPO", "rl_algs.VPG", "PPO", "VPG"
DIR_TEMPLATE = "{now:%Y-%m-%d}/" \
               "{G.run_mode}-{G.env_name}-n_grad({G.n_grad_steps})" \
               "-{G.inner_alg}-{G.inner_optimizer}" \
               "-{G.meta_alg}-{G.meta_optimizer}-alpha({G.alpha})-beta({G.beta})" \
               "-n_graphs({G.n_graphs})-env_norm({G.normalize_env})" \
               "-grad_norm({G.inner_max_grad_norm})-meta_grad_norm({G.meta_max_grad_norm})-{now:%H%M%S}-{now:%f}"

from datetime import datetime

now = datetime.now()


@cli_parse
class RUN:
    log_dir = "http://54.71.92.65:8081"
    log_prefix = 'maml-debug'


def config_run(**_G):
    G.update(_G)
    from datetime import datetime
    now = datetime.now()
    RUN.log_prefix = DIR_TEMPLATE.format(now=now, G=G)


# decorator help generate a as command line parser.
@cli_parse
class G:
    term_reward_threshold = -8000.0
    run_mode = "maml"  # type:  "Choose between maml and e_maml. Switches the loss function used for training"
    # env_name = 'HalfCheetah-v2'  # type:  "Name of the task environment"
    env_name = 'HalfCheetahGoalDir-v0'  # type:  "Name of the task environment"
    start_seed = Proto(0, help="seed for initialization of each game")
    render = False
    n_cpu = multiprocessing.cpu_count()  # type: "number of threads used"
    # Note: (E_)MAML Training Parameters
    n_tasks = Proto(20, help="40 for locomotion, 20 for 2D navigation ref:cbfinn")
    n_graphs = Proto(1, help="number of parallel graphs for multi-device parallelism. Hard coded to 1 atm.")
    n_grad_steps = 1  # type:  "number of gradient descent steps for the worker." #TODO change back to 1
    eval_grad_steps = Proto(list(range(n_grad_steps + 1)),
                            help="the gradient steps at which we evaluate the policy. Used "
                                 "to make pretty plots.")
    n_epochs = 800  # type:  "Number of epochs"
    # 40k per task (action, state) tuples, or 20k (per task) if you have 10/20 meta tasks
    n_parallel_envs = 40  # type:  "Number of parallel envs in minibatch. The SubprocVecEnv batch_size."
    batch_timesteps = 100  # type:  "max_steps for each episode, used to set env._max_steps parameter"
    env_max_timesteps = Proto(0, help="max_steps for each episode, used to set env._max_steps parameter. 0 to use "
                                      "gym default.")
    single_sampling = 0  # type:  "flag for running a single sampling step. 1 ON, 0 OFF"
    baseline = Proto('linear', help="using the critic as the baseline")
    meta_sgd = Proto(False, help="NOT YET IMPLEMENTED. Learn a gradient for each parameter")
    # Note: MAML Options
    first_order = Proto(True, help="Whether to stop gradient calculation during meta-gradient calculation")
    alpha = 0.05  # type:  "worker learning rate. use 0.1 for first step, 0.05 afterward ref:cbfinn"
    beta = 0.01  # type:  "meta learning rate"
    inner_alg = "VPG"  # type:  '"PPO" or "VPG", "rl_algs.VPG" or "rl_algs.PPO" for rl_algs baselines'
    inner_optimizer = "SGD"  # type:  '"Adam" or "SGD"'
    meta_alg = "PPO"  # type:  "PPO or TRPO, TRPO is not yet implemented."
    meta_optimizer = "Adam"  # type:  '"Adam" or "SGD"'
    activation = "tanh"
    hidden_size = 64  # type: "hidden size for the MLP policy"
    # Model options
    normalize_env = False  # type: "normalize the environment"
    vf_coef = 0.5  # type:  "loss weighing coefficient for the value function loss. with the VPG loss being 1.0"
    ent_coef = 0.01  # type:  "PPO entropy coefficient"
    max_grad_norm = 1.0  # type:  "PPO maximum gradient norm"
    clip_range = 0.2  # type:  "PPO clip_range parameter"
    # GAE runner options
    gamma = 0.99  # type:  "GAE gamma"
    lam = 0.95  # type:  "GAE lambda"
    # Grid World config parameters
    change_colors = 0  # type:  "shuffle colors of the board game"
    change_dynamics = 0  # type:  'shuffle control actions (up down, left right) of the game'


@cli_parse
class Reporting:
    report_mean = False  # type:  "plot the mean instead of the total reward per episode"
    log_device_placement = False


@cli_parse
class DEBUG:
    """To debug:
    Set debug_params = 1,
    set debug_apply_gradient = 1.
    Then the gradient ratios between the worker and the meta runner should be print out, and they should be 1.
    Otherwise, the runner model is diverging from the meta network.
    """
    no_weight_reset = 0  # type:  "flag to turn off the caching and resetting the weights"
    no_task_resample = 0  # type:  "by-pass task re-sample"
