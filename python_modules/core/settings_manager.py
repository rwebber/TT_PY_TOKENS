import json

from core.debug import debug, DebugManager


# SettingsManager handles both initialization (prefixed with 'init_') and runtime configuration.
# It provides getter methods for specific parts of the configuration used throughout the application.
class SettingsManager:
    def __init__(self, config_json):
        self.init_settings = {}
        self.runtime_settings = {}
        self.config_json = config_json  #string version of JSON
        config = json.loads(config_json)
        self._load_config(config)
        # Track last seen use_live_image to detect runtime toggles
        try:
            self._prev_use_live_image = bool(self.runtime_settings.get("input", {}).get("use_live_image", False))
        except Exception:
            self._prev_use_live_image = False

    # Separates config into init_settings and runtime_settings based on key prefix.
    def _load_config(self, config):
        for key, value in config.items():
            if key.startswith("init_"):
                self.init_settings[key] = value
            else:
                self.runtime_settings[key] = value

    def get_config_json(self):
        return self.config_json

    # Returns a tuple (width, height) for the canvas size, with defaults if unspecified.
    def get_init_canvas_size(self):
        canvas = self.init_settings.get("init_canvas", {})
        width = int(canvas.get("width", 800))
        height = int(canvas.get("height", 600))
        return (width, height)

    # Returns a tuple (width, height) for the token size, with defaults if unspecified.
    def get_token_size(self):
        token = self.init_settings.get("init_token", {})
        width = int(token.get("width", 64))
        height = int(token.get("height", 64))
        return (width, height)

    # Returns the mouse force configuration dictionary from runtime settings.
    def get_mouse_force_settings(self):
        return self.runtime_settings.get("mouse_force", {})

    # Returns the token configuration dictionary from runtime settings.
    def get_token_settings(self):
        return self.runtime_settings.get("tokens", {})

    def get_debug_settings(self):
        """Get debug-related settings"""
        return self.runtime_settings.get("debug", {})

    # Returns the visual elements configuration dictionary (debug drawing settings).
    def get_visual_elements(self):
        return self.runtime_settings.get("visual_elements", {})

    def get_active_visuals(self):
        """Return a list of visual element names that are enabled in config.
        Supports both dict entries with {enabled: bool} and legacy boolean True values.
        """
        active = []
        visuals = self.get_visual_elements()
        if isinstance(visuals, dict):
            for name, cfg in visuals.items():
                if isinstance(cfg, dict):
                    if cfg.get("enabled", False):
                        active.append(name)
                elif cfg is True:
                    active.append(name)
        return active

    def get_mouse_radius(self):
        return self.runtime_settings.get("mouse_radius", {})

    # Returns timing settings with fallbacks for respawn and fade-in durations.
    def get_timing_settings(self):
        return self.runtime_settings.get("timing", {
            "respawn_delay_sec": 0.5,
            "fade_in_duration_sec": 0.5
        })# Returns timing settings with fallbacks for respawn and fade-in durations.

    # Returns input settings that control the use of external token images.
    def get_input_settings(self):
        return self.runtime_settings.get("input", {})

    # Allows updating runtime settings during execution using a JSON string.
    # 'init_' keys are ignored to prevent changing critical startup parameters.
    def update_runtime_settings(self, new_json_str):
        try:
            updates = json.loads(new_json_str)
            for key, value in updates.items():
                if key.startswith("init_"):
                    # print(f"[WARNING] Cannot update init setting '{key}' at runtime.")
                    pass
                else:
                    self.runtime_settings[key] = value
            self.config_json = new_json_str
            # Run audit after applying updates
            try:
                self.audit_current_config()
            except Exception:
                pass
        except json.JSONDecodeError:
            print("[ERROR] Invalid JSON for runtime update.")

    def consume_use_live_image_toggle(self) -> bool:
        """Return True once when input.use_live_image changes since last check.
        Also updates the remembered value to the current one.
        """
        try:
            current = bool(self.get_input_settings().get("use_live_image", False))
        except Exception:
            current = False
        if current != getattr(self, "_prev_use_live_image", False):
            self._prev_use_live_image = current
            return True
        return False

    def get_output_settings(self):
        """Get video output configuration
        Defaults:
        - use_spout: True
        - spout_invert: False (no vertical flip by default)
        - numpy_invert: False (no vertical flip by default for NumPy output)
        """
        return self.runtime_settings.get("output", {
            "use_spout": True,
            "spout_invert": False,
            "numpy_invert": False,
        })

    # -------------------- Config Audit Utilities --------------------
    def _flatten_keys(self, data, prefix=""):
        """Flatten nested dict keys into dotted paths. Lists are treated as values (no expansion)."""
        keys = set()
        if isinstance(data, dict):
            for k, v in data.items():
                p = f"{prefix}{k}" if not prefix else f"{prefix}.{k}"
                if isinstance(v, dict):
                    keys.add(p)
                    keys |= self._flatten_keys(v, p)
                else:
                    keys.add(p)
        return keys

    def _known_keys_and_prefixes(self):
        """Return a tuple (known_keys, known_prefixes) curated from current code usage."""
        known_keys = {
            # animation
            "animation.bounce_duration_ms",
            "animation.bounce_scale",
            "animation.bounce_threshold",
            "animation.fade_in_duration_ms",
            # debug
            "debug.stats_overlay",
            "debug.show_spatial_grid",
            # init
            "init_canvas.width",
            "init_canvas.height",
            "init_canvas.min_padding",
            "init_token.width",
            "init_token.height",
            # input
            "input.hash_input",
            "input.use_live_image",
            "input.live_image_update",
            "input.compute_hash_when_live_update",
            # mouse_force
            "mouse_force.enabled",
            "mouse_force.falloff",
            "mouse_force.force_strength",
            "mouse_force.max_distance",
            # timing
            "timing.fade_in_duration_sec",
            "timing.respawn_collision_delay_sec",
            "timing.respawn_delay_sec",
            # tokens root
            "tokens.enable_wall_bounce",
            "tokens.facing",
            "tokens.hide",
            "tokens.look_at_mouse",
            "tokens.collision_behavior",
            "tokens.exit_behavior",
            "tokens.spawn_behavior",
            "tokens.enable_token_collision",
            "tokens.rotation_offset_degrees",
            # tokens.collision
            "tokens.collision.bounds_scale",
            "tokens.collision.elastic",
            "tokens.collision.enabled",
            "tokens.collision.friction",
            "tokens.collision.separation_strength",
            "tokens.collision.strength",
            "tokens.collision.type",
            # tokens.finds_home
            "tokens.finds_home.enabled",
            "tokens.finds_home.delay_sec",
            "tokens.finds_home.strength",
            # tokens.flocking
            "tokens.flocking.enabled",
            "tokens.flocking.radius",
            "tokens.flocking.alignment",
            "tokens.flocking.cohesion",
            "tokens.flocking.separation",
            # physics
            "physics.bounce_factor",
            # output (Isadora path)
            "output.use_spout",
            "output.spout_invert",
            "output.numpy_invert",
        }
        known_prefixes = {
            # Accept any visual element nested key structures
            "visual_elements",
            # Treat top-level sections as recognized prefixes so headings are not flagged as unknown
            "animation",
            "debug",
            "init_canvas",
            "init_token",
            "init_grid_mask",  # allow grid mask init-only settings like threshold
            "input",
            "mouse_force",
            "timing",
            "physics",
            "tokens",
            "tokens.collision",
            "tokens.finds_home",
            "tokens.flocking",
            "output",
        }
        return known_keys, known_prefixes

    def audit_current_config(self):
        """Audit current settings for unknown/unused keys and missing expected keys.
        Logs results via shared.debug(category='config') and returns a dict report.
        Also stores the last report in core.shared.last_config_audit for overlay display.
        """
        try:
            from core import shared as _shared
        except Exception:
            _shared = None

        # Build present keys across init and runtime
        present_keys = set()
        present_keys |= self._flatten_keys(self.init_settings)
        present_keys |= self._flatten_keys(self.runtime_settings)

        known_keys, known_prefixes = self._known_keys_and_prefixes()

        def _is_recognized(key: str) -> bool:
            # exact match
            if key in known_keys:
                return True
            # prefix matches (allow any deeper nesting)
            for pref in known_prefixes:
                if key == pref or key.startswith(pref + "."):
                    return True
            return False

        unknown_keys = sorted([k for k in present_keys if not _is_recognized(k)])
        missing_expected = sorted([k for k in known_keys if k not in present_keys])

        # Avoid spamming the same audit repeatedly: compute a signature
        try:
            import hashlib, json as _json
            sig_src = _json.dumps({
                "present": sorted(present_keys),
            }, sort_keys=True)
            sig = hashlib.md5(sig_src.encode("utf-8")).hexdigest()
        except Exception:
            sig = None

        # Only log if signature changed or first time
        should_log = True
        if hasattr(self, "_last_audit_sig") and self._last_audit_sig == sig:
            should_log = False
        self._last_audit_sig = sig

        report = {
            "unknown_keys": unknown_keys,
            "missing_expected": missing_expected,
        }

        # Persist report for overlay
        try:
            if _shared is not None:
                from time import time as _time
                _shared.last_config_audit = report
                _shared.last_config_audit_time = _time()
        except Exception:
            pass

        if should_log and _shared is not None and hasattr(_shared, 'debug'):
            try:
                _shared.debug(f"Config audit: {len(unknown_keys)} unknown, {len(missing_expected)} missing expected", category="config")
                if unknown_keys:
                    _shared.debug(f"Unknown/unused keys present: {unknown_keys}", category="config")
                if missing_expected:
                    _shared.debug(f"Keys used by code but missing in your JSON (defaults applied): {missing_expected}", category="config")
            except Exception:
                pass

        return report
