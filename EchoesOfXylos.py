import random
import os
import time
import json # Import the json module for saving/loading
import math # For distance calculation in 'look' function
import sys # For stdin/stdout manipulation
import platform # To detect OS for getch implementation

# --- Platform-specific single character input (getch) ---
# This allows reading a single key press without waiting for Enter.
if platform.system() == "Windows":
    import msvcrt
    def _getch():
        return msvcrt.getch().decode('utf-8')
else:
    import tty
    import termios
    def _getch():
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

# --- Game Configuration ---
MAP_WIDTH = 40 # Increased width for rooms
MAP_HEIGHT = 20 # Increased height for rooms
MAX_ENEMIES_PER_LEVEL = 7
MAX_ITEMS_PER_LEVEL = 5
INITIAL_PLAYER_HP = 100
INITIAL_PLAYER_ATTACK = 10
INITIAL_PLAYER_DEFENSE = 5
INITIAL_PLAYER_SPEED = 10 # Determines turn order, higher is faster
INITIAL_PLAYER_ENERGY = 50 # Player's starting energy
XP_TO_LEVEL_UP_BASE = 50
XP_LEVEL_MULTIPLIER = 1.5
REST_HEAL_AMOUNT = 15
REST_ENERGY_AMOUNT = 10 # Energy restored on rest
REST_ENCOUNTER_CHANCE = 0.2 # 20% chance of enemy encounter when resting

# Map Generation Constants
MAX_ROOMS = 10
ROOM_MIN_SIZE = 5
ROOM_MAX_SIZE = 10

# Trap Constants
TRAP_DAMAGE_BASE = 15
TRAP_SPAWN_CHANCE = 0.033 # Reduced trap frequency (was 0.1)

# Energy Crystal Goal
CRYSTALS_TO_WIN = 10
CRYSTAL_SPAWN_CHANCE_BASE = 0.02 # 2% base chance per empty tile
CRYSTAL_SPAWN_CHANCE_PER_LEVEL = 0.005 # Increases by 0.5% per level

SAVE_FILE_NAME = "savegame.json"

# ANSI escape codes for colors
COLOR_RESET = "\033[0m"
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_BLUE = "\033[94m"
COLOR_MAGENTA = "\033[95m"
COLOR_CYAN = "\033[96m"
COLOR_WHITE = "\033[97m"

# --- Utility Functions ---
def clear_screen():
    """Clears the terminal screen using ANSI escape codes to reduce flicker."""
    # \033[2J clears the entire screen, and \033[H moves the cursor to the top-left.
    # This is generally faster and smoother than calling an OS command.
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()

def get_player_input(prompt, valid_options=None, single_char_mode=True):
    """
    Gets validated input from the player.
    If single_char_mode is True, reads a single character without Enter.
    If single_char_mode is False, reads a full line with Enter.
    """
    if single_char_mode:
        sys.stdout.write(prompt) # Print the prompt
        sys.stdout.flush() # Ensure it's displayed immediately

        while True:
            user_input = _getch().strip().lower() # Read single character
            sys.stdout.write(user_input + '\n') # Echo the character and a newline for readability
            sys.stdout.flush()

            if valid_options:
                if user_input in valid_options:
                    return user_input
                else:
                    display_message(f"Invalid input. Please choose from: {', '.join(valid_options)}")
                    sys.stdout.write(prompt) # Re-print prompt if invalid
                    sys.stdout.flush()
            else:
                return user_input
    else: # Standard input mode for full strings
        while True:
            user_input = input(prompt).strip().lower()
            if valid_options:
                if user_input in valid_options:
                    return user_input
                else:
                    print(f"Invalid input. Please choose from: {', '.join(valid_options)}")
            else:
                return user_input


def display_message(message, delay=0.5):
    """Displays a message to the player with a slight delay."""
    print(message)
    time.sleep(delay)

# --- Game Entities ---

class GameEntity:
    """Base class for all entities in the game (Player, Enemies)."""
    def __init__(self, name, hp, attack, defense, speed, level=1):
        self.name = name
        self.max_hp = hp
        self.hp = hp
        self.attack = attack
        self.defense = defense
        self.speed = speed
        self.level = level

    def take_damage(self, damage):
        """Reduces entity's HP by the given damage amount."""
        self.hp -= damage
        if self.hp < 0:
            self.hp = 0
        return damage

    def is_alive(self):
        """Checks if the entity is still alive."""
        return self.hp > 0

    def attack_target(self, target):
        """Calculates and applies damage to a target."""
        damage = max(0, self.attack - target.defense)
        target.take_damage(damage)
        display_message(f"{self.name} attacks {target.name} for {damage} damage!")
        if not target.is_alive():
            display_message(f"{target.name} has been defeated!")
        return damage

class Player(GameEntity):
    """The player character."""
    def __init__(self, name, hp, attack, defense, speed, class_type):
        super().__init__(name, hp, attack, defense, speed)
        self.class_type = class_type
        self.inventory = []
        self.equipped_weapon = None
        self.equipped_armor = None
        self.xp = 0
        self.xp_to_next_level = XP_TO_LEVEL_UP_BASE
        self.current_level_num = 1 # Game level, not character level
        self.learned_skills = [] # List to hold Skill objects
        self.max_energy = INITIAL_PLAYER_ENERGY # Max energy
        self.energy = INITIAL_PLAYER_ENERGY # Current energy
        self.credits = 0 # Player's money
        self.crystals_collected = 0 # Energy Crystals collected

        # Give starting equipment only if not loading from a save
        # This logic will be handled in the Game.start_game method
        # to differentiate between new game and loaded game.


    def add_xp(self, amount):
        """Adds experience points to the player."""
        self.xp += amount
        display_message(f"You gained {amount} XP!")
        if self.xp >= self.xp_to_next_level:
            self.level_up()

    def level_up(self):
        """Increases player's character level and stats."""
        self.level += 1
        self.max_hp += 15
        self.hp = self.max_hp # Fully heal on level up
        self.attack += 3
        self.defense += 2
        self.speed += 1
        self.max_energy += 10 # Increase max energy on level up
        self.energy = self.max_energy # Fully restore energy on level up
        self.xp -= self.xp_to_next_level # Carry over excess XP
        self.xp_to_next_level = int(XP_TO_LEVEL_UP_BASE * (XP_LEVEL_MULTIPLIER ** (self.level - 1)))
        display_message(f"*** {self.name} reached Level {self.level}! ***")
        display_message("Your stats have increased, and you are fully healed and recharged!")

        # Unlock skills based on class and level
        if self.class_type == 'soldier':
            if self.level == 2 and not any(s.name == "Power Shot" for s in self.learned_skills):
                self.learned_skills.append(Skill("Power Shot", "Deals extra damage to an enemy.", 15, _soldier_power_shot_effect))
                display_message(f"You unlocked the '{self.learned_skills[-1].name}' skill!")
            if self.level == 5 and not any(s.name == "Grenade Toss" for s in self.learned_skills):
                self.learned_skills.append(Skill("Grenade Toss", "Throws a grenade, damaging all enemies.", 30, _soldier_grenade_toss_effect))
                display_message(f"You unlocked the '{self.learned_skills[-1].name}' skill!")
        elif self.class_type == 'engineer':
            if self.level == 2 and not any(s.name == "Repair Drone" for s in self.learned_skills):
                self.learned_skills.append(Skill("Repair Drone", "Summons a drone to restore your HP.", 20, _engineer_repair_drone_effect))
                display_message(f"You unlocked the '{self.learned_skills[-1].name}' skill!")
            if self.level == 5 and not any(s.name == "Shield Matrix" for s in self.learned_skills):
                self.learned_skills.append(Skill("Shield Matrix", "Deploys a temporary shield, increasing defense.", 25, _engineer_shield_matrix_effect))
                display_message(f"You unlocked the '{self.learned_skills[-1].name}' skill!")
        elif self.class_type == 'scout':
            if self.level == 2 and not any(s.name == "Burst of Speed" for s in self.learned_skills):
                self.learned_skills.append(Skill("Burst of Speed", "Temporarily increases your speed in combat.", 10, _scout_burst_of_speed_effect))
                display_message(f"You unlocked the '{self.learned_skills[-1].name}' skill!")
            if self.level == 5 and not any(s.name == "Stealth Field" for s in self.learned_skills):
                self.learned_skills.append(Skill("Stealth Field", "Activates a stealth field, increasing defense and evasion.", 35, _scout_stealth_field_effect))
                display_message(f"You unlocked the '{self.learned_skills[-1].name}' skill!")

        self.display_stats()


    def equip_item(self, item):
        """Equips a weapon or armor item."""
        if isinstance(item, Weapon):
            if self.equipped_weapon:
                self.inventory.append(self.equipped_weapon) # Unequip current
                self.attack -= self.equipped_weapon.damage_bonus
            self.equipped_weapon = item
            self.attack += item.damage_bonus
            display_message(f"You equipped {item.name}. Attack increased by {item.damage_bonus}.")
        elif isinstance(item, Armor):
            if self.equipped_armor:
                self.inventory.append(self.equipped_armor) # Unequip current
                self.defense -= self.equipped_armor.defense_bonus
            self.equipped_armor = item
            self.defense += item.defense_bonus
            display_message(f"You equipped {item.name}. Defense increased by {item.defense_bonus}.")
        else:
            display_message("You cannot equip this item.")

    def use_item(self, item):
        """Uses a consumable item."""
        if isinstance(item, Consumable):
            item.use(self)
            # Only remove if it's actually a consumable that gets used up
            if item in self.inventory: # Check if it's still in inventory (e.g. not a special persistent item)
                self.inventory.remove(item)
        else:
            display_message("This item cannot be used in this way.")

    def display_stats(self):
        """Prints the player's current stats."""
        print("\n--- Player Stats ---")
        print(f"Name: {self.name}")
        print(f"Level: {self.level} (XP: {self.xp}/{self.xp_to_next_level})")
        print(f"HP: {self.hp}/{self.max_hp}")
        print(f"Energy: {self.energy}/{self.max_energy}") # Display energy
        print(f"Credits: {self.credits}") # Display credits
        print(f"Crystals: {self.crystals_collected}/{CRYSTALS_TO_WIN}") # Display crystals
        print(f"Attack: {self.attack}")
        print(f"Defense: {self.defense}")
        print(f"Speed: {self.speed}")
        print(f"Weapon: {self.equipped_weapon.name if self.equipped_weapon else 'None'}")
        print(f"Armor: {self.equipped_armor.name if self.equipped_armor else 'None'}")
        print("--------------------")

    def display_inventory(self):
        """Prints the player's inventory."""
        if not self.inventory:
            print("Your inventory is empty.")
            return

        print("\n--- Inventory ---")
        for i, item in enumerate(self.inventory):
            equipped_status = ""
            if item == self.equipped_weapon or item == self.equipped_armor:
                equipped_status = "(Equipped)"

            bonus_info = ""
            if isinstance(item, Weapon):
                bonus_info = f"(Damage: +{item.damage_bonus})"
            elif isinstance(item, Armor):
                bonus_info = f"(Defense: +{item.defense_bonus})"

            print(f"{i+1}. {item.name} {equipped_status} ({item.item_type}) {bonus_info} - {item.description}")
        print("-----------------")

    def display_skills(self):
        """Prints the player's learned skills."""
        if not self.learned_skills:
            print("You have no skills yet.")
            return

        print("\n--- Learned Skills ---")
        for i, skill in enumerate(self.learned_skills):
            print(f"{i+1}. {skill.name} (Cost: {skill.energy_cost} Energy) - {skill.description}") # Display cost
        print("----------------------")


class Enemy(GameEntity):
    """An enemy character."""
    def __init__(self, name, hp, attack, defense, speed, xp_value, credit_value, symbol, item_drop=None): # credit_value, symbol
        super().__init__(name, hp, attack, defense, speed)
        self.xp_value = xp_value
        self.credit_value = credit_value # Credits awarded for defeating this enemy
        self.item_drop = item_drop # Can be an Item object
        self.symbol = symbol #Symbol for map display
        self.x = -1 # Placeholder for map position
        self.y = -1 # Placeholder for map position

    @staticmethod
    def create_random_enemy(player_level):
        """Creates a random enemy based on player level."""
        enemy_types = [
            ("Cyber-Drone", 30, 8, 3, 7, 20, 5, 'D'), # Name, HP, ATK, DEF, SPD, XP, Credits, Symbol
            ("Mutant Scavenger", 40, 12, 5, 6, 30, 8, 'S'),
            ("Rogue Android", 50, 15, 7, 8, 40, 10, 'A'),
            ("Alien Hunter", 60, 18, 9, 9, 50, 15, 'H')
        ]
        name, base_hp, base_atk, base_def, base_spd, base_xp, base_credits, symbol = random.choice(enemy_types)

        # Scale enemy stats with player level
        level_multiplier = 1 + (player_level - 1) * 0.2
        hp = int(base_hp * level_multiplier)
        atk = int(base_atk * level_multiplier)
        defense = int(base_def * level_multiplier)
        speed = int(base_spd * level_multiplier)
        xp = int(base_xp * level_multiplier)
        credits = int(base_credits * level_multiplier)

        # Randomly assign an item drop
        item_drop = None
        if random.random() < 0.3: # 30% chance to drop an item
            item_drop = random.choice([
                HealthPotion(),
                EnergyCell(),
                EnergyPack(),
                LaserPistol(),
                PlasmaRifle(),
                ScrapArmor(),
                ReinforcedVest()
            ])

        return Enemy(name, hp, atk, defense, speed, xp, credits, symbol, item_drop)

# --- Items ---

class Item:
    """Base class for all items."""
    def __init__(self, name, description, item_type, base_value=10): # base_value for selling
        self.name = name
        self.description = description
        self.item_type = item_type
        self.base_value = base_value # Value for selling

    def __str__(self):
        return f"{self.name} ({self.item_type})"

class Weapon(Item):
    """A weapon item that increases attack."""
    def __init__(self, name, description, damage_bonus, base_value):
        super().__init__(name, description, 'weapon', base_value)
        self.damage_bonus = damage_bonus

class Armor(Item):
    """An armor item that increases defense."""
    def __init__(self, name, description, defense_bonus, base_value):
        super().__init__(name, description, 'armor', base_value)
        self.defense_bonus = defense_bonus

class Consumable(Item):
    """A consumable item that provides an effect."""
    def __init__(self, name, description, effect_func, base_value):
        super().__init__(name, description, 'consumable', base_value)
        self.effect_func = effect_func

    def use(self, target):
        """Applies the consumable's effect to the target."""
        self.effect_func(target)
        display_message(f"You used {self.name}.")

class Collectible(Item):
    """A collectible item that serves a game objective."""
    def __init__(self, name, description, base_value=0): # Added name and description to init
        super().__init__(name, description, 'collectible', base_value)

# Specific Item Definitions
class HealthPotion(Consumable):
    def __init__(self):
        super().__init__("Health Potion", "Restores 50 HP.", self._heal_effect, 20)

    def _heal_effect(self, target):
        heal_amount = 50
        target.hp = min(target.max_hp, target.hp + heal_amount)
        display_message(f"{target.name} restored {heal_amount} HP.")

class EnergyCell(Consumable):
    def __init__(self):
        super().__init__("Energy Cell", "Restores 25 HP.", self._heal_effect, 15)

    def _heal_effect(self, target):
        heal_amount = 25
        target.hp = min(target.max_hp, target.hp + heal_amount)
        display_message(f"{target.name} restored {heal_amount} HP.")

class EnergyPack(Consumable): # Energy Pack item
    def __init__(self):
        super().__init__("Energy Pack", "Restores 40 Energy.", self._energy_effect, 25)

    def _energy_effect(self, target):
        energy_restore = 40
        target.energy = min(target.max_energy, target.energy + energy_restore)
        display_message(f"{target.name} restored {energy_restore} Energy.")

class EnergyCrystal(Collectible): # Standalone class inheriting from Collectible
    def __init__(self):
        super().__init__("Energy Crystal", "A shimmering crystal, vital for your mission.", 100) # Can be sold for credits if needed


class LaserPistol(Weapon):
    def __init__(self):
        super().__init__("Laser Pistol", "A standard issue energy weapon.", 5, 30)

class PlasmaRifle(Weapon):
    def __init__(self):
        super().__init__("Plasma Rifle", "A powerful, high-energy rifle.", 10, 60)

class ScrapArmor(Armor):
    def __init__(self):
        super().__init__("Scrap Armor", "Crude armor made from salvaged parts.", 3, 25)

class ReinforcedVest(Armor):
    def __init__(self):
        super().__init__("Reinforced Vest", "A sturdy vest offering decent protection.", 7, 50)

# --- Global Item and Skill Lookups (for serialization) ---
ALL_ITEM_CLASSES = {
    "Health Potion": HealthPotion,
    "Energy Cell": EnergyCell,
    "Energy Pack": EnergyPack,
    "Energy Crystal": EnergyCrystal,
    "Laser Pistol": LaserPistol,
    "Plasma Rifle": PlasmaRifle,
    "Scrap Armor": ScrapArmor,
    "Reinforced Vest": ReinforcedVest,
}

# Skill effect functions
def _engineer_repair_drone_effect(player, enemy):
    """Engineer skill: heals the player."""
    heal_amount = 30 + player.level * 2 # Scales with player level
    player.hp = min(player.max_hp, player.hp + heal_amount)
    display_message(f"Your Repair Drone mends your wounds, restoring {heal_amount} HP!")

def _soldier_power_shot_effect(player, enemy):
    """Soldier skill: deals extra damage to an enemy."""
    if enemy and enemy.is_alive():
        damage_bonus = player.attack // 2 # Half of player's current attack as bonus
        total_damage = max(0, player.attack + damage_bonus - enemy.defense)
        enemy.take_damage(total_damage)
        display_message(f"{player.name} unleashes a powerful shot on {enemy.name} for {total_damage} damage!")
        if not enemy.is_alive():
            display_message(f"{enemy.name} has been defeated!")
    else:
        display_message("No valid target for Power Shot!")

def _scout_burst_of_speed_effect(player, enemy):
    """Scout skill: temporarily increases player's speed for the current combat."""
    speed_boost = 5
    player.speed += speed_boost
    display_message(f"{player.name} activates a Burst of Speed, increasing speed by {speed_boost} for this combat!")
    # NOTE: This speed boost currently lasts for the remainder of the combat.
    

def _soldier_grenade_toss_effect(player, enemies_on_map): # Needs to target all enemies on map
    """Soldier skill: deals area damage to all enemies."""
    aoe_damage = player.attack // 3 + 10 # Base damage + scales with player attack
    display_message(f"{player.name} tosses a grenade, dealing {aoe_damage} damage to all nearby enemies!")
    for enemy in list(enemies_on_map): # Iterate over a copy to allow modification
        if enemy.is_alive():
            damage_dealt = max(0, aoe_damage - enemy.defense)
            enemy.take_damage(damage_dealt)
            display_message(f"{enemy.name} takes {damage_dealt} damage from the explosion!")
            if not enemy.is_alive():
                display_message(f"{enemy.name} has been defeated!")

def _engineer_shield_matrix_effect(player, enemy):
    """Engineer skill: temporarily increases player's defense."""
    defense_boost = 10
    player.defense += defense_boost
    display_message(f"{player.name} activates a Shield Matrix, increasing defense by {defense_boost} for this combat!")
    # NOTE: This defense boost currently lasts for the remainder of the combat.

def _scout_stealth_field_effect(player, enemy):
    """Scout skill: temporarily increases player's defense and evasion."""
    defense_boost = 5
    speed_boost = 3 # Also helps with evasion/turn order
    player.defense += defense_boost
    player.speed += speed_boost
    display_message(f"{player.name} activates a Stealth Field, increasing defense by {defense_boost} and speed by {speed_boost} for this combat!")
    # NOTE: This effect currently lasts for the remainder of the combat.


ALL_SKILL_DATA = {
    "Power Shot": {"cost": 15, "effect": _soldier_power_shot_effect, "description": "Deals extra damage to an enemy."},
    "Repair Drone": {"cost": 20, "effect": _engineer_repair_drone_effect, "description": "Summons a drone to restore your HP."},
    "Burst of Speed": {"cost": 10, "effect": _scout_burst_of_speed_effect, "description": "Temporarily increases your speed in combat."},
    "Grenade Toss": {"cost": 30, "effect": _soldier_grenade_toss_effect, "description": "Throws a grenade, damaging all enemies."},
    "Shield Matrix": {"cost": 25, "effect": _engineer_shield_matrix_effect, "description": "Deploys a temporary shield, increasing defense."},
    "Stealth Field": {"cost": 35, "effect": _scout_stealth_field_effect, "description": "Activates a stealth field, increasing defense and evasion."},
}

class Skill:
    """Represents an active skill usable by the player."""
    def __init__(self, name, description, energy_cost, effect_func):
        self.name = name
        self.description = description
        self.energy_cost = energy_cost
        self.effect_func = effect_func

    def use(self, player, target=None, enemies_on_map=None): # Added enemies_on_map for AoE skills
        """Applies the skill's effect."""
        if self.name == "Grenade Toss":
            self.effect_func(player, enemies_on_map)
        else:
            self.effect_func(player, target)

# --- Traps ---
class Trap:
    """A hidden trap on the map."""
    def __init__(self, x, y, damage):
        self.x = x
        self.y = y
        self.damage = damage
        self.triggered = False

    def trigger(self, player):
        """Applies trap effect to the player."""
        if self.triggered:
            return # Already triggered

        self.triggered = True
        display_message("You stepped on a hidden trap!", 0.5)
        if player.class_type == 'scout':
            display_message("As a Scout, you deftly avoid the trap's full effect!", 0.5)
        else:
            damage_dealt = self.damage
            player.take_damage(damage_dealt)
            display_message(f"The trap deals {damage_dealt} damage! Your HP: {player.hp}/{player.max_hp}", 0.5)


# --- Game Map ---

class GameMap:
    """Represents the game level map."""
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.tiles = [['#' for _ in range(width)] for _ in range(height)] # Initialize with walls
        self.player_start = (0, 0)
        self.exit_location = (0, 0)
        self.shop_location = None # Shop location
        self.entities = [] # List of Enemy objects
        self.items_on_map = {} # (x,y): Item object
        self.traps_on_map = {} # (x,y): Trap object # New: Traps
        self.rooms = [] # List to store room coordinates

    def generate_map(self, player_level, current_level_num, is_shop_floor=False): # current_level_num
        """Generates a new randomized map with rooms and corridors."""
        # Reset map to all walls
        self.tiles = [['#' for _ in range(self.width)] for _ in range(self.height)]
        self.entities = []
        self.items_on_map = {}
        self.traps_on_map = {} # Reset traps
        self.rooms = []
        self.shop_location = None # Reset shop location

        # 1. Generate Rooms
        for _ in range(MAX_ROOMS):
            w = random.randint(ROOM_MIN_SIZE, ROOM_MAX_SIZE)
            h = random.randint(ROOM_MIN_SIZE, ROOM_MAX_SIZE)
            x = random.randint(1, self.width - w - 1)
            y = random.randint(1, self.height - h - 1)

            new_room = {'x1': x, 'y1': y, 'x2': x + w, 'y2': y + h}

            # Check for overlap with existing rooms
            overlaps = False
            for existing_room in self.rooms:
                if (new_room['x1'] <= existing_room['x2'] + 1 and
                    new_room['x2'] >= existing_room['x1'] - 1 and
                    new_room['y1'] <= existing_room['y2'] + 1 and
                    new_room['y2'] >= existing_room['y1'] - 1):
                    overlaps = True
                    break
            if not overlaps:
                self.rooms.append(new_room)
                # Carve out the room
                for ry in range(new_room['y1'], new_room['y2']):
                    for rx in range(new_room['x1'], new_room['x2']):
                        self.tiles[ry][rx] = '.'

        # 2. Connect Rooms with Corridors
        if len(self.rooms) > 1:
            # Sort rooms by x-coordinate for easier connection
            self.rooms.sort(key=lambda r: r['x1'])
            for i in range(len(self.rooms) - 1):
                room1 = self.rooms[i]
                room2 = self.rooms[i+1]

                # Get center points of rooms
                center1_x = (room1['x1'] + room1['x2']) // 2
                center1_y = (room1['y1'] + room1['y2']) // 2
                center2_x = (room2['x1'] + room2['x2']) // 2
                center2_y = (room2['y1'] + room2['y2']) // 2

                # Draw L-shaped corridor
                # Horizontal part
                for x in range(min(center1_x, center2_x), max(center1_x, center2_x) + 1):
                    self.tiles[center1_y][x] = '.'
                # Vertical part
                for y in range(min(center1_y, center2_y), max(center1_y, center2_y) + 1):
                    self.tiles[y][center2_x] = '.'

        # 3. Place Player, Exit, Enemies, Items, Traps on empty tiles ('.')
        empty_tiles = []
        for y in range(self.height):
            for x in range(self.width):
                if self.tiles[y][x] == '.':
                    empty_tiles.append((x, y))

        if not empty_tiles:
            # Fallback for extremely small or failed map generation
            display_message("Warning: No empty tiles found for placement. Regenerating map...", 1)
            self.generate_map(player_level, current_level_num, is_shop_floor) # Try again
            return

        # Place player start (P)
        self.player_start = random.choice(empty_tiles)
        empty_tiles.remove(self.player_start)
        self.tiles[self.player_start[1]][self.player_start[0]] = 'P'

        # Place exit (E)
        while True:
            self.exit_location = random.choice(empty_tiles)
            if abs(self.exit_location[0] - self.player_start[0]) > self.width // 4 or \
               abs(self.exit_location[1] - self.player_start[1]) > self.height // 4:
                empty_tiles.remove(self.exit_location)
                self.tiles[self.exit_location[1]][self.exit_location[0]] = 'E'
                break
        
        # Place shop if it's a shop floor
        if is_shop_floor:
            while True:
                shop_x, shop_y = random.choice(empty_tiles)
                # Ensure shop is not on player start or exit
                if (shop_x, shop_y) != self.player_start and (shop_x, shop_y) != self.exit_location:
                    empty_tiles.remove((shop_x, shop_y))
                    self.shop_location = (shop_x, shop_y)
                    self.tiles[shop_y][shop_x] = 'S' # Mark shop on map
                    break

        # Place traps (T)
        num_traps = int(len(empty_tiles) * TRAP_SPAWN_CHANCE) # Scale with map size
        for _ in range(num_traps):
            if not empty_tiles: break
            x, y = random.choice(empty_tiles)
            empty_tiles.remove((x, y))
            self.traps_on_map[(x, y)] = Trap(x, y, TRAP_DAMAGE_BASE)
            # Do NOT mark 'T' on self.tiles here; display_map will handle it dynamically

        # Place enemies (M)
        num_enemies = random.randint(1, MAX_ENEMIES_PER_LEVEL)
        for _ in range(num_enemies):
            if not empty_tiles: break # No more space
            x, y = random.choice(empty_tiles)
            empty_tiles.remove((x, y))
            enemy = Enemy.create_random_enemy(player_level)
            enemy.x, enemy.y = x, y # Store enemy position
            self.entities.append(enemy)
            # Do NOT mark 'M' on self.tiles here; display_map will handle it dynamically

        # Place items (I) and Energy Crystals (C)
        num_items = random.randint(0, MAX_ITEMS_PER_LEVEL)
        for _ in range(num_items):
            if not empty_tiles: break # No more space
            x, y = random.choice(empty_tiles)
            empty_tiles.remove((x, y))
            item = random.choice([
                HealthPotion(), EnergyCell(), EnergyPack(), LaserPistol(), PlasmaRifle(),
                ScrapArmor(), ReinforcedVest()
            ])
            self.items_on_map[(x, y)] = item
            # Do NOT mark 'I' on self.tiles here; display_map will handle it dynamically

        # Place Energy Crystals (C)
        crystal_spawn_chance = CRYSTAL_SPAWN_CHANCE_BASE + (current_level_num * CRYSTAL_SPAWN_CHANCE_PER_LEVEL)
        for _ in range(random.randint(0, 2)): # Try to spawn 0-2 crystals per level
            if not empty_tiles: break
            if random.random() < crystal_spawn_chance:
                x, y = random.choice(empty_tiles)
                empty_tiles.remove((x, y))
                self.items_on_map[(x, y)] = EnergyCrystal()


    def display_map(self, player_x, player_y):
        """Prints the current state of the map."""
        clear_screen()
        print("--- Current Level ---")
        for y in range(self.height):
            row_str = ""
            for x in range(self.width):
                if x == player_x and y == player_y:
                    row_str += COLOR_CYAN + '@' + COLOR_RESET # Player icon
                elif (x, y) == self.exit_location: # Always show exit
                    row_str += COLOR_CYAN + 'E' + COLOR_RESET
                elif self.shop_location and (x, y) == self.shop_location: # Always show shop
                    row_str += COLOR_BLUE + 'S' + COLOR_RESET
                elif (x, y) in self.items_on_map:
                    # Determine if it's a crystal or other item
                    item_on_tile = self.items_on_map[(x,y)]
                    if isinstance(item_on_tile, EnergyCrystal):
                        row_str += COLOR_MAGENTA + 'C' + COLOR_RESET # Crystal icon
                    else:
                        row_str += COLOR_YELLOW + 'I' + COLOR_RESET # Item icon
                elif (x, y) in self.traps_on_map and not self.traps_on_map[(x,y)].triggered: # Only show untriggered traps
                    row_str += COLOR_WHITE + 'T' + COLOR_RESET
                else:
                    # Check if an enemy is at this position
                    enemy_at_pos = False
                    for enemy in self.entities:
                        if enemy.is_alive() and enemy.x == x and enemy.y == y:
                            row_str += COLOR_RED + enemy.symbol + COLOR_RESET # Monster icon
                            enemy_at_pos = True
                            break
                    if not enemy_at_pos:
                        row_str += self.tiles[y][x] # Use the base tile (wall or empty)
            print(row_str)
        print("---------------------")

# --- Game Logic ---

class Game:
    """Manages the overall game flow."""
    def __init__(self):
        self.player = None
        self.current_map = None
        self.game_over = False
        self.current_level_num = 0
        self.original_player_speed = 0 # To revert speed after Burst of Speed
        self.original_player_defense = 0 # To revert defense after Shield Matrix/Stealth Field

    def display_title_and_story(self):
        """Displays the game's ASCII title and introductory story."""
        clear_screen()
        # ASCII art for title
        print(COLOR_CYAN + r"""



░▒▓████████▓▒░▒▓██████▓▒░░▒▓█▓▒░░▒▓█▓▒░░▒▓██████▓▒░░▒▓████████▓▒░░▒▓███████▓▒░       ░▒▓██████▓▒░░▒▓████████▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░      ░▒▓██████▓▒░ ░▒▓███████▓▒░ 
░▒▓█▓▒░     ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░             ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░             ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░     ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░        
░▒▓█▓▒░     ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░             ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░             ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░     ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░        
░▒▓██████▓▒░░▒▓█▓▒░      ░▒▓████████▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓██████▓▒░  ░▒▓██████▓▒░       ░▒▓█▓▒░░▒▓█▓▒░▒▓██████▓▒░         ░▒▓██████▓▒░ ░▒▓██████▓▒░░▒▓█▓▒░     ░▒▓█▓▒░░▒▓█▓▒░░▒▓██████▓▒░  
░▒▓█▓▒░     ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░             ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░             ░▒▓█▓▒░░▒▓█▓▒░  ░▒▓█▓▒░   ░▒▓█▓▒░     ░▒▓█▓▒░░▒▓█▓▒░      ░▒▓█▓▒░ 
░▒▓█▓▒░     ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░             ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░             ░▒▓█▓▒░░▒▓█▓▒░  ░▒▓█▓▒░   ░▒▓█▓▒░     ░▒▓█▓▒░░▒▓█▓▒░      ░▒▓█▓▒░ 
░▒▓████████▓▒░▒▓██████▓▒░░▒▓█▓▒░░▒▓█▓▒░░▒▓██████▓▒░░▒▓████████▓▒░▒▓███████▓▒░        ░▒▓██████▓▒░░▒▓█▓▒░             ░▒▓█▓▒░░▒▓█▓▒░  ░▒▓█▓▒░   ░▒▓████████▓▒░▒▓██████▓▒░░▒▓███████▓▒░  
                                                                                                                                                                                       
                                                                                                                                                                                       

                                                                                                                                                            


""" + COLOR_RESET)
        display_message("Welcome to Echoes of Xylos!", 1)
        display_message("In a distant future, humanity's civilization teeters on the brink of collapse.", 1.5)
        display_message("Our once-vibrant cities now flicker, powered by dwindling energy reserves.", 1.5)
        display_message("The only hope lies in the fabled Energy Crystals, an ancient and powerful energy source.", 1.5)
        display_message("These crystals were created by the Xylos, a long-dead empire of ancient aliens.", 1.5)
        display_message("Their vast, derelict ruins, deep within uncharted sectors of the galaxy, hold the key to our survival.", 1.5)
        display_message("You are a lone prospector, a beacon of hope in the encroaching darkness.", 1.5)
        display_message("Your mission: descend into these perilous, procedurally generated ruins,", 1.5)
        display_message("brave hostile alien life, avoid deadly traps, and salvage these vital crystals.", 1.5)
        display_message("Even though the Xylos are long gone, their automated defenses are still active and will not give up their tech without a fight.", 1.5)
        display_message(f"You must collect {CRYSTALS_TO_WIN} Energy Crystals to reignite our dying world.", 2)
        display_message("The fate of civilization rests on your shoulders. Good luck, prospector.", 2)
        display_message("\nPress any key to begin your journey...", 0.5)
        _getch()


    def start_game(self):
        """Initializes and starts the game."""
        self.display_title_and_story() # Display title and story first

        clear_screen() # Clear after story
        print("Welcome to Echoes of Xylos!") # Re-print welcome message before save check

        # Check for existing save game
        if os.path.exists(SAVE_FILE_NAME):
            self.display_save_info()
            choice = get_player_input("Do you want to [l]oad game or [n]ew game? ", ['l', 'n'])
            if choice == 'l':
                self.load_game()
            else:
                self.character_creation()
        else:
            display_message("No save game found. Starting a new game...", 1)
            self.character_creation()

        # After character creation or loading, set up the initial level
        if self.current_map is None: # Only generate if not loaded
            self.generate_level()
        else: # If loaded, ensure player position is set for the loaded map
            # The player x,y are already set during load_game
            display_message(f"Resuming Level {self.current_level_num}...", 0.5)

        self.main_game_loop()

    def display_save_info(self):
        """Displays information about the existing save game."""
        try:
            with open(SAVE_FILE_NAME, 'r') as f:
                save_data = json.load(f)
            print("\n--- Saved Game Found ---")
            print(f"Character: {save_data['player_data']['name']}")
            print(f"Level: {save_data['player_data']['level']}")
            print(f"Floor: {save_data['current_level_num']}")
            print("------------------------")
        except (FileNotFoundError, json.JSONDecodeError):
            print("Error reading save file.")


    def save_game(self):
        """Saves the current game state to a JSON file."""
        if self.player is None:
            display_message("No game in progress to save.", 0.5)
            return

        # Prepare items for saving (only their names)
        inventory_names = [item.name for item in self.player.inventory]
        equipped_weapon_name = self.player.equipped_weapon.name if self.player.equipped_weapon else None
        equipped_armor_name = self.player.equipped_armor.name if self.player.equipped_armor else None
        learned_skill_names = [skill.name for skill in self.player.learned_skills]

        save_data = {
            "current_level_num": self.current_level_num,
            "player_data": {
                "name": self.player.name,
                "hp": self.player.hp,
                "max_hp": self.player.max_hp,
                "attack": self.player.attack,
                "defense": self.player.defense,
                "speed": self.player.speed,
                "level": self.player.level,
                "xp": self.player.xp,
                "xp_to_next_level": self.player.xp_to_next_level,
                "class_type": self.player.class_type,
                "max_energy": self.player.max_energy,
                "energy": self.player.energy,
                "credits": self.player.credits,
                "crystals_collected": self.player.crystals_collected, # New: Save crystals
                "x": self.player.x,
                "y": self.player.y,
                "inventory": inventory_names,
                "equipped_weapon": equipped_weapon_name,
                "equipped_armor": equipped_armor_name,
                "learned_skills": learned_skill_names,
            }
        }

        try:
            with open(SAVE_FILE_NAME, 'w') as f:
                json.dump(save_data, f, indent=4)
            display_message("Game saved successfully!", 0.5)
        except IOError:
            display_message("Error saving game.", 0.5)

    def load_game(self):
        """Loads the game state from a JSON file."""
        try:
            with open(SAVE_FILE_NAME, 'r') as f:
                save_data = json.load(f)

            player_data = save_data['player_data']
            self.current_level_num = save_data['current_level_num']

            # Reconstruct Player object
            self.player = Player(
                player_data['name'],
                player_data['max_hp'], # Use max_hp for initial player creation
                player_data['attack'],
                player_data['defense'],
                player_data['speed'],
                player_data['class_type']
            )
            # Set current HP and Energy
            self.player.hp = player_data['hp']
            self.player.energy = player_data['energy']
            self.player.credits = player_data.get('credits', 0)
            self.player.crystals_collected = player_data.get('crystals_collected', 0) # Load crystals
            # Set other loaded attributes
            self.player.level = player_data['level']
            self.player.xp = player_data['xp']
            self.player.xp_to_next_level = player_data['xp_to_next_level']
            self.player.max_energy = player_data['max_energy']
            self.player.x = player_data['x']
            self.player.y = player_data['y']
            self.original_player_speed = self.player.speed # Update original speed for skill reset
            self.original_player_defense = self.player.defense # Update original defense for skill reset

            # Reconstruct inventory
            self.player.inventory = []
            for item_name in player_data['inventory']:
                item_class = ALL_ITEM_CLASSES.get(item_name)
                if item_class:
                    self.player.inventory.append(item_class())
                else:
                    print(f"Warning: Unknown item '{item_name}' in save data.")

            # Reconstruct equipped items
            if player_data['equipped_weapon']:
                weapon_class = ALL_ITEM_CLASSES.get(player_data['equipped_weapon'])
                if weapon_class:
                    self.player.equipped_weapon = weapon_class()
                else:
                    print(f"Warning: Unknown equipped weapon '{player_data['equipped_weapon']}' in save data.")
            if player_data['equipped_armor']:
                armor_class = ALL_ITEM_CLASSES.get(player_data['equipped_armor'])
                if armor_class:
                    self.player.equipped_armor = armor_class()
                else:
                    print(f"Warning: Unknown equipped armor '{player_data['equipped_armor']}' in save data.")

            # Reconstruct learned skills
            self.player.learned_skills = []
            for skill_name in player_data['learned_skills']:
                skill_data = ALL_SKILL_DATA.get(skill_name)
                if skill_data:
                    self.player.learned_skills.append(Skill(skill_name, skill_data["description"], skill_data["cost"], skill_data["effect"]))
                else:
                    print(f"Warning: Unknown skill '{skill_name}' in save data.")

            # Generate the map for the loaded level
            # Determine if it's a shop floor
            is_shop_floor = (self.current_level_num % 5 == 0) and (self.current_level_num > 0)
            self.current_map = GameMap(MAP_WIDTH, MAP_HEIGHT)
            self.current_map.generate_map(self.player.level, self.current_level_num, is_shop_floor) # Regenerate map based on player's level and shop status

            display_message("Game loaded successfully!", 0.5)

        except (FileNotFoundError, json.JSONDecodeError) as e:
            display_message(f"Error loading game: {e}. Starting a new game.", 1)
            self.character_creation()


    def character_creation(self):
        """Guides the player through character creation."""
        print("\n--- Character Creation ---")
        player_name = get_player_input("Enter your character's name: ", single_char_mode=False)

        print("\nChoose your class:")
        print("1. Soldier (High Attack, Moderate HP)")
        print("2. Engineer (High Defense, Utility)")
        print("3. Scout (High Speed, Good Evasion)")

        class_choice_num = get_player_input("Enter class number (1, 2, or 3): ", ['1', '2', '3'])

        hp, atk, defn, spd = INITIAL_PLAYER_HP, INITIAL_PLAYER_ATTACK, INITIAL_PLAYER_DEFENSE, INITIAL_PLAYER_SPEED
        class_type = ""

        if class_choice_num == '1':
            atk += 5
            hp += 10
            class_type = 'soldier'
            display_message("You chose Soldier. Ready for combat!")
        elif class_choice_num == '2':
            defn += 5
            hp += 20
            class_type = 'engineer'
            display_message("You chose Engineer. Build and survive!")
        elif class_choice_num == '3':
            spd += 5
            atk += 2
            class_type = 'scout'
            display_message("You chose Scout. Swift and agile!")

        self.player = Player(player_name, hp, atk, defn, spd, class_type)
        self.original_player_speed = self.player.speed # Store initial speed for skill reset
        self.original_player_defense = self.player.defense # Store initial defense for skill reset

        # Give starting equipment for new game
        starting_weapon = LaserPistol()
        starting_armor = ScrapArmor()
        self.player.inventory.append(starting_weapon)
        self.player.inventory.append(starting_armor)
        self.player.equip_item(starting_weapon)
        self.player.equip_item(starting_armor)

        self.player.display_stats()
        display_message("Character created! Press any key to begin your adventure...", 0.5)
        _getch() # Wait for player to press any key

    def generate_level(self):
        """Generates a new game level."""
        display_message(f"\n--- Entering Level {self.current_level_num} ---")
        is_shop_floor = (self.current_level_num % 5 == 0) and (self.current_level_num > 0)
        self.current_map = GameMap(MAP_WIDTH, MAP_HEIGHT)
        self.current_map.generate_map(self.player.level, self.current_level_num, is_shop_floor) # Pass player's character level and shop status
        self.player.x, self.player.y = self.current_map.player_start
        display_message("The area is dark and foreboding...", 0.5)

    def main_game_loop(self):
        """The main loop of the game."""
        while not self.game_over:
            # Display map and stats at the beginning of each turn cycle
            self.current_map.display_map(self.player.x, self.player.y)
            self.player.display_stats()

            # Handle player input and loop until a turn-consuming action is taken
            # or the game state changes (e.g., quit, game over).
            player_turn_consumed = False
            while not player_turn_consumed:
                print("\nWhat do you do? (w/a/s/d to move, i[nventory], s[tats], r[est], l[ook], q[uit])")
                action = get_player_input("> ") # Default to single_char_mode=True

                if action in ['w', 'a', 's', 'd']:
                    self.move_player(action)
                    player_turn_consumed = True # Movement always consumes a turn
                elif action == 'i':
                    # handle_inventory returns True if an item was used/equipped (turn consumed)
                    # False if player just looked and backed out (turn not consumed)
                    player_turn_consumed = self.handle_inventory(in_combat=False) # Pass in_combat=False here
                    if not player_turn_consumed:
                        # If turn not consumed, re-display map and stats and prompt again
                        self.current_map.display_map(self.player.x, self.player.y)
                        self.player.display_stats()
                elif action == 's':
                    self.player.display_stats()
                    display_message("Press any key to continue...", 0.5)
                    _getch()
                    # Stats view does not consume turn, loop continues
                    self.current_map.display_map(self.player.x, self.player.y) # Re-display after pressing key
                    self.player.display_stats()
                elif action == 'r':
                    self.rest_player()
                    player_turn_consumed = True # Resting consumes a turn
                elif action == 'l':
                    self.look_around()
                    # Look does not consume turn, loop continues
                    self.current_map.display_map(self.player.x, self.player.y) # Re-display after pressing key
                    self.player.display_stats()
                elif action == 'q':
                    self.handle_quit_game()
                    if self.game_over: # If game is quit, break main game loop
                        player_turn_consumed = True # End the current turn and main loop
                    else:
                        # If player chose not to quit, loop continues
                        self.current_map.display_map(self.player.x, self.player.y) # Re-display after pressing key
                        self.player.display_stats()
                else:
                    display_message("Invalid action. Try again.", 0.5)
                    # Invalid action, loop continues, re-prompting input

            # After player's turn (if not game over)
            if self.game_over:
                break # Exit main game loop if player died or quit

            # Check for win condition after player's turn
            if self.player.crystals_collected >= CRYSTALS_TO_WIN:
                self.game_over = True
                display_message(f"*** Congratulations, {self.player.name}! ***", 1)
                display_message(f"You have collected {CRYSTALS_TO_WIN} Energy Crystals and completed your mission!", 1)
                display_message("The galaxy is safe, for now...", 1)
                display_message("Press any key to exit the game.", 0.5)
                _getch()
                break # Exit main game loop

            # Enemy turns (only if player is still alive and game not over)
            if self.player.is_alive() and not self.game_over:
                for enemy in self.current_map.entities:
                    if enemy.is_alive():
                        # Simple enemy AI: if player is adjacent, attack. Otherwise, try to move towards player.
                        dx = abs(enemy.x - self.player.x)
                        dy = abs(enemy.y - self.player.y)
                        if (dx == 1 and dy == 0) or (dx == 0 and dy == 1): # Adjacent
                            enemy.attack_target(self.player)
                        else:
                            # Move towards player
                            new_x, new_y = enemy.x, enemy.y
                            if self.player.x > enemy.x: new_x += 1
                            elif self.player.x < enemy.x: new_x -= 1
                            if self.player.y > enemy.y: new_y += 1
                            elif self.player.y < enemy.y: new_y -= 1

                            # Check if new position is valid and not occupied by another entity (player or other enemy)
                            can_move = True
                            if not (0 <= new_x < self.current_map.width and 0 <= new_y < self.current_map.height) or \
                               self.current_map.tiles[new_y][new_x] == '#': # Check for walls
                                can_move = False
                            for other_enemy in self.current_map.entities:
                                if other_enemy != enemy and other_enemy.is_alive() and other_enemy.x == new_x and other_enemy.y == new_y:
                                    can_move = False
                                    break
                            if (new_x, new_y) == (self.player.x, self.player.y): # Don't move onto player
                                can_move = False

                            if can_move:
                                enemy.x, enemy.y = new_x, new_y
                                # The line below is silenced as requested to speed up enemy turns.
                                # display_message(f"{enemy.name} moves.", 0.1)

            time.sleep(0.5) # Pause briefly after enemy turns

            if not self.player.is_alive():
                self.game_over = True
                display_message("\nYou have fallen in battle. Game Over!", 1)
                display_message("Press any key to exit the game.", 0.5)
                _getch()
                break


    def handle_player_input(self):
        """Processes player's action choice."""
        pass 

    def handle_quit_game(self):
        """Handles the player's decision to quit, including saving."""
        choice = get_player_input("Do you want to save before quitting? (y/n): ", ['y', 'n'])
        if choice == 'y':
            self.save_game()
        self.game_over = True
        display_message("Exiting game. Goodbye!", 0.5)


    def move_player(self, direction):
        """Moves the player on the map and handles interactions."""
        new_x, new_y = self.player.x, self.player.y

        if direction == 'w': new_y -= 1
        elif direction == 's': new_y += 1
        elif direction == 'a': new_x -= 1
        elif direction == 'd': new_x += 1
        else:
            # This 'else' should ideally not be reached if get_player_input validates
            # However, keeping it as a safeguard.
            display_message("Invalid direction. Use w/a/s/d.", 0.5)
            return

        # Check map boundaries and walls
        if not (0 <= new_x < self.current_map.width and 0 <= new_y < self.current_map.height) or \
           self.current_map.tiles[new_y][new_x] == '#':
            display_message("You hit a wall!", 0.5)
            return

        # Check for traps FIRST, as they are hidden and trigger on step
        if (new_x, new_y) in self.current_map.traps_on_map:
            trap = self.current_map.traps_on_map[(new_x, new_y)]
            if not trap.triggered: # Only trigger if not already triggered
                trap.trigger(self.player)
                # Trap vanishes after triggering
                del self.current_map.traps_on_map[(new_x, new_y)]
                # If player died from trap, end game
                if not self.player.is_alive():
                    return # Exit move_player, game over will be handled by main loop

                # Scouts are immune, but the trap still vanishes.
                # Non-scouts take damage and then proceed to move onto the tile.

        # Check for enemies
        target_enemy = None
        for enemy in self.current_map.entities:
            if enemy.is_alive() and enemy.x == new_x and enemy.y == new_y:
                target_enemy = enemy
                break

        if target_enemy:
            display_message(f"You bump into a {target_enemy.name}! Combat begins!", 0.5)
            display_message("Press any key to begin combat...", 0.5) # Pause for clarity
            _getch()
            self.combat_round(target_enemy)
        else:
            self.player.x, self.player.y = new_x, new_y

            # Check for items
            if (self.player.x, self.player.y) in self.current_map.items_on_map:
                item = self.current_map.items_on_map.pop((self.player.x, self.player.y))
                if isinstance(item, EnergyCrystal): # Handle crystal collection
                    self.player.crystals_collected += 1
                    display_message(f"You found an {item.name}! You now have {self.player.crystals_collected}/{CRYSTALS_TO_WIN} crystals.", 0.5)
                else:
                    self.player.inventory.append(item)
                    display_message(f"You found a {item.name} and added it to your inventory!", 0.5)

            # Check for shop
            if self.current_map.shop_location and (self.player.x, self.player.y) == self.current_map.shop_location:
                display_message("You found a mysterious shop!", 0.5)
                self.handle_shop()

            # Check for exit
            if (self.player.x, self.player.y) == self.current_map.exit_location:
                display_message("You found the exit!", 0.5)
                choice = get_player_input("Do you want to proceed to the next level? (y/n): ", ['y', 'n'])
                if choice == 'y':
                    display_message("Proceeding to the next level...", 1)
                    self.current_level_num += 1
                    self.generate_level()
                else:
                    display_message("You decide to continue exploring this level.", 0.5)
                    # Player stays on the exit tile, no change to level or map
                    pass


    def rest_player(self):
        """Allows the player to rest and regain HP and Energy, with a chance of an enemy encounter."""
        display_message("You find a quiet spot to rest...", 1)
        
        # Heal HP
        heal_amount = REST_HEAL_AMOUNT
        self.player.hp = min(self.player.max_hp, self.player.hp + heal_amount)
        display_message(f"You restored {heal_amount} HP. Current HP: {self.player.hp}/{self.player.max_hp}", 0.5)

        # Restore Energy
        energy_restore = REST_ENERGY_AMOUNT
        self.player.energy = min(self.player.max_energy, self.player.energy + energy_restore)
        display_message(f"You restored {energy_restore} Energy. Current Energy: {self.player.energy}/{self.player.max_energy}", 0.5)

        if random.random() < REST_ENCOUNTER_CHANCE:
            display_message("Suddenly, you hear movement nearby! An enemy ambushes you!", 1)
            # Create a random enemy scaled to current player level
            ambush_enemy = Enemy.create_random_enemy(self.player.level)
            # Place enemy adjacent to player if possible, otherwise just start combat
            possible_spawn_locs = []
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                spawn_x, spawn_y = self.player.x + dx, self.player.y + dy
                if (0 <= spawn_x < self.current_map.width and
                    0 <= spawn_y < self.current_map.height and
                    self.current_map.tiles[spawn_y][spawn_x] == '.'):
                    is_occupied = False
                    for e in self.current_map.entities:
                        if e.is_alive() and e.x == spawn_x and e.y == spawn_y:
                            is_occupied = True
                            break
                    if not is_occupied and (spawn_x, spawn_y) != (self.player.x, self.player.y):
                        possible_spawn_locs.append((spawn_x, spawn_y))

            if possible_spawn_locs:
                ambush_enemy.x, ambush_enemy.y = random.choice(possible_spawn_locs)
                self.current_map.entities.append(ambush_enemy)
            else: # Fallback if no adjacent empty tile
                display_message("The enemy appears out of nowhere!", 0.5)
                # For simplicity, don't place on map if no space, just start combat

            display_message("Press any key to face the threat...", 0.5)
            _getch()
            self.combat_round(ambush_enemy)
        else:
            display_message("You feel refreshed.", 0.5)
            display_message("Press any key to continue...", 0.5)
            _getch()


    def combat_round(self, enemy):
        """Handles a single round of combat between player and enemy."""
        combat_active = True
        # Store original stats for skill reset after combat
        initial_player_speed_in_combat = self.player.speed
        initial_player_defense_in_combat = self.player.defense

        while self.player.is_alive() and enemy.is_alive() and combat_active:
            clear_screen()
            print(f"\n--- Combat: {self.player.name} vs {enemy.name} ---")
            print(f"{self.player.name} HP: {self.player.hp}/{self.player.max_hp} | Energy: {self.player.energy}/{self.player.max_energy} | Attack: {self.player.attack} | Defense: {self.player.defense} | Speed: {self.player.speed}")
            print(f"{enemy.name} HP: {enemy.hp}/{enemy.max_hp} | Attack: {enemy.attack} | Defense: {enemy.defense} | Speed: {enemy.speed}")
            print("-------------------------------------------------")

            # Determine turn order based on speed
            combatants = sorted([self.player, enemy], key=lambda c: c.speed, reverse=True)

            for combatant in combatants:
                if not self.player.is_alive() or not enemy.is_alive():
                    break # Combat ended by death

                if combatant == self.player:
                    action_options = ['a', 'i', 'f']
                    if self.player.learned_skills:
                        action_options.append('k') # Add skill option if player has skills
                    action = get_player_input(f"Your turn! (a[ttack], i[nventory], f[lee]{', k[skill]' if 'k' in action_options else ''}) > ", action_options)

                    if action == 'a':
                        self.player.attack_target(enemy)
                    elif action == 'i':
                        # handle_inventory returns True if an item was used/equipped (turn consumed)
                        # False if player just looked and backed out (turn not consumed)
                        item_used_or_equipped = self.handle_inventory(in_combat=True)
                        if item_used_or_equipped:
                            pass # Turn consumed, proceed
                        else:
                            continue # Turn not consumed, re-prompt for action
                    elif action == 'f':
                        if self.attempt_flee(enemy):
                            combat_active = False # Successfully fled, end combat loop
                            break # Break out of combatants loop
                        else:
                            display_message("You failed to escape!", 0.5)
                    elif action == 'k':
                        skill_used = self.handle_skills(enemy) # handle_skills returns True if skill was used
                        if not skill_used: # If skill was not successfully used (e.g., pressed 'b' or insufficient energy)
                            continue # Player's turn is NOT consumed, re-prompt for action
                        # If skill was used, turn is consumed, proceed to next combatant
                else: # Enemy's turn
                    combatant.attack_target(self.player)
                time.sleep(0.5)

        # Combat ends: reset any temporary stat boosts from skills
        self.player.speed = initial_player_speed_in_combat
        self.player.defense = initial_player_defense_in_combat

        if not self.player.is_alive():
            display_message("You were defeated!", 1)
            self.game_over = True
        elif not enemy.is_alive():
            display_message(f"You defeated the {enemy.name}!", 1)
            self.player.add_xp(enemy.xp_value)
            self.player.credits += enemy.credit_value # New: Award credits
            display_message(f"You gained {enemy.credit_value} Credits!", 0.5)
            if enemy.item_drop:
                self.player.inventory.append(enemy.item_drop)
                display_message(f"The {enemy.name} dropped a {enemy.item_drop.name}!", 0.5)
            # Remove defeated enemy from map entities
            self.current_map.entities = [e for e in self.current_map.entities if e.is_alive()]
            display_message("Press any key to continue...", 0.5)
            _getch()


    def attempt_flee(self, enemy):
        """
        Attempts to flee from combat.
        Success chance is based on player speed vs enemy speed.
        """
        flee_chance = self.player.speed / (self.player.speed + enemy.speed)
        display_message(f"Attempting to flee... (Chance: {flee_chance:.2f})", 0.5)

        if random.random() < flee_chance:
            display_message("You successfully escaped!", 1)
            # Move player to a random adjacent empty tile
            possible_moves = []
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                new_x, new_y = self.player.x + dx, self.player.y + dy
                # Check if tile is within bounds, is an empty floor tile, and not occupied by another enemy
                if (0 <= new_x < self.current_map.width and
                    0 <= new_y < self.current_map.height and
                    self.current_map.tiles[new_y][new_x] == '.'):
                    is_occupied = False
                    for e in self.current_map.entities:
                        if e.is_alive() and e.x == new_x and e.y == new_y:
                            is_occupied = True
                            break
                    if not is_occupied:
                        possible_moves.append((new_x, new_y))

            if possible_moves:
                self.player.x, self.player.y = random.choice(possible_moves)
                display_message("You quickly move to a safer position.", 0.5)
            else:
                display_message("No clear escape route, but you still got away!", 0.5)
            return True
        else:
            return False

    def handle_inventory(self, in_combat=False):
        """Manages player's inventory actions."""
        if not self.player.inventory:
            display_message("Your inventory is empty.", 0.5)
            if not in_combat:
                display_message("Press any key to continue...", 0.5)
                _getch()
            return False # Indicate no item was used/equipped

        self.player.display_inventory()
        print("Enter item number to use/equip, or 'b' to go back.")
        while True:
            # Use single_char_mode=False for numerical input in inventory, as it can be multi-digit
            choice = get_player_input("> ", single_char_mode=False)
            if choice == 'b':
                return False # Player chose to go back
            try:
                item_index = int(choice) - 1
                if 0 <= item_index < len(self.player.inventory):
                    item = self.player.inventory[item_index]
                    if item.item_type == 'consumable':
                        self.player.use_item(item)
                        return True # Item used, turn consumed
                    elif item.item_type == 'collectible': # Can't use/equip crystals
                        display_message("You can't use or equip Energy Crystals here. They are for your mission!", 0.5)
                        continue # Stay in inventory menu
                    elif item.item_type in ['weapon', 'armor']:
                        # Check if the item is already equipped
                        if (isinstance(item, Weapon) and item == self.player.equipped_weapon) or \
                           (isinstance(item, Armor) and item == self.player.equipped_armor):
                            display_message(f"{item.name} is already equipped.", 0.5)
                            # Do not consume turn if already equipped and re-selecting
                            continue # Stay in the inventory loop
                        
                        self.player.equip_item(item)
                        # Remove from inventory after equipping only if it was successfully equipped
                        if item in self.player.inventory: # Check if it's still in inventory
                            self.player.inventory.pop(item_index)
                        return True # Item equipped, turn consumed
                    else:
                        display_message("You can't use or equip that item.", 0.5)
                else:
                    display_message("Invalid item number.", 0.5)
            except ValueError:
                display_message("Invalid input. Please enter a number or 'b'.", 0.5)
            if not in_combat: # If not in combat, allow multiple inventory actions until 'b' is pressed
                self.player.display_inventory()
                print("Enter item number to use/equip, or 'b' to go back.")

    def handle_skills(self, enemy):
        """Manages player's skill usage in combat."""
        if not self.player.learned_skills:
            display_message("You have no skills to use!", 0.5)
            return False # No skill used

        self.player.display_skills()
        print("Enter skill number to use, or 'b' to go back.")
        while True:
            # Use single_char_mode=False for numerical input in skills, as it can be multi-digit
            choice = get_player_input("> ", single_char_mode=False)
            if choice == 'b':
                return False # Player chose to go back
            try:
                skill_index = int(choice) - 1
                if 0 <= skill_index < len(self.player.learned_skills):
                    skill = self.player.learned_skills[skill_index]
                    if self.player.energy >= skill.energy_cost: # Check energy cost
                        self.player.energy -= skill.energy_cost # Deduct energy
                        if skill.name == "Grenade Toss": # Special handling for AoE skill
                            skill.use(self.player, enemies_on_map=self.current_map.entities)
                            # After AoE, re-evaluate if enemy is still alive for combat loop
                            self.current_map.entities = [e for e in self.current_map.entities if e.is_alive()]
                        else:
                            skill.use(self.player, enemy) # Pass player and enemy to the skill effect
                        return True # Skill used, turn consumed
                    else:
                        display_message(f"Not enough energy to use {skill.name}! (Requires {skill.energy_cost} Energy)", 0.5)
                else:
                    display_message("Invalid skill number.", 0.5)
            except ValueError:
                display_message("Invalid input. Please enter a number or 'b'.", 0.5)

    def handle_shop(self):
        """Manages player interaction with the shop."""
        shop_items = self.generate_shop_inventory()
        while True:
            clear_screen()
            print("\n--- Welcome to the Shop-o-Matic! ---")
            print(f"Your Credits: {self.player.credits}")
            print("\n--- Items for Sale ---")
            if not shop_items:
                print("The shop is currently out of stock.")
            for i, item in enumerate(shop_items):
                bonus_info = ""
                if isinstance(item, Weapon):
                    bonus_info = f"(Damage: +{item.damage_bonus})"
                elif isinstance(item, Armor):
                    bonus_info = f"(Defense: +{item.defense_bonus})"
                print(f"{i+1}. {item.name} ({item.item_type}) {bonus_info} - {item.description} | Price: {item.base_value * 2} Credits") # Buy price is higher
            
            print("\n--- Your Inventory (for Selling) ---")
            if not self.player.inventory:
                print("Your inventory is empty.")
            else:
                for i, item in enumerate(self.player.inventory):
                    equipped_status = ""
                    if item == self.player.equipped_weapon or item == self.player.equipped_armor:
                        equipped_status = "(Equipped)"
                    
                    bonus_info = ""
                    if isinstance(item, Weapon):
                        bonus_info = f"(Damage: +{item.damage_bonus})"
                    elif isinstance(item, Armor):
                        bonus_info = f"(Defense: +{item.defense_bonus})"
                    print(f"{i+1}. {item.name} {equipped_status} ({item.item_type}) {bonus_info} - {item.description} | Sell Value: {item.base_value} Credits")

            print("\nWhat do you want to do? (b[uy], s[ell], e[exit shop])")
            choice = get_player_input("> ", ['b', 's', 'e']) # Default to single_char_mode=True

            if choice == 'b':
                self.buy_item(shop_items)
            elif choice == 's':
                self.sell_item()
            elif choice == 'e':
                display_message("Thank you for your business! Farewell.", 0.5)
                break

    def generate_shop_inventory(self):
        """Generates a random set of items for the shop."""
        available_items = [
            HealthPotion(), EnergyCell(), EnergyPack(),
            LaserPistol(), PlasmaRifle(),
            ScrapArmor(), ReinforcedVest()
        ]
        num_items_in_shop = random.randint(3, 6)
        return random.sample(available_items, min(num_items_in_shop, len(available_items)))

    def buy_item(self, shop_items):
        """Handles buying an item from the shop."""
        if not shop_items:
            display_message("The shop has no items to sell.", 0.5)
            return

        print("\nEnter number of item to buy, or 'b' to go back.")
        # Use single_char_mode=False for numerical input in shop, as it can be multi-digit
        buy_choice = get_player_input("> ", single_char_mode=False)
        if buy_choice == 'b':
            return

        try:
            item_index = int(buy_choice) - 1
            if 0 <= item_index < len(shop_items):
                item_to_buy = shop_items[item_index]
                buy_price = item_to_buy.base_value * 2 # Shop sells for double base value
                if self.player.credits >= buy_price:
                    self.player.credits -= buy_price
                    self.player.inventory.append(item_to_buy)
                    shop_items.pop(item_index) # Remove from shop inventory
                    display_message(f"You bought {item_to_buy.name} for {buy_price} Credits!", 0.5)
                else:
                    display_message("Not enough credits!", 0.5)
            else:
                display_message("Invalid item number.", 0.5)
        except ValueError:
            display_message("Invalid input. Please enter a number or 'b'.", 0.5)

    def sell_item(self):
        """Handles selling an item to the shop."""
        if not self.player.inventory:
            display_message("Your inventory is empty, nothing to sell.", 0.5)
            return

        self.player.display_inventory() # This will now show equipped status and bonuses
        print("Enter item number to sell, or 'b' to go back.")
        # Use single_char_mode=False for numerical input in shop, as it can be multi-digit
        sell_choice = get_player_input("> ", single_char_mode=False)
        if sell_choice == 'b':
            return

        try:
            item_index = int(sell_choice) - 1
            if 0 <= item_index < len(self.player.inventory):
                item_to_sell = self.player.inventory[item_index]
                if item_to_sell == self.player.equipped_weapon or item_to_sell == self.player.equipped_armor:
                    display_message("You cannot sell an equipped item! Unequip it first.", 0.5)
                    return
                
                # Prevent selling Energy Crystals for now, as they are a mission item
                if isinstance(item_to_sell, EnergyCrystal):
                    display_message("You cannot sell Energy Crystals! They are vital for your mission.", 0.5)
                    return

                sell_value = item_to_sell.base_value
                self.player.credits += sell_value
                self.player.inventory.pop(item_index)
                display_message(f"You sold {item_to_sell.name} for {sell_value} Credits!", 0.5)
            else:
                display_message("Invalid item number.", 0.5)
        except ValueError:
            display_message("Invalid input. Please enter a number or 'b'.", 0.5)

    def look_around(self):
        """Provides information about the nearest monster."""
        closest_enemy = None
        min_distance = float('inf')

        for enemy in self.current_map.entities:
            if enemy.is_alive():
                distance = math.sqrt((self.player.x - enemy.x)**2 + (self.player.y - enemy.y)**2)
                if distance < min_distance:
                    min_distance = distance
                    closest_enemy = enemy
        
        clear_screen()
        if closest_enemy:
            print("\n--- Nearest Monster ---")
            print(f"Name: {closest_enemy.name} ({closest_enemy.symbol})")
            print(f"HP: {closest_enemy.hp}/{closest_enemy.max_hp}")
            print(f"Attack: {closest_enemy.attack}")
            print(f"Defense: {closest_enemy.defense}")
            print(f"Speed: {closest_enemy.speed}")

            # Determine strength relative to player
            strength_indicator = ""
            player_power = (self.player.attack + self.player.defense + self.player.speed) / 3
            enemy_power = (closest_enemy.attack + closest_enemy.defense + closest_enemy.speed) / 3

            if enemy_power > player_power * 1.5:
                strength_indicator = "(Very Strong)"
            elif enemy_power > player_power * 1.1:
                strength_indicator = "(Strong)"
            elif enemy_power < player_power * 0.7:
                strength_indicator = "(Weak)"
            else:
                strength_indicator = "(Normal)"
            
            print(f"Strength: {strength_indicator}")
            print(f"Distance: {min_distance:.1f} units")
            print("-----------------------")
        else:
            display_message("No enemies detected nearby.", 0.5)
        
        display_message("Press any key to continue...", 0.5)
        _getch()


# --- Game Start ---
if __name__ == "__main__":
    game = Game()
    game.start_game()
