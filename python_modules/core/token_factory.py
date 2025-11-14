import pygame
from OpenGL.GL import *

from core import shared
from core.token import Token
from core.rendering import TexturePool
from core.debug import debug, DebugManager
import pygame


class TokenFactory:

    def __init__(self, settings, token_class=None):
        """Creates and manages token instances"""
        self.settings = settings
        self.token_positions = []
        self.token_class = token_class or Token
        self.texture_pool = None
        # Optional background mask surface for grid filtering (set by Simulation)
        self.grid_mask_surface = None

        try:
            # Initialize OpenGL context if not already done
            if not pygame.display.get_init():
                pygame.init()

            # Ensure we have a valid OpenGL context
            if not pygame.display.get_surface():
                display_info = pygame.display.Info()
                pygame.display.set_mode((display_info.current_w, display_info.current_h),
                                        pygame.OPENGL | pygame.DOUBLEBUF | pygame.HIDDEN)

            # Calculate initial token count based on canvas size
            canvas_size = settings.get_init_canvas_size()
            token_size = settings.get_token_size()
            min_padding = settings.init_settings.get("init_canvas", {}).get("min_padding", 10)

            max_cols = int((canvas_size[0] - 2 * min_padding) // (token_size[0] + min_padding))
            max_rows = int((canvas_size[1] - 2 * min_padding) // (token_size[1] + min_padding))
            initial_count = max_cols * max_rows

            shared.debug(f"Canvas size: {canvas_size}", category="factory")
            shared.debug(f"Token size: {token_size}", category="factory")
            shared.debug(f"Grid: {max_cols}x{max_rows} = {initial_count} tokens", category="factory")
            shared.debug(f"Min padding: {min_padding}", category="factory")

            # Initialize texture pool with single transfer texture
            try:
                pygame.time.wait(100)  # Give OpenGL context time to initialize

                self.texture_pool = TexturePool(
                    texture_size=token_size
                )

                shared.debug(f"Created TexturePool with size {token_size} using shared transfer texture",
                             category="factory")

            except Exception as e:
                shared.debug(f"Failed to create TexturePool: {str(e)}", category="factory")
                if self.texture_pool:
                    self.texture_pool.cleanup()
                self.texture_pool = None
                raise

        except Exception as e:
            shared.debug(f"Error in TokenFactory initialization: {str(e)}", category="factory")
            import traceback
            shared.debug(f"Traceback: {traceback.format_exc()}", category="factory")
            if self.texture_pool:
                self.texture_pool.cleanup()
            self.texture_pool = None
            raise

    def create_token_at_home(self, home_position):
        """Create a single token at the specified home position"""
        if self.texture_pool is None:
            shared.debug("No texture pool available", category="factory")
            return None

        try:
            token_size = self.settings.get_token_size()
            token_cfg = self.settings.get_token_settings()
            facing = token_cfg.get("facing", "top")

            # Create the token instance
            token = self.token_class(
                home_position,
                token_size,
                facing,
                texture_pool=self.texture_pool
            )

            # Set additional properties
            token.settings = self.settings
            token.home = pygame.Vector2(home_position)

            # Generate initial image
            token.image = token.generate_image(self.settings)
            if token.image is None:
                token.image = pygame.Surface(token_size, pygame.SRCALPHA)
                token.image.fill((255, 255, 255, 128))

            # Now get a texture ID using the token's id as entity_id
            token.texture_id = self.texture_pool.get_texture(id(token))
            if token.texture_id is None:
                shared.debug("Failed to get texture for token", category="factory")
                return None

            # Make sure OpenGL state is properly set up
            glBindTexture(GL_TEXTURE_2D, token.texture_id)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)

            # Create initial texture with correct dimensions
            img_width, img_height = token.image.get_size()
            texture_data = pygame.image.tostring(token.image, "RGBA", 1)

            glTexImage2D(
                GL_TEXTURE_2D, 0, GL_RGBA,
                img_width, img_height,
                0, GL_RGBA, GL_UNSIGNED_BYTE, texture_data
            )

            # Update texture with settings
            if not token._update_texture(self.settings):  # Pass settings here
                shared.debug("Failed to update texture", category="factory")
                self.texture_pool.release_texture(id(token))
                return None

            return token

        except Exception as e:
            shared.debug(f"Error creating token: {str(e)}", category="factory")
            return None

    def set_grid_mask_surface(self, surface):
        """Set a background mask surface used to filter grid positions at init.
        The surface will be scaled to the canvas size if needed. Pass a pygame.Surface or None.
        """
        self.grid_mask_surface = surface

    def _filter_positions_with_mask(self, positions, canvas_size, threshold=128):
        """Filter grid positions using the optional background mask surface.
        - positions: list[(x,y)] of centers
        - canvas_size: (w,h)
        - threshold: luminance threshold [0-255] to accept a position
        Returns a possibly reduced list of positions. If filtering eliminates all positions,
        returns the original positions to avoid empty scenes.
        """
        try:
            if not isinstance(self.grid_mask_surface, pygame.Surface):
                return positions
            surf = self.grid_mask_surface
            w, h = int(canvas_size[0]), int(canvas_size[1])
            if surf.get_size() != (w, h):
                try:
                    surf = pygame.transform.smoothscale(surf, (w, h))
                except Exception:
                    surf = pygame.transform.scale(surf, (w, h))
            # Determine threshold from settings if present
            try:
                cfg = self.settings.init_settings.get('init_grid_mask', {})
                threshold = int(cfg.get('threshold', threshold))
            except Exception:
                pass

            filtered = []
            px = None
            try:
                px = pygame.PixelArray(surf)
            except Exception:
                px = None
            try:
                for (x, y) in positions:
                    xi = max(0, min(w - 1, int(round(x))))
                    yi = max(0, min(h - 1, int(round(y))))
                    try:
                        color = surf.get_at((xi, yi)) if px is None else surf.unmap_rgb(px[xi, yi])
                    except Exception:
                        color = surf.get_at((xi, yi))
                    r, g, b = int(color[0]), int(color[1]), int(color[2])
                    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
                    if luminance >= threshold:
                        filtered.append((x, y))
            finally:
                try:
                    if px is not None:
                        del px
                except Exception:
                    pass
            if not filtered:
                shared.debug("Grid mask filtered all positions; falling back to unfiltered grid", category="factory")
                return positions
            shared.debug(f"Grid mask kept {len(filtered)}/{len(positions)} positions (threshold={threshold})", category="factory")
            return filtered
        except Exception as e:
            shared.debug(f"Error applying grid mask: {e}", category="factory")
            return positions

    def cleanup(self):
        """Clean up resources"""
        if self.texture_pool:
            self.texture_pool.cleanup()
            self.texture_pool = None

    def _calculate_optimal_grid(self, canvas_width, canvas_height, token_width, token_height, min_padding):
        """
        Calculate optimal grid layout with multiple passes to find best fit.
        Returns (positions, best_spacing) where:
        - positions is list of (x,y) center positions
        - best_spacing is (spacing_x, spacing_y) for the chosen layout
        """
        # Calculate maximum possible tokens with minimum padding
        max_cols = int((canvas_width - 2 * min_padding) // (token_width + min_padding))
        max_rows = int((canvas_height - 2 * min_padding) // (token_height + min_padding))

        def try_layout(n_cols, n_rows):
            # Calculate total space needed for tokens
            total_token_width = n_cols * token_width
            total_token_height = n_rows * token_height

            # Calculate total available space
            available_space_x = canvas_width - total_token_width
            available_space_y = canvas_height - total_token_height

            # Calculate spacing between tokens and edges
            spacing_x = available_space_x / (n_cols + 1)  # +1 for edges
            spacing_y = available_space_y / (n_rows + 1)  # +1 for edges

            if spacing_x < min_padding or spacing_y < min_padding:
                return None, None  # Invalid layout - spacing too small

            # Generate positions array
            positions = []
            for row in range(n_rows):
                for col in range(n_cols):
                    # Fixed position calculation with proper centering
                    x = spacing_x + col * (token_width + spacing_x) + token_width / 2
                    y = spacing_y + row * (token_height + spacing_y) + token_height / 2
                    positions.append((x, y))

            return positions, (token_width + spacing_x, token_height + spacing_y)

        # Try different combinations, starting with maximum
        for cols in range(max_cols, max_cols - 1, -1):
            for rows in range(max_rows, max_rows - 1, -1):
                positions, spacing = try_layout(cols, rows)
                if positions is not None:
                    return positions, spacing

        return try_layout(max_cols - 1, max_rows - 1)

    def create_initial_tokens(self):
        """Create the initial set of tokens in a grid layout"""
        if self.texture_pool is None:
            shared.debug("TexturePool not initialized", category="factory")
            raise RuntimeError("TexturePool not initialized")

        try:
            canvas_size = self.settings.get_init_canvas_size()
            token_size = self.settings.get_token_size()
            token_cfg = self.settings.get_token_settings()
            facing = token_cfg.get("facing", "top")

            # Calculate grid layout
            canvas_settings = self.settings.init_settings.get("init_canvas", {})
            min_padding = canvas_settings.get("min_padding", 10)

            shared.debug(f"Creating initial tokens with size {token_size}", category="factory")

            positions, _ = self._calculate_optimal_grid(
                canvas_size[0], canvas_size[1],
                token_size[0], token_size[1],
                min_padding
            )

            # Phase 2: optionally filter positions using background mask image
            try:
                positions = self._filter_positions_with_mask(positions, canvas_size)
            except Exception:
                pass

            # Cache positions for respawning
            self.token_positions = positions

            # Create tokens with texture pool reference
            tokens = []
            shared.debug(f"Creating {len(positions)} tokens", category="factory")

            for i, pos in enumerate(positions):
                try:
                    # Get a texture from the pool first
                    texture_id = self.texture_pool.get_texture(id(pos))  # Use position id as entity_id
                    if texture_id is None:
                        shared.debug(f"Failed to get texture for token {i}", category="factory")
                        continue

                    # Create token with proper error handling
                    token = self.token_class(
                        pos,
                        token_size,
                        facing,
                        texture_pool=self.texture_pool
                    )
                    token.settings = self.settings  # Set settings before updating texture
                    token.texture_id = texture_id

                    # Generate and set initial image
                    token.image = token.generate_image(self.settings)
                    shared.debug(f"Token image generated: {token.image is not None}, size: {token.image.get_size() if token.image else 'None'}", category="factory")
                    if token.image is None:
                        shared.debug("Using fallback white rectangle image", category="factory")
                        token.image = pygame.Surface(token_size, pygame.SRCALPHA)
                        token.image.fill((255, 255, 255, 128))

                    # Update texture, passing settings explicitly
                    if not token._update_texture(self.settings):  # Pass settings here
                        raise RuntimeError("Failed to update texture")

                    tokens.append(token)

                except Exception as e:
                    shared.debug(f"Error creating token {i}: {str(e)}", category="factory")
                    if texture_id is not None:
                        self.texture_pool.release_texture(texture_id)
                    continue

            if not tokens:
                raise RuntimeError("Failed to create any tokens")

            shared.debug(f"Successfully created {len(tokens)} tokens", category="factory")
            return tokens

        except Exception as e:
            shared.debug(f"Error in create_initial_tokens: {str(e)}", category="factory")
            raise