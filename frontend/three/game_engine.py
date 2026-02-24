"""
Game Engine for vehicle simulation and collision detection.

Uses constants from the constants module to maintain single source of truth
for all configuration values.
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional
from enum import Enum
import math

try:
    from . import constants
except ImportError:
    import constants


class GameState(Enum):
    """Enumeration of possible game states."""
    MENU = constants.GAME_STATE_MENU
    PLAYING = constants.GAME_STATE_PLAYING
    PAUSED = constants.GAME_STATE_PAUSED
    GAME_OVER = constants.GAME_STATE_GAME_OVER


class DifficultyLevel(Enum):
    """Enumeration of difficulty levels."""
    EASY = constants.DIFFICULTY_EASY
    NORMAL = constants.DIFFICULTY_NORMAL
    HARD = constants.DIFFICULTY_HARD
    EXPERT = constants.DIFFICULTY_EXPERT


@dataclass
class Vector3:
    """3D vector representation."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def distance_to(self, other: "Vector3") -> float:
        """Calculate Euclidean distance to another vector."""
        dx = self.x - other.x
        dy = self.y - other.y
        dz = self.z - other.z
        return math.sqrt(dx*dx + dy*dy + dz*dz)

    def __add__(self, other: "Vector3") -> "Vector3":
        """Vector addition."""
        return Vector3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __mul__(self, scalar: float) -> "Vector3":
        """Scalar multiplication."""
        return Vector3(self.x * scalar, self.y * scalar, self.z * scalar)


@dataclass
class Obstacle:
    """Represents an obstacle in the game world."""
    position: Vector3
    radius: float = 1.0
    
    def distance_to(self, point: Vector3) -> float:
        """Calculate distance from obstacle center to a point."""
        return self.position.distance_to(point)


@dataclass
class Vehicle:
    """Represents the player's vehicle."""
    position: Vector3 = None
    velocity: Vector3 = None
    fuel: float = None
    max_speed: float = None
    
    def __post_init__(self):
        if self.position is None:
            self.position = Vector3()
        if self.velocity is None:
            self.velocity = Vector3()
        if self.fuel is None:
            self.fuel = constants.DEFAULT_FUEL_CAPACITY_GAL
        if self.max_speed is None:
            self.max_speed = constants.MAX_SPEED_MPS
    
    def speed_mph(self) -> float:
        """Get current speed in miles per hour."""
        speed_mps = math.sqrt(
            self.velocity.x**2 + self.velocity.y**2 + self.velocity.z**2
        )
        return speed_mps / constants.MPH_TO_MPS
    
    def speed_mps(self) -> float:
        """Get current speed in meters per second."""
        return math.sqrt(
            self.velocity.x**2 + self.velocity.y**2 + self.velocity.z**2
        )
    
    def consume_fuel(self, amount: float) -> None:
        """Consume fuel from the vehicle."""
        self.fuel = max(0.0, self.fuel - amount)
    
    def refuel(self, amount: float) -> None:
        """Refuel the vehicle."""
        self.fuel = min(constants.DEFAULT_FUEL_CAPACITY_GAL, self.fuel + amount)
    
    def has_fuel(self) -> bool:
        """Check if vehicle has any fuel remaining."""
        return self.fuel > 0.0


class GameEngine:
    """
    Core game engine handling physics, collisions, and game state.
    """
    
    def __init__(self, difficulty: DifficultyLevel = DifficultyLevel.NORMAL):
        """
        Initialize the game engine.
        
        Args:
            difficulty: Game difficulty level
        """
        self.state = GameState.MENU
        self.difficulty = difficulty
        self.vehicle = Vehicle()
        self.obstacles: List[Obstacle] = []
        self.score: int = 0
        self.time_elapsed: float = 0.0
    
    def start_game(self) -> None:
        """Start a new game."""
        self.state = GameState.PLAYING
        self.vehicle = Vehicle()
        self.obstacles = []
        self.score = 0
        self.time_elapsed = 0.0
    
    def pause_game(self) -> None:
        """Pause the current game."""
        if self.state == GameState.PLAYING:
            self.state = GameState.PAUSED
    
    def resume_game(self) -> None:
        """Resume the paused game."""
        if self.state == GameState.PAUSED:
            self.state = GameState.PLAYING
    
    def end_game(self) -> None:
        """End the current game."""
        self.state = GameState.GAME_OVER
    
    def add_obstacle(self, position: Vector3, radius: float = 1.0) -> None:
        """
        Add an obstacle to the game world.
        
        Args:
            position: Position of the obstacle
            radius: Collision radius of the obstacle
        """
        obstacle = Obstacle(position=position, radius=radius)
        self.obstacles.append(obstacle)
    
    def update(self, delta_time: float) -> None:
        """
        Update game state for a frame.
        
        Args:
            delta_time: Time elapsed since last frame in seconds
        """
        if self.state != GameState.PLAYING:
            return
        
        self.time_elapsed += delta_time
        
        # Update vehicle position
        self.vehicle.position = self.vehicle.position + (
            self.vehicle.velocity * delta_time
        )
        
        # Apply gravity (simple downward acceleration)
        gravity_acceleration = Vector3(0, -constants.GRAVITY_MPS2, 0)
        self.vehicle.velocity = self.vehicle.velocity + (
            gravity_acceleration * delta_time
        )
        
        # Limit max speed
        speed = self.vehicle.speed_mps()
        if speed > self.vehicle.max_speed:
            scale_factor = self.vehicle.max_speed / speed
            self.vehicle.velocity = self.vehicle.velocity * scale_factor
        
        # Consume fuel
        fuel_consumption_rate = 0.01  # gallons per second
        self.vehicle.consume_fuel(fuel_consumption_rate * delta_time)
        
        # Check game over conditions
        if not self.vehicle.has_fuel():
            self.end_game()
        
        # Check collisions
        if self._check_collisions():
            self.end_game()
    
    def _check_collisions(self) -> bool:
        """
        Check for collisions between vehicle and obstacles.
        
        Returns:
            True if collision detected, False otherwise
        """
        vehicle_radius = 1.0
        
        for obstacle in self.obstacles:
            distance = self.vehicle.position.distance_to(obstacle.position)
            collision_distance = vehicle_radius + obstacle.radius
            
            if distance < collision_distance:
                return True
        
        return False
    
    def get_nearby_obstacles(self, max_distance: float = constants.OBSTACLE_FAR_DISTANCE_M) -> List[Obstacle]:
        """
        Get obstacles within max_distance from the vehicle.
        
        Args:
            max_distance: Maximum distance to search
            
        Returns:
            List of nearby obstacles sorted by distance
        """
        nearby = []
        
        for obstacle in self.obstacles:
            distance = self.vehicle.position.distance_to(obstacle.position)
            if distance <= max_distance:
                nearby.append(obstacle)
        
        # Sort by distance (closest first)
        nearby.sort(key=lambda o: self.vehicle.position.distance_to(o.position))
        return nearby
    
    def get_closest_obstacle(self) -> Optional[Obstacle]:
        """
        Get the closest obstacle to the vehicle.
        
        Returns:
            Closest obstacle or None if no obstacles exist
        """
        if not self.obstacles:
            return None
        
        return min(
            self.obstacles,
            key=lambda o: self.vehicle.position.distance_to(o.position)
        )
    
    def categorize_obstacles(self) -> Tuple[List[Obstacle], List[Obstacle]]:
        """
        Categorize obstacles as near or far based on distance thresholds.
        
        Returns:
            Tuple of (near_obstacles, far_obstacles)
        """
        near = []
        far = []
        
        for obstacle in self.obstacles:
            distance = self.vehicle.position.distance_to(obstacle.position)
            
            if distance <= constants.OBSTACLE_NEAR_DISTANCE_M:
                near.append(obstacle)
            elif distance <= constants.OBSTACLE_FAR_DISTANCE_M:
                far.append(obstacle)
        
        return near, far
    
    def accelerate(self, acceleration_mps: float) -> None:
        """
        Accelerate the vehicle.
        
        Args:
            acceleration_mps: Acceleration in meters per second
        """
        if self.state != GameState.PLAYING:
            return
        
        # Increase forward velocity
        self.vehicle.velocity.z += acceleration_mps
        
        # Clamp to max speed
        speed = self.vehicle.speed_mps()
        if speed > self.vehicle.max_speed:
            scale_factor = self.vehicle.max_speed / speed
            self.vehicle.velocity = self.vehicle.velocity * scale_factor
    
    def decelerate(self, deceleration_mps: float) -> None:
        """
        Decelerate the vehicle.
        
        Args:
            deceleration_mps: Deceleration in meters per second
        """
        if self.state != GameState.PLAYING:
            return
        
        speed = self.vehicle.speed_mps()
        if speed > 0:
            # Calculate direction vector
            direction = Vector3(
                self.vehicle.velocity.x / speed,
                self.vehicle.velocity.y / speed,
                self.vehicle.velocity.z / speed
            )
            
            # Apply deceleration
            new_speed = max(0, speed - deceleration_mps)
            self.vehicle.velocity = direction * new_speed
    
    def turn(self, angle_radians: float) -> None:
        """
        Turn the vehicle (rotate velocity vector in XZ plane).
        
        Args:
            angle_radians: Rotation angle in radians
        """
        if self.state != GameState.PLAYING:
            return
        
        # Rotate velocity in XZ plane
        cos_a = math.cos(angle_radians)
        sin_a = math.sin(angle_radians)
        
        new_x = self.vehicle.velocity.x * cos_a - self.vehicle.velocity.z * sin_a
        new_z = self.vehicle.velocity.x * sin_a + self.vehicle.velocity.z * cos_a
        
        self.vehicle.velocity.x = new_x
        self.vehicle.velocity.z = new_z
    
    def get_game_info(self) -> dict:
        """
        Get current game state information.
        
        Returns:
            Dictionary with game state, vehicle state, and statistics
        """
        return {
            "state": self.state.value,
            "difficulty": self.difficulty.value,
            "vehicle": {
                "position": (self.vehicle.position.x, self.vehicle.position.y, self.vehicle.position.z),
                "velocity": (self.vehicle.velocity.x, self.vehicle.velocity.y, self.vehicle.velocity.z),
                "speed_mph": self.vehicle.speed_mph(),
                "speed_mps": self.vehicle.speed_mps(),
                "fuel_gallons": self.vehicle.fuel,
                "fuel_capacity": constants.DEFAULT_FUEL_CAPACITY_GAL,
                "fuel_percent": (self.vehicle.fuel / constants.DEFAULT_FUEL_CAPACITY_GAL) * 100,
                "max_speed_mps": self.vehicle.max_speed,
            },
            "world": {
                "obstacles_count": len(self.obstacles),
                "time_elapsed": self.time_elapsed,
            },
            "score": self.score,
        }


if __name__ == "__main__":
    # Demo usage
    engine = GameEngine(difficulty=DifficultyLevel.NORMAL)
    engine.start_game()
    
    # Add some obstacles
    engine.add_obstacle(Vector3(10, 0, 20), radius=2.0)
    engine.add_obstacle(Vector3(-10, 0, 50), radius=1.5)
    engine.add_obstacle(Vector3(5, 0, 100), radius=2.0)
    
    # Simulate a few frames
    for frame in range(10):
        engine.accelerate(5.0)
        engine.update(0.016)  # ~60 FPS
        
        info = engine.get_game_info()
        print(f"Frame {frame}: Speed={info['vehicle']['speed_mph']:.1f} MPH, "
              f"Fuel={info['vehicle']['fuel_percent']:.1f}%, "
              f"State={info['state']}")
