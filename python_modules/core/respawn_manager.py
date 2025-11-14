import time

from core.debug import debug, DebugManager


class RespawnManager:
    def __init__(self, respawn_delay_sec=1.0, token_factory=None, settings=None):
        self.respawn_delay_sec = respawn_delay_sec
        self.respawn_queue = {}  # {index: death_time}
        self.token_factory = token_factory
        self.settings = settings

    def schedule_respawn(self, index):
        """Schedule a token for respawning after the delay."""
        self.respawn_queue[index] = time.time()

    def update(self):
        """Check for tokens that are ready to respawn."""
        current_time = time.time()
        ready_indices = []

        # Find indices ready to respawn
        for index, death_time in list(self.respawn_queue.items()):
            if current_time - death_time >= self.respawn_delay_sec:
                ready_indices.append(index)
                del self.respawn_queue[index]

        return ready_indices

    def set_token_factory(self, factory):
        """Set the token factory to use for respawning."""
        self.token_factory = factory

    def set_settings(self, settings):
        """Set the settings to use for respawning."""
        self.settings = settings



# import time
#
# class RespawnManager:
#     def __init__(self, respawn_delay_sec=1.0, token_factory=None):
#         self.respawn_delay_sec = respawn_delay_sec
#         self.respawn_queue = {}  # {index: death_time}
#         self.token_factory = token_factory
#
#     def schedule_respawn(self, index):
#         """Schedule a token for respawning after the delay."""
#         self.respawn_queue[index] = time.time()
#
#     def update(self):
#         """Check for tokens that are ready to respawn."""
#         current_time = time.time()
#         ready_indices = []
#
#         # Find indices ready to respawn
#         for index, death_time in list(self.respawn_queue.items()):
#             if current_time - death_time >= self.respawn_delay_sec:
#                 ready_indices.append(index)
#                 del self.respawn_queue[index]
#
#         return ready_indices
#
#     def set_token_factory(self, factory):
#         """Set the token factory to use for respawning."""
#         self.token_factory = factory