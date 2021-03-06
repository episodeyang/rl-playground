import copy
import os
import sys
from params_proto import cli_parse, Proto
from tqdm import trange, tnrange
import torch as t
import torch.nn as nn
import torch.nn.init as init
from ml_logger import logger
from moleskin import moleskin as M

if 'IPython' in sys.modules and 'pydev_ipython' not in sys.modules:
    trange = tnrange


class RNN(nn.Module):
    is_recurrent = True  # used by comp_loss to roll out over samples.

    def __init__(self, input_n, output_n, optimizer="SGD", meta_optimizer="SGD", **_):
        super(RNN, self).__init__()
        self.add_module('model', nn.Sequential(
            nn.Linear(input_n, 40),
            nn.ReLU(),
            nn.Linear(40, 40),
            nn.ReLU(),
            nn.Linear(40, output_n), ), )
        self.reset_parameters()
        if optimizer is not None:
            self.optimizer = getattr(t.optim, optimizer)(self.parameters(), lr=1e-2)
        if meta_optimizer is not None:
            self.meta_optimizer = getattr(t.optim, meta_optimizer)(self.parameters(), lr=1e-2)

    def criteria(self, x, target):
        """Mean-Square Error"""
        return t.mean((x - target) ** 2)

    def gradients(self):
        """generator for parameter gradients """
        for p in self.parameters():
            yield p.grad

    @staticmethod
    def _weight_init(m):
        if isinstance(m, nn.Linear):
            init.xavier_normal_(m.weight)
            init.uniform_(m.bias)

    def reset_parameters(self):
        self.apply(self._weight_init)

    def forward(self, *args):
        return self.model(*args)

    def step(self, lr=None):
        if lr is not None:
            self.optimizer.param_groups[0]['lr'] = lr
        self.optimizer.step()

    def meta_step(self, lr=None):
        if lr is not None:
            self.meta_optimizer.param_groups[0]['lr'] = lr
        self.meta_optimizer.step()


class MLP(nn.Module):
    def __init__(self, input_n, output_n, optimizer="SGD", meta_optimizer="SGD", **_):
        super(MLP, self).__init__()
        self.add_module('model', nn.Sequential(
            nn.Linear(input_n, 40),
            nn.ReLU(),
            nn.Linear(40, 40),
            nn.ReLU(),
            nn.Linear(40, output_n), ), )
        self.reset_parameters()
        if optimizer is not None:
            self.optimizer = getattr(t.optim, optimizer)(self.parameters(), lr=1e-2)
        if meta_optimizer is not None:
            self.meta_optimizer = getattr(t.optim, meta_optimizer)(self.parameters(), lr=1e-2)

    def criteria(self, x, target):
        """Mean-Square Error"""
        return t.mean((x - target) ** 2)

    def gradients(self):
        """generator for parameter gradients """
        for p in self.parameters():
            yield p.grad

    @staticmethod
    def _weight_init(m):
        if isinstance(m, nn.Linear):
            init.xavier_normal_(m.weight)
            init.uniform_(m.bias)

    def reset_parameters(self):
        self.apply(self._weight_init)

    def forward(self, *args):
        return self.model(*args)

    def step(self, lr=None):
        if lr is not None:
            self.optimizer.param_groups[0]['lr'] = lr
        self.optimizer.step()

    def meta_step(self, lr=None):
        if lr is not None:
            self.meta_optimizer.param_groups[0]['lr'] = lr
        self.meta_optimizer.step()


Model = MLP  # make the code standard

from collections import defaultdict, deque


@M.timeit
def regular_sgd_baseline(model, Task, n_epochs, batch_n, k_shot=100, **_):
    problem = Task()
    # simple gradient descent
    for ep_ind in trange(n_epochs, desc="Epochs", ncols=50, leave=False):
        loss = 0
        for _ in range(batch_n):
            xs, ys = problem.samples(k_shot)
            output = model(t.tensor(xs).unsqueeze(dim=-1))
            targets = t.tensor(ys).unsqueeze(dim=-1)
            loss += model.criteria(output, targets)

        loss /= batch_n

        model.zero_grad()
        loss.backward()
        model.step(lr=G.alpha)

        logger.log(ep_ind, loss=loss.item())

        if ep_ind % 100 == 0 or ep_ind == (n_epochs - 1):
            pass
            # plot(ep_ind, problem, model, logger, **rest)
    # plot(ep_ind, problem, model, logger, save_as=final_figure if final_figure else None, **rest)


from datetime import datetime

now = datetime.now()


@cli_parse
class G:
    plot_interval = 10
    log_dir = os.path.realpath('./outputs')
    log_prefix = f"{now:%Y-%m-%d}/maml_torch/local-debug"
    seed = 0
    # model parameters
    input_n = 1
    output_n = 1
    optimizer = 'SGD'  # currently not used. Hard coded inner optimizer.
    meta_optimizer = 'Adam'
    # maml parameters
    npts = Proto(100, help="the number of datapoints in the generated dataset")
    n_epochs = 8000
    task_batch_n = 40
    k_shot = 5
    n_gradient_steps = 1
    test_grad_steps = [1]
    save_interval = 100
    test_interval = 1
    alpha = 0.001
    beta = 1e-3
    # aws run configs
    # mode = "spot"
    # spot_price = Proto(0.472, help="set to use on-demand machines")
    # use_gpu = True
    # docker_image = f"ufoym/deepo{':cpu' if not use_gpu else ''}"
    # instance_type = "p2.xlarge" if use_gpu else "c4.8xlarge"
    # docker_image = "digitalgenius/ubuntu-pytorch"
    # docker_image = "floydhub/dl-docker:cpu"


@M.timeit
def maml_supervised(model, Task, n_epochs, task_batch_n, npts, k_shot, n_gradient_steps, test_fn=None, **_):
    """
    supervised MAML. Task need to implement .proper and .sample methods, where proper is the full,
    dense set of data from which samples are drawn.

    :param model:
    :param Task:
    :param n_epochs:
    :param task_batch_n:
    :param npts: the total number of samples for the sinusoidal task
    :param k_shot:
    :param n_gradient_steps:
    :param _:
    :return:
    """
    import playground.maml.maml_torch.archive.paper_metrics as metrics

    device = t.device('cuda' if t.cuda.is_available() else 'cpu')
    model.to(device)


    ps = list(model.parameters())

    # for ep_ind in trange(n_epochs, desc='Epochs', ncols=50, leave=False):
    M.tic('epoch')
    for ep_ind in trange(n_epochs):
        M.split('epoch', silent=True)
        meta_grads = defaultdict(lambda: 0)
        theta = copy.deepcopy(model.state_dict())
        tasks = [Task(npts=npts) for _ in range(task_batch_n)]
        for task_ind, task in enumerate(tasks):  # sample a new problem
            # todo: this part is highly-parallelizable
            if task_ind != 0:
                model.load_state_dict(theta)

            task_grads = defaultdict(deque)
            proper = t.tensor(task.proper()).to(device)
            samples = t.tensor(task.samples(k_shot)).to(device)

            for grad_ind in range(n_gradient_steps):
                # done: ready to be repackaged
                loss, _ = metrics.comp_loss(*samples, model)
                model.zero_grad()
                # back-propagate once, retain graph.
                loss.backward(t.ones(1).to(device), retain_graph=True)

                # done: need to use gradient descent, plus creating a meta graph.
                U, grad_outputs = [], []
                for p in model.parameters():
                    U.append(p - G.alpha * p.grad)  # meta update
                    grad_outputs.append(t.ones(1).to(device).expand_as(p))

                # t.autograd.grad returns sum of gradient between all U and all grad_outputs
                # note: this is the row sum of \partial theta_prime \partial theta, which is a matrix.
                dU = t.autograd.grad(outputs=U, grad_outputs=grad_outputs, inputs=model.parameters())

                # Now update the param.figs
                for p, updated_p, du in zip(ps, U, dU):
                    p.data = updated_p.data  # these are leaf notes, so we can directly manipulate the data attribute.
                    task_grads[p].append(du)

                # note: evaluate the 1-grad loss
                if G.test_interval and ep_ind % G.test_interval and grad_ind + 1 in G.test_grad_steps:
                    with t.no_grad():
                        if test_fn is not None:
                            test_fn(grad_ind + 1, model, task=task, epoch=ep_ind)
                        _loss, _ = metrics.comp_loss(*proper, model)
                    logger.log_keyvalue(ep_ind, key=f"{grad_ind + 1:d}-grad-loss-{task_ind:02d}", value=_loss.item(),
                                        silent=True)

            # compute Loss_theta_prime
            samples = t.tensor(task.samples(k_shot)).to(device)  # sample from this problem
            loss, _ = metrics.comp_loss(*samples, model)
            model.zero_grad()
            loss.backward()

            for i, grad in enumerate(model.gradients()):  # Now accumulate the gradient
                p = ps[i]
                task_grads[p].append(grad)
                meta_grads[p] += t.prod(t.cat(list(map(
                    lambda d: d.unsqueeze(dim=-1), task_grads[p])),
                    dim=-1), dim=-1)

        # theta_prime = copy.deepcopy(model.state_dict())
        model.load_state_dict(theta)
        for p in ps:
            p.grad = t.tensor((meta_grads[p] / task_batch_n).detach()).to(device)

        model.meta_step(lr=G.beta)

        with t.no_grad():
            if test_fn is not None:
                test_fn(0, model, epoch=ep_ind)
            _loss, _ = metrics.comp_loss(*proper, model)
        # it is very easy to use the wrong loss here.
        logger.log_keyvalue(ep_ind, '0-grad-loss', _loss.item(), silent=True)

        # save model weight
        if G.save_interval and ep_ind % G.save_interval == 0:
            logger.log_module(ep_ind, **{type(model).__name__: model})

        # note: remove plotting code to make this as compact as possible.
        # if (ep_ind % G.plot_interval == 0 or ep_ind == (n_epochs - 1)):
        #     plot(ep_ind, task, model, logger, k_shot=k_shot)


def launch(model=None, test_fn=None, **_G):
    import matplotlib

    matplotlib.use('Agg')

    G.update(_G)

    import numpy as np
    np.random.seed(G.seed)
    t.manual_seed(G.seed)
    t.cuda.manual_seed(G.seed)

    logger.configure(log_directory=G.log_dir, prefix=G.log_prefix)

    logger.log_params(G=vars(G))

    model = model or Model(**vars(G))
    logger.print(str(model))

    from playground.maml.maml_torch.tasks import Sine
    maml_supervised(model, Sine, test_fn=test_fn, **vars(G))


# note: for jaynes launches
launch.Args = G

if __name__ == "__main__":
    import warnings

    warnings.filterwarnings("ignore")
    launch()
