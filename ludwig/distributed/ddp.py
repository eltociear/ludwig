import contextlib
import socket
from typing import Any, Callable, Optional, Tuple

import torch
import torch.distributed as dist
from torch import nn
from torch.nn.parallel import DistributedDataParallel as DDP
from torch.optim import Optimizer
from torchmetrics.utilities.distributed import gather_all_tensors

from ludwig.distributed.base import DistributedStrategy


class DDPStrategy(DistributedStrategy):
    def __init__(self):
        self._local_rank, self._local_size = local_rank_and_size()
        print("\n!!! DDP BACKEND !!!\n")

    def wrap_model(self, model: nn.Module) -> nn.Module:
        return DDP(model)

    def wrap_optimizer(self, optimizer: Optimizer, model: nn.Module) -> Optimizer:
        return optimizer

    def size(self) -> int:
        return dist.get_world_size()

    def rank(self) -> int:
        return dist.get_rank()

    def local_size(self) -> int:
        return self._local_size

    def local_rank(self) -> int:
        return self._local_rank

    def barrier(self):
        return dist.barrier()

    def allreduce(self, t: torch.Tensor) -> torch.Tensor:
        dist.all_reduce(t)
        return t

    def broadcast(self, t: torch.Tensor) -> torch.Tensor:
        dist.broadcast(t)
        return t

    def sync_model(self, model: nn.Module):
        # TODO(travis): open question if this is needed to ensure all workers using same weights
        pass

    def sync_optimizer(self, optimizer: Optimizer):
        # TODO(travis): open question if this is needed to ensure all workers using same optimizer state
        pass

    def broadcast_object(self, v: Any, name: Optional[str] = None) -> Any:
        output = [v]
        dist.broadcast_object_list(output)
        return output[0]

    def wait_optimizer_synced(self, optimizer: Optimizer):
        pass

    @contextlib.contextmanager
    def prepare_optimizer_update(self, optimizer: Optimizer):
        yield

    @classmethod
    def is_available(cls) -> bool:
        return dist.is_available() and dist.is_initialized()

    @classmethod
    def gather_all_tensors_fn(cls) -> Optional[Callable]:
        return gather_all_tensors

    @classmethod
    def get_ray_trainer_backend(cls, **kwargs) -> Optional[Any]:
        return "torch"

    def shutdown(self):
        # TODO(travis): currently Ray handles this for us, but is subject to hangs if one of the workers raises an
        # exception and the other makes a collective op. We should figure out a way to make this safe to call
        # multiple times. It looks like there is a fix we can make use of when we upgrade to Ray 2.1:
        # https://discuss.ray.io/t/torchtrainer-hangs-when-only-1-worker-raises-error/7447/11
        # dist.destroy_process_group()
        pass


def local_rank_and_size() -> Tuple[int, int]:
    # Gather the rank and hostnames from every worker so we can count up how many belong to the same host, which
    # constitutes the local group.
    rank = dist.get_rank()
    host = socket.gethostname()
    output = [None for _ in range(dist.get_world_size())]
    dist.all_gather_object(output, (rank, host))

    # Every time we find a worker with the same host, we increment the size counter.
    # The local rank is determined by the world rank relative to the other workers on the same host, so every time
    # we see a worker on our host with a lower rank, we increment the rank counter.
    local_size = 0
    local_rank = 0
    for other_rank, other_host in output:
        if other_host == host:
            local_size += 1
            if other_rank < rank:
                local_rank += 1

    print("DETECTED", rank, host, local_rank, local_size, output)
    return local_rank, local_size
