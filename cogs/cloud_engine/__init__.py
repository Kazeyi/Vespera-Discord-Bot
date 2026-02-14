"""
Cloud Infrastructure ChatOps Engine - Enterprise Edition

Architecture:
- models/    - State objects and data classes
- core/      - Business logic (orchestrator, terraform runner, validator)
- ui/        - Discord UI components (views, modals, selects)
- cogs/      - Discord command handlers (user, admin)

This follows the "Plan-First" architecture where terraform plan runs
before approval, similar to D&D's "Truth Block" validation.
"""

__version__ = "2.0.0"
__author__ = "GitHub Copilot (Claude Sonnet 4.5)"

from .core.orchestrator import CloudOrchestrator
from .models.session import CloudSession, DeploymentState

__all__ = ["CloudOrchestrator", "CloudSession", "DeploymentState"]
