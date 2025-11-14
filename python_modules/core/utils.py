"""
Core OpenGL/pygame utilities used across the project.

All general-purpose helpers related to textures, drawing quads, OpenGL state,
format conversion, and small helpers (like str_to_bool) should live here so
they can be reused by both standalone and Isadora runtimes.
"""
import pygame
import numpy
from OpenGL.GL import *
from OpenGL.GLU import *
import logging

from core.debug import debug, DebugManager


def create_gl_texture():
    """
    Create and configure an OpenGL texture with standard parameters.

    Returns:
        int: OpenGL texture handle
    """
    texture = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, texture)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    return texture

def surface_to_texture(surface, texture_id=None, flip_vertical=True):
    """
    Convert a pygame surface to an OpenGL texture.

    Args:
        surface (pygame.Surface): Source surface
        texture_id (int, optional): Existing texture ID to update. If None, creates new texture.
        flip_vertical (bool): Whether to flip the texture vertically for OpenGL

    Returns:
        int: OpenGL texture handle
    """
    try:
        _t0 = None
        try:
            from core import shared as _shared
            from time import time as _time
            _t0 = _time()
        except Exception:
            _t0 = None
        if surface is None:
            raise ValueError("Cannot convert None surface to texture")

        if surface.get_width() <= 0 or surface.get_height() <= 0:
            raise ValueError(f"Invalid surface dimensions: {surface.get_size()}")

        if texture_id is None:
            texture_id = create_gl_texture()

        if flip_vertical:
            surface = pygame.transform.flip(surface, False, True)

        texture_data = pygame.image.tostring(surface, "RGBA", 1)

        glBindTexture(GL_TEXTURE_2D, texture_id)

        # Check if we're updating an existing texture with different dimensions
        try:
            current_width = glGetTexLevelParameteriv(GL_TEXTURE_2D, 0, GL_TEXTURE_WIDTH)
            current_height = glGetTexLevelParameteriv(GL_TEXTURE_2D, 0, GL_TEXTURE_HEIGHT)

            if current_width != surface.get_width() or current_height != surface.get_height():
                # If dimensions don't match, recreate the texture with new size
                if __name__ != "__main__":
                    from core import shared
                    shared.debug(f"Recreating texture due to size mismatch. Old: {current_width}x{current_height}, New: {surface.get_width()}x{surface.get_height()}", category="texture")
        except:
            # If we can't get current dimensions, just recreate the texture
            pass

        # Always use glTexImage2D for safety, which recreates the texture if needed
        glTexImage2D(
            GL_TEXTURE_2D, 0, GL_RGBA,
            surface.get_width(), surface.get_height(),
            0, GL_RGBA, GL_UNSIGNED_BYTE, texture_data
        )

        # Update perf counters
        try:
            if _t0 is not None:
                elapsed = (_time() - _t0) * 1000.0
                if hasattr(_shared, 'perf'):
                    _shared.perf['tex_uploads'] += 1
                    _shared.perf['tex_upload_ms'] += elapsed
        except Exception:
            pass

        return texture_id

    except Exception as e:
        if __name__ != "__main__":
            from core import shared
            shared.debug(f"Error in surface_to_texture: {str(e)}", category="texture")
        return texture_id

def draw_textured_quad_OLD(x, y, width, height, texture_id, opacity=1.0):
    """
    Draw a textured quad at the specified position.

    Args:
        x, y (float): Position to draw
        width, height (float): Size of quad
        texture_id (int): OpenGL texture handle
        opacity (float): Alpha value (0.0 to 1.0)
    """
    glEnable(GL_TEXTURE_2D)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    glBindTexture(GL_TEXTURE_2D, texture_id)
    glColor4f(1, 1, 1, opacity)

    glBegin(GL_QUADS)
    glTexCoord2f(0, 0); glVertex2f(x, y)
    glTexCoord2f(1, 0); glVertex2f(x + width, y)
    glTexCoord2f(1, 1); glVertex2f(x + width, y + height)
    glTexCoord2f(0, 1); glVertex2f(x, y + height)
    glEnd()

    glDisable(GL_TEXTURE_2D)
    glDisable(GL_BLEND)


def draw_textured_quad(x, y, width, height, texture_id, opacity=1.0):
    """Draw a textured quad with the specified texture."""
    glColor4f(1.0, 1.0, 1.0, opacity)
    glEnable(GL_TEXTURE_2D)
    glBindTexture(GL_TEXTURE_2D, texture_id)

    glBegin(GL_QUADS)
    # Adjust to draw from center
    half_width = width / 2
    half_height = height / 2

    # Draw quad with texture coordinates
    glTexCoord2f(0, 1)
    glVertex2f(x - half_width, y - half_height)  # Bottom-left

    glTexCoord2f(1, 1)
    glVertex2f(x + half_width, y - half_height)  # Bottom-right

    glTexCoord2f(1, 0)
    glVertex2f(x + half_width, y + half_height)  # Top-right

    glTexCoord2f(0, 0)
    glVertex2f(x - half_width, y + half_height)  # Top-left
    glEnd()

    glDisable(GL_TEXTURE_2D)


def setup_gl_state(window_size=None):
    """
    Set up common OpenGL state for 2D rendering with alpha blending.

    Args:
        window_size (tuple, optional): Window dimensions (width, height) for viewport setup.
    """
    glEnable(GL_TEXTURE_2D)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    # If window size is provided, set up viewport and projection matrix
    if window_size:
        width, height = window_size
        glViewport(0, 0, width, height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0, width, height, 0, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

def cleanup_gl_texture(texture_id):
    """
    Safely delete an OpenGL texture.

    Args:
        texture_id (int): OpenGL texture handle to delete
    """
    if texture_id is not None:
        glDeleteTextures([texture_id])

def surfaceToTexture(pygame_surface, use_alpha):
    """Convert PyGame surface to OpenGL texture

    Note: Assumes straight (unassociated) alpha from PyGame surfaces
    """
    gl_format = GL_RGBA if use_alpha else GL_RGB
    data_format = 'RGBA' if use_alpha else 'RGB'
    pixel_data = pygame.image.tostring(pygame_surface, data_format, True)

    texture_id = create_gl_texture()
    glBindTexture(GL_TEXTURE_2D, texture_id)
    glTexImage2D(GL_TEXTURE_2D, 0, gl_format,
                 pygame_surface.get_width(), pygame_surface.get_height(),
                 0, gl_format, GL_UNSIGNED_BYTE, pixel_data)
    return texture_id

def prepare_spout_output(surface, useAlpha, spout_sender, width, height):
    """Prepare and send surface to Spout output"""
    flipped_surface = pygame.transform.flip(surface, False, True) if not useAlpha else surface
    texture_id = surfaceToTexture(flipped_surface, useAlpha)

    glBindTexture(GL_TEXTURE_2D, texture_id)
    spout_sender.sendTexture(texture_id, GL_TEXTURE_2D, width, height, useAlpha, 0)
    glDeleteTextures([texture_id])

# def init_opengl(width, height):
#     """Initialize OpenGL settings for the application"""
#     pygame.display.gl_set_attribute(pygame.GL_ALPHA_SIZE, 8)
#     #TODO review below line
#     # pygame.display.set_mode((width, height), pygame.OPENGL | pygame.DOUBLEBUF | pygame.HIDDEN)
#     glViewport(0, 0, width, height)
#     glClearColor(0.0, 0.0, 0.0, 1.0)

def str_to_bool(s):
    if isinstance(s, bool):
        return s
    if isinstance(s, str):
        boolean_map = {"true": True, "1": True, "yes": True, "false": False, "0": False, "no": False}
        result = boolean_map.get(s.lower())
        if result is not None:
            return result
    logging.error(f"Invalid input for boolean conversion: {s}")
    raise ValueError(f"Input '{s}' cannot be converted to a boolean.")


def draw_debug_quad(x, y, width, height, color=(1,1,1,1)):
    """Draw a colored quad for debug visualization"""
    glDisable(GL_TEXTURE_2D)
    glColor4f(*color)
    glBegin(GL_QUADS)
    glVertex2f(x, y)
    glVertex2f(x + width, y)
    glVertex2f(x + width, y + height)
    glVertex2f(x, y + height)
    glEnd()
    glColor4f(1, 1, 1, 1)
    glEnable(GL_TEXTURE_2D)


def _normalize_color(color):
    """Accept (r,g,b) or (r,g,b,a) in 0-255 or 0-1, return 0-1 tuple with alpha."""
    if not isinstance(color, (list, tuple)):
        return (1.0, 1.0, 1.0, 1.0)
    vals = list(color)
    if len(vals) == 3:
        vals.append(255 if max(vals) > 1.0 else 1.0)
    # If any component > 1 assume 0-255 and normalize
    if any(v > 1.0 for v in vals):
        vals = [v / 255.0 for v in vals]
    return tuple(vals[:4])


def draw_gl_line(x1, y1, x2, y2, color=(1,1,1,1), thickness=1.0):
    """Draw a colored line using OpenGL immediate mode."""
    glDisable(GL_TEXTURE_2D)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glLineWidth(float(thickness))
    glColor4f(*_normalize_color(color))
    glBegin(GL_LINES)
    glVertex2f(float(x1), float(y1))
    glVertex2f(float(x2), float(y2))
    glEnd()
    glColor4f(1,1,1,1)
    glLineWidth(1.0)
    glDisable(GL_BLEND)
    glEnable(GL_TEXTURE_2D)


def draw_gl_rect_outline(x, y, w, h, color=(1,1,1,1), thickness=1.0):
    """Draw rectangle outline with GL lines."""
    draw_gl_line(x, y, x + w, y, color, thickness)
    draw_gl_line(x + w, y, x + w, y + h, color, thickness)
    draw_gl_line(x + w, y + h, x, y + h, color, thickness)
    draw_gl_line(x, y + h, x, y, color, thickness)


def draw_gl_circle_outline(cx, cy, radius, color=(1,1,1,1), thickness=1.0, segments=64):
    """Draw a circle outline centered at (cx,cy)."""
    if radius <= 0:
        return
    segs = max(8, int(segments))
    glDisable(GL_TEXTURE_2D)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glLineWidth(float(thickness))
    glColor4f(*_normalize_color(color))
    glBegin(GL_LINE_LOOP)
    import math
    for i in range(segs):
        ang = (i / float(segs)) * 2.0 * math.pi
        x = cx + math.cos(ang) * radius
        y = cy + math.sin(ang) * radius
        glVertex2f(float(x), float(y))
    glEnd()
    glColor4f(1,1,1,1)
    glLineWidth(1.0)
    glDisable(GL_BLEND)
    glEnable(GL_TEXTURE_2D)


def prepare_video_output(surface, useAlpha):
    flipped_surface = pygame.transform.flip(surface, False, True)
    rotated_surface = pygame.transform.rotate(flipped_surface, 270)
    np_surface_rgb = pygame.surfarray.pixels3d(rotated_surface).copy()
    np_surface_bgr = np_surface_rgb[:, :, [2, 1, 0]]

    if useAlpha:
        np_surface_alpha = pygame.surfarray.pixels_alpha(rotated_surface).copy()
        np_surface_bgra = numpy.dstack((np_surface_bgr, np_surface_alpha))
        return numpy.ascontiguousarray(np_surface_bgra, dtype=numpy.uint8)
    else:
        return numpy.ascontiguousarray(np_surface_bgr, dtype=numpy.uint8)

def draw_rotated_textured_quad(x, y, width, height, texture_id, rotation, scale=1.0, opacity=1.0):
    """
      Draw a textured quad with rotation and scale around its center.

      Args:
          x, y (float): Position to draw
          width, height (float): Base size of quad
          texture_id (int): OpenGL texture handle
          rotation (float): Rotation in degrees
          scale (float): Scale factor (1.0 = normal size)
          opacity (float): Alpha value (0.0 to 1.0)
      """

    glEnable(GL_TEXTURE_2D)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    glBindTexture(GL_TEXTURE_2D, texture_id)
    glColor4f(1, 1, 1, opacity)

    glPushMatrix()

    # Calculate the center based on the original position and size
    center_x = x + width/2
    center_y = y + height/2

    # Modified transform order for more consistent scaling
    glTranslatef(center_x, center_y, 0)  # Move to rotation center
    glRotatef(rotation, 0, 0, 1)         # Apply rotation
    glScalef(scale, scale, 1.0)          # Apply scale uniformly
    glTranslatef(-width/2, -height/2, 0)  # Center the quad

    # Draw the quad with consistent dimensions
    glBegin(GL_QUADS)
    glTexCoord2f(0, 0); glVertex2f(0, 0)
    glTexCoord2f(1, 0); glVertex2f(width, 0)
    glTexCoord2f(1, 1); glVertex2f(width, height)
    glTexCoord2f(0, 1); glVertex2f(0, height)
    glEnd()
    
    glPopMatrix()
    
    glDisable(GL_TEXTURE_2D)
    glDisable(GL_BLEND)