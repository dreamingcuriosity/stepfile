"""
Stepfile Runner - A Pythonic stepfile runner that executes commands from a configuration file.

This package provides tools for parsing and executing Stepfile configurations
with variable expansion and environment management.
"""

from .stepfile_runner import (
    StepfileConfig,
    StepfileRunner,
    main,
)

__version__ = "0.1.0"
__all__ = [
    "StepfileConfig",
    "StepfileRunner",
    "main",
]
