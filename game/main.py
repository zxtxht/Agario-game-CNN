import pygame
import random
import math
import os
import time
import numpy as np
from collections import deque
from PIL import Image
import asyncio

# Try to import onnxruntime - will work if available
try:
    import onnxruntime as ort
except ImportError:
    try:
        # Try alternative import name
        import onnxruntime_web as ort
    except ImportError:
        print("WARNING: onnxruntime not available. AI models will not work.")
        ort = None  

class Config:
    SCREEN_WIDTH = 1600
    SCREEN_HEIGHT = 1200
    BACKGROUND_COLOR = (10, 10, 10) 
    FOOD_COLOR = (0, 255, 0)
    PLAYER_COLOR = (0, 191, 255) 
    CPU_COLOR = (255, 0, 0)
    FONT_COLOR = (224, 224, 224)
    VIRUS_COLOR = (0, 255, 127) 
    MASS_COLOR = (200, 200, 200)
    NUM_FOOD = 850
    NUM_CPU = 14
    NUM_VIRUSES = 14
    PLAYER_START_RADIUS = 5
    CPU_START_RADIUS = 4
    FOOD_RADIUS = 3
    VIRUS_RADIUS = 11
    SHOOT_MASS_RADIUS = 2
    BASE_SPEED = 2.0
    MAX_SPEED = 8.0
    DOMINANCE_ABS_SIZE = 250**2
    DOMINANCE_REL_SIZE = 2.2
    DOMINANCE_REWARD = 300.0
    DOMINANCE_PENALTY = -155.0
    MAX_EPISODE_FRAMES = 3600
    OBS_SIZE = 84
    FRAME_STACK = 4
    FRAME_SKIP = 1
    EXPLORATION_ANNEAL_FRAMES = 50000 
    DISTANCE_REWARD_SCALER = 0.005
    DIRECTION_CHANGE_REWARD_SCALER = 0.015
    STAGNATION_PENALTY_SCALER = 0.005
    SHAPED_REWARD_ANNEAL_FRAMES = 1_000_000
    AI_AGGRESSOR_COLOR = (255, 128, 0) 
    AI_FARMER_COLOR = (128, 0, 128)    
    AI_SURVIVOR_COLOR = (0, 128, 255)    
   





  


cfg = Config()

class SpatialHashGrid:
    """
    A robust spatial hash grid for optimizing collision detection.
    This version correctly handles objects spanning multiple cells.
    """
    def __init__(self, width, height, cell_size):
        self.width = width
        self.height = height
        self.cell_size = cell_size
        self.grid_width = math.ceil(width / cell_size)
        self.grid_height = math.ceil(height / cell_size)
        self.grid = [[] for _ in range(self.grid_width * self.grid_height)]

    def _hash(self, x, y):
        """Hashes a grid cell coordinate to a 1D list index."""
        return x + y * self.grid_width

    def clear(self):
        """Clears the grid for the next frame."""
        for cell in self.grid:
            cell.clear()

    def insert(self, obj, obj_data):
        """
        Inserts an object into all grid cells it overlaps with. obj_data is a
        dictionary to store extra info like the owner or object type.
        """
        min_x = max(0, int((obj.x - obj.radius) / self.cell_size))
        max_x = min(self.grid_width - 1, int((obj.x + obj.radius) / self.cell_size))
        min_y = max(0, int((obj.y - obj.radius) / self.cell_size))
        max_y = min(self.grid_height - 1, int((obj.y + obj.radius) / self.cell_size))

        for y in range(min_y, max_y + 1):
            for x in range(min_x, max_x + 1):
                cell_index = self._hash(x, y)
                self.grid[cell_index].append((obj, obj_data))

# --- In Block 2, inside the SpatialHashGrid class, REPLACE this one method ---

    def get_nearby(self, obj):
        """
        Gets all potential colliders. This returns a list of (object, obj_data)
        tuples. It uses a helper set of object IDs to ensure uniqueness efficiently.
        """
        # --- START OF THE FIX ---
        nearby_items_list = []
        seen_obj_ids = set()

        # Get the cell range the object covers
        min_x = max(0, int((obj.x - obj.radius) / self.cell_size))
        max_x = min(self.grid_width - 1, int((obj.x + obj.radius) / self.cell_size))
        min_y = max(0, int((obj.y - obj.radius) / self.cell_size))
        max_y = min(self.grid_height - 1, int((obj.y + obj.radius) / self.cell_size))

        # Query all cells the object is in
        for y in range(min_y, max_y + 1):
            for x in range(min_x, max_x + 1):
                cell_index = self._hash(x, y)
                for item_tuple in self.grid[cell_index]:
                    # The object is the first element in the stored tuple
                    colliding_obj = item_tuple[0]
                    # Use the object's unique id() for the fast 'seen' check
                    if id(colliding_obj) not in seen_obj_ids:
                        seen_obj_ids.add(id(colliding_obj))
                        nearby_items_list.append(item_tuple)
        
        return nearby_items_list


class Blob:
    def __init__(self, x, y, radius, color):
        self.x, self.y, self.radius, self.color = x, y, radius, color
        self.dx, self.dy = 0, 0
        self.merge_timer = 0
    def draw(self, screen, name="", override_color=None):
        draw_color = override_color if override_color is not None else self.color
        pygame.draw.circle(screen, draw_color, (int(self.x), int(self.y)), int(self.radius))
        if name:
            font = pygame.font.SysFont(None, int(self.radius / 1.5))
            text = font.render(name, True, cfg.FONT_COLOR)
            screen.blit(text, text.get_rect(center=(int(self.x), int(self.y))))
    def move(self):
        self.x = max(self.radius, min(self.x + self.dx, cfg.SCREEN_WIDTH - self.radius))
        self.y = max(self.radius, min(self.y + self.dy, cfg.SCREEN_HEIGHT - self.radius))
        self.dx *= 0.98; self.dy *= 0.98
    def collides_with(self, other):
        return math.hypot(self.x - other.x, self.y - other.y) < self.radius + other.radius

class Virus(Blob):
    def __init__(self, x, y):
        super().__init__(x, y, cfg.VIRUS_RADIUS, cfg.VIRUS_COLOR)

class Mass(Blob):
    def __init__(self, x, y, dx, dy):
        super().__init__(x, y, cfg.SHOOT_MASS_RADIUS, cfg.MASS_COLOR)
        self.dx, self.dy = dx, dy
        self.decay_timer = 180
    def move(self):
        self.x += self.dx; self.y += self.dy
        self.dx *= 0.95; self.dy *= 0.95
        self.decay_timer -= 1

class PlayerController:
    def __init__(self, name, color, start_radius, ai_model=None,is_human=False):
        self.name, self.color, self.start_radius = name, color, start_radius
        self.is_human = is_human
        self.ai_model = ai_model
        self.frame_stack = deque(maxlen=cfg.FRAME_STACK) if self.ai_model else None
        self.blobs = []; self.respawn()
        self.state = 'wandering'; self.target = None; self.flee_from = None
        self.wander_target = None; self.vision_range = 300
        self.state_timer = 0  # ADD THIS LINE
        self.decision_cooldown = 30 # ADD THIS LINE (30 frames = 0.5 sec)
        self.lead_blob = None
    @property
    def mass(self): return sum(b.radius**2 for b in self.blobs) if self.blobs else 0
   
    @property
    def center_x(self):
        # If the lead blob exists and is still part of our blobs, use its position.
        if self.lead_blob and self.lead_blob in self.blobs:
            return self.lead_blob.x
        # Fallback logic if there's no lead blob
        return sum(b.x * b.radius for b in self.blobs) / sum(b.radius for b in self.blobs) if self.blobs else 0

    @property
    def center_y(self):
        # If the lead blob exists and is still part of our blobs, use its position.
        if self.lead_blob and self.lead_blob in self.blobs:
            return self.lead_blob.y
        # Fallback logic if there's no lead blob
        return sum(b.y * b.radius for b in self.blobs) / sum(b.radius for b in self.blobs) if self.blobs else 0
    @property
    def total_radius(self):
        return math.sqrt(sum(b.radius**2 for b in self.blobs))

    def respawn(self):
        self.blobs = [Blob(random.randint(0, cfg.SCREEN_WIDTH), random.randint(0, cfg.SCREEN_HEIGHT), self.start_radius, self.color)]
        self.lead_blob = self.blobs[0] # ADD THIS LINE
                        



    def decide_cpu_state(self, all_controllers, food_list, virus_list):
        if not self.blobs: return
    
        if self.state_timer > 0:
            self.state_timer -= 1
            return
            
        current_radius = self.total_radius

        if current_radius < 20:
            vision_multiplier = 6.0
        elif current_radius > 20:
            vision_multiplier = 5.0
        else:
            # Linear interpolation between (15, 8x) and (25, 5x)
            vision_multiplier = 5.5
        dynamic_vision_range = current_radius * vision_multiplier

        self.target, self.flee_from = None, None
        all_other_blobs = [b for c in all_controllers if c is not self for b in c.blobs]
        threats = [b for b in all_other_blobs if math.hypot(self.center_x - b.x, self.center_y - b.y) < dynamic_vision_range and b.radius > self.total_radius * 1.15]
        largest_blob_radius = max(b.radius for b in self.blobs) if self.blobs else 0
        prey = [b for b in all_other_blobs if math.hypot(self.center_x - b.x, self.center_y - b.y) < dynamic_vision_range and largest_blob_radius > b.radius * 1.15]
    
        new_state = 'wandering'
    
        if threats:
            new_state = 'fleeing'
            self.flee_from = min(threats, key=lambda t: math.hypot(self.center_x - t.x, self.center_y - t.y))
        elif prey:
            new_state = 'hunting'
            self.target = max(prey, key=lambda p: p.radius)
            blocking_virus = self.find_blocking_virus(virus_list)
            if blocking_virus:
                new_state = 'clearing_virus'
                self.target = blocking_virus
        elif [f for f in food_list if math.hypot(self.center_x - f.x, self.center_y - f.y) < dynamic_vision_range]: # Also use it here
            new_state = 'hunting'
            self.target = min([f for f in food_list if math.hypot(self.center_x - f.x, self.center_y - f.y) < dynamic_vision_range], key=lambda f: math.hypot(self.center_x - f.x, self.center_y - f.y))
    
        if self.state != new_state:
            self.state = new_state
            self.state_timer = self.decision_cooldown
            
    def update(self, all_controllers, mass_list, mouse_pos=None, ai_action=None):
        if not self.blobs: return
        target_pos = None
    
        if self.is_human and mouse_pos:
            target_pos = mouse_pos
            self.target = Blob(target_pos[0], target_pos[1], 1, (0,0,0)) # Dummy target for aiming
    
        elif self.ai_model and ai_action is not None:
            move_action = ai_action['move']; special_action = ai_action['special']
            raw_target_x = self.center_x + move_action[0] * 500
            raw_target_y = self.center_y + move_action[1] * 500
            buffer = self.blobs[0].radius if self.blobs else 20
            target_pos = (max(buffer, min(raw_target_x, cfg.SCREEN_WIDTH - buffer)), max(buffer, min(raw_target_y, cfg.SCREEN_HEIGHT - buffer)))
            self.target = Blob(target_pos[0], target_pos[1], 1, (0,0,0))
            if special_action == 1 and random.random() < 0.60: self.shoot_mass(mass_list)
            if special_action == 2 and random.random() < 0.05: self.split()
    
        elif not self.is_human and not self.ai_model:
            if self.state == 'fleeing' and self.flee_from:
                angle = math.atan2(self.center_y - self.flee_from.y, self.center_x - self.flee_from.x)
                target_pos = (self.center_x + math.cos(angle) * 500, self.center_y + math.sin(angle) * 500)
            elif self.state == 'hunting' and self.target:
                target_pos = (self.target.x, self.target.y)
            elif self.state == 'clearing_virus' and self.target:
                target_pos = (self.target.x, self.target.y)
            elif self.state == 'wandering':
                if self.wander_target is None or math.hypot(self.center_x - self.wander_target[0], self.center_y - self.wander_target[1]) < 50:
                    self.wander_target = (random.randint(50, cfg.SCREEN_WIDTH - 50), random.randint(50, cfg.SCREEN_HEIGHT - 50))
                target_pos = self.wander_target

        for blob in self.blobs:
            if target_pos:
                angle = math.atan2(target_pos[1] - blob.y, target_pos[0] - blob.x)
                speed = max(cfg.BASE_SPEED, cfg.MAX_SPEED - (blob.radius / 50))
                target_dx = math.cos(angle) * speed
                target_dy = math.sin(angle) * speed
                lerp_factor = 0.15
                blob.dx = blob.dx * (1 - lerp_factor) + target_dx * lerp_factor
                blob.dy = blob.dy * (1 - lerp_factor) + target_dy * lerp_factor
            blob.move()
            if blob.merge_timer > 0: blob.merge_timer -= 1
        self.merge_blobs()
    def merge_blobs(self):
        if len(self.blobs) > 1:
            center_x = self.center_x
            center_y = self.center_y
            pull_strength = 0.18 
        
            for blob in self.blobs:
                dist_x = center_x - blob.x
                dist_y = center_y - blob.y
                dist = math.hypot(dist_x, dist_y)
                if dist > 1:
                    blob.dx += (dist_x / dist) * pull_strength
                    blob.dy += (dist_y / dist) * pull_strength
        
        # Part 2: Original Merge Logic (The "Fuse")
        mergable = [b for b in self.blobs if b.merge_timer <= 0]
        if len(mergable) < 2: return
        
        merged = True
        while merged:
            merged = False
            for i in range(len(mergable)):
                for j in range(i + 1, len(mergable)):
                    b1, b2 = mergable[i], mergable[j]
                    if b1 in self.blobs and b2 in self.blobs and b1.collides_with(b2):
                        larger, smaller = (b1, b2) if b1.radius > b2.radius else (b2, b1)
                        if smaller == self.lead_blob:
                            self.lead_blob = larger
                        new_mass = larger.radius**2 + smaller.radius**2
                        larger.radius = math.sqrt(new_mass)
                        self.blobs.remove(smaller)
                        mergable.remove(smaller)
                        merged = True
                        break
                if merged: break
# ADD THIS REPLACEMENT METHOD
    def split(self):
        """Splits all blobs that are large enough, creating them at an offset to prevent overlap."""
        if len(self.blobs) >= 8: return 
    
        
        for blob in self.blobs[:]:
            if blob.radius > 14: 
                self.blobs.remove(blob)
                new_radius = math.sqrt(blob.radius**2 / 2)
    
                
                if blob.dx == 0 and blob.dy == 0:
                    base_angle = random.uniform(0, 2 * math.pi)
                else:
                    base_angle = math.atan2(blob.dy, blob.dx)

                for i in range(2):
                    # The first blob goes forward (angle), the second goes backward (angle + 180 deg).
                    split_angle = base_angle + (i * math.pi)
    
                    # It is placed just outside the original blob's radius.
                    offset_x = blob.x + (new_radius) * math.cos(split_angle)
                    offset_y = blob.y + (new_radius) * math.sin(split_angle)
    
                    new_blob = Blob(offset_x, offset_y, new_radius, self.color)
    
                    # 5. Propel the new blob in the same direction as its offset.
                    new_blob.dx = math.cos(split_angle) * 18
                    new_blob.dy = math.sin(split_angle) * 18
                    new_blob.merge_timer = 90 # Set the cooldown before they can merge again
                    
                    self.blobs.append(new_blob)
                    if i == 0:
                        self.lead_blob = new_blob
    def shoot_mass(self, mass_list):
        """Ejects mass from the largest blob."""
        if not self.blobs or not self.target: return

        largest_blob = max(self.blobs, key=lambda b: b.radius)
        if largest_blob.radius > 16: # Must be big enough to shoot
            # Lose mass from the shooter
            new_radius_squared = largest_blob.radius**2 - cfg.SHOOT_MASS_RADIUS**2
            if new_radius_squared < cfg.CPU_START_RADIUS**2: return # Don't shoot if it makes you too small
            largest_blob.radius = math.sqrt(new_radius_squared)

            # Eject in the direction of the current target
            angle = math.atan2(self.target.y - largest_blob.y, self.target.x - largest_blob.x)
            mass_list.append(Mass(
                largest_blob.x, largest_blob.y,
                math.cos(angle) * 25, math.sin(angle) * 25
            ))
    # --- ADD THIS CODE BLOCK ---
    def is_split_safe(self, all_controllers):
        """Predicts if a split would result in an immediate loss."""
        if not self.target: return False

        # Calculate where the new blob would go
        angle = math.atan2(self.target.y - self.center_y, self.target.x - self.center_x)
        split_dist = 7 * self.blobs[0].radius # Approximate split distance
        projected_x = self.center_x + math.cos(angle) * split_dist
        projected_y = self.center_y + math.sin(angle) * split_dist
        projected_radius = math.sqrt(self.blobs[0].radius**2 / 2)

        # Check if that projected position is near a larger threat
        for controller in all_controllers:
            if controller is self: continue
            for enemy_blob in controller.blobs:
                if enemy_blob.radius > projected_radius * 1.15:
                    dist = math.hypot(projected_x - enemy_blob.x, projected_y - enemy_blob.y)
                    if dist < enemy_blob.radius:
                        return False # Split is not safe
        return True # No immediate threats found

# In the PlayerController class:

    def find_blocking_virus(self, virus_list):
        """
        Checks if a virus is geometrically between the player and the target
        using accurate vector projection.
        """
        if not self.target or not self.blobs:
            return None

        # Define the line segment from the player's primary blob to the target
        p_x, p_y = self.blobs[0].x, self.blobs[0].y
        t_x, t_y = self.target.x, self.target.y

        # Create the vector representing the path to the target
        path_vec_x, path_vec_y = t_x - p_x, t_y - p_y
        path_length_sq = path_vec_x**2 + path_vec_y**2

        # If the player is already on the target, no virus can be blocking
        if path_length_sq == 0:
            return None

        for virus in virus_list:
            # Create the vector from the player to the virus
            virus_vec_x, virus_vec_y = virus.x - p_x, virus.y - p_y

            # Calculate the dot product to find the projection of the virus vector
            # onto the path vector. This tells us how far "along the path" the virus is.
            dot_product = virus_vec_x * path_vec_x + virus_vec_y * path_vec_y

            # If the projection is negative, the virus is behind the player.
            # If the projection is greater than the path's length, the virus is beyond the target.
            # In either case, it is not "between" them.
            if dot_product < 0 or dot_product > path_length_sq:
                continue

            # Find the closest point on the infinite line of the path to the virus center
            closest_point_on_line_x = p_x + (dot_product / path_length_sq) * path_vec_x
            closest_point_on_line_y = p_y + (dot_product / path_length_sq) * path_vec_y

            # Calculate the distance from the virus center to that closest point on the path.
            # This is the perpendicular distance from the virus to the player's line of sight.
            distance_to_path = math.hypot(virus.x - closest_point_on_line_x, virus.y - closest_point_on_line_y)

            # If the perpendicular distance is less than the combined radii of the virus
            # and the player's blob, it is a blocker. We add a small buffer.
            if distance_to_path < (virus.radius + self.blobs[0].radius):
                return virus # This virus is blocking the path.

        return None # No blocking viruses found


class Game:
    def __init__(self):
        pygame.init(); pygame.font.init()
        # pygame-ce in PyScript will automatically create a canvas
        self.screen = pygame.display.set_mode((cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT))
        pygame.display.set_caption("Agar AI")
        self.clock = pygame.time.Clock()
        self.grid = SpatialHashGrid(cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT, cell_size=200)

        os.environ["PYGAME_ASYNC_EVENT"] = "0"
        self.ai_models = self._load_ai_models()

        self.player = None; self.all_controllers = []; self.food_list = []
        self.virus_list = []; self.mass_list = []
        
        self.reset_game()

    def _load_ai_models(self):
        models = {}
        if ort is None:
            print("--- WARNING: onnxruntime not available. AI models disabled. ---")
            return models
        
        model_paths = { "aggressor": "aggressor.onnx", "farmer": "farmer.onnx", "survivor": "survivor.onnx" }
        print("--- Loading AI Models ---")
        for name, path in model_paths.items():
            try:
                print(f"  > Loading '{name}' from {path}")
                # This InferenceSession() is the FAST part
                models[name] = ort.InferenceSession(path)
                print(f"  > Successfully loaded {name}.")
            except Exception as e:
                # This error often shows if the file wasn't fetched correctly in py-config
                print(f"  > WARNING: Could not load ONNX model at {path}. Error: {e}")
                print(f"  > CHECK YOUR <py-config> in index.html to ensure this file is fetched!")
        return models

    # --- THIS IS YOUR ORIGINAL LOGIC FROM AGARENV, MOVED HERE ---
    def reset_game(self, num_cpu=cfg.NUM_CPU, num_food=cfg.NUM_FOOD, num_viruses=cfg.NUM_VIRUSES, ai_opponents=None):
        if ai_opponents is None: ai_opponents = {'aggressor': 1, 'farmer': 1, 'survivor': 1}
        self.mass_list = []
        self.food_list = [Blob(random.randint(0, cfg.SCREEN_WIDTH), random.randint(0, cfg.SCREEN_HEIGHT), cfg.FOOD_RADIUS, cfg.FOOD_COLOR) for _ in range(num_food)]
        self.virus_list = []; margin = 15
        corners = [(margin, margin), (cfg.SCREEN_WIDTH - margin, margin), (margin, cfg.SCREEN_HEIGHT - margin), (cfg.SCREEN_WIDTH - margin, cfg.SCREEN_HEIGHT - margin)]
        for x, y in corners:
            if len(self.virus_list) < num_viruses: self.virus_list.append(Virus(x, y))
        for _ in range(num_viruses - len(self.virus_list)):
            self.virus_list.append(Virus(random.randint(100, cfg.SCREEN_WIDTH-100), random.randint(100, cfg.SCREEN_HEIGHT-100)))
        
        self.player = PlayerController("Player", cfg.PLAYER_COLOR, cfg.PLAYER_START_RADIUS, is_human=True)
        opponents = []
        # Only create AI opponents if models are available
        if self.ai_models:
            for name, count in ai_opponents.items():
                if name in self.ai_models:
                    for i in range(count):
                        color = {'aggressor': cfg.AI_AGGRESSOR_COLOR, 'farmer': cfg.AI_FARMER_COLOR, 'survivor': cfg.AI_SURVIVOR_COLOR}.get(name)
                        opponents.append(PlayerController(f"AI-{name.capitalize()}", color, cfg.CPU_START_RADIUS, ai_model=self.ai_models[name]))
        # Add regular CPU opponents
        for i in range(num_cpu):
            opponents.append(PlayerController(f"CPU {i+1}", cfg.CPU_COLOR, cfg.CPU_START_RADIUS))
        self.all_controllers = [self.player] + opponents

        for controller in self.all_controllers:
            if controller.ai_model:
                initial_screen = self._get_processed_screen(center_on_controller=controller)
                for _ in range(controller.frame_stack.maxlen): controller.frame_stack.append(initial_screen)


    def _unpack_action(self, continuous_action):
        move_action = continuous_action[:2]; special_action_continuous = continuous_action[2]
        if special_action_continuous < -0.33: special_action = 0
        elif special_action_continuous < 0.33: special_action = 1
        else: special_action = 2
        return {"move": move_action, "special": special_action}

    def _handle_collisions(self):
        removed_food = set(); removed_mass = set(); removed_viruses = set()
        removed_blobs = {c: set() for c in self.all_controllers}
        self.grid.clear()
        for controller in self.all_controllers:
            for blob in controller.blobs: self.grid.insert(blob, {'type': 'blob', 'owner': controller})
        for food in self.food_list: self.grid.insert(food, {'type': 'food'})
        for mass in self.mass_list: self.grid.insert(mass, {'type': 'mass'})
        for virus in self.virus_list: self.grid.insert(virus, {'type': 'virus'})
        for c1 in self.all_controllers:
            for b1 in c1.blobs[:]:
                if b1 in removed_blobs[c1]: continue
                for b2, b2_data in self.grid.get_nearby(b1):
                    if b1 is b2 or not b1.collides_with(b2): continue
                    b2_type = b2_data.get('type')
                    if b2_type == 'blob':
                        c2 = b2_data['owner']
                        if c1 != c2:
                            larger, smaller = (b1, b2) if b1.radius > b2.radius else (b2, b1)
                            larger_c, smaller_c = (c1, c2) if b1.radius > b2.radius else (c2, c1)
                            if smaller not in removed_blobs[smaller_c] and larger.radius > smaller.radius * 1.1:
                                larger.radius = math.sqrt(larger.radius**2 + smaller.radius**2)
                                removed_blobs[smaller_c].add(smaller)
                    elif b2_type == 'food' and b2 not in removed_food:
                        b1.radius = math.sqrt(b1.radius**2 + b2.radius**2); removed_food.add(b2)
                    elif b2_type == 'mass' and b2 not in removed_mass:
                        b1.radius = math.sqrt(b1.radius**2 + b2.radius**2); removed_mass.add(b2)
                    elif b2_type == 'virus' and b2 not in removed_viruses and b1.radius > b2.radius * 1.1:
                        original_mass = b1.radius**2; removed_blobs[c1].add(b1); removed_viruses.add(b2)
                        for _ in range(random.randint(6, 10)):
                            if len(c1.blobs) >= 16: break
                            angle = random.uniform(0, 2 * math.pi)
                            new_blob = Blob(b1.x, b1.y, max(math.sqrt(original_mass / 10), cfg.CPU_START_RADIUS), c1.color)
                            new_blob.dx, new_blob.dy = math.cos(angle) * 22, math.sin(angle) * 22
                            new_blob.merge_timer = 40; c1.blobs.append(new_blob)
                        break
        for food in removed_food: food.x, food.y = random.randint(0, cfg.SCREEN_WIDTH), random.randint(0, cfg.SCREEN_HEIGHT)
        if removed_mass: self.mass_list = [m for m in self.mass_list if m not in removed_mass]
        if removed_viruses:
            self.virus_list = [v for v in self.virus_list if v not in removed_viruses]
            for _ in range(len(removed_viruses)): self.virus_list.append(Virus(random.randint(100, cfg.SCREEN_WIDTH-100), random.randint(100, cfg.SCREEN_HEIGHT-100)))
        for controller, blobs_to_remove in removed_blobs.items():
            if blobs_to_remove:
                controller.blobs = [b for b in controller.blobs if b not in blobs_to_remove]
                if not controller.blobs: controller.respawn()

    def _get_processed_screen(self, center_on_controller):
        agent_radius = center_on_controller.total_radius if center_on_controller.blobs else cfg.PLAYER_START_RADIUS
        vision_multiplier = 6.0 if agent_radius < 20 else (4.0 if agent_radius > 20 else 5.0)
        viewport_size = max(400, min(cfg.SCREEN_WIDTH, agent_radius * vision_multiplier * 2))
        cam_x, cam_y = (center_on_controller.center_x, center_on_controller.center_y) if center_on_controller.blobs else (cfg.SCREEN_WIDTH / 2, cfg.SCREEN_HEIGHT / 2)
        local_view_surface = pygame.Surface((viewport_size, viewport_size))
        source_rect_x = cam_x - viewport_size / 2
        source_rect_y = cam_y - viewport_size / 2
        local_view_surface.blit(self.screen, (0, 0), (source_rect_x, source_rect_y, viewport_size, viewport_size))
        viewport_pixels = pygame.image.tostring(local_view_surface, "RGB")
        pil_image = Image.frombytes("RGB", (int(viewport_size), int(viewport_size)), viewport_pixels)
        pil_resized = pil_image.resize((cfg.OBS_SIZE, cfg.OBS_SIZE), Image.Resampling.LANCZOS).convert('L')
        return np.array(pil_resized, dtype=np.uint8)

    def update_game_state(self):
        mouse_pos = pygame.mouse.get_pos()
        for controller in self.all_controllers:
            if controller.is_human:
                controller.update(self.all_controllers, self.mass_list, mouse_pos=mouse_pos)
            elif controller.ai_model:
                screen = self._get_processed_screen(center_on_controller=controller)
                controller.frame_stack.append(screen)
                # Stack frames: shape should be (1, 4, 84, 84) for CNN input
                # Normalize to [0, 1] range
                stacked_frames = np.array(list(controller.frame_stack), dtype=np.float32) / 255.0
                obs = stacked_frames[np.newaxis, ...]  # Add batch dimension: (1, 4, 84, 84)
                input_name = controller.ai_model.get_inputs()[0].name
                outputs = controller.ai_model.run(None, {input_name: obs})
                action_raw = outputs[0]
                
                unpacked_action = self._unpack_action(action_raw)
                controller.update(self.all_controllers, self.mass_list, ai_action=unpacked_action)
            else: # Scripted CPU
                controller.decide_cpu_state(self.all_controllers, self.food_list, self.virus_list)
                controller.update(self.all_controllers, self.mass_list)
        for m in self.mass_list[:]:
            m.move()
            if m.decay_timer <= 0: self.mass_list.remove(m)
        self._handle_collisions()

    def draw_elements(self):
        self.screen.fill(cfg.BACKGROUND_COLOR)
        for f in self.food_list: f.draw(self.screen)
        for v in self.virus_list: v.draw(self.screen)
        for m in self.mass_list: m.draw(self.screen)
        all_blobs_sorted = sorted([b for c in self.all_controllers for b in c.blobs], key=lambda b: b.radius)
        for blob in all_blobs_sorted:
            owner = next((c for c in self.all_controllers if blob in c.blobs), None)
            if owner: blob.draw(self.screen, name=owner.name if len(owner.blobs) == 1 else "")
        pygame.display.flip()

    async def main_loop(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT: running = False
                if self.player and self.player.blobs:
                    if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE: self.player.split()
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1: self.player.shoot_mass(self.mass_list)
            
            self.update_game_state()
            self.draw_elements()
            self.clock.tick(60)
            await asyncio.sleep(0)
        pygame.quit()

# Game initialization and PyScript setup
game = None
_game_loop_task = None

async def init_game():
    global game, _game_loop_task
    if game is None:
        print("Initializing game...")
        try:
            game = Game()
            print("Game initialized!")
            # Start the game loop
            _game_loop_task = asyncio.create_task(game.main_loop())
        except Exception as e:
            print(f"Error initializing game: {e}")
            import traceback
            traceback.print_exc()

# Auto-initialize when this module loads in PyScript
try:
    import pyscript
    from pyodide.ffi import create_proxy
    
    @pyscript.ffi.export_to_js
    def reset_game_from_js(settings):
        global game
        if game is None:
            print("Game not initialized yet, initializing now...")
            asyncio.ensure_future(init_game())
            return
        if game:
            print(f"Python received settings from JS: {settings}")
            # Handle both dict and JS object
            if hasattr(settings, 'to_py'):
                js_settings = settings.to_py()
            else:
                js_settings = settings
            num_cpu = js_settings.get('cpu_opponents', 10)
            num_food = js_settings.get('food', 850)
            num_viruses = js_settings.get('viruses', 14)
            ai_opponents = js_settings.get('ai_opponents', {})
            game.reset_game(
                num_cpu=num_cpu,
                num_food=num_food,
                num_viruses=num_viruses,
                ai_opponents=ai_opponents
            )
    
    # Wait a bit for PyScript to be fully ready, then initialize
    import js
    def start_game():
        asyncio.ensure_future(init_game())
    
    # Use setTimeout to ensure DOM is ready
    js.setTimeout(create_proxy(start_game), 100)
    
except ImportError:
    # Not running in PyScript, use standard Python
    pass
        
if __name__ == '__main__':
    game = Game()
    asyncio.run(game.main_loop())
