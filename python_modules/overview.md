
# Technical Implementation Details
This technical documentation focuses on implementation details, data flows, and system relationships that would be valuable for developers working with the codebase.

## Core Architecture

### Token Lifecycle Management
1. Creation Pipeline:
   - TokenFactory creates tokens via grid layout algorithm
   - Each token initialized with position, size, and facing direction
   - Optional custom token class injection via TokenSimulation constructor

2. Update Cycle:
   - Time delta calculation for physics (dt = current_time - last_update_time)
   - Mouse position/velocity processing (Vector2 based)
   - Image input processing (optional numpy array)
   - Token state updates (position, rotation, scale)
   - Visual state updates (surface generation)
   - OpenGL render pass (texture updates)

3. Destruction/Respawn:
   - RespawnManager tracks dead tokens in queue
   - Configurable delay before respawn (default 1.5s)
   - Home position preservation (grid-based)
   - State reset on respawn (velocity, rotation, scale)

### Component Relationships

#### TokenSimulation (Controller)
- Manages simulation lifecycle and resources
- Holds main token collection (List[Token])
- Coordinates subsystems:
  - TokenFactory (creation)
  - RespawnManager (lifecycle)
  - SettingsManager (configuration)
- Handles rendering pipeline (pygame/OpenGL)
- Manages Spout integration (SpoutGL sender)

#### Token (Entity)
Core Properties:
- Position: pygame.Vector2
- Velocity: pygame.Vector2
- Home position: tuple(float, float)
- Visual state: 
  - rotation: float (degrees)
  - scale: float (1.0 = normal)
  - opacity: int (0-255)
- Collision bounds: Circle(radius) or Rect(w,h)
- Debug visualization state: dict[str, bool]

Behaviors:
1. Physics:
   - Velocity-based movement (pos += vel * dt)
   - Force accumulation (vel += force * dt)
   - Collision response (elastic/inelastic)
   - Boundary handling (bounce or off-screen death; no wrap)

2. Flocking:
   - Neighbor detection (radius-based)
   - Rule application:
     - Alignment (avg velocity)
     - Cohesion (avg position)
     - Separation (inverse square)
   - Force combination (weighted sum)

3. Mouse Interaction:
   - Distance-based force calculation (1/r or 1/r²)
   - Configurable falloff (linear, inverse, quadratic, smoothstep)
   - Optional facing behavior (lookAt)

#### Settings System
For the complete, authoritative list of configuration keys and their behaviors, see python_modules/CONFIGURATION.md. Key sections:
- init_canvas, init_token (initialization-only)
- tokens (collision, flocking, home-seeking, behaviors, orientation)
- mouse_force (enabled, max_distance, force_strength, falloff)
- physics (bounce_factor)
- timing (fade/respawn timings)
- input (live image usage and hashing)
- output (Spout/NumPy orientation toggles)
- visual_elements (per-element enabled/color/thickness)

## Data Flow

### Main Update Loop
Mouse/Image Input → Physics Engine → State Manager → Visual System → Renderer ↓ ↓ ↓ ↓ ↓ Vector2 pos Force Updates Life Cycle Surface Gen OpenGL Vector2 vel Collisions Respawning Debug Draw Spout numpy array Flocking Config Animation Texture

### Token State Machine
[Created] ────→ [Active] ←──────────────────┐ ↓ ↓ │ │ [Death Event] │ │ ↓ │ │ [Dead State] ────→ [Respawning]┘ │ ↓ └─────── [Destroyed]
States affected by:
- Collision events
- Boundary conditions
- Configuration changes
- Resource management
## Performance Considerations

### Collision Detection
- Spatial partitioning (grid-based)
  ```python
  grid_size = max(token_radius * 2)
  grid_pos = (token.x // grid_size, token.y // grid_size)
  ```
- Circle collision optimization
  ```python
  dist_sq = (dx * dx + dy * dy)  # Avoid sqrt
  if dist_sq < (r1 + r2) * (r1 + r2):
      # Collision detected
  ```
- Early-out checks
  ```python
  if abs(dx) > max_radius or abs(dy) > max_radius:
      return False  # No collision possible
  ```

### Rendering Pipeline
- Surface reuse for memory efficiency
  ```python
  if not self._surface:
      self._surface = pygame.Surface(size, pygame.SRCALPHA)
  else:
      self._surface.fill((0,0,0,0))
  ```
- Texture management
  ```python
  glGenTextures(1)
  glBindTexture(GL_TEXTURE_2D, texture_id)
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
  ```
- Spout integration considerations
  - Texture format compatibility
  - Flip correction for OpenGL
  - Buffer synchronization

### Memory Management
- Token pooling strategies
  ```python
  class TokenPool:
      def __init__(self, max_size):
          self._available = []
          self._active = set()
  ```
- Surface caching with LRU
- Resource cleanup patterns
  ```python
  def cleanup(self):
      self.surface = None
      self.spout_sender.ReleaseSender()
      pygame.quit()
  ```

## Extension Points

### Custom Token Implementation
python class CustomToken(Token): def generate_image(self) -> pygame.Surface: # Custom visualization

def update_physics(self, dt: float) -> None:
    # Custom physics

def process_collision(self, other: Token) -> None:
    # Custom collision response

def apply_forces(self, forces: List[Vector2]) -> None:
    # Custom force handling

### Behavior Modification
- Settings injection points
- Runtime configuration hooks
- Custom force implementations
- Event system integration

### Visual Customization
- Debug overlay system
  - Vector visualization
  - State indicators
  - Performance metrics
- Custom rendering pipeline
- Texture management system

## Threading Model
- Main thread: OpenGL context, rendering
- Physics thread (optional): 
  - Collision detection
  - Force calculations
- Resource thread:
  - Texture loading
  - Configuration updates
