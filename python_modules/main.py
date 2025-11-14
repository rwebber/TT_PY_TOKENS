"""
Standalone visualization application for the token simulation system.
Provides a windowed OpenGL renderer for the token simulation, with mouse interaction
and configuration loading capabilities. This is the development/testing version of
the simulation that runs independently of Isadora.

The application reads configuration from config.json and renders tokens as simple
white circles that respond to mouse movement.
"""

import sys, os
# Ensure this file's directory (python_modules) is on sys.path so `core.*` imports work regardless of CWD
_pkg_dir = os.path.dirname(__file__)
if _pkg_dir not in sys.path:
    sys.path.insert(0, _pkg_dir)

import pygame
import json
import time
import builtins
import traceback

from OpenGL.GL import *
from OpenGL.GLU import *
from core.simulation import TokenSimulation
from core import shared
from core.utils import setup_gl_state  # OpenGL state setup utility



shared.init_debug(enable=True, categories=['token', 'collision', 'texture', 'factory', 'config'])

CONFIG_PATH = "config.json"


# """ Override Print() as a way to stop print output globally"""
# def noop(*args, **kwargs):
#     pass
# # Store original print for potential restoration
# original_print = print
# # Replace print with no-op function
# print = noop
#
# def configure_printing(enable=False):
#     if enable:
#         builtins.print = original_print
#     else:
#         builtins.print = noop
# configure_printing(enable=True)


class CustomToken():
    """
    Template token class for developers.

    Important:
    - This class is intentionally incomplete and is not used by default.
    - It does NOT currently inherit from core.token.Token. If you want to activate it,
      change the base class to Token and hook it up via your token factory/registration.
    - Use this as a starting point to create different default graphic designs for a token.

    How to activate:
    1) Change `class CustomToken():` to `class CustomToken(Token):`
    2) Provide/override methods as needed (e.g., generate_image)
    3) Register it in your token factory or configuration so the simulation can instantiate it
    """
    # To activate: change the base class to Token and wire it into the factory
    def __init__(self, position, size, facing="top", texture_pool=None):
        super().__init__(position, size, facing, texture_pool)
        self.custom_property = None

    def cleanup(self):
        """Ensure proper cleanup of OpenGL resources"""
        if self.texture_pool and self.texture_id is not None:
            self.texture_pool.release_texture(id(self))
            self.texture_id = None
        super().cleanup()

    def generate_image(self, settings):
        """Create the visual representation of the token with improved aesthetics."""
        surface = pygame.Surface(self.size, pygame.SRCALPHA)
        surface.fill((0, 0, 0, 0))  # Transparent background

        # Calculate dimensions
        width, height = self.size
        radius = min(width, height) // 2
        center = (width // 2, height // 2)

        # Draw main circle with slight transparency
        main_color = (255, 255, 255, 230)  # Slightly transparent white
        pygame.draw.circle(surface, main_color, center, radius)

        # Draw border
        border_color = (255, 255, 255, 255)  # Solid white
        pygame.draw.circle(surface, border_color, center, radius, 2)  # 2 pixel border

        # Add a highlight effect (smaller circle at top-left)
        highlight_radius = int(radius * 0.6)
        highlight_offset = -int(radius * 0.2)  # Move highlight up and left
        highlight_pos = (center[0] + highlight_offset, center[1] + highlight_offset)
        highlight_color = (255, 255, 255, 100)  # Very transparent white
        pygame.draw.circle(surface, highlight_color, highlight_pos, highlight_radius)

        return surface






def main():
    simulation = None
    try:
        print("Starting initialization...")
        pygame.init()

        # Set OpenGL attributes before creating window
        pygame.display.gl_set_attribute(pygame.GL_ALPHA_SIZE, 8)
        pygame.display.gl_set_attribute(pygame.GL_DEPTH_SIZE, 24)
        pygame.display.gl_set_attribute(pygame.GL_STENCIL_SIZE, 8)
        pygame.display.gl_set_attribute(pygame.GL_DOUBLEBUFFER, 1)

        # Create window with default size
        window_size = (800, 600)
        screen = pygame.display.set_mode(window_size, pygame.OPENGL | pygame.DOUBLEBUF)
        pygame.display.set_caption("Token Simulation")

        # Setup OpenGL state immediately after window creation
        setup_gl_state(window_size)

        # Load configuration
        with open('config.json', 'r') as f:
            config_str = f.read()

        # Initialize simulation
        simulation = TokenSimulation()
        # Try to load optional grid mask image (gridBG.png) from this module directory
        bg_surface = None
        try:
            bg_path = os.path.join(_pkg_dir, 'gridBG.png')
            if os.path.exists(bg_path):
                # Load then flip vertically so mask orientation matches on-screen y-down rendering
                tmp = pygame.image.load(bg_path)
                tmp = pygame.transform.flip(tmp, False, True)
                # Keep as 32-bit surface if it has alpha; else convert
                bg_surface = tmp.convert_alpha() if tmp.get_bitsize() in (32, 24) else tmp.convert()
        except Exception:
            bg_surface = None
        simulation.init(config_str, use_spout=False, standalone_mode=True, bg_mask_surface=bg_surface)

        # Update window size based on simulation settings
        window_size = (simulation.display_width, simulation.display_height)
        screen = pygame.display.set_mode(window_size, pygame.OPENGL | pygame.DOUBLEBUF)

        # Re-setup OpenGL state with updated window size
        setup_gl_state(window_size)

        clock = pygame.time.Clock()
        running = True
        last_time = time.time()

        while running:
            current_time = time.time()
            dt = current_time - last_time
            last_time = current_time

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False

            # Get current mouse position in screen space (y-down)
            mx, my = pygame.mouse.get_pos()
            current_mouse_pos = pygame.Vector2(mx, my)

            # Let the simulation handle rendering and display update internally
            simulation.update(current_mouse_pos)

            # Limit frame rate
            clock.tick(60)

    except Exception as e:
        print(f"Critical error: {str(e)}")
        traceback.print_exc()
    finally:
        if simulation:
            simulation.cleanup()
        pygame.quit()


if __name__ == "__main__":
    main()


    # end of file