from .base import Allocator, RiskBudget, apply_constraints
from .mean_variance import MeanVarianceAllocator
from .risk_parity import RiskParityAllocator
from .vol_target import VolTargetAllocator

ALLOCATORS = {
    "vol_target": VolTargetAllocator,
    "risk_parity": RiskParityAllocator,
    "mean_variance": MeanVarianceAllocator,
}

__all__ = [
    "ALLOCATORS",
    "Allocator",
    "MeanVarianceAllocator",
    "RiskBudget",
    "RiskParityAllocator",
    "VolTargetAllocator",
    "apply_constraints",
]
