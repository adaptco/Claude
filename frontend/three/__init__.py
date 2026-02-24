"""
Frontend Three - Game Engine and Rendering Module

This package provides the core game engine with physics, collision detection,
and vehicle simulation, along with rendering and UI components.
"""

from .game_engine import (
    GameEngine,
    GameState,
    DifficultyLevel,
    Vehicle,
    Obstacle,
    Vector3,
)
from . import constants

__all__ = [
    "GameEngine",
    "GameState",
    "DifficultyLevel",
    "Vehicle",
    "Obstacle",
    "Vector3",
    "constants",
]
