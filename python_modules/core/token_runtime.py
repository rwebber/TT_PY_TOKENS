import pygame
import SpoutGL
from OpenGL.GL import *
from time import time
from collections import deque

from core.debug import debug, DebugManager
from core.settings_manager import SettingsManager
from core.token_factory import TokenFactory
from core.token import Token
from core.respawn_manager import RespawnManager
from core import shared
from core.spatial_grid_manager import SpatialGrid
from core.utils import (
    prepare_spout_output,
    prepare_video_output,
    setup_gl_state
)

# Add these initializations at the module level in token_runtime.py
_grid_cache_surface = None
_grid_cache_size = (0, 0)
_grid_cache_cell_size = 0
_grid_cache_counter = 0
_grid_cache_text_interval = 30  # How often to update text labels (frames)
_spatial_grid = None
_collision_checks = 0
_potential_collisions = 0


# GLOBALS
# _spatial_grid = None
# _collision_checks = 0
# _potential_collisions = 0


def update_tokens(tokens, respawner, surface, mouse_pos, mouse_velocity, settings, canvas_size, dt):
    """Main per-frame update logic for all tokens"""
    global _spatial_grid, _collision_checks, _potential_collisions
    _collision_checks = 0
    _potential_collisions = 0

    shared.debug(f"update_tokens() called with canvas_size {canvas_size}")

    # Initialize spatial grid if needed
    if _spatial_grid is None:
        # Use maximum token radius/size for cell size
        token_size = max(settings.get_token_size())
        collision_settings = settings.get_token_settings().get("collision", {})
        bounds_scale = collision_settings.get("bounds_scale", 0.5)
        # Make cells 2x the actual collision size to reduce overlap checks
        cell_size = token_size * bounds_scale * 2
        _spatial_grid = SpatialGrid(cell_size=cell_size)

    # Update spatial grid with current token positions
    _spatial_grid.update([t for t in tokens if t is not None])

    # Clear buffer
    glClearColor(0.0, 0.0, 0.0, 0.0)
    glClear(GL_COLOR_BUFFER_BIT)

    # Setup basic GL state using utility function
    setup_gl_state()  # This handles texture, blend modes and other common state

    # Handle mouse visibility for forces only (do not override actual mouse_pos used for rotation)
    mouse_force_cfg = settings.get_mouse_force_settings()
    force_mouse_pos = mouse_pos
    if not mouse_force_cfg.get("enabled", False):
        force_mouse_pos = (-1000, -1000)

    # Update shared resources and process tokens
    update_shared_image_cache(tokens, settings)

    # Process each token
    for i, token in enumerate(tokens):
        if isinstance(token, Token):
            shared.debug(f"Updating token {id(token)}")

            # Reset per-frame accumulated force for visualization
            try:
                token.last_applied_force = pygame.Vector2(0, 0)
            except Exception:
                pass

            # Get potential interaction partners using spatial grid
            nearby_tokens = _spatial_grid.get_nearby_tokens(
                token.position,
                settings.get_mouse_force_settings().get("max_distance", 50)
            )

            # Cache neighbors for visual debug drawing (e.g., separation_lines)
            try:
                token._nearby_for_visuals = list(nearby_tokens)
            except Exception:
                pass

            # Apply behaviors with filtered token list
            token.apply_flocking(list(nearby_tokens), settings)
            # Apply forces and rotation: method itself checks if forces are enabled; always pass real mouse_pos so rotation can work regardless of force setting
            token.apply_mouse_force(mouse_pos, mouse_velocity, settings)
            # Apply home-seeking force based on tokens.finds_home (enabled, delay_sec, strength)
            try:
                token.apply_home_force(settings, dt)
            except Exception:
                pass

            # Check collisions only with nearby tokens
            collision_candidates = _spatial_grid.get_potential_collisions(token)
            _potential_collisions += len(collision_candidates)  # Track how many tokens we check

            for other in collision_candidates:
                if other is not None and other is not token:
                    _collision_checks += 1  # Count actual collision checks
                    if token.check_collision(other, settings):
                        shared.debug(f"Collision detected between tokens {id(token)} and {id(other)}")

            # Update state
            token.update(canvas_size, settings, dt)

            # Handle token death/respawn
            if getattr(token, "dead", False):
                # Make sure to cleanup before removing the token
                token.cleanup()  # Add this line
                respawner.schedule_respawn(i)
                tokens[i] = None

    # Draw performance overlay
    draw_spatial_grid_debug(surface, settings)
    draw_performance_stats(surface, settings, tokens, dt)


_frame_times = deque(maxlen=30)  # Store last 30 frame times
_last_frame_time = time()


# Simple cache for static grid lines to avoid per-frame 2D drawing overhead
# _grid_cache_surface = None
# _grid_cache_size = (0, 0)
# _grid_cache_cell_size = 0
# _grid_cache_counter = 0
# _grid_cache_text_interval = 10  # update occupancy text every N frames

def draw_spatial_grid_debug(surface, settings):
    """Draw debug visualization of the spatial grid with caching for performance"""
    global _grid_cache_surface, _grid_cache_size, _grid_cache_cell_size, _grid_cache_counter

    if not settings.get_debug_settings().get("show_spatial_grid", True):
        return

    if _spatial_grid is None:
        return

    width, height = surface.get_width(), surface.get_height()
    cell_size = int(max(1, _spatial_grid.cell_size))

    # Rebuild cached grid if size or cell size changed
    if (_grid_cache_surface is None or
        _grid_cache_size != (width, height) or
        _grid_cache_cell_size != cell_size):
        _grid_cache_surface = pygame.Surface((width, height), pygame.SRCALPHA)
        _grid_cache_surface.fill((0, 0, 0, 0))
        color = (50, 50, 50, 255)
        # Vertical lines
        for x in range(0, width, cell_size):
            pygame.draw.line(_grid_cache_surface, color, (x, 0), (x, height))
        # Horizontal lines
        for y in range(0, height, cell_size):
            pygame.draw.line(_grid_cache_surface, color, (0, y), (width, y))
        _grid_cache_size = (width, height)
        _grid_cache_cell_size = cell_size

    # Blit cached grid lines onto the debug surface
    surface.blit(_grid_cache_surface, (0, 0))

    # Throttle occupancy text updates for performance
    _grid_cache_counter = (_grid_cache_counter + 1) % _grid_cache_text_interval
    if _grid_cache_counter != 0:
        return

    # Draw cell occupancy counts (throttled)
    font = pygame.font.Font(None, 20)
    for cell, tokens in _spatial_grid.grid.items():
        if tokens:  # Only draw cells with tokens
            x = int(cell[0] * cell_size + cell_size / 2)
            y = int(cell[1] * cell_size + cell_size / 2)
            count = len(tokens)
            text = font.render(str(count), True, (200, 200, 0))
            surface.blit(text, (x, y))


def draw_performance_stats(surface, settings, tokens, dt):
    """Draw performance statistics in the upper left corner"""
    global _collision_checks, _potential_collisions

    # Check if stats overlay is enabled in debug settings
    debug_settings = settings.get_debug_settings()
    if not debug_settings.get("stats_overlay", False):
        return

    # Use the dt passed from simulation
    _frame_times.append(dt)

    # Calculate average FPS over the last 30 frames
    if _frame_times:
        average_dt = sum(_frame_times) / len(_frame_times)
        fps = int(1.0 / average_dt) if average_dt > 0 else 0
    else:
        fps = 0

    # Create font (using default font since it's guaranteed to exist)
    font = pygame.font.Font(None, 24)

    # Get required information
    canvas_size = settings.get_init_canvas_size()
    token_size = settings.get_token_size()
    active_tokens = sum(1 for token in tokens if token is not None)

    # Prepare text lines
    stats = [
        f"Canvas: {canvas_size[0]}x{canvas_size[1]}",
        f"Token Size: {token_size[0]}x{token_size[1]}",
        f"Total Tokens: {len(tokens)}",
        f"Active Tokens: {active_tokens}",
        f"FPS: {fps}"
    ]

    # # Add collision statistics
    # total_tokens = len([t for t in tokens if t is not None])
    # max_possible_checks = (total_tokens * (total_tokens - 1)) // 2

    # Add collision statistics with safe division
    total_tokens = len([t for t in tokens if t is not None])
    max_possible_checks = (total_tokens * (total_tokens - 1)) // 2 if total_tokens > 1 else 0

    # Safe grid efficiency calculation
    try:
        grid_eff = 100 - (_collision_checks * 100 / max_possible_checks) if max_possible_checks > 0 else 100.0
    except Exception:
        grid_eff = 0.0

    additional_stats = [
        f"Collision Checks: {_collision_checks}",
        f"Potential Collisions: {_potential_collisions}",
        f"Max Possible Checks: {max_possible_checks}",
        f"Grid Efficiency: {grid_eff:.1f}%"
    ]

    # Performance breakdown (ms)
    try:
        p = shared.perf if hasattr(shared, 'perf') else {}
        perf_lines = [
            "--- Frame Perf (ms) ---",
            f"begin_frame: {p.get('begin_frame_ms', 0.0):.2f}",
            f"process_image_input: {p.get('process_image_input_ms', 0.0):.2f}",
            f"update_simulation: {p.get('update_simulation_ms', 0.0):.2f}",
            f"render_tokens: {p.get('render_tokens_ms', 0.0):.2f} (n={p.get('rendered_tokens', 0)})",
            f"mouse_radius: {p.get('mouse_radius_ms', 0.0):.2f}",
            f"debug_overlay: {p.get('debug_overlay_ms', 0.0):.2f}",
            f"end_frame: {p.get('end_frame_ms', 0.0):.2f}",
            f"tex_uploads: {p.get('tex_uploads', 0)} in {p.get('tex_upload_ms', 0.0):.2f} ms",
            f"overlay_uploads: {p.get('overlay_uploads', 0)} in {p.get('debug_overlay_upload_ms', 0.0):.2f} ms",
            "--- Token Graphics ---",
            f"generate_image calls: {p.get('token_generate_image_calls', 0)}",
            f"_get_base_image calls: {p.get('token_get_base_image_calls', 0)}",
            f"base from live shared: {p.get('token_base_from_live', 0)}",
            f"base generated: {p.get('token_base_generated', 0)}",
            f"shared rescales: {p.get('shared_image_rescales', 0)}",
            f"shared direct copies: {p.get('shared_image_direct_copies', 0)}",
            f"shared tokens updated: {p.get('shared_image_tokens_updated', 0)}",
            "--- Input Hashing ---",
            f"hash computed: {p.get('image_hash_computed', 0)}",
            f"hash time (ms): {p.get('image_hash_ms', 0.0):.2f}",
            f"hash prevented updates: {p.get('image_hash_prevented_updates', 0)}",
        ]
    except Exception:
        perf_lines = []

    # Config audit mini-summary
    try:
        audit = getattr(shared, 'last_config_audit', None)
        if isinstance(audit, dict):
            stats.append("--- Config Audit ---")
            unk = audit.get('unknown_keys', []) or []
            mis = audit.get('missing_expected', []) or []
            stats.append(f"unknown: {len(unk)}; missing: {len(mis)}")
            # Show a few examples to guide the user
            max_list = 4
            if unk:
                show = ", ".join(unk[:max_list]) + (" ..." if len(unk) > max_list else "")
                stats.append(f"unknown keys: {show}")
            if mis:
                showm = ", ".join(mis[:max_list]) + (" ..." if len(mis) > max_list else "")
                stats.append(f"missing keys: {showm}")
    except Exception:
        pass

    stats.extend(additional_stats + perf_lines)

    # Compute panel rect (for GL pass), but draw only text here
    padding = 5
    line_height = 25
    max_width = max(font.size(text)[0] for text in stats) if stats else 0
    panel_x, panel_y = 10, 10
    panel_w = max_width + padding * 2
    panel_h = (len(stats) * line_height) + padding * 2
    try:
        shared.stats_panel_rect = (panel_x, panel_y, panel_w, panel_h)
    except Exception:
        pass

    # Render each line (shadow + text), no background panel to keep content visible
    y_offset = panel_y + padding
    x_offset = panel_x + padding
    for text in stats:
        glow = font.render(text, True, (0, 0, 0))
        text_surface = font.render(text, True, (255, 255, 255))
        # Drop shadow
        surface.blit(glow, (x_offset + 1, y_offset + 1))
        # Text
        surface.blit(text_surface, (x_offset, y_offset))
        y_offset += line_height


def process_image_input(image_input, settings, tokens):
    """Process incoming image data and update token images if needed.

    Precedence and behavior:
    - If input.live_image_update is True: always update the shared image every frame.
      Optionally compute and store a hash (input.compute_hash_when_live_update, default True)
      so downstream caches (per-size token caches) can use a consistent frame identifier.
    - Else if input.hash_input is True: compute md5 for the incoming buffer and only update
      the shared image when the hash changes (avoids redundant work).
    - Else: always update the shared image (no hashing or change detection).
    """
    input_cfg = settings.get_input_settings()
    use_live_image = input_cfg.get("use_live_image", False)
    hash_input = input_cfg.get("hash_input", True)
    live_update = input_cfg.get("live_image_update", False)
    compute_hash_when_live = input_cfg.get("compute_hash_when_live_update", True)
    token_cfg = settings.get_token_settings()
    tokens_hidden = token_cfg.get("hide", False)

    if image_input is None or not use_live_image or tokens_hidden:
        return

    try:
        # Convert color channels
        if image_input.shape[2] == 4:
            image_input = image_input[:, :, [2, 1, 0, 3]]
        elif image_input.shape[2] == 3:
            image_input = image_input[:, :, [2, 1, 0]]

        # Create new surface
        new_surface = pygame.image.frombuffer(image_input.tobytes(),
                                              image_input.shape[1::-1], "RGBA")

        if live_update:
            # Force update every frame regardless of hash_input
            shared.shared_token_image = new_surface
            # Optionally compute hash for downstream consumers
            if compute_hash_when_live:
                try:
                    from time import time as _time
                    _t0 = _time()
                    import hashlib
                    shared.shared_token_image_hash = hashlib.md5(image_input.tobytes()).hexdigest()
                    # perf: hash computed
                    try:
                        if hasattr(shared, 'perf'):
                            shared.perf['image_hash_computed'] += 1
                            shared.perf['image_hash_ms'] += (_time() - _t0) * 1000.0
                    except Exception:
                        pass
                except Exception:
                    shared.shared_token_image_hash = None
            update_token_images(tokens, settings)
        elif hash_input:
            # When hash_input is True, only update if image has changed
            from time import time as _time
            _t0 = _time()
            import hashlib
            new_hash = hashlib.md5(image_input.tobytes()).hexdigest()
            try:
                if hasattr(shared, 'perf'):
                    shared.perf['image_hash_computed'] += 1
                    shared.perf['image_hash_ms'] += (_time() - _t0) * 1000.0
            except Exception:
                pass

            if new_hash != shared.shared_token_image_hash:
                shared.shared_token_image = new_surface
                shared.shared_token_image_hash = new_hash
                update_token_images(tokens, settings)
            else:
                # Hash prevented an unnecessary update
                try:
                    if hasattr(shared, 'perf'):
                        shared.perf['image_hash_prevented_updates'] += 1
                except Exception:
                    pass
        else:
            # When hash_input is False, always update the image
            shared.shared_token_image = new_surface
            update_token_images(tokens, settings)

    except Exception as e:
        print(f"Failed to convert image input to Pygame Surface: {e}")
        # logging.warning(f"Failed to convert image input to Pygame Surface: {e}")
        shared.shared_token_image = None


def update_simulation(tokens, respawner, surface, mouse_pos, mouse_velocity, settings, canvas_size, dt):
    """Main simulation update function that handles all per-frame updates"""
    # Clear surface
    surface.fill((0, 0, 0, 0))

    # Update all token states
    update_tokens(tokens, respawner, surface, mouse_pos, mouse_velocity, settings, canvas_size, dt)

    # Directly use the respawner which already has its token_factory
    respawn_tokens(respawner, respawner.token_factory, tokens)

    update_token_fades(tokens, settings, dt)


def update_shared_image_cache(tokens, settings):
    """
    If a new shared image was received from Isadora, this rescales it
    once per size and caches the result into each token for drawing.
    When input.live_image_update is True, tokens are refreshed every frame
    regardless of whether the hash changed.
    """
    input_cfg = settings.get_input_settings()
    use_live_image = input_cfg.get("use_live_image", False)
    live_update = input_cfg.get("live_image_update", False)
    token_cfg = settings.get_token_settings()
    tokens_hidden = token_cfg.get("hide", False)

    # Skip all image processing if tokens are hidden or live image is disabled
    if tokens_hidden or not use_live_image or not isinstance(shared.shared_token_image, pygame.Surface):
        return

    image_hash = shared.shared_token_image_hash
    cache = {}  # {(image_hash, size): scaled_image}

    # Instrumentation counters (local) to accumulate and then push once
    _rescales = 0
    _directs = 0
    _updated = 0

    for token in tokens:
        if token is None:
            continue

        key = (image_hash, token.size)

        # If live update is on, refresh every frame; otherwise only when hash changes
        if live_update or token._cached_image_hash != image_hash:
            if key not in cache:
                # Check if we need to scale the image
                if shared.shared_token_image.get_size() != token.size:
                    cache[key] = pygame.transform.smoothscale(shared.shared_token_image, token.size)
                    shared.debug("---> Smooth Scaled ---->")
                    _rescales += 1
                else:
                    cache[key] = shared.shared_token_image
                    shared.debug("---> Direct Copy (No Scale Needed) ---->")
                    _directs += 1

            token._cached_scaled_image = cache[key]
            token._cached_image_hash = image_hash
            _updated += 1

    # Flush instrumentation to shared perf
    try:
        if hasattr(shared, 'perf'):
            shared.perf['shared_image_rescales'] += _rescales
            shared.perf['shared_image_direct_copies'] += _directs
            shared.perf['shared_image_tokens_updated'] += _updated
    except Exception:
        pass


def respawn_tokens(respawner, token_factory, tokens):
    """
    Replaces dead tokens (marked by None) with new ones at home position.

    Args:
        respawner (RespawnManager): Tracks when each token can respawn
        token_factory (TokenFactory): Re-creates tokens from saved positions
        tokens (list): List of Token or None (modified in-place)
    """
    for index in respawner.update():
        # Clean up old token if it exists
        if index < len(tokens) and tokens[index] is not None:
            tokens[index].cleanup()

        # Determine home position safely
        if hasattr(token_factory, 'token_positions') and index < len(token_factory.token_positions):
            home_pos = token_factory.token_positions[index]
        else:
            # Fallback: center of canvas
            canvas_w = int(respawner.settings.get_init_canvas_size()[0]) if hasattr(respawner.settings, 'get_init_canvas_size') else 0
            canvas_h = int(respawner.settings.get_init_canvas_size()[1]) if hasattr(respawner.settings, 'get_init_canvas_size') else 0
            home_pos = (canvas_w // 2, canvas_h // 2)

        # Create new token at its home position
        new_token = token_factory.create_token_at_home(home_pos)

        # Get spawn behavior from settings
        token_cfg = respawner.settings.get_token_settings()
        spawn_behaviors = token_cfg.get("spawn_behavior", ["fade_in"])

        # Set initial opacity based on spawn behavior
        if "instant_in" in spawn_behaviors:
            new_token.opacity = 255
            new_token.fade_timer = 0
        else:  # Default to fade_in behavior
            new_token.opacity = 0
            new_token.fade_timer = 0

        # Reset respawn timer
        new_token.time_since_respawn = 0.0

        # Ensure texture is properly initialized
        if new_token.texture_id is None:
            new_token._initialize_texture()
        new_token._update_texture(respawner.settings)

        tokens[index] = new_token


def update_token_fades(tokens, settings, dt):
    """
    Updates opacity for tokens that are fading in based on their fade timers.
    Handles fade-in, fade-out, and bounce effects based on configured behaviors.
    """
    token_cfg = settings.get_token_settings()
    spawn_behaviors = token_cfg.get("spawn_behavior", ["fade_in"])
    
    # Skip fade updates if using instant_in
    if "instant_in" in spawn_behaviors:
        return
        
    animation = settings.runtime_settings.get("animation", {})
    fade_duration_sec = animation.get("fade_in_duration_ms", 300) / 1000.0  # Convert ms to seconds

    for token in tokens:
        if token is not None:
            if token.opacity < 255:  # Only update fading tokens
                token.fade_timer += dt
                progress = min(1.0, token.fade_timer / fade_duration_sec)
                new_opacity = int(255 * progress)
                token.opacity = new_opacity


def update_token_images(tokens, settings):
    """
    Updates the images of tokens based on the provided settings.

    This function modifies the `_cached_scaled_image` attribute of each token in
    the provided list of tokens. If the `use_live_image` setting is enabled and
    the shared `shared_token_image` is a valid `pygame.Surface`, the function
    assigns this shared image to each token's `_cached_scaled_image`.

    :param tokens: A list of token objects to update. Each token should have a
        `_cached_scaled_image` attribute to update.
    :type tokens: list
    :param settings: The settings object that provides configuration for updating
        token images. It must have a `get_input_settings` method that returns a
        dictionary-like object containing the "use_live_image" key.
    :type settings: object
    :return: None
    :rtype: None
    """
    if not tokens:
        return

    input_cfg = settings.get_input_settings()
    use_live_image = input_cfg.get("use_live_image", False)

    if use_live_image and isinstance(shared.shared_token_image, pygame.Surface):
        for token in tokens:
            if token is not None:
                token._cached_scaled_image = shared.shared_token_image


def draw_mouse_radius(surface, mouse_pos, settings):
    """
    Optionally draws a circle showing the range of mouse influence.

    Args:
        surface (pygame.Surface): Drawing surface
        mouse_pos (pygame.Vector2): Center of the radius
        settings (SettingsManager): Visual toggles and radius config
    """
    visuals = settings.get_visual_elements()
    mouse_radius = visuals.get("mouse_radius", {})

    if isinstance(mouse_radius, dict) and mouse_radius.get("enabled", False):
        color = mouse_radius.get("color", [200, 200, 0])
        thickness = int(mouse_radius.get("thickness", 1))
        radius = settings.get_mouse_force_settings().get("max_distance", 50)
        pygame.draw.circle(surface, color, mouse_pos, radius, thickness)

    elif mouse_radius is True:  # Legacy support: mouse_radius: true
        radius = settings.get_mouse_force_settings().get("max_distance", 50)
        pygame.draw.circle(surface, (200, 200, 0), mouse_pos, radius, 1)