
from collections import defaultdict
import pygame
from typing import List, Dict, Tuple, Set, Optional

class SpatialGrid:
    """Manages a grid-based spatial partitioning system for efficient neighbor queries"""
    
    def __init__(self, cell_size: float):
        """
        Initialize the spatial grid
        
        Args:
            cell_size: Size of each grid cell (should be >= largest token diameter)
        """
        self.cell_size = cell_size
        self.grid: Dict[Tuple[int, int], List] = defaultdict(list)
        
    def _get_cell_coords(self, position: pygame.Vector2) -> Tuple[int, int]:
        """Convert a world position to grid cell coordinates"""
        return (int(position.x // self.cell_size), 
                int(position.y // self.cell_size))
    
    def _get_neighbor_cells(self, cell: Tuple[int, int]) -> List[Tuple[int, int]]:
        """Get coordinates of this cell and all adjacent cells"""
        x, y = cell
        return [(x + dx, y + dy) for dx in (-1, 0, 1) 
                                for dy in (-1, 0, 1)]
    
    def clear(self):
        """Remove all entries from the grid"""
        self.grid.clear()
    
    def insert(self, token) -> None:
        """Add a token to the appropriate grid cell"""
        if token is None:
            return
            
        cell = self._get_cell_coords(token.position)
        self.grid[cell].append(token)
    
    def update(self, tokens: List) -> None:
        """Update entire grid with new token positions"""
        self.clear()
        for token in tokens:
            self.insert(token)
    
    def get_nearby_tokens(self, position: pygame.Vector2, radius: float) -> Set:
        """
        Get all tokens that could potentially interact with a position
        
        Args:
            position: Center point to check from
            radius: Maximum distance to check
            
        Returns:
            Set of tokens within the specified radius
        """
        # Convert position to cell coordinates
        center_cell = self._get_cell_coords(position)
        
        # Calculate how many cells we need to check based on radius
        cells_to_check = max(1, int(radius // self.cell_size) + 1)
        
        # Get all tokens in nearby cells
        nearby_tokens = set()
        for dx in range(-cells_to_check, cells_to_check + 1):
            for dy in range(-cells_to_check, cells_to_check + 1):
                cell = (center_cell[0] + dx, center_cell[1] + dy)
                nearby_tokens.update(self.grid[cell])
        
        return nearby_tokens
    
    def get_potential_collisions(self, token) -> Set:
        """
        Get all tokens that could potentially collide with the given token
        
        Args:
            token: Token to check collisions for
            
        Returns:
            Set of tokens that might be colliding
        """
        if token is None:
            return set()
            
        # Get tokens in this cell and adjacent cells
        cell = self._get_cell_coords(token.position)
        neighbor_cells = self._get_neighbor_cells(cell)
        
        # Collect all tokens in these cells
        nearby_tokens = set()
        for neighbor_cell in neighbor_cells:
            nearby_tokens.update(self.grid[neighbor_cell])
        
        # Remove self from results
        nearby_tokens.discard(token)
        return nearby_tokens