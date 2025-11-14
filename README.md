# NOT READY FOR RELEASE. 
## This is ALPHA software, expect breaking changes!!

---

# Token Simulation Framework

This project is a modular, extensible token simulation framework built with **Python** and **Pygame**, designed for real-time visual interaction. It serves as both a creative coding environment and an educational example for learning object-oriented design, interactive physics, and dynamic visualization.

## 🚀 Overview

Tokens are visual elements displayed on a canvas, featuring rich interactive behaviors and customizable physics. The framework supports both standalone operation and integration with Isadora via Spout.

## 🎯 Core Token Behavior

### Position & Movement
- Position and velocity using `pygame.Vector2`
- Home location tracking with return-to-home behavior
- Configurable wall bounce or off-screen death
- Elastic collision response (circle or rectangle)

### Visual Elements
- Custom image support with rotation
- Scale animation for collision feedback
- Configurable opacity for fade effects
- Debug visualization options:
  - Collision boundaries
  - Center markers
  - Velocity vectors
  - Force vectors
  - Flocking radius
  - Separation lines
  - Dead state overlay

### Physics & Interaction
- Mouse force field with configurable strength and falloff
- Flocking behavior (Boids algorithm):
  - Alignment (0.2)
  - Cohesion (0.05)
  - Separation (0.8)
- Home-seeking behavior after configurable delay
- Collision detection with elastic response
- Customizable friction and separation strength

## 📁 Project Structure
python_modules/ 
├── core/ 
│ ├── token.py # Core token physics and behavior 
│ ├── token_factory.py # Token creation and grid placement 
│ ├── settings_manager.py # Configuration management 
│ ├── respawn_manager.py # Death and respawn handling 
│ ├── token_runtime.py # Frame update and token management 
│ ├── utils.py # Shared utilities 
│ └── simulation.py # Main simulation controller 
├── main.py # Standalone application 
├── izzy_main.py # Isadora integration 
└── config.json # Behavior and visual settings


## OpenGL Architecture

The framework uses an OpenGL renderer tailored for the simulation:
- Rendering via `core.rendering.SimulationRenderer`
- GL state setup via `core.utils.setup_gl_state`
- Texture utilities in `core.utils` (surface_to_texture, draw_textured_quad, draw_rotated_textured_quad)
- Supports both windowed and hidden (headless-style) operation
- Handles alpha blending for token transparency
- Compatible with Spout video sharing


## 🎨 Configuration

All behaviors are configurable via JSON. Most can be updated in real-time, and provide a wide range of range of capabilities.
Here are the main configuration sections:


### Token Settings (example)
{
  "tokens": {
    "hide": false,
    "enable_wall_bounce": false,
    "look_at_mouse": true,
    "facing": "top",
    "enable_token_collision": true,
    "rotation_offset_degrees": 0,
    "collision": {
      "type": "circle",
      "enabled": true,
      "bounds_scale": 0.5,
      "elastic": true,
      "friction": 0.6,
      "separation_strength": 0.2,
      "strength": 0.2
    },
    "finds_home": { "enabled": true, "delay_sec": 3.0, "strength": 100.0 },
    "flocking": { "enabled": true, "radius": 149.6, "alignment": 0.4, "cohesion": 0.01, "separation": 1.15 },
    "spawn_behavior": ["fade_in"],
    "collision_behavior": ["bounce_pop"],
    "exit_behavior": ["fade_out"]
  },
  "mouse_force": {
    "enabled": true,
    "max_distance": 100.0,
    "force_strength": 3.0,
    "falloff": "linear"
  },
  "physics": { "bounce_factor": 0.8 },
  "timing": { "fade_in_duration_sec": 2.5, "respawn_delay_sec": 1.5, "respawn_collision_delay_sec": 10.0 },
  "input": { "use_live_image": true, "live_image_update": true, "hash_input": true, "compute_hash_when_live_update": true }
}

### Visual Settings (example)
{
  "visual_elements": {
    "token_center": { "enabled": true, "color": [255,255,255], "thickness": 6.0 },
    "force_vector": { "enabled": true, "color": [255,128,0], "thickness": 1.0 },
    "velocity_vector": { "enabled": true, "color": [255,255,0], "thickness": 3.0 },
    "token_collision_bounds": { "enabled": true, "color": [255,0,0], "thickness": 2.0 },
    "flocking_radius": { "enabled": true, "color": [128,128,128], "thickness": 2.0 },
    "separation_lines": { "enabled": true, "color": [0,255,255], "thickness": 1.0 }
  },
  "animation": { "bounce_duration_ms": 500.0, "bounce_scale": 1.5, "bounce_threshold": 0.5, "fade_in_duration_ms": 789.0 }
}

## 🎯 Token Orientation

Tokens use a texture coordinate system for orientation and rendering:
- Origin (0,0) is at the top-left corner
- X-axis extends right, Y-axis extends down
- Rotation is measured in degrees clockwise from the top
- Default facing direction is "top" (0 degrees)
- Textures are automatically flipped vertically in OpenGL for correct rendering

## 🔍 Debugging & Performance

### Debug Visualization
Enable various debug overlays via configuration:
- Token Centers: Shows the pivot point of each token
- Force Vectors: Displays mouse force influence
- Velocity Vectors: Shows movement direction and speed
- Collision Boundaries: Visualizes collision shapes
- Flocking Radius: Shows neighborhood detection range
- Separation Lines: Displays flocking separation connections

### Performance Monitoring
The system includes real-time performance stats:
- FPS counter
- Token count
- Active/Dead token ratio
- Collision checks per frame
- Mouse interaction radius

## 🔄 Operating Modes

### Standalone Mode
- Runs as a windowed application
- Direct mouse interaction
- Configuration via local JSON file
- Real-time visual feedback
- Performance overlay
- ESC to exit

### Isadora Integration Mode
- Headless operation
- Spout video output
- External configuration via JSON string
- Remote mouse position input
- Optional image input for token visuals
- Performance data via Isadora channels


## 📊 Version Information

Current Version: 1.0.0
- Python: 3.10.9
- Required Packages:
  - numpy
  - opencv-python
  - pygame
  - wheel
- OpenGL Support: 3.3+
- Spout SDK: 2.007


## 🛠️ Development

### Custom Token Creation
The framework supports custom token implementations by subclassing the base Token class. This allows you to:
- Create unique visual appearances for tokens
- Add custom properties and behaviors
- Override default movement patterns
- Implement specialized interaction rules

Basic example:
```python
class CustomToken(Token):
    def __init__(self, position, size, facing="top"):
        super().__init__(position, size, facing)
        # Add custom properties here
        self.custom_property = None

    def generate_image(self, settings):
        """Customize token appearance"""
        surface = pygame.Surface(self.size, pygame.SRCALPHA)
        # Draw your custom visualization here
        return surface
```

To use custom tokens, initialize the simulation with your custom class:
```python
simulation = TokenSimulation(custom_token_class=CustomToken)
```

### Runtime Configuration
Update settings dynamically:
python simulation.update_settings(new_config_json)


## 🙏 **Credits**

This project was created by **Ryan Webber (DusX)**  
Toronto-based multimedia programmer, creative technologist, and member of the TroikaTronix development team.

You are free to use, modify, and build upon this project.  
If you do, **please include attribution**:

**Credit:**  
_“Includes code or assets by Ryan Webber (DusX)”_  
https://dusxproductions.com

### 📄 License
This project uses a **dual-license model**:

- **Code:** MIT License — free to use commercially or non-commercially with attribution  
- **Media, documentation & artistic assets:** Creative Commons Attribution 4.0 (CC-BY 4.0)

See the included `LICENSE.txt` for full details.


## Configuration Reference

If you are looking for the full list of configurable settings and their explanations, see:
- python_modules/CONFIGURATION.md

This document describes every setting in python_modules/config.json, visual elements, Isadora/Spout output options, and runtime update behavior.



## 🧭 Roadmap (Next Steps)

Last updated: 2025-08-15

This roadmap outlines prioritized steps to continue development. It complements the technical docs in python_modules/overview.md and python_modules/CONFIGURATION.md.

1) Immediate consistency fixes (quick wins)
- Implement visual_elements.dead_overlay
  - Add an optional OpenGL overlay drawn for dead tokens when enabled.
  - Acceptance: dead_overlay=true visibly marks dead tokens; false leaves visuals unchanged; no measurable FPS drop with ~200 tokens.
- Cross-link docs
  - Ensure README links to configuration reference and roadmap (this section).

2) Testing & stability (short term, 1–2 weeks)
- Unit tests (headless logic)
  - SettingsManager: update_runtime_settings ignores init_ keys; config audit returns stable unknown/missing sets.
  - Token: boundary handling for enable_wall_bounce on/off; off-screen death detection.
  - SpatialGrid: basic bucketing/occupancy where applicable.
- Basic CI
  - GitHub Actions on Windows (and optionally Ubuntu) to run tests/lint.

3) Performance & rendering (2–4 weeks)
- Reduce texture uploads
  - Audit and cache where possible; leverage existing shared.perf counters.
- Spatial grid tuning
  - Adaptive cell size to token dimensions; throttle occupancy labels.
  - Target: grid efficiency >70% on typical scenes.
- Separation lines draw pass
  - Ensure mode="over" consolidates draws; validate 60 FPS at ~200 tokens with lines enabled on reference hardware.

4) Feature completeness & UX (1–2 months)
- Isadora/Spout polish
  - Sender name control; robust toggles for output.spout_invert/numpy_invert; verify re-init without leaks.
- Input pipeline modes clarity
  - Document/validate interactions of use_live_image, live_image_update, hash_input; overlay counters guide tuning.
- Example scenes
  - Provide 2–3 JSON presets (flocking demo, mouse-force demo, collision-bounds demo).

5) Developer experience
- Packaging & entry points
  - Optional wheel + `python -m tokens` launcher.
- Logging categories
  - Consistent use of DebugManager categories (config, render, texture, factory, token, collision) and short mapping doc.

6) Advanced (long term)
- Optional threading
  - Physics thread prototype (collisions/forces); GL remains main thread; opt-in config flag.
- Custom Token API stabilization
  - Document minimal contract; ship example under python_modules/assets/examples.
- Alternate render backends
  - Abstract renderer; evaluate pyglet/ModernGL as optional backends.
- Cross-platform hardening
  - Validate standalone on Windows/macOS/Linux; document Spout limitations on non-Windows.

Quality gates
- 60 FPS target on reference hardware with default visuals.
- Config Audit remains accurate; overlay mini-summary of unknown/missing maintained.
- New features are configuration-gated with sensible defaults.
- README, CONFIGURATION.md, and overview.md remain consistent after changes.
