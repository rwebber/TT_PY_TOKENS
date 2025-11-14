import pygame
import math
from math import cos, sin
from OpenGL.GL import *
from OpenGL.GLU import *

from core import shared
from core.utils import surface_to_texture, draw_textured_quad
from core.utils import draw_rotated_textured_quad
from core.utils import draw_gl_line, draw_gl_rect_outline, draw_gl_circle_outline
from core.debug import debug, DebugManager


class Token:

    def __init__(self, position, size, facing="top", texture_pool=None):
        """Initialize a new token."""
        # Convert position to Vector2 for easier manipulation
        self.position = pygame.Vector2(position)
        self.home = pygame.Vector2(position)  # Original spawn position
        self.velocity = pygame.Vector2(0, 0)
        self.color = (255, 255, 255)  # Default white

        # Size management
        self.original_size = pygame.Vector2(size)
        self.current_size = pygame.Vector2(size)
        # Ensure a tuple-of-ints size is always available for surface generation
        self.size = (int(self.original_size.x), int(self.original_size.y))
        self.bounce_scale = 1.0

        # Texture management
        self.texture_pool = texture_pool
        self.texture_id = None

        # Visual state
        self.opacity = 255
        self.fade_timer = 0
        self.rotation = 0
        self.facing = facing

        # Physics state
        self.time_since_force = 0
        self.time_since_respawn = 0

        # Image management
        self.image = None  # Will be set by factory after settings are available
        self._cached_image_hash = None
        self._base_image = None
        self._cached_scaled_image = None

        # Collision state
        self.dead = False
        self.is_colliding = False
        self.collision_time = 0
        self.collision_partner = None
        self.collision_radius = min(size[0], size[1]) / 2
        self.collision_bounds_rect = pygame.Rect(position, size)

        # Configuration
        self.settings = None
        self._should_update_texture = True


    def reset(self):
        """Reset token state for respawning"""
        self.velocity = pygame.Vector2(0, 0)
        self.rotation = 0
        self.bounce_scale = 1.0
        self.opacity = 255
        self.fade_timer = 0
        self.dead = False
        self.is_colliding = False
        self.collision_time = 0.0
        self.collision_partner = None
        self.time_since_force = 0.0
        self.time_since_respawn = 0.0

        # Reset image state
        self.image = None
        self._base_image = None
        self._cached_scaled_image = None
        self._cached_image_hash = None
        self._should_update_texture = True

        # Release old texture if exists
        if self.texture_pool and self.texture_id is not None:
            self.texture_pool.release_texture(id(self))
            self.texture_id = None


    def cleanup(self):
        """Release any resources held by this token"""
        if self.texture_id is not None and self.texture_pool is not None:
            self.texture_pool.release_texture(id(self))
            self.texture_id = None
            self._cached_scaled_image = None
            self._cached_image_hash = None
            self._base_image = None  # Add this line
            self.image = None  # Add this line
            self._should_update_texture = True  # Add this line

    # def _get_base_image(self, settings):
    #     """Get the base image to draw"""
    #     # Check if we need to regenerate the image
    #     input_cfg = settings.get_input_settings()
    #     use_live_image = input_cfg.get("use_live_image", False)
    #
    #     if use_live_image and self._cached_scaled_image is not None:
    #         base_image = self._cached_scaled_image
    #     else:
    #         if self.image is None:
    #             self.image = self.generate_image(settings)
    #         base_image = self.image
    #
    #     if base_image:
    #         # Store original center
    #         center_x = self.position.x + self.size[0] / 2
    #         center_y = self.position.y + self.size[1] / 2
    #
    #         # Create a copy to avoid modifying the original
    #         base_image = base_image.copy()
    #
    #         # Apply rotation if needed
    #         if self.rotation != 0:
    #             base_image = pygame.transform.rotate(base_image, -self.rotation)
    #
    #         # Recenter the image
    #         new_rect = base_image.get_rect(center=(center_x, center_y))
    #         self.position.x = new_rect.x
    #         self.position.y = new_rect.y
    #
    #     return base_image

    def _update_texture(self, settings):
        """Update the transfer texture with this token's current image"""
        if not self.texture_pool:
            return False

        # If tokens are hidden, skip any texture uploads entirely.
        try:
            if bool(settings.get_token_settings().get("hide", False)):
                # Pretend update succeeded so renderer continues to token.draw(),
                # where we intentionally skip drawing the textured quad but can still
                # render debug/visual overlays.
                return True
        except Exception:
            pass

        try:
            # Get current image for texture upload: use base image only (no rotation/scale);
            # rotation and scale are applied in the GPU during draw to avoid double transforms.
            current_image = self._get_base_image(settings)
            if current_image is None:
                return False

            # Bind texture
            glBindTexture(GL_TEXTURE_2D, self.texture_pool.transfer_texture)

            # Ensure pixel row alignment does not corrupt uploads on non-4-byte widths
            glPixelStorei(GL_UNPACK_ALIGNMENT, 1)

            # First check the size of the current texture
            tex_width = glGetTexLevelParameteriv(GL_TEXTURE_2D, 0, GL_TEXTURE_WIDTH)
            tex_height = glGetTexLevelParameteriv(GL_TEXTURE_2D, 0, GL_TEXTURE_HEIGHT)

            # Get image dimensions
            img_width = current_image.get_width()
            img_height = current_image.get_height()
            shared.debug(f"Preparing to upload {img_width}x{img_height} to transfer texture (current {tex_width}x{tex_height})", category="texture")

            # Convert surface to texture data
            texture_data = pygame.image.tostring(current_image, "RGBA", 0)

            # If dimensions don't match, recreate the texture with new dimensions
            if tex_width != img_width or tex_height != img_height:
                shared.debug(f"Recreating texture to match image size: {img_width}x{img_height}", category="texture")
                glTexImage2D(
                    GL_TEXTURE_2D, 0, GL_RGBA,
                    img_width, img_height,
                    0, GL_RGBA, GL_UNSIGNED_BYTE, texture_data
                )
            else:
                # Update existing texture
                glTexSubImage2D(
                    GL_TEXTURE_2D, 0,
                    0, 0,  # x, y offset
                    img_width, img_height,
                    GL_RGBA, GL_UNSIGNED_BYTE,
                    texture_data
                )

            # Confirm new texture size
            new_w = glGetTexLevelParameteriv(GL_TEXTURE_2D, 0, GL_TEXTURE_WIDTH)
            new_h = glGetTexLevelParameteriv(GL_TEXTURE_2D, 0, GL_TEXTURE_HEIGHT)
            shared.debug(f"Transfer texture now {new_w}x{new_h} for token {id(self)}", category="texture")

            return True

        except Exception as e:
            shared.debug(f"Error updating texture: {str(e)}", category="texture")
            return False

    def update_visual_state(self, settings):
        """Update the visual representation of the token"""
        if self._should_update_texture:
            self._update_texture(settings)

    def _initialize_texture(self):
        """Initialize OpenGL texture for this token."""
        if self.texture_pool is None:
            shared.debug("No texture pool available", category="texture")
            return

        # Get texture from pool
        self.texture_id = self.texture_pool.get_texture(id(self))

        if self.texture_id is None:
            shared.debug("Failed to get texture from pool", category="texture")
            return

        shared.debug(f"Initialized texture {self.texture_id} for token {id(self)}", category="texture")

        # Update the texture with current image
        self._update_texture(self.settings)

    def _get_base_image(self, settings):
        """Get or generate the untransformed base token image"""
        try:
            # Instrument: count base image requests
            try:
                from core import shared as _shared
                if hasattr(_shared, 'perf'):
                    _shared.perf['token_get_base_image_calls'] += 1
            except Exception:
                pass
            input_cfg = settings.get_input_settings()
            use_live_image = input_cfg.get("use_live_image", False)
            live_update = input_cfg.get("live_image_update", False)

            # If we're using live images and live_image_update is enabled, adopt the
            # current cached/shared image every call (per-frame update path)
            if use_live_image and live_update and isinstance(shared.shared_token_image, pygame.Surface):
                if getattr(self, '_cached_scaled_image', None) is not None and \
                   getattr(self, '_cached_image_hash', None) == shared.shared_token_image_hash:
                    self._base_image = self._cached_scaled_image
                    self._cached_image_hash = shared.shared_token_image_hash
                else:
                    # Fallback: copy the shared image (may be unscaled)
                    self._base_image = shared.shared_token_image.copy()
                    self._cached_image_hash = shared.shared_token_image_hash
                try:
                    from core import shared as _shared
                    if hasattr(_shared, 'perf'):
                        _shared.perf['token_base_from_live'] += 1
                except Exception:
                    pass
                return self._base_image

            # Otherwise, only regenerate base image if:
            # 1. We don't have one yet, or
            # 2. Using live image and the shared image hash changed
            if (self._base_image is None or
                    (use_live_image and self._cached_image_hash != shared.shared_token_image_hash)):

                if use_live_image and isinstance(shared.shared_token_image, pygame.Surface):
                    # Prefer the per-size scaled cache prepared once per frame
                    if getattr(self, '_cached_scaled_image', None) is not None and \
                       getattr(self, '_cached_image_hash', None) == shared.shared_token_image_hash:
                        self._base_image = self._cached_scaled_image
                        self._cached_image_hash = shared.shared_token_image_hash
                    else:
                        # Fallback: copy the shared image (may be unscaled)
                        self._base_image = shared.shared_token_image.copy()
                        self._cached_image_hash = shared.shared_token_image_hash
                    try:
                        from core import shared as _shared
                        if hasattr(_shared, 'perf'):
                            _shared.perf['token_base_from_live'] += 1
                    except Exception:
                        pass
                else:
                    generated_image = self.generate_image(settings)
                    if generated_image is None:
                        # Create a fallback image if generate_image fails
                        fallback = pygame.Surface(self.size, pygame.SRCALPHA)
                        fallback.fill((255, 255, 255, 128))  # Semi-transparent white
                        self._base_image = fallback
                        shared.debug("Created fallback image for token", category="texture")
                        try:
                            from core import shared as _shared
                            if hasattr(_shared, 'perf'):
                                _shared.perf['token_base_generated'] += 1
                        except Exception:
                            pass
                    else:
                        self._base_image = generated_image
                        try:
                            from core import shared as _shared
                            if hasattr(_shared, 'perf'):
                                _shared.perf['token_base_generated'] += 1
                        except Exception:
                            pass

            return self._base_image
        except Exception as e:
            shared.debug(f"Error in _get_base_image: {str(e)}", category="texture")
            # Return an emergency fallback
            fallback = pygame.Surface(self.size, pygame.SRCALPHA)
            fallback.fill((255, 0, 0, 128))  # Semi-transparent red to indicate error
            return fallback

    def _get_transformed_image_GL(self, settings):
        """OpenGL-based transformation pipeline"""
        # First, ensure we have a base image
        if self._base_image is None:
            self._base_image = self._get_base_image(settings)
            if self._base_image is None:
                return None

        # If we don't have a texture yet, or if using live image and hash changed
        input_cfg = settings.get_input_settings()
        use_live_image = input_cfg.get("use_live_image", False)

        if (self.texture_id is None or
                (use_live_image and self._cached_image_hash != shared.shared_token_image_hash)):

            # Convert the pygame surface to OpenGL texture
            if self.texture_pool is not None:
                self.texture_id = self.texture_pool.get_texture(id(self))
                # Use our utility function to convert surface to texture
                try:
                    # Always use the shared utility to ensure consistent behavior
                    surface_to_texture(
                        self._base_image,
                        self.texture_id,
                        flip_vertical=False
                    )
                except Exception as e:
                    shared.debug(f"Error converting surface to texture: {str(e)}", category="texture")

                if use_live_image:
                    self._cached_image_hash = shared.shared_token_image_hash

        return {
            'texture_id': self.texture_id,
            'rotation': self.rotation,  # Negative for OpenGL coordinate system
            'scale': self.bounce_scale,
            'size': self.original_size,
            'width': self._base_image.get_width(),
            'height': self._base_image.get_height()
        }

    def _surface_to_texture(self, surface, texture_id, flip_vertical=False):
        """Convert a pygame surface to an OpenGL texture"""
        if surface is None or texture_id is None:
            return False

        try:
            # Get surface dimensions
            width, height = surface.get_size()
            if width <= 0 or height <= 0:
                return False

            # Convert surface to string
            if flip_vertical:
                surface = pygame.transform.flip(surface, False, True)

            texture_data = pygame.image.tostring(surface, "RGBA", 0)

            # Bind the texture and update it
            glBindTexture(GL_TEXTURE_2D, texture_id)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, texture_data)
            return True
        except Exception as e:
            shared.debug(f"Error in _surface_to_texture: {e}", category="texture")
            return False

    def _get_transformed_image(self, settings):
        """Get current frame's transformed version of the base image"""
        # Get base image first
        base_image = self._get_base_image(settings)
        if base_image is None:
            return None

        # Create a new surface for the transformed image
        transformed = base_image.copy()

        # Apply current frame's transformations in order
        if self.bounce_scale != 1.0:
            new_size = (
                int(self.original_size[0] * self.bounce_scale),
                int(self.original_size[1] * self.bounce_scale)
            )
            transformed = pygame.transform.smoothscale(transformed, new_size)

        if self.rotation != 0:
            transformed = pygame.transform.rotate(transformed, -self.rotation)

        return transformed

    def _check_circle_collision(self, other, with_response=True):
        """
        Check for collision between two circular tokens.
        Returns the collision intensity (0.0 to 1.0) or 0.0 if no collision.
        """
        dx = self.position.x - other.position.x
        dy = self.position.y - other.position.y
        distance = (dx * dx + dy * dy) ** 0.5

        # Update to use current_size for collision radius calculation
        self_radius = min(self.current_size[0], self.current_size[1]) / 2
        other_radius = min(other.current_size[0], other.current_size[1]) / 2
        combined_radius = self_radius + other_radius

        if distance >= combined_radius:
            return 0.0  # No collision

        # Calculate intensity based on overlap percentage
        intensity = 1.0 - (distance / combined_radius)

        if with_response:
            # Apply collision response if requested
            if distance > 0:  # Avoid division by zero
                # Normal vector from other to self
                nx = dx / distance
                ny = dy / distance

                # Calculate separation vector
                overlap = combined_radius - distance
                self.position.x += nx * overlap * 0.5
                self.position.y += ny * overlap * 0.5

                if hasattr(other, 'position'):
                    other.position.x -= nx * overlap * 0.5
                    other.position.y -= ny * overlap * 0.5

        return intensity

    def _check_rectangle_collision(self, other, with_response=True):
        """
        Check for collision between two rectangular tokens.
        Returns the collision intensity (0.0 to 1.0) or 0.0 if no collision.
        """
        # Get the bounds using current_size for both tokens
        self_left = self.position.x - self.current_size[0] / 2
        self_right = self.position.x + self.current_size[0] / 2
        self_top = self.position.y - self.current_size[1] / 2
        self_bottom = self.position.y + self.current_size[1] / 2

        other_left = other.position.x - other.current_size[0] / 2
        other_right = other.position.x + other.current_size[0] / 2
        other_top = other.position.y - other.current_size[1] / 2
        other_bottom = other.position.y + other.current_size[1] / 2

        # Check for no collision cases
        if (self_right < other_left or
                self_left > other_right or
                self_bottom < other_top or
                self_top > other_bottom):
            return 0.0

        # Calculate overlap in both dimensions
        overlap_x = min(self_right, other_right) - max(self_left, other_left)
        overlap_y = min(self_bottom, other_bottom) - max(self_top, other_top)

        # Calculate overlap area and maximum possible overlap area
        overlap_area = overlap_x * overlap_y
        max_area = min(self.current_size[0] * self.current_size[1],
                       other.current_size[0] * other.current_size[1])

        # Calculate collision intensity
        intensity = overlap_area / max_area

        if with_response:
            # Apply collision response if requested
            if overlap_x < overlap_y:
                # Separate horizontally
                if self.position.x < other.position.x:
                    self.position.x = other_left - self.current_size[0] / 2
                else:
                    self.position.x = other_right + self.current_size[0] / 2
            else:
                # Separate vertically
                if self.position.y < other.position.y:
                    self.position.y = other_top - self.current_size[1] / 2
                else:
                    self.position.y = other_bottom + self.current_size[1] / 2

        return min(1.0, intensity)


    def draw(self, mouse_pos, settings, tokens):
        """Draw the token using OpenGL with hardware transforms.
        Respect tokens.hide at runtime: when true, skip drawing the token's textured quad
        but still allow visual/debug overlays to render.
        """
        try:
            # Use token.position as the visual center (consistent across physics/collision)
            center = self.position

            # Determine if token graphics should be hidden
            hidden = False
            try:
                hidden = bool(settings.get_token_settings().get("hide", False))
            except Exception:
                hidden = False

            if not hidden:
                # Get transformed image data only when visible
                image_data = self._get_transformed_image_GL(settings)
                if image_data is not None and image_data.get('texture_id') is not None:
                    # Ensure texture is bound correctly: use the shared transfer texture that was just updated
                    texture_to_use = None
                    if hasattr(self, 'texture_pool') and self.texture_pool is not None and hasattr(self.texture_pool, 'transfer_texture'):
                        texture_to_use = self.texture_pool.transfer_texture
                    else:
                        # Fallback to the image_data texture id if pool is unavailable
                        texture_to_use = image_data.get('texture_id')

                    if texture_to_use is not None:
                        # Ensure texturing is enabled before binding
                        glEnable(GL_TEXTURE_2D)
                        glBindTexture(GL_TEXTURE_2D, texture_to_use)

                        # Draw using OpenGL transforms
                        draw_rotated_textured_quad(
                            x=center.x - (image_data['width'] / 2),
                            y=center.y - (image_data['height'] / 2),
                            width=image_data['width'],
                            height=image_data['height'],
                            texture_id=texture_to_use,
                            rotation=image_data['rotation'],
                            scale=image_data['scale'],
                            opacity=self.opacity / 255.0
                        )
                    else:
                        shared.debug("No valid texture available for drawing", category="render")
                # If image_data is None, silently skip drawing the textured quad

            # Regardless of hidden state, draw visual/debug overlays if enabled in settings
            if hasattr(self, '_draw_graphic_elements') and settings is not None:
                try:
                    self._draw_graphic_elements(center, mouse_pos, settings, tokens)
                except Exception as e:
                    shared.debug(f"Error in _draw_graphic_elements: {str(e)}", category="render")
        except Exception as e:
            shared.debug(f"Error drawing token: {str(e)}", category="render")


    def generate_image(self, settings):
        """Generate the base image at full opacity"""
        shared.debug(f"Generating base image for token {id(self)} with size {self.size}", category="texture")
        try:
            from core import shared as _shared
            if hasattr(_shared, 'perf'):
                _shared.perf['token_generate_image_calls'] += 1
        except Exception:
            pass

        if not (isinstance(self.size, (tuple, list)) and len(self.size) == 2 and
                all(isinstance(v, int) and v > 0 for v in self.size)):
            shared.debug(f"WARNING: Invalid size for token {id(self)}: {self.size}")
            return None

        surface = pygame.Surface(self.size, pygame.SRCALPHA)
        surface.fill((0, 0, 0, 0))  # Start with fully transparent
        token_cfg = settings.get_token_settings()

        if not token_cfg.get("hide"):
            # Always use full opacity in base image
            if len(self.color) == 3:
                triangle_color = (self.color[0], self.color[1], self.color[2], 255)
            else:
                triangle_color = (255, 255, 255, 255)
        else:
            triangle_color = (0, 0, 0, 0) # Transparent

        width, height = self.size
        triangle = [(width // 2, 0), (width, height), (0, height)]

        # Draw the main triangle
        pygame.draw.polygon(surface, triangle_color, triangle)

        # Draw markers
        if not token_cfg.get("hide"):
            marker_size = 4
            pygame.draw.rect(surface, (255, 255, 0, 255),
                             pygame.Rect((width // 2 - marker_size // 2, 0), (marker_size, marker_size)))
            pygame.draw.rect(surface, (255, 0, 0, 255),
                             pygame.Rect((0, height - marker_size), (marker_size, marker_size)))
            pygame.draw.rect(surface, (0, 255, 0, 255),
                             pygame.Rect((width - marker_size, height - marker_size), (marker_size, marker_size)))

        shared.debug(f"Generated image for token {id(self)}: {surface.get_size()}", category="texture")
        try:
            debug_settings = settings.get_debug_settings() if settings else {}
            if debug_settings.get("save_token_images", False):
                pygame.image.save(surface, f"debug_token_{id(self)}.png")
        except Exception:
            pass
        return surface

    def apply_mouse_force(self, mouse_pos, mouse_velocity, settings):
        mouse_cfg = settings.get_mouse_force_settings()

        # Compute token center and mouse direction once
        center = self.position

        # For physical forces, compensate for vertical inversion by reflecting the mouse Y once
        # Use mouse position directly in y-down coordinates (no vertical flip needed)
        force_mouse = pygame.Vector2(mouse_pos.x, mouse_pos.y)

        direction = center - force_mouse
        distance = direction.length()

        # Apply mouse force only if enabled in settings
        if mouse_cfg.get("enabled", False):
            max_distance = mouse_cfg.get("max_distance", 200)
            strength = mouse_cfg.get("force_strength", 1.0)
            falloff = mouse_cfg.get("falloff", "linear")

            if 0 < distance < max_distance:
                direction.normalize_ip()
                if falloff == "linear":
                    factor = strength * (1 - distance / max_distance)
                elif falloff == "inverse":
                    factor = strength / (distance + 1)
                elif falloff == "quadratic":
                    factor = strength * ((1 - distance / max_distance) ** 2)
                elif falloff == "smoothstep":
                    t = max(0.0, min(1.0, 1 - (distance / max_distance)))
                    factor = strength * (t * t * (3 - 2 * t))
                else:
                    factor = strength

                applied = direction * factor * mouse_velocity.length()
                self.velocity += applied
                # Accumulate applied force for debug rendering
                try:
                    if not hasattr(self, 'last_applied_force') or self.last_applied_force is None:
                        self.last_applied_force = pygame.Vector2(0, 0)
                    self.last_applied_force += applied
                except Exception:
                    pass
                self.time_since_force = 0.0

                # # Apply mouse velocity with proper time scaling
                # if self._last_dt > 0:
                #     scaled_velocity = mouse_velocity / self._last_dt
                #     self.velocity += direction * factor * scaled_velocity.length()
                # self.time_since_force = 0.0

        # Apply look-at-mouse rotation independently of mouse force enable flag
        if settings.get_token_settings().get("look_at_mouse", False):
            # Use mouse position directly for rotation (no vertical flip needed)
            rot_mouse = pygame.Vector2(mouse_pos.x, mouse_pos.y)
            angle_rad = math.atan2(rot_mouse.y - center.y, rot_mouse.x - center.x)
            angle_deg = math.degrees(angle_rad)
            # In a y-down screen space, atan2 yields 0=right, 90=down, 180=left, -90=up.
            # The base token triangle points "top" (up). To align triangle tip to the vector,
            # use an offset mapping with no sign inversion of angle.
            facing_offset = {"top": 90, "right": 0, "bottom": -90, "left": 180}.get(self.facing, 90)
            extra_offset = settings.get_token_settings().get("rotation_offset_degrees", 0)
            self.rotation = angle_deg + facing_offset + extra_offset
            shared.debug(f"Token rotation: {self.rotation}, Center: {center}, Mouse: {mouse_pos}, RotMouse: {rot_mouse}")

    def apply_flocking(self, neighbors, settings):
        cfg = settings.get_token_settings().get("flocking", {})
        if not cfg.get("enabled", False):
            return

        radius = cfg.get("radius", 100)
        align_w, cohes_w, separ_w = cfg.get("alignment", 0.5), cfg.get("cohesion", 0.5), cfg.get("separation", 0.5)

        com, avg_vel, sep_force, count = pygame.Vector2(), pygame.Vector2(), pygame.Vector2(), 0
        for other in neighbors:
            if other is self or other is None:
                continue
            offset = other.position - self.position
            dist = offset.length()
            if 0 < dist < radius:
                com += other.position
                avg_vel += other.velocity
                if dist > 0:
                    sep_force -= (offset / dist) * (1 - dist / radius)
                count += 1

        if count > 0:
            com /= count
            avg_vel /= count
            delta = (com - self.position) * cohes_w + (avg_vel - self.velocity) * align_w + sep_force * separ_w
            self.velocity += delta
            # Accumulate applied force for debug rendering
            try:
                if not hasattr(self, 'last_applied_force') or self.last_applied_force is None:
                    self.last_applied_force = pygame.Vector2(0, 0)
                self.last_applied_force += delta
            except Exception:
                pass

    def apply_home_force(self, settings, dt):
        cfg = settings.get_token_settings().get("finds_home", {})
        if cfg.get("enabled", False) and self.time_since_force > cfg.get("delay_sec", 2.0):
            to_home = self.home - self.position
            if to_home.length() > 0:
                to_home.normalize_ip()
                delta = to_home * cfg.get("strength", 0.5) * dt
                self.velocity += delta
                try:
                    if not hasattr(self, 'last_applied_force') or self.last_applied_force is None:
                        self.last_applied_force = pygame.Vector2(0, 0)
                    self.last_applied_force += delta
                except Exception:
                    pass

    def apply_collision(self, all_tokens, settings):
        if not settings.get_token_settings().get("enable_token_collision", False):
            return
        scale = settings.get_token_settings().get("collision", {}).get("bounds_scale", 1.0)
        for other in all_tokens:
            if other is self or other is None:
                continue
            dx = self.position.x - other.position.x
            dy = self.position.y - other.position.y
            distance = math.hypot(dx, dy)
            scaled_radius = (self.size[0] + other.size[0]) / 2 * scale
            if distance < scaled_radius and distance > 0:
                repel = pygame.Vector2(dx, dy).normalize() * 0.5
                self.velocity += repel
                other.velocity -= repel
                self.is_colliding = True
                self.collision_partner = other
                self.collision_time = 0.0

    def _update_sizes(self):
        #  TODO: this needs to be implemented, to simplify size management.
        """Update current_size based on rotation and bounce scale"""
        if self.rotation != 0:
            angle_rad = math.radians(self.rotation)
            cos_rot = abs(math.cos(angle_rad))
            sin_rot = abs(math.sin(angle_rad))
            width = self.original_size[0] * cos_rot + self.original_size[1] * sin_rot
            height = self.original_size[0] * sin_rot + self.original_size[1] * cos_rot
            self.current_size = (width, height)
        else:
            self.current_size = self.original_size

        if self.bounce_scale != 1.0:
            self.size = (
                self.original_size[0] * self.bounce_scale,
                self.original_size[1] * self.bounce_scale
            )
            self.current_size = (
                self.current_size[0] * self.bounce_scale,
                self.current_size[1] * self.bounce_scale
            )

    def check_collision(self, other: 'Token', settings) -> bool:
        """Check for collision with another token."""
        try:
            # Skip if either token is None
            if other is None:
                return False

            # Get timing settings for collision delay
            timing_cfg = settings.get_timing_settings()
            collision_delay = timing_cfg.get("respawn_collision_delay_sec", 0.5)

            # Skip collision check if within delay period
            if self.time_since_respawn < collision_delay:
                return False

            token_cfg = settings.get_token_settings()
            collision_behaviors = token_cfg.get("collision_behavior", [])
            collision_type = token_cfg.get("collision", {}).get("type", "circle")

            # Get bounce threshold from animation settings
            animation_cfg = settings.runtime_settings.get("animation", {})
            bounce_threshold = animation_cfg.get("bounce_threshold", 0.3)

            shared.debug(f"Checking collision between tokens {id(self)} and {id(other)}")
            shared.debug(f"Collision behaviors: {collision_behaviors}")
            shared.debug(f"Bounce threshold: {bounce_threshold}")

            # Ensure collision_behaviors is a list
            if isinstance(collision_behaviors, str):
                collision_behaviors = [collision_behaviors]

            if "bounce_pop" in collision_behaviors:
                # Calculate intensity based on overlap percentage, honoring collision type and bounds_scale
                try:
                    coll_cfg = token_cfg.get("collision", {}) if isinstance(token_cfg, dict) else {}
                    bounds_scale = float(coll_cfg.get("bounds_scale", 1.0))
                    ctype = str(collision_type).lower()

                    if ctype.startswith("rect"):
                        # Scaled rectangle overlap based on current_size
                        half_w_a = 0.5 * float(self.current_size[0]) * bounds_scale
                        half_h_a = 0.5 * float(self.current_size[1]) * bounds_scale
                        half_w_b = 0.5 * float(other.current_size[0]) * bounds_scale
                        half_h_b = 0.5 * float(other.current_size[1]) * bounds_scale

                        left_a = self.position.x - half_w_a
                        right_a = self.position.x + half_w_a
                        top_a = self.position.y - half_h_a
                        bottom_a = self.position.y + half_h_a

                        left_b = other.position.x - half_w_b
                        right_b = other.position.x + half_w_b
                        top_b = other.position.y - half_h_b
                        bottom_b = other.position.y + half_h_b

                        # No collision cases
                        if right_a < left_b or left_a > right_b or bottom_a < top_b or top_a > bottom_b:
                            return False

                        overlap_x = min(right_a, right_b) - max(left_a, left_b)
                        overlap_y = min(bottom_a, bottom_b) - max(top_a, top_b)
                        overlap_area = max(0.0, overlap_x) * max(0.0, overlap_y)
                        max_area = max(1e-6, min((2*half_w_a)*(2*half_h_a), (2*half_w_b)*(2*half_h_b)))
                        intensity = max(0.0, min(1.0, overlap_area / max_area))
                    else:
                        # Default: circle-collision using scaled radii
                        dx = float(self.position.x - other.position.x)
                        dy = float(self.position.y - other.position.y)
                        dist = (dx * dx + dy * dy) ** 0.5
                        r_a = 0.5 * float(min(self.current_size[0], self.current_size[1])) * bounds_scale
                        r_b = 0.5 * float(min(other.current_size[0], other.current_size[1])) * bounds_scale
                        combined = r_a + r_b
                        if combined <= 0 or dist >= combined:
                            return False
                        intensity = 1.0 - (dist / combined)

                    shared.debug(f"Collision intensity: {intensity}")

                    if intensity >= bounce_threshold:
                        shared.debug(
                            f"Collision detected! Intensity: {intensity:.2f}, Bounce threshold: {bounce_threshold}")
                        self.is_colliding = True
                        self.collision_partner = other
                        self.collision_time = 0.0
                        self.bounce_scale = 1.0
                        shared.debug(f"Token {id(self)} colliding with {id(other)}")
                        return True

                except (AttributeError, TypeError, ValueError) as e:
                    shared.debug(f"Error calculating collision: {str(e)}")
                    return False

        except Exception as e:
            shared.debug(f"Error in collision check: {str(e)}")
            return False

        return False

    def _draw_graphic_elements(self, center, mouse_pos, settings, tokens):
        """Draw debug graphics and visual effects for the token"""
        # Draw visual elements based on visual_elements settings (no longer gated by debug.enabled)
        visuals = settings.get_visual_elements() if hasattr(settings, 'get_visual_elements') else {}

        # Draw token collision bounds if enabled (OpenGL)
        bounds_cfg = visuals.get("token_collision_bounds", {}) if isinstance(visuals, dict) else {}
        if isinstance(bounds_cfg, dict) and bounds_cfg.get("enabled", False):
            color = tuple(bounds_cfg.get("color", [255, 0, 0]))
            thickness = float(bounds_cfg.get("thickness", 2))
            # Read collision settings
            token_cfg = settings.get_token_settings() if hasattr(settings, 'get_token_settings') else {}
            coll_cfg = token_cfg.get("collision", {}) if isinstance(token_cfg, dict) else {}
            coll_type = str(coll_cfg.get("type", "circle")).lower()
            bounds_scale = float(coll_cfg.get("bounds_scale", 1.0))
            if coll_type.startswith("rect"):
                # Draw scaled rectangle centered on token
                w = float(self.current_size[0]) * bounds_scale
                h = float(self.current_size[1]) * bounds_scale
                x = float(self.position.x) - w / 2.0
                y = float(self.position.y) - h / 2.0
                draw_gl_rect_outline(x, y, w, h, color=color, thickness=thickness)
            else:
                # Default to circle
                radius = 0.5 * float(min(self.current_size[0], self.current_size[1])) * bounds_scale
                draw_gl_circle_outline(float(self.position.x), float(self.position.y), radius, color=color, thickness=thickness)

        # Draw velocity vector if enabled (OpenGL)
        vel_cfg = visuals.get("velocity_vector", {}) if isinstance(visuals, dict) else {}
        if isinstance(vel_cfg, dict) and vel_cfg.get("enabled", False) and self.velocity.length() > 0.1:
            color = tuple(vel_cfg.get("color", [255, 255, 0]))
            thickness = float(vel_cfg.get("thickness", 2))
            end_pos = center + self.velocity * 5
            draw_gl_line(center.x, center.y, end_pos.x, end_pos.y, color=color, thickness=thickness)

        # Draw force vector if enabled (sum of applied forces this frame) (OpenGL)
        force_cfg = visuals.get("force_vector", {}) if isinstance(visuals, dict) else {}
        last_force = getattr(self, 'last_applied_force', None)
        if isinstance(force_cfg, dict) and force_cfg.get("enabled", False) and isinstance(last_force, pygame.Vector2) and last_force.length() > 0.05:
            color = tuple(force_cfg.get("color", [255, 128, 0]))
            thickness = float(force_cfg.get("thickness", 1))
            scale = 8
            end_pos = center + last_force * scale
            draw_gl_line(center.x, center.y, end_pos.x, end_pos.y, color=color, thickness=thickness)

        # Draw flocking radius if enabled (OpenGL)
        flock_cfg = visuals.get("flocking_radius", {}) if isinstance(visuals, dict) else {}
        if isinstance(flock_cfg, dict) and flock_cfg.get("enabled", False):
            # Use tokens.flocking.radius for radius
            tokens_cfg = settings.get_token_settings() if hasattr(settings, 'get_token_settings') else {}
            flocking = tokens_cfg.get("flocking", {}) if isinstance(tokens_cfg, dict) else {}
            radius = float(flocking.get("radius", 100.0))
            color = tuple(flock_cfg.get("color", [128,128,128]))
            thickness = float(flock_cfg.get("thickness", 2))
            # Adaptive segment count to reduce cost
            segs = int(max(16, min(64, radius / 4.0)))
            draw_gl_circle_outline(center.x, center.y, radius, color=color, thickness=thickness, segments=segs)

        # Draw token center (OpenGL)
        center_cfg = visuals.get("token_center", {}) if isinstance(visuals, dict) else {}
        if isinstance(center_cfg, dict) and center_cfg.get("enabled", False):
            ccolor = tuple(center_cfg.get("color", [255,255,255]))
            cthick = float(center_cfg.get("thickness", 2))
            # Render a small circle at the center; radius derived from thickness
            cradius = max(2.0, cthick * 0.5)
            segs_center = 12
            draw_gl_circle_outline(center.x, center.y, cradius, color=ccolor, thickness=cthick, segments=segs_center)

        # Draw separation lines to nearby tokens within flocking radius (OpenGL)
        sep_cfg = visuals.get("separation_lines", {}) if isinstance(visuals, dict) else {}
        if isinstance(sep_cfg, dict) and sep_cfg.get("enabled", False):
            # Support draw order toggle: "over" draws in a dedicated pass after tokens; "in_order" draws here
            mode = str(sep_cfg.get("mode", "over")).lower()
            if mode == "in_order":
                scolor = tuple(sep_cfg.get("color", [0,255,255]))
                sthick = float(sep_cfg.get("thickness", 1))
                # Use cached neighbors from runtime
                neighbors = getattr(self, "_nearby_for_visuals", [])
                try:
                    tokens_cfg = settings.get_token_settings() if hasattr(settings, 'get_token_settings') else {}
                    flocking = tokens_cfg.get("flocking", {}) if isinstance(tokens_cfg, dict) else {}
                    max_r = float(flocking.get("radius", 100.0))
                except Exception:
                    max_r = 100.0
                cx, cy = center.x, center.y
                for other in neighbors:
                    try:
                        if other is None or other is self:
                            continue
                        # Avoid drawing each pair twice
                        if id(self) > id(other):
                            continue
                        ox, oy = other.position.x, other.position.y
                        dx = ox - cx
                        dy = oy - cy
                        if dx*dx + dy*dy <= max_r*max_r:
                            draw_gl_line(cx, cy, ox, oy, color=scolor, thickness=sthick)
                    except Exception:
                        continue
            # else: mode == "over" => skip here; Simulation.update will draw them in a single pass over tokens

    def update(self, canvas_size, settings, dt):
        shared.debug("Token.update() called")
        self.time_since_respawn += dt
        self._last_dt = dt  # Store dt for use in force calculations

        # Handle collision animation
        if self.is_colliding:
            shared.debug(f"Token {id(self)} collision animation in Token.update()")
            old_scale = self.bounce_scale
            self.collision_time += dt
            bounce_duration = settings.runtime_settings.get("animation", {}).get("bounce_duration_ms", 150) / 1000.0

            shared.debug(f"Token {id(self)} colliding - Time: {self.collision_time:.3f}/{bounce_duration:.3f}")

            if self.collision_time >= bounce_duration:
                self.is_colliding = False
                self.collision_partner = None
                self.collision_time = 0.0
                self.bounce_scale = 1.0
                shared.debug(f"Collision animation complete - Scale reset to 1.0")
            else:
                bounce_max = settings.runtime_settings.get("animation", {}).get("bounce_scale", 1.2)
                progress = self.collision_time / bounce_duration
                if progress < 0.5:
                    self.bounce_scale = 1.0 + (bounce_max - 1.0) * (progress * 2)
                else:
                    self.bounce_scale = bounce_max - (bounce_max - 1.0) * ((progress - 0.5) * 2)

                if self.bounce_scale != old_scale:
                    shared.debug(f"Bounce scale changed: {old_scale:.3f} -> {self.bounce_scale:.3f}")

        # Update position and velocity
        self.position += self.velocity
        self.velocity *= 0.9
        self.time_since_force += dt

        # Calculate rotated bounding box size
        if self.rotation != 0:
            angle_rad = math.radians(self.rotation)
            cos_rot = abs(math.cos(angle_rad))
            sin_rot = abs(math.sin(angle_rad))
            width = self.original_size[0] * cos_rot + self.original_size[1] * sin_rot
            height = self.original_size[0] * sin_rot + self.original_size[1] * cos_rot
            self.current_size = (width, height)
        else:
            self.current_size = self.original_size

        # Apply bounce scale to sizes
        if self.bounce_scale != 1.0:
            self.size = (
                self.original_size[0] * self.bounce_scale,
                self.original_size[1] * self.bounce_scale
            )
            self.current_size = (
                self.current_size[0] * self.bounce_scale,
                self.current_size[1] * self.bounce_scale
            )

        # Handle boundary collisions
        token_cfg = settings.get_token_settings()
        bounce_factor = settings.runtime_settings.get("physics", {}).get("bounce_factor", 0.8)

        if token_cfg.get("enable_wall_bounce", False):
            half_width = self.current_size[0] / 2
            half_height = self.current_size[1] / 2

            # Left/Right boundaries
            if self.position.x - half_width < 0:
                self.position.x = half_width
                if self.velocity.x < 0:
                    self.velocity.x = -self.velocity.x * bounce_factor
            elif self.position.x + half_width > canvas_size[0]:
                self.position.x = canvas_size[0] - half_width
                if self.velocity.x > 0:
                    self.velocity.x = -self.velocity.x * bounce_factor

            # Top/Bottom boundaries
            if self.position.y - half_height < 0:
                self.position.y = half_height
                if self.velocity.y < 0:
                    self.velocity.y = -self.velocity.y * bounce_factor
            elif self.position.y + half_height > canvas_size[1]:
                self.position.y = canvas_size[1] - half_height
                if self.velocity.y > 0:
                    self.velocity.y = -self.velocity.y * bounce_factor
        else:
            # Mark as dead if completely off screen (position treated as center)
            half_width = self.current_size[0] / 2
            half_height = self.current_size[1] / 2
            self.dead = (
                self.position.x + half_width < 0 or  # Completely off left
                self.position.x - half_width > canvas_size[0] or  # Completely off right
                self.position.y + half_height < 0 or  # Completely off top
                self.position.y - half_height > canvas_size[1]  # Completely off bottom
            )

            # Update collision bounds rect
        self.collision_bounds_rect.x = self.position.x - self.current_size[0] / 2
        self.collision_bounds_rect.y = self.position.y - self.current_size[1] / 2
        self.collision_bounds_rect.width = self.current_size[0]
        self.collision_bounds_rect.height = self.current_size[1]

        # Update collision radius
        self.collision_radius = min(self.current_size[0], self.current_size[1]) / 2

        # Return whether the token is still alive
        return not self.dead
