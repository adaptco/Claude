"""
Configuration constants for the Game Engine.

Immutable constants are defined at module level.
Tuning knobs (adjustable values) are clearly marked.
All values use SI units where applicable.
"""

# ============================================================================
# Physics Constants (Immutable - do not modify)
# ============================================================================
MPH_TO_MPS = 0.44704
"""Conversion factor from miles per hour to meters per second."""

GRAVITY_MPS2 = 9.81
"""Gravitational acceleration in meters per second squared."""

# ============================================================================
# Vehicle Configuration (Tuning Knobs - adjust for game balance)
# ============================================================================
DEFAULT_FUEL_CAPACITY_GAL = 13.2
"""Default fuel tank capacity in US gallons."""

MAX_SPEED_MPH = 155.0
"""Maximum speed in miles per hour."""

# ============================================================================
# Derived Constants (Calculated from base constants)
# ============================================================================
MAX_SPEED_MPS = MAX_SPEED_MPH * MPH_TO_MPS
"""Maximum speed converted to meters per second."""

# ============================================================================
# Obstacle Configuration (Tuning Knobs - adjust for difficulty)
# ============================================================================
OBSTACLE_NEAR_DISTANCE_M = 5.0
"""Distance threshold for near obstacles in meters."""

OBSTACLE_FAR_DISTANCE_M = 100.0
"""Distance threshold for far obstacles in meters."""

# ============================================================================
# Rendering Constants (UI/Visual Tuning)
# ============================================================================
DEFAULT_RENDER_WIDTH = 1920
"""Default viewport width in pixels."""

DEFAULT_RENDER_HEIGHT = 1080
"""Default viewport height in pixels."""

FIELD_OF_VIEW_DEGREES = 75
"""Camera field of view in degrees."""

# ============================================================================
# Game State Constants
# ============================================================================
GAME_STATE_MENU = "menu"
GAME_STATE_PLAYING = "playing"
GAME_STATE_PAUSED = "paused"
GAME_STATE_GAME_OVER = "game_over"

# ============================================================================
# Difficulty Levels
# ============================================================================
DIFFICULTY_EASY = "easy"
DIFFICULTY_NORMAL = "normal"
DIFFICULTY_HARD = "hard"
DIFFICULTY_EXPERT = "expert"
