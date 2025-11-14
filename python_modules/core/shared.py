# core/shared.py
import os
import json
from core.debug import debug, DebugManager


# Initialize debug settings
def init_debug(enable=True, categories=None, config_json: str | None = None):
    """Initialize debug settings globally.

    Precedence to decide enable/disable:
    1) If config_json (string) is provided and contains debug.debug_manager, use it.
    2) Else, try to read python_modules\\config.json and use debug.debug_manager if present.
    3) Else, fall back to the `enable` argument.

    Categories parameter is passed through when enabling.
    """
    desired_enable = enable

    # Try explicit JSON string first
    try:
        cfg_obj = None
        if isinstance(config_json, (str, bytes)) and len(config_json) > 0:
            cfg_obj = json.loads(config_json)
        else:
            # Attempt to read ../config.json relative to this file
            base_dir = os.path.dirname(__file__)  # .../python_modules/core
            cfg_path = os.path.normpath(os.path.join(base_dir, os.pardir, 'config.json'))
            if os.path.isfile(cfg_path):
                with open(cfg_path, 'r') as f:
                    cfg_obj = json.load(f)
        if isinstance(cfg_obj, dict):
            dbg = cfg_obj.get('debug', {}) if isinstance(cfg_obj.get('debug', {}), dict) else {}
            if 'debug_manager' in dbg:
                desired_enable = bool(dbg.get('debug_manager'))
    except Exception:
        # On any error, keep the fallback `enable` value
        pass

    if desired_enable:
        DebugManager.enable(categories)
        try:
            debug(f"DebugManager enabled (categories={categories})", category="config")
        except Exception:
            pass
    else:
        DebugManager.disable()
        try:
            debug("DebugManager disabled via config", category="config")
        except Exception:
            pass


# Export debug function and manager for easy access
__all__ = ['debug', 'DebugManager', 'init_debug']

# Simple per-frame performance stats container
perf = {
    'begin_frame_ms': 0.0,
    'process_image_input_ms': 0.0,
    'update_simulation_ms': 0.0,
    'render_tokens_ms': 0.0,
    'rendered_tokens': 0,
    'mouse_radius_ms': 0.0,
    'debug_overlay_ms': 0.0,
    'debug_overlay_upload_ms': 0.0,
    'end_frame_ms': 0.0,
    'tex_uploads': 0,
    'tex_upload_ms': 0.0,
    'overlay_uploads': 0,
    # Token graphics instrumentation
    'token_generate_image_calls': 0,
    'token_get_base_image_calls': 0,
    'token_base_from_live': 0,
    'token_base_generated': 0,
    'shared_image_rescales': 0,
    'shared_image_direct_copies': 0,
    'shared_image_tokens_updated': 0,
    # Hashing instrumentation
    'image_hash_computed': 0,
    'image_hash_ms': 0.0,
    'image_hash_prevented_updates': 0,
}

def reset_perf():
    try:
        for k in perf.keys():
            if isinstance(perf[k], (int, float)):
                perf[k] = 0 if isinstance(perf[k], int) else 0.0
        # Keep rendered_tokens and counts as ints, already reset above
    except Exception:
        pass


# This shared variable is used to store the dynamic image input
# provided by Pythoner (e.g., from Isadora). It is accessed by
# all Token objects during their draw() routines.

shared_token_image = None

# This tracks a hash of the last used image to avoid unnecessary updates
shared_token_image_hash = None



# Shared globals for runtime communication between modules
# (Keeps lightweight cross-module state like debug surfaces and panel rects)

# These may be set during simulation init
debug_surface = None
shared_token_image = None
shared_token_image_hash = None

# Optional rectangle (x, y, w, h) designating where to draw a translucent
# stats background panel in the GL composite pass
stats_panel_rect = None

# Last config audit report for overlay use
last_config_audit = None
last_config_audit_time = None
