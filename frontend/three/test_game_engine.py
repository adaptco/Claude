"""
Test suite for the Game Engine.

Tests physics, collision detection, vehicle behavior, and game state management.
"""

import pytest
import math
from game_engine import (
    GameEngine,
    GameState,
    DifficultyLevel,
    Vehicle,
    Obstacle,
    Vector3,
)
from . import constants


class TestVector3:
    """Test Vector3 class."""
    
    def test_vector_creation(self):
        """Test creating vectors."""
        v = Vector3(1, 2, 3)
        assert v.x == 1
        assert v.y == 2
        assert v.z == 3
    
    def test_vector_default(self):
        """Test default vector is origin."""
        v = Vector3()
        assert v.x == 0
        assert v.y == 0
        assert v.z == 0
    
    def test_distance_calculation(self):
        """Test Euclidean distance calculation."""
        v1 = Vector3(0, 0, 0)
        v2 = Vector3(3, 4, 0)
        assert v1.distance_to(v2) == 5.0
    
    def test_vector_addition(self):
        """Test vector addition."""
        v1 = Vector3(1, 2, 3)
        v2 = Vector3(4, 5, 6)
        result = v1 + v2
        assert result.x == 5
        assert result.y == 7
        assert result.z == 9
    
    def test_scalar_multiplication(self):
        """Test scalar multiplication."""
        v = Vector3(2, 3, 4)
        result = v * 2.0
        assert result.x == 4
        assert result.y == 6
        assert result.z == 8


class TestVehicle:
    """Test Vehicle class."""
    
    def test_vehicle_creation(self):
        """Test vehicle initialization."""
        v = Vehicle()
        assert v.position == Vector3(0, 0, 0)
        assert v.velocity == Vector3(0, 0, 0)
        assert v.fuel == constants.DEFAULT_FUEL_CAPACITY_GAL
    
    def test_speed_calculation_mps(self):
        """Test speed calculation in m/s."""
        v = Vehicle()
        v.velocity = Vector3(3, 0, 4)
        assert v.speed_mps() == 5.0
    
    def test_speed_calculation_mph(self):
        """Test speed conversion to mph."""
        v = Vehicle()
        # Set velocity to 1 m/s
        v.velocity = Vector3(1, 0, 0)
        speed_mph = v.speed_mph()
        expected = 1.0 / constants.MPH_TO_MPS
        assert abs(speed_mph - expected) < 0.01
    
    def test_fuel_consumption(self):
        """Test fuel consumption."""
        v = Vehicle()
        initial_fuel = v.fuel
        v.consume_fuel(1.0)
        assert v.fuel == initial_fuel - 1.0
    
    def test_fuel_cannot_go_negative(self):
        """Test fuel cannot become negative."""
        v = Vehicle()
        v.consume_fuel(100.0)
        assert v.fuel == 0.0
    
    def test_refuel(self):
        """Test refueling."""
        v = Vehicle()
        v.consume_fuel(5.0)
        v.refuel(2.0)
        assert v.fuel == constants.DEFAULT_FUEL_CAPACITY_GAL - 3.0
    
    def test_refuel_does_not_overfill(self):
        """Test refueling cannot exceed capacity."""
        v = Vehicle()
        v.refuel(100.0)
        assert v.fuel == constants.DEFAULT_FUEL_CAPACITY_GAL
    
    def test_has_fuel(self):
        """Test fuel checking."""
        v = Vehicle()
        assert v.has_fuel()
        v.consume_fuel(100.0)
        assert not v.has_fuel()


class TestGameEngine:
    """Test GameEngine class."""
    
    def test_engine_initialization(self):
        """Test game engine initialization."""
        engine = GameEngine()
        assert engine.state == GameState.MENU
        assert engine.difficulty == DifficultyLevel.NORMAL
        assert len(engine.obstacles) == 0
        assert engine.score == 0
    
    def test_start_game(self):
        """Test starting a game."""
        engine = GameEngine()
        engine.start_game()
        assert engine.state == GameState.PLAYING
        assert engine.time_elapsed == 0.0
    
    def test_pause_game(self):
        """Test pausing game."""
        engine = GameEngine()
        engine.start_game()
        engine.pause_game()
        assert engine.state == GameState.PAUSED
    
    def test_resume_game(self):
        """Test resuming game."""
        engine = GameEngine()
        engine.start_game()
        engine.pause_game()
        engine.resume_game()
        assert engine.state == GameState.PLAYING
    
    def test_end_game(self):
        """Test ending game."""
        engine = GameEngine()
        engine.start_game()
        engine.end_game()
        assert engine.state == GameState.GAME_OVER
    
    def test_add_obstacle(self):
        """Test adding obstacles."""
        engine = GameEngine()
        engine.add_obstacle(Vector3(10, 0, 20))
        assert len(engine.obstacles) == 1
        assert engine.obstacles[0].position.x == 10
    
    def test_acceleration(self):
        """Test vehicle acceleration."""
        engine = GameEngine()
        engine.start_game()
        initial_speed = engine.vehicle.speed_mps()
        engine.accelerate(5.0)
        assert engine.vehicle.speed_mps() > initial_speed
    
    def test_deceleration(self):
        """Test vehicle deceleration."""
        engine = GameEngine()
        engine.start_game()
        engine.accelerate(10.0)
        current_speed = engine.vehicle.speed_mps()
        engine.decelerate(5.0)
        assert engine.vehicle.speed_mps() < current_speed
    
    def test_turn(self):
        """Test vehicle turning."""
        engine = GameEngine()
        engine.start_game()
        engine.accelerate(5.0)
        
        initial_x = engine.vehicle.velocity.x
        engine.turn(math.pi / 2)  # 90 degree turn
        
        # After 90 degree turn, X and Z should swap (approximately)
        assert abs(engine.vehicle.velocity.x) > abs(initial_x)
    
    def test_max_speed_limit(self):
        """Test max speed is enforced."""
        engine = GameEngine()
        engine.start_game()
        
        # Accelerate multiple times
        for _ in range(100):
            engine.accelerate(50.0)
            if engine.vehicle.speed_mps() >= engine.vehicle.max_speed * 0.99:
                break
        
        # Speed should not exceed max
        assert engine.vehicle.speed_mps() <= engine.vehicle.max_speed * 1.01  # Small tolerance
    
    def test_collision_detection_no_collision(self):
        """Test collision detection with no collision."""
        engine = GameEngine()
        engine.start_game()
        engine.add_obstacle(Vector3(100, 0, 100))
        
        assert not engine._check_collisions()
    
    def test_collision_detection_with_collision(self):
        """Test collision detection with collision."""
        engine = GameEngine()
        engine.start_game()
        # Add obstacle at vehicle position
        engine.add_obstacle(Vector3(0, 0, 0))
        
        assert engine._check_collisions()
    
    def test_get_nearby_obstacles(self):
        """Test getting nearby obstacles."""
        engine = GameEngine()
        engine.start_game()
        
        # Add obstacles at various distances
        engine.add_obstacle(Vector3(10, 0, 0))
        engine.add_obstacle(Vector3(50, 0, 0))
        engine.add_obstacle(Vector3(200, 0, 0))
        
        nearby = engine.get_nearby_obstacles(constants.OBSTACLE_FAR_DISTANCE_M)
        assert len(nearby) >= 2
    
    def test_get_closest_obstacle(self):
        """Test getting closest obstacle."""
        engine = GameEngine()
        engine.start_game()
        
        engine.add_obstacle(Vector3(100, 0, 0))
        engine.add_obstacle(Vector3(10, 0, 0))
        
        closest = engine.get_closest_obstacle()
        assert closest.position.x == 10
    
    def test_categorize_obstacles(self):
        """Test obstacle categorization."""
        engine = GameEngine()
        engine.start_game()
        
        # Near obstacle
        engine.add_obstacle(Vector3(3, 0, 0))
        # Far obstacle
        engine.add_obstacle(Vector3(50, 0, 0))
        # Very far obstacle
        engine.add_obstacle(Vector3(200, 0, 0))
        
        near, far = engine.categorize_obstacles()
        assert len(near) >= 1
        assert len(far) >= 1
    
    def test_update_frame(self):
        """Test game update frame."""
        engine = GameEngine()
        engine.start_game()
        engine.accelerate(5.0)
        
        initial_time = engine.time_elapsed
        engine.update(0.016)  # 16ms frame
        
        assert engine.time_elapsed > initial_time
        assert engine.vehicle.position.z > 0
    
    def test_fuel_depletion_ends_game(self):
        """Test fuel depletion ends game."""
        engine = GameEngine()
        engine.start_game()
        engine.vehicle.fuel = 0.01
        
        engine.update(1.0)
        assert engine.state == GameState.GAME_OVER
    
    def test_game_info(self):
        """Test getting game info."""
        engine = GameEngine()
        engine.start_game()
        engine.accelerate(5.0)
        engine.update(0.016)
        
        info = engine.get_game_info()
        assert info["state"] == "playing"
        assert info["score"] == 0
        assert "vehicle" in info
        assert "world" in info


class TestConstants:
    """Test constants module."""
    
    def test_physics_constants(self):
        """Test physics constants are reasonable."""
        assert constants.MPH_TO_MPS > 0
        assert constants.GRAVITY_MPS2 > 0
    
    def test_vehicle_constants(self):
        """Test vehicle constants."""
        assert constants.DEFAULT_FUEL_CAPACITY_GAL > 0
        assert constants.MAX_SPEED_MPH > 0
    
    def test_derived_constants(self):
        """Test derived constants are calculated correctly."""
        expected_mps = constants.MAX_SPEED_MPH * constants.MPH_TO_MPS
        assert abs(constants.MAX_SPEED_MPS - expected_mps) < 0.01
    
    def test_obstacle_constants(self):
        """Test obstacle distance thresholds."""
        assert constants.OBSTACLE_NEAR_DISTANCE_M < constants.OBSTACLE_FAR_DISTANCE_M
    
    def test_game_state_constants(self):
        """Test game state constants."""
        assert constants.GAME_STATE_MENU == "menu"
        assert constants.GAME_STATE_PLAYING == "playing"
        assert constants.GAME_STATE_PAUSED == "paused"
        assert constants.GAME_STATE_GAME_OVER == "game_over"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
