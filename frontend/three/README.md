# Frontend Three - Game Engine

A refactored, production-ready game engine with physics simulation, collision detection, and vehicle control.

## Overview

This module provides a complete game engine implementation with:

- **Vehicle Physics** - Velocity, acceleration, deceleration, turning, max speed enforcement
- **Collision Detection** - Automatic collision checking and response
- **Game State Management** - Menu, playing, paused, game over states
- **Obstacle Management** - Add, categorize (near/far), and query obstacles
- **Constants Management** - Single source of truth for all tuning parameters

## Refactoring Summary

### Problem
The original game engine contained magic numbers scattered throughout the code, making it difficult to:
- Understand what values control behavior
- Adjust game parameters consistently
- Maintain the codebase over time

### Solution
Created a dedicated `constants.py` module that centralizes all configuration values:

```python
from frontend.three import constants

# Physics constants (immutable)
constants.MPH_TO_MPS          # 0.44704
constants.GRAVITY_MPS2        # 9.81

# Vehicle tuning (adjustable)
constants.DEFAULT_FUEL_CAPACITY_GAL   # 13.2 gallons
constants.MAX_SPEED_MPH               # 155.0 mph

# Derived constants (calculated)
constants.MAX_SPEED_MPS       # 69.32 m/s

# Obstacle tuning
constants.OBSTACLE_NEAR_DISTANCE_M    # 5.0 m
constants.OBSTACLE_FAR_DISTANCE_M     # 100.0 m
```

### Changes Made

1. **Extracted Constants** - All magic numbers → named constants
2. **Added Documentation** - Each constant has a docstring explaining its purpose
3. **Organized by Category** - Physics, Vehicle, Obstacles, Rendering, Game State
4. **Centralized Imports** - All code imports from `constants` module
5. **Maintained SI Units** - Consistent metric system for physics

## File Structure

```
frontend/three/
├── constants.py              # Configuration constants (NEW)
├── game_engine.py            # Refactored engine using constants
├── test_game_engine.py       # Comprehensive test suite
├── __init__.py              # Package exports
└── README.md                # This file
```

## Quick Start

### Basic Usage

```python
from frontend.three import GameEngine, DifficultyLevel, Vector3

# Create engine
engine = GameEngine(difficulty=DifficultyLevel.NORMAL)
engine.start_game()

# Add obstacles
engine.add_obstacle(Vector3(10, 0, 20), radius=2.0)
engine.add_obstacle(Vector3(-10, 0, 50), radius=1.5)

# Control vehicle
engine.accelerate(5.0)
engine.turn(0.1)

# Update each frame
engine.update(0.016)  # 16ms for ~60 FPS

# Check state
if engine.state.value == "game_over":
    print("Game Over!")
```

### Accessing Constants

```python
from frontend.three import constants

print(f"Max Speed: {constants.MAX_SPEED_MPS} m/s")
print(f"Gravity: {constants.GRAVITY_MPS2} m/s²")
print(f"Near Threshold: {constants.OBSTACLE_NEAR_DISTANCE_M} m")
```

### Adjusting Game Parameters

Simply edit `constants.py`:

```python
# Make the game faster
MAX_SPEED_MPH = 200.0  # was 155.0

# Increase fuel capacity
DEFAULT_FUEL_CAPACITY_GAL = 20.0  # was 13.2

# Change obstacle detection range
OBSTACLE_FAR_DISTANCE_M = 150.0  # was 100.0
```

## API Reference

### GameEngine

```python
class GameEngine:
    """Main game engine class."""
    
    def __init__(self, difficulty: DifficultyLevel = DifficultyLevel.NORMAL)
    def start_game() -> None
    def pause_game() -> None
    def resume_game() -> None
    def end_game() -> None
    def add_obstacle(position: Vector3, radius: float = 1.0) -> None
    def update(delta_time: float) -> None
    def accelerate(acceleration_mps: float) -> None
    def decelerate(deceleration_mps: float) -> None
    def turn(angle_radians: float) -> None
    def get_nearby_obstacles(max_distance: float) -> List[Obstacle]
    def get_closest_obstacle() -> Optional[Obstacle]
    def categorize_obstacles() -> Tuple[List[Obstacle], List[Obstacle]]
    def get_game_info() -> dict
```

### Vehicle

```python
@dataclass
class Vehicle:
    position: Vector3
    velocity: Vector3
    fuel: float
    max_speed: float
    
    def speed_mph() -> float
    def speed_mps() -> float
    def consume_fuel(amount: float) -> None
    def refuel(amount: float) -> None
    def has_fuel() -> bool
```

### Vector3

```python
@dataclass
class Vector3:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    
    def distance_to(other: Vector3) -> float
    def __add__(other: Vector3) -> Vector3
    def __mul__(scalar: float) -> Vector3
```

### Enums

```python
class GameState(Enum):
    MENU = "menu"
    PLAYING = "playing"
    PAUSED = "paused"
    GAME_OVER = "game_over"

class DifficultyLevel(Enum):
    EASY = "easy"
    NORMAL = "normal"
    HARD = "hard"
    EXPERT = "expert"
```

## Constants Reference

### Physics Constants
- `MPH_TO_MPS` = 0.44704 - Conversion factor
- `GRAVITY_MPS2` = 9.81 - Gravitational acceleration

### Vehicle Configuration
- `DEFAULT_FUEL_CAPACITY_GAL` = 13.2 - Tank size
- `MAX_SPEED_MPH` = 155.0 - Speed limit
- `MAX_SPEED_MPS` = 69.32 - Converted speed limit

### Obstacle Configuration
- `OBSTACLE_NEAR_DISTANCE_M` = 5.0 - Near detection threshold
- `OBSTACLE_FAR_DISTANCE_M` = 100.0 - Far detection threshold

### Rendering Configuration
- `DEFAULT_RENDER_WIDTH` = 1920 - Viewport width
- `DEFAULT_RENDER_HEIGHT` = 1080 - Viewport height
- `FIELD_OF_VIEW_DEGREES` = 75 - Camera FOV

### Game States
- `GAME_STATE_MENU` = "menu"
- `GAME_STATE_PLAYING` = "playing"
- `GAME_STATE_PAUSED` = "paused"
- `GAME_STATE_GAME_OVER` = "game_over"

### Difficulty Levels
- `DIFFICULTY_EASY` = "easy"
- `DIFFICULTY_NORMAL` = "normal"
- `DIFFICULTY_HARD` = "hard"
- `DIFFICULTY_EXPERT` = "expert"

## Testing

Run the comprehensive test suite:

```bash
pytest frontend/three/test_game_engine.py -v
```

Test coverage includes:
- Vector3 operations (addition, multiplication, distance)
- Vehicle physics (speed, fuel, acceleration)
- Game state management
- Obstacle management and categorization
- Collision detection
- Physics update loop
- Constants validation

## Before & After Example

### Before (Magic Numbers)
```python
class Vehicle:
    def __init__(self):
        self.fuel = 13.2  # What is this?
        self.max_speed = 155.0  # mph or m/s?
    
    def speed_mph(self):
        speed_mps = self.get_speed()
        return speed_mps / 0.44704  # Magic number!
```

### After (Constants)
```python
from . import constants

class Vehicle:
    def __init__(self):
        self.fuel = constants.DEFAULT_FUEL_CAPACITY_GAL
        self.max_speed = constants.MAX_SPEED_MPS
    
    def speed_mph(self):
        speed_mps = self.get_speed()
        return speed_mps / constants.MPH_TO_MPS  # Clear intent!
```

## Benefits of Refactoring

✅ **Single Source of Truth** - All values defined in one place  
✅ **Self-Documenting** - Constants have names and docstrings  
✅ **Easy to Tune** - Change one value affects entire system  
✅ **Type Safe** - IDE autocomplete and linting support  
✅ **Maintainable** - New developers understand parameter purpose  
✅ **Testable** - Constants can be mocked for testing  
✅ **Scalable** - Easy to add new constants without refactoring  

## Best Practices

1. **Always use constants** - Never hardcode values in logic code
2. **Document purpose** - Add docstrings explaining each constant
3. **Organize by category** - Group related constants together
4. **Use SI units** - Meters, seconds, kilograms, etc.
5. **Derive when possible** - Calculate dependent values from base constants
6. **Label tuning knobs** - Make it clear which values are adjustable

## Future Enhancements

- [ ] Load constants from JSON/YAML configuration file
- [ ] Per-difficulty constant overrides
- [ ] Real-time constant adjustment (debug mode)
- [ ] Constants validation (min/max ranges)
- [ ] Performance profiling with different constant values

## Contributing

When adding new game features:

1. Define constants in `constants.py` (with docstrings)
2. Import constants in your code: `from . import constants`
3. Use constants instead of magic numbers
4. Add tests to `test_game_engine.py`
5. Update this README if adding major features

## License

Same as parent project.

---

**Complete refactoring with improved maintainability and zero functional changes.** ✨
