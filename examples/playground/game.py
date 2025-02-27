import random
import asyncio
from enum import Enum, auto
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field

from flock.core import Flock, FlockFactory
from flock.core.logging.formatters.themes import OutputTheme

# Basic game constants
MAP_WIDTH = 20
MAP_HEIGHT = 10
DEFAULT_MODEL = "openai/gpt-4o"  # Can be changed based on availability

# Define the map with # as walls, . as floor, P as player starting position
DEFAULT_MAP = [
    "####################",
    "#P...#.............#",
    "#....#.............#",
    "#....#.............#",
    "#....#.............#",
    "#....#.............#",
    "#....#.............#",
    "#....#.............#",
    "#..................#",
    "####################"
]

class EntityType(Enum):
    PLAYER = auto()
    NPC = auto()
    WALL = auto()

class Direction(Enum):
    UP = auto()
    DOWN = auto()
    LEFT = auto()
    RIGHT = auto()

class Action(Enum):
    MOVE = auto()
    ATTACK = auto()
    TALK = auto()
    WAIT = auto()

@dataclass
class Entity:
    name: str
    type: EntityType
    x: int
    y: int
    char: str
    health: int = 10
    max_health: int = 10
    attack_power: int = 2
    personality: str = ""
    is_alive: bool = True
    
    def __str__(self):
        return f"{self.name} ({self.char}) at ({self.x}, {self.y}) HP: {self.health}/{self.max_health}"

@dataclass
class GameState:
    map_data: List[str]
    entities: List[Entity] = field(default_factory=list)
    turn: int = 0
    player_index: int = 0
    game_log: List[str] = field(default_factory=list)
    max_log_length: int = 10
    
    def add_to_log(self, message: str):
        self.game_log.append(message)
        if len(self.game_log) > self.max_log_length:
            self.game_log.pop(0)
    
    @property
    def player(self) -> Entity:
        return self.entities[self.player_index]

class RoguelikeGame:
    def __init__(self, map_data=None, model=DEFAULT_MODEL):
        self.state = GameState(map_data or DEFAULT_MAP)
        self.flock = Flock(model=model)
        self.initialize_map()
        self.setup_agents()
        
    def initialize_map(self):
        """Parse the map and create entities"""
        # First, find the player starting position and create the player
        player = None
        for y, row in enumerate(self.state.map_data):
            for x, cell in enumerate(row):
                if cell == 'P':
                    player = Entity(
                        name="Player",
                        type=EntityType.PLAYER,
                        x=x,
                        y=y,
                        char="@"
                    )
                    # Replace player position with floor in the map
                    self.state.map_data[y] = row[:x] + '.' + row[x+1:]
                    break
            if player:
                break
        
        if player:
            self.state.entities.append(player)
            self.state.player_index = 0
        
        # Now add some NPCs for testing
        self.add_npc("Friendly Guard", 5, 3, "G", personality="Helpful and protective guard who patrols the area")
        self.add_npc("Suspicious Merchant", 10, 5, "M", personality="Greedy merchant who is always looking for a good deal")
        self.add_npc("Angry Orc", 15, 7, "O", personality="Aggressive orc warrior who hates humans")
    
    def add_npc(self, name, x, y, char, personality=""):
        """Add an NPC to the game"""
        npc = Entity(
            name=name,
            type=EntityType.NPC,
            x=x,
            y=y,
            char=char,
            personality=personality
        )
        self.state.entities.append(npc)
        return npc
    
    def setup_agents(self):
        """Create Flock agents for each NPC"""
        for entity in self.state.entities:
            if entity.type == EntityType.NPC:
                # Create an agent for this NPC
                agent = FlockFactory.create_default_agent(
                    name=f"agent_{entity.name.lower().replace(' ', '_')}",
                    description=f"Agent controlling the actions of {entity.name}, a character in a roguelike game",
                    input="""
                        entity_info: dict | Information about the entity this agent controls
                        entity_position: tuple | Current coordinates (x, y) of the entity
                        nearby_entities: list | List of nearby entities including the player
                        map_view: list | The portion of the map that this entity can see
                        game_log: list | Recent game events
                    """,
                    output="""
                        action: str | The action to take (move, attack, talk, wait)
                        direction: str | Direction for movement (up, down, left, right) if action is move
                        target: str | Target entity name if action is attack or talk
                        message: str | Message to say if action is talk
                        reasoning: str | Explanation of why this action was chosen
                    """,
                    temperature=0.7,
                    enable_rich_tables=True,
                    output_theme=OutputTheme.dracula
                )
                
                # Store the agent in the Flock system
                self.flock.add_agent(agent)
                
                # Attach agent name to entity for reference
                entity.agent_name = agent.name
    
    def get_cell(self, x, y) -> str:
        """Get the cell type at the given coordinates"""
        if 0 <= y < len(self.state.map_data) and 0 <= x < len(self.state.map_data[y]):
            return self.state.map_data[y][x]
        return '#'  # Treat out of bounds as walls
    
    def is_walkable(self, x, y) -> bool:
        """Check if a position is walkable (not a wall or occupied by another entity)"""
        # Check if it's a wall
        if self.get_cell(x, y) == '#':
            return False
        
        # Check if there's an entity there
        for entity in self.state.entities:
            if entity.is_alive and entity.x == x and entity.y == y:
                return False
        
        return True
    
    def get_entity_at(self, x, y) -> Optional[Entity]:
        """Find an entity at the given position"""
        for entity in self.state.entities:
            if entity.is_alive and entity.x == x and entity.y == y:
                return entity
        return None
    
    def get_nearby_entities(self, entity: Entity, distance: int = 5) -> List[Entity]:
        """Get entities within a certain distance of the given entity"""
        nearby = []
        for other in self.state.entities:
            if other != entity and other.is_alive:
                dx = abs(entity.x - other.x)
                dy = abs(entity.y - other.y)
                if dx <= distance and dy <= distance:
                    nearby.append(other)
        return nearby
    
    def get_map_view(self, entity: Entity, vision_range: int = 5) -> List[str]:
        """Get a portion of the map centered on the entity"""
        map_view = []
        for y in range(entity.y - vision_range, entity.y + vision_range + 1):
            row = ""
            for x in range(entity.x - vision_range, entity.x + vision_range + 1):
                # Check if there's an entity here
                entity_here = self.get_entity_at(x, y)
                if entity_here:
                    row += entity_here.char
                else:
                    row += self.get_cell(x, y)
            map_view.append(row)
        return map_view
    
    def move_entity(self, entity: Entity, direction: Direction) -> bool:
        """Move an entity in the given direction if possible"""
        new_x, new_y = entity.x, entity.y
        
        if direction == Direction.UP:
            new_y -= 1
        elif direction == Direction.DOWN:
            new_y += 1
        elif direction == Direction.LEFT:
            new_x -= 1
        elif direction == Direction.RIGHT:
            new_x += 1
        
        if self.is_walkable(new_x, new_y):
            entity.x, entity.y = new_x, new_y
            return True
        return False
    
    def entity_attack(self, attacker: Entity, defender: Entity) -> bool:
        """Handle one entity attacking another"""
        # Check if they're adjacent
        dx = abs(attacker.x - defender.x)
        dy = abs(attacker.y - defender.y)
        
        if dx <= 1 and dy <= 1:  # Adjacent (including diagonals)
            damage = attacker.attack_power
            defender.health -= damage
            self.state.add_to_log(f"{attacker.name} attacks {defender.name} for {damage} damage!")
            
            if defender.health <= 0:
                defender.health = 0
                defender.is_alive = False
                self.state.add_to_log(f"{defender.name} is defeated!")
            return True
        else:
            self.state.add_to_log(f"{attacker.name} can't reach {defender.name}!")
            return False
    
    def entity_talk(self, speaker: Entity, listener: Entity, message: str) -> bool:
        """Handle one entity talking to another"""
        # Check if they're in hearing range (2 tiles)
        dx = abs(speaker.x - listener.x)
        dy = abs(speaker.y - listener.y)
        
        if dx <= 2 and dy <= 2:
            self.state.add_to_log(f"{speaker.name} to {listener.name}: {message}")
            return True
        else:
            self.state.add_to_log(f"{speaker.name} is too far to talk to {listener.name}!")
            return False
    
    async def process_player_action(self, action: Action, **kwargs) -> None:
        """Process an action from the player"""
        player = self.state.player
        
        if action == Action.MOVE:
            direction = kwargs.get('direction')
            success = self.move_entity(player, direction)
            if success:
                self.state.add_to_log(f"Player moved {direction.name.lower()}")
            else:
                self.state.add_to_log("Player couldn't move that way")
        
        elif action == Action.ATTACK:
            target = kwargs.get('target')
            if target:
                self.entity_attack(player, target)
            else:
                self.state.add_to_log("No target to attack")
        
        elif action == Action.TALK:
            target = kwargs.get('target')
            message = kwargs.get('message', "Hello there!")
            if target:
                self.entity_talk(player, target, message)
            else:
                self.state.add_to_log("No one to talk to")
        
        elif action == Action.WAIT:
            self.state.add_to_log("Player waits...")
    
    async def process_npc_turn(self, entity: Entity) -> None:
        """Process a turn for an NPC using its Flock agent"""
        if not entity.is_alive:
            return
        
        # Skip if this entity doesn't have an agent
        if not hasattr(entity, 'agent_name'):
            return
        
        agent = self.flock.registry.get_agent(entity.agent_name)
        if not agent:
            self.state.add_to_log(f"Error: No agent found for {entity.name}")
            return
        
        # Prepare the input for the agent
        nearby_entities = self.get_nearby_entities(entity)
        map_view = self.get_map_view(entity)
        
        # Format nearby entities for the agent
        nearby_info = []
        for other in nearby_entities:
            nearby_info.append({
                "name": other.name,
                "char": other.char,
                "position": (other.x, other.y),
                "health": other.health,
                "type": "Player" if other.type == EntityType.PLAYER else "NPC"
            })
        
        input_data = {
            "entity_info": {
                "name": entity.name,
                "health": entity.health,
                "max_health": entity.max_health,
                "personality": entity.personality
            },
            "entity_position": (entity.x, entity.y),
            "nearby_entities": nearby_info,
            "map_view": map_view,
            "game_log": self.state.game_log
        }
        
        # Run the agent to get the NPC's action
        try:
            result = agent.run(input_data)
            action_str = result.get("action", "wait").lower()
            direction_str = result.get("direction", "").lower()
            target_name = result.get("target", "")
            message = result.get("message", "")
            reasoning = result.get("reasoning", "")
            
            # Find the target entity if specified
            target = None
            if target_name:
                for other in self.state.entities:
                    if other.name.lower() == target_name.lower() and other.is_alive:
                        target = other
                        break
            
            # Process the action
            if action_str == "move":
                direction = None
                if direction_str == "up":
                    direction = Direction.UP
                elif direction_str == "down":
                    direction = Direction.DOWN
                elif direction_str == "left":
                    direction = Direction.LEFT
                elif direction_str == "right":
                    direction = Direction.RIGHT
                
                if direction:
                    success = self.move_entity(entity, direction)
                    if success:
                        self.state.add_to_log(f"{entity.name} moved {direction_str}")
                else:
                    self.state.add_to_log(f"{entity.name} tries to move in an invalid direction")
            
            elif action_str == "attack":
                if target:
                    self.entity_attack(entity, target)
                else:
                    self.state.add_to_log(f"{entity.name} tries to attack but has no target")
            
            elif action_str == "talk":
                if target and message:
                    self.entity_talk(entity, target, message)
                else:
                    self.state.add_to_log(f"{entity.name} tries to talk but has no target or message")
            
            elif action_str == "wait":
                self.state.add_to_log(f"{entity.name} waits...")
            
            else:
                self.state.add_to_log(f"{entity.name} does something unexpected")
        
        except Exception as e:
            self.state.add_to_log(f"Error processing {entity.name}'s turn: {str(e)}")
    
    async def process_game_turn(self) -> None:
        """Process a complete game turn (all entities)"""
        # First process all NPCs
        for entity in self.state.entities:
            if entity.type == EntityType.NPC:
                await self.process_npc_turn(entity)
        
        # Increment the turn counter
        self.state.turn += 1
    
    def render(self) -> str:
        """Render the game state as a string"""
        # Create a copy of the map
        render_map = self.state.map_data.copy()
        
        # Place entities on the map
        for entity in self.state.entities:
            if entity.is_alive:
                # Ensure we don't go out of bounds
                if 0 <= entity.y < len(render_map) and 0 <= entity.x < len(render_map[entity.y]):
                    row = render_map[entity.y]
                    render_map[entity.y] = row[:entity.x] + entity.char + row[entity.x+1:]
        
        # Combine the map and game log
        output = []
        output.append(f"Turn: {self.state.turn}")
        output.append("Map:")
        output.extend(render_map)
        output.append("\nEntities:")
        for entity in self.state.entities:
            if entity.is_alive:
                output.append(f"  {entity}")
        
        output.append("\nGame Log:")
        for log_entry in self.state.game_log:
            output.append(f"  {log_entry}")
        
        return "\n".join(output)

# Simple text-based interface for the game
async def main():
    game = RoguelikeGame()
    player = game.state.player
    running = True
    
    print("Welcome to the LLM-Powered Roguelike!")
    print("Controls: w/a/s/d to move, t to talk, f to attack, q to quit")
    
    while running:
        # Render the game state
        print("\n" + "="*40)
        print(game.render())
        print("="*40)
        
        # Get player input
        action = input("\nEnter action (w/a/s/d=move, t=talk, f=attack, q=quit): ").lower()
        
        if action == 'q':
            running = False
            continue
        
        # Process player action
        if action in ('w', 'a', 's', 'd'):
            direction = None
            if action == 'w':
                direction = Direction.UP
            elif action == 's':
                direction = Direction.DOWN
            elif action == 'a':
                direction = Direction.LEFT
            elif action == 'd':
                direction = Direction.RIGHT
                
            await game.process_player_action(Action.MOVE, direction=direction)
        
        elif action == 't':  # Talk
            # Find nearby entities to talk to
            nearby = game.get_nearby_entities(player, distance=2)
            if not nearby:
                print("No one nearby to talk to.")
                continue
                
            print("Nearby entities:")
            for i, entity in enumerate(nearby):
                print(f"{i+1}. {entity.name}")
                
            try:
                target_idx = int(input("Who do you want to talk to? (number): ")) - 1
                if 0 <= target_idx < len(nearby):
                    message = input("What do you want to say? ")
                    await game.process_player_action(Action.TALK, target=nearby[target_idx], message=message)
            except ValueError:
                print("Invalid input")
        
        elif action == 'f':  # Attack
            # Find nearby entities to attack
            nearby = game.get_nearby_entities(player, distance=1)
            if not nearby:
                print("No one nearby to attack.")
                continue
                
            print("Nearby entities:")
            for i, entity in enumerate(nearby):
                print(f"{i+1}. {entity.name}")
                
            try:
                target_idx = int(input("Who do you want to attack? (number): ")) - 1
                if 0 <= target_idx < len(nearby):
                    await game.process_player_action(Action.ATTACK, target=nearby[target_idx])
            except ValueError:
                print("Invalid input")
        
        else:
            await game.process_player_action(Action.WAIT)
        
        # After player's turn, process NPCs
        await game.process_game_turn()
        
        # Check game over conditions
        if not player.is_alive:
            print("\nGame Over - You were defeated!")
            running = False
        
        # Check if all NPCs are defeated
        npcs_alive = any(e.is_alive and e.type == EntityType.NPC for e in game.state.entities)
        if not npcs_alive:
            print("\nVictory! All enemies defeated!")
            running = False

if __name__ == "__main__":
    asyncio.run(main())