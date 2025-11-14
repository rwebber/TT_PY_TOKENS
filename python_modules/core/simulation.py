import pygame
import SpoutGL
from OpenGL.GL import *
from time import time

from core.rendering import SimulationRenderer
from core import shared
from core.settings_manager import SettingsManager
from core.token_factory import TokenFactory
from core.token import Token
from core.respawn_manager import RespawnManager
from core.token_runtime import update_simulation, process_image_input
from core.debug import debug, DebugManager
from core.utils import (
    prepare_spout_output,
    prepare_video_output,
    draw_gl_circle_outline,
    draw_gl_line
)


class TokenSimulation:
    """
    Manages the core token simulation system.
    Handles initialization, updates, and rendering for both standalone and Isadora usage.

    The simulation supports three types of behavior arrays in configuration:
        - spawn_behavior: Controls how tokens appear in the simulation
        - collision_behavior: Controls how tokens react to collisions
        - exit_behavior: Controls how tokens are removed from the simulation

    These behaviors are designed as arrays to support future stacking of multiple behaviors.
    Currently implemented as single behaviors, but architecture allows for future expansion.
    """

    # --- Back-compat shims for izzy_main.py ---
    def update_settings(self, new_json_str):
        """Update runtime settings from a JSON string (back-compat for Isadora wrapper).
        Only updates runtime (non-init_) keys.
        """
        try:
            if not hasattr(self, 'settings') or self.settings is None:
                self.settings = SettingsManager(new_json_str)
                self.settings_json = self.settings.get_config_json()
                return
            self.settings.update_runtime_settings(new_json_str)
            self.settings_json = new_json_str
        except Exception as e:
            shared.debug(f"update_settings error: {e}", category="render")

    def update_spout_name(self, name):
        """Set the Spout sender name if available (back-compat for Isadora wrapper)."""
        try:
            if hasattr(self, 'spout_sender') and self.spout_sender:
                self.spout_sender.setSenderName(str(name))
        except Exception as e:
            shared.debug(f"update_spout_name error: {e}", category="render")

    def send_to_spout(self, use_alpha=True):
        """Send the current composed texture to Spout (back-compat for Isadora wrapper).
        Note: SpoutGL.SpoutSender.sendTexture signature is (texID, texTarget, width, height, bInvert, hostFBO).
        bInvert is now configurable via settings.runtime_settings.output.spout_invert (default True) so you can
        resolve any remaining vertical inversion in Isadora without code changes.
        The use_alpha parameter is retained for API compatibility but not used here.
        """
        try:
            if not hasattr(self, 'spout_sender') or not self.spout_sender:
                return
            if not hasattr(self, 'renderer') or self.renderer is None:
                return
            tex_id = getattr(self.renderer, 'main_texture', None)
            if not tex_id:
                return
            glBindTexture(GL_TEXTURE_2D, tex_id)
            out_cfg = {}
            try:
                out_cfg = self.settings.get_output_settings() if hasattr(self, 'settings') else {}
            except Exception:
                out_cfg = {}
            b_invert = bool(out_cfg.get('spout_invert', True))
            self.spout_sender.sendTexture(int(tex_id), GL_TEXTURE_2D,
                                          int(self.display_width), int(self.display_height),
                                          b_invert, 0)
        except Exception as e:
            shared.debug(f"send_to_spout error: {e}", category="render")

    def get_frame_numpy(self, use_alpha=True):
        """Read back the current composed frame into a NumPy array (BGR/BGRA).
        Vertical orientation is controlled by settings.output.numpy_invert.
        Returns None on failure.
        """
        try:
            import numpy as _np
        except Exception:
            return None
        try:
            w, h = int(self.display_width), int(self.display_height)
            if w <= 0 or h <= 0:
                return None
            # Save current framebuffer binding
            try:
                prev_fbo = glGetIntegerv(GL_FRAMEBUFFER_BINDING)
            except Exception:
                prev_fbo = 0
            # Bind our main FBO if available; otherwise read from default framebuffer
            target_fbo = getattr(self.renderer, 'main_fbo', 0) if hasattr(self, 'renderer') else 0
            try:
                glBindFramebuffer(GL_FRAMEBUFFER, target_fbo or 0)
            except Exception:
                pass
            # Read RGBA always, then drop A if not needed
            pixel_data = glReadPixels(0, 0, w, h, GL_RGBA, GL_UNSIGNED_BYTE)
            if not pixel_data:
                # Restore framebuffer
                try:
                    glBindFramebuffer(GL_FRAMEBUFFER, prev_fbo)
                except Exception:
                    pass
                return None
            arr = _np.frombuffer(pixel_data, dtype=_np.uint8)
            arr = arr.reshape((h, w, 4))
            # Decide vertical orientation based on settings
            try:
                out_cfg = self.settings.get_output_settings() if hasattr(self, 'settings') else {}
                do_flip = bool(out_cfg.get('numpy_invert', False))
            except Exception:
                do_flip = False
            if do_flip:
                # Flip vertically to convert from GL's bottom-left origin to top-left
                arr = _np.flipud(arr)
            # Convert RGBA -> BGRA or BGR
            if use_alpha:
                arr = arr[:, :, [2, 1, 0, 3]]
            else:
                arr = arr[:, :, [2, 1, 0]]
            # Ensure contiguous
            out = _np.ascontiguousarray(arr, dtype=_np.uint8)
            # Restore framebuffer binding
            try:
                glBindFramebuffer(GL_FRAMEBUFFER, prev_fbo)
            except Exception:
                pass
            return out
        except Exception as e:
            shared.debug(f"get_frame_numpy error: {e}", category="render")
            return None

    # --- Back-compat shims for izzy_main.py ---
    def update_settings(self, new_json_str):
        """Update runtime settings from a JSON string (back-compat for Isadora wrapper).
        Only updates runtime (non-init_) keys.
        """
        try:
            if not hasattr(self, 'settings') or self.settings is None:
                self.settings = SettingsManager(new_json_str)
                self.settings_json = self.settings.get_config_json()
                return
            self.settings.update_runtime_settings(new_json_str)
            self.settings_json = new_json_str
        except Exception as e:
            shared.debug(f"update_settings error: {e}", category="render")

    def update_spout_name(self, name):
        """Set the Spout sender name if available (back-compat for Isadora wrapper)."""
        try:
            if hasattr(self, 'spout_sender') and self.spout_sender:
                self.spout_sender.setSenderName(str(name))
        except Exception as e:
            shared.debug(f"update_spout_name error: {e}", category="render")

    def send_to_spout(self, use_alpha=True):
        """Send the current composed texture to Spout (back-compat for Isadora wrapper).
        Note: SpoutGL.SpoutSender.sendTexture signature is (texID, texTarget, width, height, bInvert, hostFBO).
        bInvert is now configurable via settings.runtime_settings.output.spout_invert (default True) so you can
        resolve any remaining vertical inversion in Isadora without code changes.
        The use_alpha parameter is retained for API compatibility but not used here.
        """
        try:
            if not hasattr(self, 'spout_sender') or not self.spout_sender:
                return
            if not hasattr(self, 'renderer') or self.renderer is None:
                return
            tex_id = getattr(self.renderer, 'main_texture', None)
            if not tex_id:
                return
            glBindTexture(GL_TEXTURE_2D, tex_id)
            out_cfg = {}
            try:
                out_cfg = self.settings.get_output_settings() if hasattr(self, 'settings') else {}
            except Exception:
                out_cfg = {}
            b_invert = bool(out_cfg.get('spout_invert', True))
            self.spout_sender.sendTexture(int(tex_id), GL_TEXTURE_2D,
                                          int(self.display_width), int(self.display_height),
                                          b_invert, 0)
        except Exception as e:
            shared.debug(f"send_to_spout error: {e}", category="render")

    def get_frame_numpy(self, use_alpha=True):
        """Read back the current composed frame into a NumPy array (BGR/BGRA).
        Vertical orientation is controlled by settings.output.numpy_invert.
        Returns None on failure.
        """
        try:
            import numpy as _np
        except Exception:
            return None
        try:
            w, h = int(self.display_width), int(self.display_height)
            if w <= 0 or h <= 0:
                return None
            # Save current framebuffer binding
            try:
                prev_fbo = glGetIntegerv(GL_FRAMEBUFFER_BINDING)
            except Exception:
                prev_fbo = 0
            # Bind our main FBO if available; otherwise read from default framebuffer
            target_fbo = getattr(self.renderer, 'main_fbo', 0) if hasattr(self, 'renderer') else 0
            try:
                glBindFramebuffer(GL_FRAMEBUFFER, target_fbo or 0)
            except Exception:
                pass
            # Read RGBA always, then drop A if not needed
            pixel_data = glReadPixels(0, 0, w, h, GL_RGBA, GL_UNSIGNED_BYTE)
            if not pixel_data:
                # Restore framebuffer
                try:
                    glBindFramebuffer(GL_FRAMEBUFFER, prev_fbo)
                except Exception:
                    pass
                return None
            arr = _np.frombuffer(pixel_data, dtype=_np.uint8)
            arr = arr.reshape((h, w, 4))
            # Decide vertical orientation based on settings
            try:
                out_cfg = self.settings.get_output_settings() if hasattr(self, 'settings') else {}
                do_flip = bool(out_cfg.get('numpy_invert', False))
            except Exception:
                do_flip = False
            if do_flip:
                # Flip vertically to convert from GL's bottom-left origin to top-left
                arr = _np.flipud(arr)
            # Convert RGBA -> BGRA or BGR
            if use_alpha:
                arr = arr[:, :, [2, 1, 0, 3]]
            else:
                arr = arr[:, :, [2, 1, 0]]
            # Ensure contiguous
            out = _np.ascontiguousarray(arr, dtype=_np.uint8)
            # Restore framebuffer binding
            try:
                glBindFramebuffer(GL_FRAMEBUFFER, prev_fbo)
            except Exception:
                pass
            return out
        except Exception as e:
            shared.debug(f"get_frame_numpy error: {e}", category="render")
            return None
 
    def set_use_spout(self, flag: bool, sender_name: str | None = None):
        """Enable or disable Spout usage at runtime.
        - When enabling: (re)create sender if missing and optionally set sender_name.
        - When disabling: release sender if present.
        Also writes the value into settings.runtime_settings.output.use_spout so downstream
        code can query the current state consistently.
        """
        try:
            # Update runtime settings copy if available
            if hasattr(self, 'settings') and self.settings is not None:
                try:
                    out = dict(self.settings.get_output_settings())
                except Exception:
                    out = {}
                out['use_spout'] = bool(flag)
                # Persist back to runtime_settings
                if not hasattr(self.settings, 'runtime_settings') or not isinstance(self.settings.runtime_settings, dict):
                    self.settings.runtime_settings = {}
                self.settings.runtime_settings['output'] = out
        except Exception as e:
            shared.debug(f"set_use_spout settings update error: {e}", category="render")

        try:
            if flag:
                # Enable: ensure we have a sender
                if not hasattr(self, 'spout_sender') or self.spout_sender is None:
                    self.spout_sender = SpoutGL.SpoutSender()
                if sender_name:
                    try:
                        self.spout_sender.setSenderName(str(sender_name))
                    except Exception:
                        pass
            else:
                # Disable: release sender and set to None to free resources
                if hasattr(self, 'spout_sender') and self.spout_sender is not None:
                    try:
                        self.spout_sender.releaseSender()
                    except Exception:
                        pass
                    self.spout_sender = None
        except Exception as e:
            shared.debug(f"set_use_spout error: {e}", category="render")

    def __init__(self, custom_token_class=None):
        self.renderer = None  # Will hold SimulationRenderer instance
        self.spout_sender = SpoutGL.SpoutSender()
        self.settings = None
        self.settings_json = "{}"
        self.tokens = []
        self.token_factory = None
        self.respawner = None
        self.last_mouse_pos = pygame.Vector2(-1000, -1000)
        self.display_width = 1920
        self.display_height = 1080
        self.token_class = custom_token_class or Token
        self.window_mode = False
        self.last_update_time = time()
        self.debug_surface = None  # For debug overlay rendering

    def update(self, mouse_pos=(0, 0), image_input=None):
        """Process one frame of the simulation."""
        if not pygame.display.get_init():
            return None

        try:
            # Calculate time delta
            current_time = time()
            dt = current_time - self.last_update_time
            self.last_update_time = current_time


            # Process mouse input (normalize to y-down once, independent of entry point)
            try:
                mx, my = float(mouse_pos[0]), float(mouse_pos[1])
            except Exception:
                mx, my = float(getattr(mouse_pos, 'x', 0.0)), float(getattr(mouse_pos, 'y', 0.0))
            # Flip Y against the canvas height so internal logic consistently uses y-down coordinates
            current_mouse_pos = pygame.Vector2(mx, self.display_height - my)
            mouse_velocity = current_mouse_pos - self.last_mouse_pos
            self.last_mouse_pos = current_mouse_pos

            # Make sure we're in the correct OpenGL context
            if not pygame.display.get_init():
                shared.debug("Display not initialized", category="render")
                return None

            # Begin frame
            try:
                _t0 = time()
                self.renderer.begin_frame()
                if hasattr(shared, 'perf'): shared.perf['begin_frame_ms'] = (time() - _t0) * 1000.0
            except Exception as e:
                shared.debug(f"Error in begin_frame: {str(e)}", category="render")
                return None

            # If use_live_image was toggled, invalidate all token images so they switch immediately
            try:
                if hasattr(self.settings, 'consume_use_live_image_toggle') and self.settings.consume_use_live_image_toggle():
                    # Determine the new desired state
                    try:
                        new_use_live = bool(self.settings.get_input_settings().get('use_live_image', False))
                    except Exception:
                        new_use_live = False
                    for t in self.tokens:
                        if t is None:
                            continue
                        try:
                            # Invalidate all cached image state
                            t._base_image = None
                            t._cached_scaled_image = None
                            t._cached_image_hash = None
                            t.image = None
                            # If live images were just disabled, immediately generate default art
                            if not new_use_live:
                                try:
                                    t._base_image = t.generate_image(self.settings)
                                except Exception:
                                    t._base_image = None
                            # Ensure texture refresh
                            t._should_update_texture = True
                        except Exception:
                            pass
            except Exception as _e:
                shared.debug(f"Error invalidating token images after use_live_image toggle: {_e}", category="render")

            # Process image input if any
            try:
                _t0 = time()
                # Respect the current configuration: do not force-enable live image usage.
                # If input.use_live_image is True, process_image_input will update the shared image.
                process_image_input(image_input, self.settings, self.tokens)
                if hasattr(shared, 'perf'): shared.perf['process_image_input_ms'] = (time() - _t0) * 1000.0
            except Exception as e:
                shared.debug(f"Error processing image input: {str(e)}", category="render")

            # Update simulation using token_runtime
            try:
                _t0 = time()
                update_simulation(
                    self.tokens,
                    self.respawner,
                    self.debug_surface,
                    current_mouse_pos,
                    mouse_velocity,
                    self.settings,
                    (self.display_width, self.display_height),
                    dt
                )
                if hasattr(shared, 'perf'): shared.perf['update_simulation_ms'] = (time() - _t0) * 1000.0
            except Exception as e:
                shared.debug(f"Error in simulation update: {str(e)}", category="render")

            # Render each token with error handling
            shared.debug(f"Rendering {len(self.tokens)} tokens", category="render")
            for i, token in enumerate(self.tokens[:5]):  # Check first 5 tokens
                if token is not None:
                    shared.debug(f"Token {i}: pos={token.position}, size={token.current_size}, opacity={getattr(token, 'opacity', 'N/A')}", category="render")
            _t0 = time()
            rendered_count = 0
            for token in self.tokens:
                if token is not None:  # Check for None since tokens can be removed
                    try:
                        self.renderer.render_token(token)
                        rendered_count += 1
                    except Exception as e:
                        shared.debug(f"Error rendering token: {str(e)}", category="render")
                        continue
            if hasattr(shared, 'perf'):
                shared.perf['render_tokens_ms'] = (time() - _t0) * 1000.0
                shared.perf['rendered_tokens'] = rendered_count

            # Separation lines 'over tokens' pass (optional)
            try:
                visuals = self.settings.get_visual_elements() if hasattr(self.settings, 'get_visual_elements') else {}
                sep_cfg = visuals.get("separation_lines", {}) if isinstance(visuals, dict) else {}
                if isinstance(sep_cfg, dict) and sep_cfg.get("enabled", False):
                    mode = str(sep_cfg.get("mode", "over")).lower()
                    if mode == "over":
                        scolor = tuple(sep_cfg.get("color", [0,255,255]))
                        sthick = float(sep_cfg.get("thickness", 1))
                        try:
                            tokens_cfg = self.settings.get_token_settings() if hasattr(self.settings, 'get_token_settings') else {}
                            flocking = tokens_cfg.get("flocking", {}) if isinstance(tokens_cfg, dict) else {}
                            max_r = float(flocking.get("radius", 100.0))
                        except Exception:
                            max_r = 100.0
                        max_r2 = max_r * max_r
                        # Draw each pair once
                        for t in self.tokens:
                            if t is None:
                                continue
                            neighbors = getattr(t, "_nearby_for_visuals", [])
                            cx, cy = float(t.position.x), float(t.position.y)
                            for other in neighbors:
                                try:
                                    if other is None or other is t:
                                        continue
                                    if id(t) > id(other):
                                        continue
                                    ox, oy = float(other.position.x), float(other.position.y)
                                    dx = ox - cx
                                    dy = oy - cy
                                    if dx*dx + dy*dy <= max_r2:
                                        draw_gl_line(cx, cy, ox, oy, color=scolor, thickness=sthick)
                                except Exception:
                                    continue
            except Exception as e:
                shared.debug(f"Error drawing separation lines over-pass: {str(e)}", category="render")

            # Draw mouse radius using OpenGL (after tokens for visibility)
            try:
                _t0 = time()
                visuals = self.settings.get_visual_elements() if hasattr(self.settings, 'get_visual_elements') else {}
                mouse_vis = visuals.get("mouse_radius", {}) if isinstance(visuals, dict) else {}
                if isinstance(mouse_vis, dict) and mouse_vis.get("enabled", False):
                    color = mouse_vis.get("color", [0,128,255])
                    thickness = float(mouse_vis.get("thickness", 1))
                    radius = self.settings.get_mouse_force_settings().get("max_distance", 50)
                    # Draw directly in y-down coordinates (OpenGL projection is set to y-down)
                    draw_gl_circle_outline(current_mouse_pos.x, current_mouse_pos.y, float(radius), color=color, thickness=thickness)
                if hasattr(shared, 'perf'): shared.perf['mouse_radius_ms'] = (time() - _t0) * 1000.0
            except Exception as e:
                shared.debug(f"Error drawing GL mouse radius: {str(e)}", category="render")

            # Draw debug overlay only if stats overlay or spatial grid is enabled
            try:
                _t0 = time()
                dbg = self.settings.get_debug_settings() if hasattr(self.settings, 'get_debug_settings') else {}
                stats_on = bool(dbg.get("stats_overlay", False))
                grid_on = bool(dbg.get("show_spatial_grid", False))
                overlay_needed = stats_on or grid_on
                if overlay_needed:
                    # Throttle texture uploads for overlay for performance; draw every frame using last uploaded texture
                    now_t = time()
                    if not hasattr(self, '_last_overlay_upload_time'):
                        self._last_overlay_upload_time = 0.0
                    if not hasattr(self, '_overlay_update_interval'):
                        self._overlay_update_interval = 0.1  # seconds, ~10 Hz
                    should_upload = (now_t - self._last_overlay_upload_time) >= self._overlay_update_interval
                    if should_upload:
                        self._last_overlay_upload_time = now_t
                    self.renderer.render_debug_overlay(self.debug_surface, upload=should_upload)
                if hasattr(shared, 'perf'):
                    shared.perf['debug_overlay_ms'] = (time() - _t0) * 1000.0 if overlay_needed else 0.0
            except Exception as e:
                shared.debug(f"Error drawing debug overlay: {str(e)}", category="render")

            # End frame
            try:
                _t0 = time()
                self.renderer.end_frame()
                if hasattr(shared, 'perf'): shared.perf['end_frame_ms'] = (time() - _t0) * 1000.0
            except Exception as e:
                shared.debug(f"Error in end_frame: {str(e)}", category="render")
                return None

            # Reset perf at end so the overlay in next frame shows this frame's measurements
            try:
                if hasattr(shared, 'perf') and hasattr(shared, 'reset_perf'):
                    # Do not reset immediately; leave values for next frame's overlay draw
                    pass
            except Exception:
                pass

            # Return texture ID for external use
            return self.renderer.main_texture

        except Exception as e:
            shared.debug(f"Critical error in update: {str(e)}", category="render")
            import traceback
            shared.debug(f"Traceback: {traceback.format_exc()}", category="render")
            return None

    def run_config_audit(self):
        """Manually trigger a config audit and return the report.
        Useful in external hosts (e.g., Isadora) to re-check after dynamic updates.
        """
        try:
            if hasattr(self, 'settings') and hasattr(self.settings, 'audit_current_config'):
                return self.settings.audit_current_config()
        except Exception:
            pass
        return None

    def cleanup(self):
        """Clean up resources when unloading."""
        try:
            if self.renderer:
                self.renderer.cleanup()
                self.renderer = None

            if self.spout_sender:
                self.spout_sender.releaseSender()
                self.spout_sender = None

            self.tokens.clear()
            self.token_factory = None
            self.respawner = None
            self.settings = None
            self.debug_surface = None

        except Exception as e:
            print(f"Error during cleanup: {e}")

    def _draw_debug_overlay(self):
        """Draw debug information on the debug surface"""
        debug_settings = self.settings.get_debug_settings()
        if not debug_settings.get("enabled", False):
            return

        # Draw performance stats with a subtle shadow (no panel) to keep background visible
        stats = self._get_performance_stats()
        font = pygame.font.Font(None, 24)
        line_height = 25
        y = 10
        x = 10
        for line in stats:
            # Shadow
            shadow = font.render(line, True, (0, 0, 0))
            self.debug_surface.blit(shadow, (x + 1, y + 1))
            # Text
            text = font.render(line, True, (255, 255, 255))
            self.debug_surface.blit(text, (x, y))
            y += line_height

    def init(self, config_json="{}", use_spout=False, sender_name="TokenSimulation", standalone_mode=False, bg_mask_surface=None):
        """Initialize the simulation environment."""
        try:
            self.settings = SettingsManager(config_json)
            self.settings_json = self.settings.get_config_json()

            # Report active visual elements and implementation coverage
            try:
                active_visuals = []
                if hasattr(self.settings, 'get_active_visuals'):
                    active_visuals = self.settings.get_active_visuals()
                visuals = self.settings.get_visual_elements() if hasattr(self.settings, 'get_visual_elements') else {}
                supported = {"token_collision_bounds", "velocity_vector", "mouse_radius", "force_vector", "flocking_radius", "separation_lines", "token_center"}
                if isinstance(active_visuals, list):
                    shared.debug(f"Active visual elements: {active_visuals}", category="render")
                    for name in active_visuals:
                        if name not in supported:
                            shared.debug(f"WARNING: Visual element '{name}' is enabled but has no drawing implementation yet.", category="render")
                elif isinstance(visuals, dict):
                    # Fallback: compute on the fly
                    tmp = []
                    for k, cfg in visuals.items():
                        if (isinstance(cfg, dict) and cfg.get("enabled", False)) or cfg is True:
                            tmp.append(k)
                    shared.debug(f"Active visual elements: {tmp}", category="render")
                    for name in tmp:
                        if name not in supported:
                            shared.debug(f"WARNING: Visual element '{name}' is enabled but has no drawing implementation yet.", category="render")
            except Exception as e:
                shared.debug(f"Error reporting visual elements: {str(e)}", category="render")

            # Audit current config for unknown/unused and missing expected keys
            try:
                if hasattr(self.settings, 'audit_current_config'):
                    self.settings.audit_current_config()
            except Exception:
                pass

            canvas_size = self.settings.get_init_canvas_size()
            self.display_width, self.display_height = canvas_size
            self.last_mouse_pos = pygame.Vector2(-1000, -1000)

            if not pygame.get_init():
                pygame.init()

            # Initialize renderer with error handling
            try:
                self.renderer = SimulationRenderer(self.display_width, self.display_height)
            except Exception as e:
                shared.debug(f"Error initializing renderer: {str(e)}")
                raise

            # Initialize debug surface
            self.debug_surface = pygame.Surface(canvas_size, pygame.SRCALPHA)
            shared.debug_surface = self.debug_surface  # Set in shared module for access by tokens
            
            # Clear window  
            glClearColor(0.0, 0.0, 0.0, 1.0)  # This sets clear color to black
            glClear(GL_COLOR_BUFFER_BIT)

            # Initialize Spout
            if use_spout:
                self.spout_sender.setSenderName(str(sender_name))

            # Initialize tokens
            try:
                self.token_factory = TokenFactory(self.settings, token_class=self.token_class)
                # Provide optional background mask to factory if available
                try:
                    if bg_mask_surface is not None:
                        self.token_factory.set_grid_mask_surface(bg_mask_surface)
                except Exception:
                    pass
                self.tokens.clear()
                new_tokens = self.token_factory.create_initial_tokens()
                shared.debug(f"Created {len(new_tokens)} tokens")
                self.tokens.extend(new_tokens)
            except Exception as e:
                shared.debug(f"Error creating tokens: {str(e)}")
                raise

            # Initialize respawn manager
            try:
                self.respawner = RespawnManager(
                    self.settings.get_timing_settings().get("respawn_delay_sec", 1.5),
                    token_factory=self.token_factory,
                    settings=self.settings
                )
            except Exception as e:
                shared.debug(f"Error initializing respawn manager: {str(e)}")
                raise

            self.window_mode = standalone_mode

        except Exception as e:
            shared.debug(f"Error in simulation initialization: {str(e)}")
            raise


# END OF FILE