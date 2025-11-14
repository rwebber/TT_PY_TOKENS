from typing import Optional
import sys, os
# Ensure this file's directory (python_modules) is on sys.path so `core.*` imports work regardless of host CWD
_pkg_dir = os.path.dirname(__file__)
if _pkg_dir not in sys.path:
    sys.path.insert(0, _pkg_dir)

import pygame
from pygame.locals import OPENGL, DOUBLEBUF, HIDDEN
from core.token import Token
from core.utils import str_to_bool, prepare_video_output
from core.simulation import TokenSimulation
from core.rendering import Renderer
from core.settings_manager import SettingsManager



# iz_input 1 "Use Spout ('True'/'False')" - Enable or disable Spout output
# iz_input 2 "Spout Sender Name (str)" - Spout sender name
# iz_input 3 "Use Alpha ('True'/'False')" - Whether to include alpha in output
# iz_input 4 "Config JSON (str)" - JSON string containing all runtime settings
# iz_input 5 "Mouse X (float)" - Current X position of the mouse
# iz_input 6 "Mouse Y (float)" - Current Y position of the mouse
# iz_input 7 "Image Input (RGBA NumPy)" - Optional image input to replace token visuals
# iz_input 8 "BG Image" - Optional image input to define grid shape
# iz_input 9 "Trigger" - Signal to trigger the update and render pass
# iz_output 1 "Video Output" - NumPy array (BGR or BGRA) representing the video frame


class CustomToken(Token):
    """
    A basic implementation of the Token class that renders as a white circle.
    This class can be modified to change the appearance and behavior of tokens.
    """

    def __init__(self, position, size, facing="top"):
        """
        Initialize the custom token.

        Args:
            position: Initial (x, y) position of the token
            size: (width, height) dimensions of the token
            facing: Direction the token faces ("top" by default)
        """
        super().__init__(position, size, facing)
        self.custom_property = None

    def generate_image(self, settings):
        """
        Create the visual representation of the token.

        Args:
            settings: Current simulation settings

        Returns:
            pygame.Surface: A circular token rendered as a white circle on transparent background
        """
        surface = pygame.Surface(self.size, pygame.SRCALPHA)
        surface.fill((0, 0, 0, 0))  # Transparent background
        radius = min(self.size[0], self.size[1]) // 2
        center = (self.size[0] // 2, self.size[1] // 2)
        pygame.draw.circle(surface, (255, 255, 255, 255), center, radius)
        return surface


# Global simulation instance
# _simulation = TokenSimulation(custom_token_class=CustomToken)  # use custom class for Token generation
# _simulation = TokenSimulation()  # use default/builtin Token Image
_simulation: Optional[TokenSimulation] = None
_renderer: Optional[Renderer] = None


def python_init(useSpout="False", sendername="TokenSimulation", useAlpha="True",
                config_json="{}", mouseX=0.0, mouseY=0.0, imageInput=None, BGimage=None,
                izTrig=False):
    """Initialize the simulation (called once by Isadora)"""
    global _simulation, _renderer
    use_spout = str_to_bool(str(useSpout))

    if _simulation is not None:
        return

    try:
        print("Initializing Token Simulation...")
        # Create settings manager first to get canvas size
        settings = SettingsManager(config_json)
        canvas_size = settings.get_init_canvas_size()

        # Initialize simulation
        _simulation = TokenSimulation()

        # Build optional grid mask from initial BGimage (runs once)
        bg_surface = None
        try:
            import numpy as _np
            if BGimage is not None and hasattr(BGimage, 'shape') and len(BGimage.shape) == 3:
                arr = BGimage
                # Convert color channels BGR(A) -> RGBA where possible
                if arr.shape[2] == 4:
                    arr = arr[:, :, [2, 1, 0, 3]]
                    mode = "RGBA"
                elif arr.shape[2] == 3:
                    arr = arr[:, :, [2, 1, 0]]
                    mode = "RGB"
                else:
                    arr = None
                if arr is not None:
                    bg_surface = pygame.image.frombuffer(arr.tobytes(), arr.shape[1::-1], mode)
        except Exception:
            bg_surface = None

        _simulation.init(config_json, use_spout, sendername, standalone_mode=False, bg_mask_surface=bg_surface)

        # Ensure Spout orientation default in Isadora matches Spout's expected origin
        # Default to True (invert vertically) unless explicitly set in config.
        try:
            if hasattr(_simulation, 'settings') and _simulation.settings is not None:
                out = dict(_simulation.settings.get_output_settings() or {})
                if 'spout_invert' not in out:
                    out['spout_invert'] = True
                if 'numpy_invert' not in out:
                    out['numpy_invert'] = True
                # Persist back into runtime settings so send_to_spout reads it
                if not hasattr(_simulation.settings, 'runtime_settings') or not isinstance(_simulation.settings.runtime_settings, dict):
                    _simulation.settings.runtime_settings = {}
                _simulation.settings.runtime_settings['output'] = out
        except Exception:
            pass

        # Create renderer with the same canvas size
        _renderer = Renderer(canvas_size[0], canvas_size[1])


    except Exception as e:
        print(f"Failed to initialize: {str(e)}")
        raise


def python_main(useSpout="False", sendername="TokenSimulation", useAlpha="True",
                config_json="{}", mouseX=0.0, mouseY=0.0, imageInput=None, BGimage=None,
                izTrig=False):

    """Process one frame (called repeatedly by Isadora)"""
    if not izTrig:
        return None

    global _simulation, _renderer, _last_config_json, _last_use_spout, _last_sender_name

    # Only update settings if the JSON actually changed (avoid per-frame parse cost)
    try:
        if _last_config_json != str(config_json):
            _simulation.update_settings(config_json)
            # Ensure default Spout orientation if user did not specify
            try:
                if hasattr(_simulation, 'settings') and _simulation.settings is not None:
                    out = dict(_simulation.settings.get_output_settings() or {})
                    if 'spout_invert' not in out:
                        out['spout_invert'] = True
                    if 'numpy_invert' not in out:
                        out['numpy_invert'] = True
                    if not hasattr(_simulation.settings, 'runtime_settings') or not isinstance(_simulation.settings.runtime_settings, dict):
                        _simulation.settings.runtime_settings = {}
                    _simulation.settings.runtime_settings['output'] = out
            except Exception:
                pass
            _last_config_json = str(config_json)
    except NameError:
        # First run: initialize cache and apply settings
        _last_config_json = str(config_json)
        _simulation.update_settings(config_json)
        # Ensure default Spout/Numpy orientation if user did not specify
        try:
            if hasattr(_simulation, 'settings') and _simulation.settings is not None:
                out = dict(_simulation.settings.get_output_settings() or {})
                if 'spout_invert' not in out:
                    out['spout_invert'] = True
                if 'numpy_invert' not in out:
                    out['numpy_invert'] = True
                if not hasattr(_simulation.settings, 'runtime_settings') or not isinstance(_simulation.settings.runtime_settings, dict):
                    _simulation.settings.runtime_settings = {}
                _simulation.settings.runtime_settings['output'] = out
        except Exception:
            pass
    except Exception:
        # On any error, still attempt to proceed with existing settings
        pass

    # Update sender name only when changed to avoid redundant calls
    try:
        if _last_sender_name != str(sendername):
            _simulation.update_spout_name(sendername)
            _last_sender_name = str(sendername)
    except NameError:
        _last_sender_name = str(sendername)
        _simulation.update_spout_name(sendername)
    except Exception:
        pass
    surface = _simulation.update((float(mouseX), float(mouseY)), imageInput)
    use_spout = str_to_bool(str(useSpout))
    use_alpha = str_to_bool(str(useAlpha))

    # Apply runtime Spout toggle to simulation only when changed
    try:
        if _last_use_spout != use_spout:
            _simulation.set_use_spout(use_spout, sendername)
            _last_use_spout = use_spout
    except NameError:
        _last_use_spout = use_spout
        _simulation.set_use_spout(use_spout, sendername)
    except Exception:
        pass

    if use_spout:
        if surface is not None:
            _renderer.render_surface(surface)  # Legacy no-op; kept for API compatibility
        _simulation.send_to_spout(use_alpha)
        return None

    # Produce a NumPy frame from the current GL composition when Spout is disabled
    # Orientation is now controlled inside TokenSimulation.get_frame_numpy via output.numpy_invert.
    frame = _simulation.get_frame_numpy(use_alpha)
    try:
        import numpy as _np
        if frame is not None and not frame.flags['C_CONTIGUOUS']:
            frame = _np.ascontiguousarray(frame, dtype=_np.uint8)
    except Exception:
        pass
    return frame


def python_finalize():
    """
    Comprehensive cleanup function called when Isadora unloads the script.
    Ensures proper release of all resources and memory to prevent leaks.
    """
    global _simulation, _renderer

    try:
        # 0. Renderer Cleanup
        if _renderer is not None:
            try:
                _renderer.cleanup()
            except Exception as e:
                print(f"Warning: Renderer cleanup error: {e}")
            finally:
                _renderer = None

        # 1. Simulation Cleanup
        if _simulation is not None:
            try:
                # Clean up Spout sender and OpenGL resources
                _simulation.cleanup()
            except Exception as e:
                print(f"Warning: Simulation cleanup error: {e}")
            finally:
                # Ensure simulation reference is cleared even if cleanup fails
                _simulation = None

        # 2. Force Garbage Collection
        import gc
        try:
            # Run garbage collection to clean up any circular references
            gc.collect()
        except Exception as e:
            print(f"Warning: Garbage collection error: {e}")

        # 3. Pygame Cleanup
        try:
            # First quit display to release OpenGL context
            if pygame.display.get_init():
                pygame.display.quit()

            # Then quit pygame to release all pygame resources
            if pygame.get_init():
                pygame.quit()
        except Exception as e:
            print(f"Warning: Pygame cleanup error: {e}")

        # 4. Clear Module-Level Variables
        try:
            # Get a copy of globals to avoid modification during iteration
            globals_copy = dict(globals())

            # Clear all global variables except essential functions
            protected_names = {
                'python_init',
                'python_main',
                'python_finalize'
            }

            for var_name, var_value in globals_copy.items():
                if var_name not in protected_names:
                    try:
                        globals()[var_name] = None
                    except Exception as e:
                        print(f"Warning: Could not clear global variable {var_name}: {e}")
        except Exception as e:
            print(f"Warning: Global variable cleanup error: {e}")

        # 5. Final Garbage Collection
        try:
            # Run garbage collection one more time to clean up any remaining objects
            gc.collect()
        except Exception as e:
            print(f"Warning: Final garbage collection error: {e}")

    except Exception as e:
        # If any unexpected error occurs, log it but continue with cleanup
        print(f"Critical error during finalization: {e}")

        # Emergency cleanup attempt for critical resources
        try:
            if pygame.get_init():
                pygame.quit()
        except:
            pass

    finally:
        # 6. Final Verification (Optional debug information)
        try:
            remaining_objects = gc.get_count()
            print(f"Finalization complete. Remaining objects: {remaining_objects}")
        except:
            pass