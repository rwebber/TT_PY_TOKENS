# TOKENS Configuration Reference

This document describes every configurable setting used by the TOKENS simulation and how to change behavior at runtime. It reflects the current codebase under `python_modules`.

Contents:
- How configuration is loaded (init_ vs runtime)
- Complete setting reference (all keys in config.json and used by the code)
- Visual elements (OpenGL overlays)
- Additional ways to change behavior (APIs, entry‑point specifics)
- Example config


## How configuration is loaded

Settings are provided as a JSON object (commonly in `python_modules/config.json` or via Isadora’s “Config JSON” input). The SettingsManager splits keys into two buckets:
- init_ settings (only read at initialization): keys under `init_*` (e.g., `init_canvas`, `init_token`). Changing these at runtime via update_settings has no effect until you reinitialize the simulation.
- runtime settings: everything else. These can be changed on the fly using `TokenSimulation.update_settings(json_str)` or via Isadora’s Config JSON input.

Other important notes:
- The debug system (DebugManager) is initialized by shared.init_debug at app startup. It will read `debug.debug_manager` from config.json if available.
- The simulation also performs a config audit (logs under category `config`) indicating any unknown/unused keys and missing expected keys.

### How to use the Config Audit
The config audit helps you spot typos and missing settings.
- Where it runs: automatically at simulation init and after any TokenSimulation.update_settings(json_str).
- Where to see it:
  - Logs: enable DebugManager and include the 'config' category. In the standalone app, main.py enables it by default. In other hosts, call `shared.init_debug(enable=True, categories=['config'])` or include 'config' among your categories.
  - On‑screen: if `debug.stats_overlay` is true, a mini section "Config Audit" shows counts and a few sample keys for both unknown and missing.
- How to trigger manually: call `TokenSimulation.run_config_audit()`; it returns a dict with `unknown_keys` and `missing_expected` and also logs under category 'config'.
Tips:
- Unknown keys are present in your JSON but not recognized by the code (safe to remove/rename).
- Missing expected keys mean the code can use them; defaults will be applied if absent. Add them to your JSON if you want to override defaults.


## Complete settings reference

Below are all settings either present in `python_modules/config.json` or referenced by the codebase. Defaults shown reflect the repository’s current config.json unless otherwise noted. Types are indicated in parentheses.

### animation (object)
- bounce_duration_ms (number): Duration (ms) of collision/bounce animation. Default: 500.0
- bounce_scale (number): Max scale factor for bounce animation. Default: 1.5
- bounce_threshold (number): Minimum collision intensity to trigger a bounce. Default: 0.5
- fade_in_duration_ms (number): Token fade-in duration in ms. Default: 789.0

### debug (object)
- stats_overlay (bool): Draw performance and status text overlay. Default: true
- show_spatial_grid (bool): Draw the cell grid visualization on the overlay. Default: true
- debug_manager (bool): Initialize DebugManager (global debug printing) enabled/disabled. Default: false

Notes:
- DebugManager categories can be set from main.py; the top-level enable/disable comes from `debug.debug_manager` if present.

### init_canvas (object) [init-only]
- width (number): Canvas width in pixels. Default: 1920.0
- height (number): Canvas height in pixels. Default: 1080.0
- min_padding (number): Minimum padding used by the token factory to compute initial grid spawn. Default: 20.0

### init_token (object) [init-only]
- width (number): Token width (px). Default: 120.0
- height (number): Token height (px). Default: 120.0

### input (object)
- use_live_image (bool): If true, tokens will use the incoming “Image Input” (Isadora/Pythoner) instead of generated art. Default: true
- live_image_update (bool): If true and use_live_image is true, token images update from the live input every frame. Default: true
- hash_input (bool): If true and live_image_update is false, the system hashes incoming images to update only when the content changes. Default: true
- compute_hash_when_live_update (bool): If true, still compute an md5 hash per frame (useful as a stable frame ID for caches). Default: true

Behavior notes:
- When `live_image_update=true`, each token will adopt the current input image every frame (shared per-size scaling is cached per frame). Hashing here is optional.
- When `live_image_update=false` and `hash_input=true`, the shared image is updated only when the hash changes, reducing redundant work.
- When tokens are hidden (`tokens.hide=true`) or use_live_image=false, image ingestion is skipped.

### mouse_force (object)
- enabled (bool): Enables mouse-based forces. Default: true
- falloff (string): "linear" | "inverse" | "quadratic" | "smoothstep" (strength vs. distance). Default: "linear"
- force_strength (number): Base strength of the mouse force. Default: 3.0
- max_distance (number): Max distance (px) within which the force is applied. Default: 100.0

Additional behavior:
- Tokens also rotate to look at the mouse if `tokens.look_at_mouse=true` (independent of mouse_force.enabled).

### timing (object)
- fade_in_duration_sec (number): Spawn fade-in duration (seconds). Default: 2.5
- respawn_delay_sec (number): Time before a token respawns after death (seconds). Default: 1.5
- respawn_collision_delay_sec (number): Grace period after (re)spawn during which token-token collision checks are suppressed (seconds). Default: 10.0

### physics (object)
- bounce_factor (number): Energy retained on wall bounces; scales the reflected velocity component. Default: 0.8

### tokens (object)
Root toggles:
- hide (bool): If true, token art is fully transparent (and live input ingestion is skipped). Default: false
- enable_wall_bounce (bool): If true, tokens bounce off canvas boundaries. Default: false
- look_at_mouse (bool): Token rotates to face the mouse position. Default: true
- facing (string): Base facing direction for the generated triangle art. "top" | "right" | "bottom" | "left". Default: "top"
- enable_token_collision (bool): Enables a secondary collision response pass for simple repulsion. Default: true
- rotation_offset_degrees (number): Additional rotation offset applied when looking at mouse. Default: 0
- spawn_behavior (array of string): Currently supports ["fade_in"]. Default: ["fade_in"]
- collision_behavior (array of string): Currently supports ["bounce_pop"]. Default: ["bounce_pop"]
- exit_behavior (array of string): Currently supports ["fade_out"]. Default: ["fade_out"]

#### tokens.collision (object)
- enabled (bool): Enables collision computation. Default: true
- type (string): "circle" or any string starting with "rect" (e.g. "rectangle"). Default: "circle"
- bounds_scale (number): Scales the collision radius/rect around each token’s current size. Default: 0.5
- elastic (bool): Present for future use; not currently changing logic. Default: true
- friction (number): Present for future use; not currently changing logic. Default: 0.6
- separation_strength (number): Present for future use; not currently changing logic. Default: 0.2
- strength (number): Present for future use; not currently changing logic. Default: 0.2

Collision details:
- When `type` is circle, collisions use the scaled sum of token radii.
- When `type` starts with rect, collisions use scaled AABB overlap area.
- Collision intensity is computed and compared against `animation.bounce_threshold` to trigger bounce_pop.

#### tokens.finds_home (object)
- enabled (bool): After a delay with no forces, tokens drift back toward their home position. Default: true
- delay_sec (number): Delay before home force engages. Default: 3.0
- strength (number): Magnitude of home force (per second). Default: 100.0

#### tokens.flocking (object)
- enabled (bool): Enable flocking forces. Default: true
- radius (number): Neighbor radius for flocking/neighborhood visuals. Default: 149.6
- alignment (number): Weight for alignment force. Default: 0.4
- cohesion (number): Weight for cohesion force. Default: 0.01
- separation (number): Weight for separation force. Default: 1.15

### output (object)
- use_spout (bool): If true, send composed frames via Spout (Isadora path). Default: true
- spout_invert (bool): Vertical inversion for Spout output. Default: false
- numpy_invert (bool): Vertical inversion flag for NumPy frames (if used externally). Default: false

Notes:
- In Isadora via izzy_main.py: use the “Use Spout” input to toggle at runtime; the Pythoner script calls `set_use_spout` under the hood.
- The simulation exposes `TokenSimulation.send_to_spout()` and `TokenSimulation.get_frame_numpy(use_alpha)`.

### visual_elements (object)
All of these are rendered using OpenGL for speed. Each element’s object supports:
- enabled (bool)
- color ([r,g,b] or [r,g,b,a]; 0–255 or 0–1)
- thickness (number)

Implemented elements:
- token_collision_bounds: Draws either a circle or a rectangle outline around tokens based on `tokens.collision.type` and scaled by `tokens.collision.bounds_scale`.
- velocity_vector: A line showing the current velocity. Thresholded to avoid tiny vectors.
- force_vector: A line showing the sum of physical forces applied this frame.
- flocking_radius: A circle centered on the token using `tokens.flocking.radius`. Segment count adapts to radius to limit cost.
- separation_lines: Lines to nearby tokens within the flocking radius. Each pair is drawn once. Supports draw order toggle via visual_elements.separation_lines.mode: "over" (default; drawn after tokens so lines are always on top) or "in_order" (drawn during each token’s pass, interleaving with token quads).
- token_center: A small circle at the token’s center (fixed small segment count).
- mouse_radius: A circle at the mouse position sized by `mouse_force.max_distance`. Drawn in the simulation’s GL pass. The Y coordinate is adjusted to match final screen orientation.
- dead_overlay: Present in config; no current implementation (typically left false).


## Additional ways to change behavior

These are configuration-adjacent controls and APIs that modify behavior at runtime or influence the pipeline.

- Runtime updates via JSON (Isadora or API)
  - Call `TokenSimulation.update_settings(json_str)` with a JSON string containing runtime keys (non-`init_`) to change behavior while running.
  - izzy_main.py reads the “Config JSON (str)” input and passes it through; we also avoid re-parsing if the JSON is unchanged.
  - The simulation performs a config audit on update, logging unknown/missing keys under category `config`.

- Spout control (Isadora)
  - Toggling `Use Spout` input in izzy_main.py calls `TokenSimulation.set_use_spout(flag, sender_name)` which creates/releases the Spout sender and writes `output.use_spout` into the runtime settings.
  - Orientation: control with `output.spout_invert` (default false). If your host expects the opposite orientation, set it to true.
  - NumPy output: `TokenSimulation.get_frame_numpy(use_alpha)` returns an upright BGR/BGRA NumPy frame. izzy_main can apply an extra flip depending on `output.numpy_invert`.

- Live images and token art updates
  - To use incoming images each frame, set `input.use_live_image=true` and `input.live_image_update=true`.
  - To reduce cost when input only sometimes changes, set `live_image_update=false` and `hash_input=true`.
  - To switch back to generated token art immediately, set `use_live_image=false` (the simulation invalidates token caches and regenerates art right away).

- DebugManager
  - Global debugging can be enabled at startup via `shared.init_debug(enable, categories, config_json)`; it will respect `debug.debug_manager` if present. Use categories like `render`, `texture`, `factory`, `token`, `collision`, `config`.

- Custom token visuals / behavior
  - Subclass `Token` and override `generate_image` or other methods. Wire your class into `TokenSimulation(custom_token_class=YourToken)` or the TokenFactory.
  - Behavior arrays (`spawn_behavior`, `collision_behavior`, `exit_behavior`) are designed to stack in the future. Currently one value per category is used, but they accept arrays.

- Performance tips
  - Turn off `debug.stats_overlay` and `debug.show_spatial_grid` for clarity/less overlay work.
  - Visual elements like flocking circles and separation lines are OpenGL-based, but they still add draw calls; disable them in `visual_elements` for higher FPS.
  - The debug overlay texture upload is throttled internally; you can keep `stats_overlay=true` with lower upload frequency while still drawing the last uploaded texture each frame.


## Example configuration

This example mirrors the repository’s default config.json at time of writing.

```json
{
  "animation": {
    "bounce_duration_ms": 500.0,
    "bounce_scale": 1.5,
    "bounce_threshold": 0.5,
    "fade_in_duration_ms": 789.0
  },
  "debug": {
    "stats_overlay": true,
    "show_spatial_grid": true,
    "debug_manager": false
  },
  "init_canvas": {
    "height": 1080.0,
    "min_padding": 20.0,
    "width": 1920.0
  },
  "init_token": {
    "height": 120.0,
    "width": 120.0
  },
  "input": {
    "hash_input": true,
    "use_live_image": true,
    "live_image_update": true,
    "compute_hash_when_live_update": true
  },
  "mouse_force": {
    "enabled": true,
    "falloff": "linear",
    "force_strength": 3.0,
    "max_distance": 100.0
  },
  "timing": {
    "fade_in_duration_sec": 2.5,
    "respawn_collision_delay_sec": 10.0,
    "respawn_delay_sec": 1.5
  },
  "physics": {
    "bounce_factor": 0.8
  },
  "tokens": {
    "collision": {
      "bounds_scale": 0.5,
      "elastic": true,
      "enabled": true,
      "friction": 0.6000000238418579,
      "separation_strength": 0.20000000298023224,
      "strength": 0.20000000298023224,
      "type": "circle"
    },
    "collision_behavior": ["bounce_pop"],
    "enable_wall_bounce": false,
    "exit_behavior": ["fade_out"],
    "facing": "top",
    "finds_home": {
      "delay_sec": 3.0,
      "enabled": true,
      "strength": 100.0
    },
    "flocking": {
      "alignment": 0.4000000059604645,
      "cohesion": 0.009999999776482582,
      "enabled": true,
      "radius": 149.6,
      "separation": 1.149999976158142
    },
    "hide": false,
    "look_at_mouse": true,
    "enable_token_collision": true,
    "rotation_offset_degrees": 0,
    "spawn_behavior": ["fade_in"]
  },
  "output": {
    "use_spout": true,
    "spout_invert": false,
    "numpy_invert": false
  },
  "visual_elements": {
    "dead_overlay": false,
    "flocking_radius": {
      "color": [128, 128, 128],
      "enabled": true,
      "thickness": 2.0
    },
    "force_vector": {
      "enabled": true,
      "color": [255, 128, 0],
      "thickness": 1.0
    },
    "mouse_radius": {
      "color": [0, 128, 255],
      "enabled": true,
      "thickness": 9.0
    },
    "separation_lines": {
      "color": [0, 255, 255],
      "enabled": true,
      "thickness": 1.0
    },
    "token_center": {
      "color": [255, 255, 255],
      "enabled": true,
      "thickness": 6.0
    },
    "token_collision_bounds": {
      "color": [255, 0, 0],
      "enabled": true,
      "thickness": 2.0
    },
    "velocity_vector": {
      "color": [255, 255, 0],
      "enabled": true,
      "thickness": 3.0
    }
  }
}
```

---

If you notice any discrepancies between this document and your build’s behavior, please share the config audit logs (category `config`) from initialization or after an update. The audit will list unknown/unused keys and any missing keys that the code expects (using defaults instead).
