import pygame
from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GL import (
    glGenTextures, glBindTexture, glTexImage2D, glDeleteTextures,
    GL_TEXTURE_2D, GL_RGBA, GL_UNSIGNED_BYTE, GL_TEXTURE_MIN_FILTER,
    GL_TEXTURE_MAG_FILTER, GL_LINEAR
)
from pygame.locals import OPENGL, DOUBLEBUF, HIDDEN, SHOWN  # Add this import at the top

from core.debug import debug, DebugManager
from core import shared
from core.utils import (
    draw_textured_quad,
    # prepare_spout_output,
    # prepare_video_output,
    # setup_gl_state
)


class GLContext:
    """Handles OpenGL context initialization and management"""

    def __init__(self):
        self.screen = None

    def setup(self, width, height, is_hidden=False):
        """Initialize OpenGL context with pygame"""
        self.screen = self._setup_context(width, height, is_hidden)
        self._init_settings(width, height)
        return self.screen

    def _setup_context(self, width, height, is_hidden=False):
        try:
            if not pygame.get_init():
                pygame.init()

            pygame.display.gl_set_attribute(pygame.GL_ALPHA_SIZE, 8)
            pygame.display.gl_set_attribute(pygame.GL_DOUBLEBUFFER, 1)

            flags = OPENGL | DOUBLEBUF
            if is_hidden:
                flags |= HIDDEN

            return pygame.display.set_mode((width, height), flags)
        except pygame.error as e:
            raise RuntimeError(f"Failed to setup OpenGL context: {e}")

    def _init_settings(self, width, height, use_alpha=True):
        """Initialize OpenGL settings"""
        if width <= 0 or height <= 0:
            raise ValueError("Invalid dimensions for OpenGL viewport")

        try:
            glViewport(0, 0, width, height)
            glClearColor(0.0, 0.0, 0.0, 0.0)

            glMatrixMode(GL_PROJECTION)
            glLoadIdentity()
            glOrtho(0, width, height, 0, -1, 1)

            glMatrixMode(GL_MODELVIEW)
            glLoadIdentity()

            glEnable(GL_TEXTURE_2D)
            if use_alpha:
                glEnable(GL_BLEND)
                glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize OpenGL settings: {e}")


# class Renderer:
#     """Manages OpenGL rendering state and operations"""
# 
#     def __init__(self, width, height):
#         self.width = width
#         self.height = height
#         self.context = GLContext()
#         self.context.setup(width, height)
#         self.texture = TextureManager.create_texture()
# 
#     def render_surface(self, surface, rotation=0, center=None):
#         shared.debug(f"Rendering surface with rotation: {rotation}")  # Debug print
#         if surface is None:
#             return
# 
#         glEnable(GL_TEXTURE_2D)
#         glEnable(GL_BLEND)
#         glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
# 
#         # Update texture with new surface data
#         glBindTexture(GL_TEXTURE_2D, self.texture)
#         data_format = 'RGBA'
#         pixel_data = pygame.image.tostring(surface, data_format, True)
#         glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA,
#                      surface.get_width(), surface.get_height(),
#                      0, GL_RGBA, GL_UNSIGNED_BYTE, pixel_data)
# 
#         # Save current transformation matrix
#         glPushMatrix()
#         shared.debug(f"Rendering with rotation {rotation} at center {center}")
# 
#         # Move to center point, rotate, then move back
#         if center is None:
#             center = (surface.get_width() / 2, surface.get_height() / 2)
# 
#         glTranslatef(center[0], center[1], 0)
#         glRotatef(rotation, 0, 0, 1)  # Make sure rotation is being applied
#         glTranslatef(-center[0], -center[1], 0)
# 
#         # Draw the quad
#         glBegin(GL_QUADS)
#         glTexCoord2f(0, 1);
#         glVertex2f(0, 0)
#         glTexCoord2f(1, 1);
#         glVertex2f(surface.get_width(), 0)
#         glTexCoord2f(1, 0);
#         glVertex2f(surface.get_width(), surface.get_height())
#         glTexCoord2f(0, 0);
#         glVertex2f(0, surface.get_height())
#         glEnd()
# 
#         # Restore previous transformation matrix
#         glPopMatrix()
# 
#     def render_to_screen(self, surface):
#         """Legacy method for compatibility - uses the same rendering pipeline"""
#         self.render_surface(surface)
# 
#     def cleanup(self):
#         """Clean up OpenGL resources"""
#         if self.texture:
#             glDeleteTextures([self.texture])


class Renderer:
    """
    Backward-compatibility renderer shim for izzy_main.py.
    This project now uses SimulationRenderer internally; this class exists only
    so that legacy code importing `from core.rendering import Renderer` continues
    to work without errors. The render_surface method is a no-op because the
    simulation already composes to a texture and Spout sending is handled by
    TokenSimulation.send_to_spout().
    """
    def __init__(self, width, height):
        self.width = width
        self.height = height
    def render_surface(self, surface, rotation=0, center=None):
        # No-op on purpose; legacy call retained for API compatibility
        return None
    def render_to_screen(self, surface):
        return self.render_surface(surface)
    def cleanup(self):
        pass

class SimulationRenderer:
    """Handles all OpenGL rendering operations for the simulation"""

    def __init__(self, width, height):
        """Initialize renderer with canvas dimensions"""
        self.width = width
        self.height = height

        # Ensure there is a valid OpenGL context (important for Isadora entry point)
        try:
            if not pygame.get_init():
                pygame.init()
            if not pygame.display.get_surface():
                # Create a hidden OpenGL window to host the context
                ctx = GLContext()
                ctx.setup(width, height, is_hidden=True)
        except Exception as e:
            raise RuntimeError(f"Failed to create OpenGL context: {e}")

        # Determine if FBOs are available in this context
        self.fbo_supported = bool(glGenFramebuffers)

        if self.fbo_supported:
            # Create main framebuffer for composition
            self.main_fbo = glGenFramebuffers(1)
            self.main_texture = glGenTextures(1)

            # Setup main texture
            glBindTexture(GL_TEXTURE_2D, self.main_texture)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, None)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)

            # Setup framebuffer
            glBindFramebuffer(GL_FRAMEBUFFER, self.main_fbo)
            glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, self.main_texture, 0)

            # Check framebuffer status
            if glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE:
                raise RuntimeError("Framebuffer setup failed")

            glBindFramebuffer(GL_FRAMEBUFFER, 0)
        else:
            # Fallback: no FBO support; render directly to default framebuffer
            self.main_fbo = 0
            self.main_texture = None
            shared.debug("FBOs not supported or not available; using default framebuffer", category="render")

        # Persistent texture for debug overlay to avoid per-frame create/delete
        self.debug_texture = glGenTextures(1)
        self._debug_tex_w = 0
        self._debug_tex_h = 0

        shared.debug("SimulationRenderer initialized")

    def begin_frame(self):
        """Start a new frame"""
        shared.debug("Beginning frame render", category="render")

        # Bind to target framebuffer and verify binding
        glBindFramebuffer(GL_FRAMEBUFFER, self.main_fbo if self.fbo_supported else 0)
        try:
            current_fbo = glGetInteger(GL_FRAMEBUFFER_BINDING)  # May not be available on all platforms
            shared.debug(f"Current FBO: {current_fbo}", category="render")
        except Exception:
            pass

        glViewport(0, 0, self.width, self.height)

        # Clear with alpha
        glClearColor(0.0, 0.0, 0.0, 0.0)
        glClear(GL_COLOR_BUFFER_BIT)

        # Setup projection
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0, self.width, self.height, 0, -1, 1)

        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        # Check for GL errors
        error = glGetError()
        if error != GL_NO_ERROR:
            shared.debug(f"GL error during begin_frame: {error}", category="render")

    def render_token(self, token):
        """Render a single token using the transfer texture"""
        if not token:
            shared.debug("render_token called with invalid token", category="render")
            return

        try:
            # Check if token has texture pool/transfer texture
            if not hasattr(token, 'texture_pool') or not hasattr(token.texture_pool, 'transfer_texture'):
                shared.debug("Token missing texture pool or transfer texture", category="render")
                return

            # Update the transfer texture with current token image (from pygame surface)
            if hasattr(token, '_update_texture'):
                if not token._update_texture(token.settings):
                    shared.debug("Failed to update token texture", category="render")
                    return

            # Verify token has valid position and size
            if not hasattr(token, 'position') or not hasattr(token, 'current_size'):
                shared.debug("Token missing position or size", category="render")
                return

            # Use token's draw method if available
            if hasattr(token, 'draw'):
                token.draw(None, token.settings, None)
            else:
                # Fallback rendering method (uses transfer texture)
                glEnable(GL_BLEND)
                glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

                x, y = token.position
                w, h = token.current_size
                rotation = token.rotation if hasattr(token, 'rotation') else 0
                opacity = token.opacity / 255.0 if hasattr(token, 'opacity') else 1.0
                glColor4f(1.0, 1.0, 1.0, opacity)

                glEnable(GL_TEXTURE_2D)
                glBindTexture(GL_TEXTURE_2D, token.texture_pool.transfer_texture)

                glPushMatrix()
                glTranslatef(x, y, 0)
                if rotation:
                    glRotatef(rotation, 0, 0, 1)

                glBegin(GL_QUADS)
                glTexCoord2f(0, 0); glVertex2f(-w/2, -h/2)
                glTexCoord2f(1, 0); glVertex2f(w/2, -h/2)
                glTexCoord2f(1, 1); glVertex2f(w/2, h/2)
                glTexCoord2f(0, 1); glVertex2f(-w/2, h/2)
                glEnd()

                glPopMatrix()

                glColor4f(1.0, 1.0, 1.0, 1.0)
                glDisable(GL_TEXTURE_2D)
                glDisable(GL_BLEND)
        except Exception as e:
            shared.debug(f"Error rendering token: {str(e)}", category="render")

    def render_debug_overlay(self, debug_surface, upload=True):
        """Render debug information overlay
        upload (bool): when True, update the overlay texture from the pygame surface.
                       when False, reuse the previously uploaded texture.
        """
        if debug_surface is None:
            return

        # Ensure we have a texture
        if not hasattr(self, 'debug_texture') or self.debug_texture is None:
            self.debug_texture = glGenTextures(1)
            self._debug_tex_w = 0
            self._debug_tex_h = 0

        w, h = debug_surface.get_size()

        # Upload only if requested, or if size changed / texture not initialized
        if upload or self._debug_tex_w != w or self._debug_tex_h != h:
            from time import time as _time
            _t0 = _time()
            data = pygame.image.tostring(debug_surface, "RGBA", True)

            glBindTexture(GL_TEXTURE_2D, self.debug_texture)
            if self._debug_tex_w != w or self._debug_tex_h != h:
                glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, data)
                self._debug_tex_w, self._debug_tex_h = w, h
            else:
                glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, w, h, GL_RGBA, GL_UNSIGNED_BYTE, data)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)

            # Perf: record overlay upload time and count
            try:
                from core import shared as _shared
                _elapsed = (_time() - _t0) * 1000.0
                if hasattr(_shared, 'perf'):
                    _shared.perf['overlay_uploads'] += 1
                    _shared.perf['debug_overlay_upload_ms'] += _elapsed
            except Exception:
                pass
        else:
            glBindTexture(GL_TEXTURE_2D, self.debug_texture)

        # Draw debug overlay with proper alpha blending so transparent areas don't overwrite tokens
        glEnable(GL_TEXTURE_2D)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        # Optional: draw a semi-transparent black panel behind stats text so tokens show through
        try:
            from core import shared as _shared
            if hasattr(_shared, 'stats_panel_rect') and _shared.stats_panel_rect:
                px, py, pw, ph = _shared.stats_panel_rect
                # Convert surface-space Y (top-left origin) to GL draw Y that matches the
                # vertically flipped texture upload: y_gl = h - (py + ph)
                try:
                    # w,h are from debug_surface.get_size() above
                    panel_y_gl = float(self._debug_tex_h if self._debug_tex_h else h) - (float(py) + float(ph))
                except Exception:
                    panel_y_gl = py  # fallback
                glColor4f(0, 0, 0, 0.5)
                glBegin(GL_QUADS)
                glVertex2f(px, panel_y_gl)
                glVertex2f(px + pw, panel_y_gl)
                glVertex2f(px + pw, panel_y_gl + ph)
                glVertex2f(px, panel_y_gl + ph)
                glEnd()
        except Exception:
            pass

        # Draw the overlay texture (text, grid, etc.)
        glColor4f(1, 1, 1, 1)
        glBegin(GL_QUADS)
        glTexCoord2f(0, 0); glVertex2f(0, 0)
        glTexCoord2f(1, 0); glVertex2f(w, 0)
        glTexCoord2f(1, 1); glVertex2f(w, h)
        glTexCoord2f(0, 1); glVertex2f(0, h)
        glEnd()

        glDisable(GL_BLEND)

    def end_frame(self):
        """End frame rendering"""
        # Bind back to default framebuffer
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        glViewport(0, 0, self.width, self.height)

        if self.fbo_supported and self.main_texture:
            # Clear window
            glClearColor(0.1, 0.1, 0.1, 1.0)
            glClear(GL_COLOR_BUFFER_BIT)

            # Draw main texture to screen (no vertical flip; content is already in y-down orientation)
            glEnable(GL_TEXTURE_2D)
            glBindTexture(GL_TEXTURE_2D, self.main_texture)

            glColor4f(1.0, 1.0, 1.0, 1.0)
            glBegin(GL_QUADS)
            glTexCoord2f(0, 0); glVertex2f(0, 0)
            glTexCoord2f(1, 0); glVertex2f(self.width, 0)
            glTexCoord2f(1, 1); glVertex2f(self.width, self.height)
            glTexCoord2f(0, 1); glVertex2f(0, self.height)
            glEnd()
            glDisable(GL_TEXTURE_2D)
        else:
            # If no FBO support, we've already rendered directly to the default framebuffer.
            pass
        
        # Force display update
        pygame.display.flip()

    def cleanup(self):
        """Clean up OpenGL resources"""
        if getattr(self, 'main_texture', None):
            try:
                glDeleteTextures([self.main_texture])
            except Exception:
                pass
            self.main_texture = None

        if hasattr(self, 'debug_texture') and self.debug_texture:
            try:
                glDeleteTextures([self.debug_texture])
            except Exception:
                pass
            self.debug_texture = None

        if getattr(self, 'main_fbo', None) and self.fbo_supported:
            try:
                glDeleteFramebuffers(1, [self.main_fbo])
            except Exception:
                pass
            self.main_fbo = None


class SimulationRenderer_OLD:
    """Manages all rendering operations for the token simulation"""

    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.context = GLContext()
        self.context.setup(width, height)

        # Create texture pools
        self.main_texture = TextureManager.create_texture()  # Main composition texture
        self.token_pool = TexturePool(
            texture_size=(width, height),
            required_count=50  # Adjust based on expected token count
        )
        self.debug_texture = TextureManager.create_texture()  # For debug overlays

    def begin_frame(self):
        """Setup for new frame"""
        glClearColor(0.0, 0.0, 0.0, 0.0)
        glClear(GL_COLOR_BUFFER_BIT)

        glViewport(0, 0, self.width, self.height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0, self.width, self.height, 0, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

    def render_token(self, token):
        """Render a single token"""
        if not token or not token.texture_id:
            return

        # Get token properties
        pos = token.position
        size = token.current_size
        rotation = token.rotation
        opacity = token.opacity / 255.0

        # Setup GL state
        glEnable(GL_TEXTURE_2D)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        # Bind token texture
        glBindTexture(GL_TEXTURE_2D, token.texture_id)

        # Draw token with rotation and opacity
        glPushMatrix()
        glTranslatef(pos.x, pos.y, 0)
        glRotatef(rotation, 0, 0, 1)

        glColor4f(1.0, 1.0, 1.0, opacity)
        draw_textured_quad(-size[0] / 2, -size[1] / 2, size[0], size[1])
        glColor4f(1.0, 1.0, 1.0, 1.0)

        glPopMatrix()

    def render_debug_overlay(self, surface):
        """Render debug information overlay"""
        if surface:
            # Convert debug surface to texture
            TextureManager.surface_to_texture(surface, self.debug_texture)

            # Draw debug overlay
            glEnable(GL_TEXTURE_2D)
            glEnable(GL_BLEND)
            glBindTexture(GL_TEXTURE_2D, self.debug_texture)
            draw_textured_quad(0, 0, self.width, self.height)

    def end_frame(self):
        """Finish frame and present"""
        pygame.display.flip()

    def cleanup(self):
        """Clean up resources"""
        if self.token_pool:
            self.token_pool.cleanup()
        if self.main_texture:
            glDeleteTextures([self.main_texture])
        if self.debug_texture:
            glDeleteTextures([self.debug_texture])


class TextureManager:
    """Handles conversion between PyGame surfaces and OpenGL textures"""

    @staticmethod
    def surface_to_texture(pygame_surface, use_alpha):
        if not pygame_surface:
            raise ValueError("Invalid surface provided")

        if pygame_surface.get_width() <= 0 or pygame_surface.get_height() <= 0:
            raise ValueError("Surface has invalid dimensions")

        """Convert PyGame surface to OpenGL texture"""
        gl_format = GL_RGBA if use_alpha else GL_RGB
        data_format = 'RGBA' if use_alpha else 'RGB'
        pixel_data = pygame.image.tostring(pygame_surface, data_format, True)

        texture_id = TextureManager.create_texture()
        glBindTexture(GL_TEXTURE_2D, texture_id)
        glTexImage2D(GL_TEXTURE_2D, 0, gl_format,
                     pygame_surface.get_width(), pygame_surface.get_height(),
                     0, gl_format, GL_UNSIGNED_BYTE, pixel_data)
        return texture_id

    @staticmethod
    def create_texture():
        """Create and configure a new OpenGL texture"""
        texture_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, texture_id)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glBindTexture(GL_TEXTURE_2D, 0)
        return texture_id

    @staticmethod
    def prepare_spout_output(surface, use_alpha, spout_sender, width, height):
        """Prepare and send surface to Spout output"""
        flipped_surface = pygame.transform.flip(surface, False, True) if not use_alpha else surface
        texture_id = TextureManager.surface_to_texture(flipped_surface, use_alpha)

        glBindTexture(GL_TEXTURE_2D, texture_id)
        spout_sender.sendTexture(texture_id, GL_TEXTURE_2D, width, height, use_alpha, 0)
        glDeleteTextures([texture_id])


class TransferTexturePool:
    """
    A minimal staging/transfer texture manager for token rendering.

    Note: This is not a true pool. It owns a single shared OpenGL texture
    (transfer_texture) that is reused as a staging buffer for uploads before
    drawing tokens. Historically named "TexturePool"; kept a compatibility
    alias below.
    """
    def __init__(self, texture_size, required_count=1, safety_margin=0):
        """Initialize with a single transfer (staging) texture"""
        self.texture_size = texture_size
        
        # Create the single transfer texture
        self.transfer_texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.transfer_texture)
        
        # Ensure texture size components are integers
        width = int(texture_size[0])
        height = int(texture_size[1])

        # Keep the original size for reference
        self.original_size = (width, height)

        # Initialize with empty data
        glTexImage2D(
            GL_TEXTURE_2D, 0, GL_RGBA,
            width, height,
            0, GL_RGBA, GL_UNSIGNED_BYTE, None
        )

        # Set texture parameters
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)

        shared.debug(f"Initialized TransferTexturePool (single staging texture) {width}x{height}", category="texture")

    def get_transfer_texture(self):
        """Return the shared transfer (staging) texture id."""
        return getattr(self, 'transfer_texture', None)

    def get_texture(self, entity_id):
        """
        Back-compat: Always return the transfer texture.
        Prefer get_transfer_texture() for clarity.
        """
        if not hasattr(self, 'transfer_texture'):
            shared.debug("No transfer texture available", category="texture")
            return None
        return self.transfer_texture

    def release_texture(self, entity_id):
        """No-op; texture is shared and reused each frame."""
        pass

    def get_available_texture_count(self):
        """Always return 1 since we only have one shared texture."""
        return 1

    def cleanup(self):
        """Clean up the transfer texture"""
        if hasattr(self, 'transfer_texture'):
            glDeleteTextures(1, [self.transfer_texture])
            shared.debug("Cleaned up transfer (staging) texture", category="texture")

# Backward compatibility alias for existing imports/usages
TexturePool = TransferTexturePool