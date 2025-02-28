import random
import asyncio
from enum import Enum, auto
from typing import List, Optional
from dataclasses import dataclass, field
from itertools import cycle

from flock.core import Flock, FlockFactory
from flock.core.logging.formatters.themes import OutputTheme

# Import rich components
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt
from pydantic import BaseModel

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
    


    
class Map(BaseModel):
    width: int
    height: int
    data: List[str]
    


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
    chat_history: List[str] = field(default_factory=list)
    is_alive: bool = True
    color: str = "white"   # New attribute for the entity's color

    def __str__(self):
        return f"[{self.color}]{self.name}[/{self.color}] ({self.char}) at ({self.x}, {self.y}) HP: {self.health}/{self.max_health}"

def format_entity(entity: Entity) -> str:
    """Helper to wrap an entity's name in rich markup based on its color."""
    return f"[{entity.color}]{entity.name}[/{entity.color}]"

class Scene(BaseModel):
    name: str
    description: str
    entities: List[Entity]
    map_data: Map
    turn: int
    player_index: int

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
        self.console = Console()
        # Cycle through a list of colors for NPCs.
        self.npc_color_cycle = cycle([
            "red", "green", "blue", "magenta", "cyan", "yellow",
            "bright_green", "bright_blue", "bright_magenta", "bright_cyan"
        ])
        self.initialize_map()
        self.setup_agents()

    def initialize_map(self):
        """Parse the map and create entities."""
        player = None
        for y, row in enumerate(self.state.map_data):
            for x, cell in enumerate(row):
                if cell == 'P':
                    player = Entity(
                        name="Player",
                        type=EntityType.PLAYER,
                        x=x,
                        y=y,
                        char="@",
                        color="bright_white"  # Set player color
                    )
                    # Replace the player starting position with floor.
                    self.state.map_data[y] = row[:x] + '.' + row[x+1:]
                    break
            if player:
                break

        if player:
            self.state.entities.append(player)
            self.state.player_index = 0

        # Add NPCs with unique colors.
        self.add_npc("Edgar, Friendly Guard", 5, 3, "G", personality="Helpful and protective guard who patrols the area")
        self.add_npc("Malon, Suspicious Merchant", 10, 5, "M", personality="Greedy merchant who is always looking for a good deal")
        self.add_npc("Oshram, Angry Orc", 15, 7, "O", personality="Aggressive orc warrior who hates humans, especially merchants")

    def add_npc(self, name, x, y, char, personality=""):
        """Add an NPC with a unique color."""
        npc = Entity(
            name=name,
            type=EntityType.NPC,
            x=x,
            y=y,
            char=char,
            personality=personality,
            color=next(self.npc_color_cycle)
        )
        self.state.entities.append(npc)
        return npc

    def setup_agents(self):
        """Create Flock agents for each NPC."""
        for entity in self.state.entities:
            if entity.type == EntityType.NPC:
                agent = FlockFactory.create_default_agent(
                    name=f"agent_{entity.name.lower().replace(' ', '_')}",
                    description=f"You are {entity.name}, a character in a roguelike game. Never break character.",
                    input="""
                        myself: Entity | Your own entity information,
                        nearby_entities: list | List of nearby entities including the player,
                        map_view: list | The portion of the map that this entity can see,
                        game_log: list | Recent game events
                    """,
                    output="""
                        action: Literal["move", "attack", "talk", "wait"] | The action to take. talk has a range of 2 tiles,
                        direction: Literal["up", "down", "left", "right"] | Direction for movement if action is move,
                        target: str | Target entity name if action is attack or talk,
                        message: str | Message to say if action is talk,
                        reasoning: str | Short explanation of why this action was chosen
                    """,
                    temperature=0.7,
                    no_output=True
                )
                self.flock.add_agent(agent)
                entity.agent_name = agent.name

    def get_cell(self, x, y) -> str:
        if 0 <= y < len(self.state.map_data) and 0 <= x < len(self.state.map_data[y]):
            return self.state.map_data[y][x]
        return '#'

    def is_walkable(self, x, y) -> bool:
        if self.get_cell(x, y) == '#':
            return False
        for entity in self.state.entities:
            if entity.is_alive and entity.x == x and entity.y == y:
                return False
        return True

    def get_entity_at(self, x, y) -> Optional[Entity]:
        for entity in self.state.entities:
            if entity.is_alive and entity.x == x and entity.y == y:
                return entity
        return None

    def get_nearby_entities(self, entity: Entity, distance: int = 5) -> List[Entity]:
        nearby = []
        for other in self.state.entities:
            if other != entity and other.is_alive:
                dx = abs(entity.x - other.x)
                dy = abs(entity.y - other.y)
                if dx <= distance and dy <= distance:
                    nearby.append(other)
        return nearby

    def get_map_view(self, entity: Entity, vision_range: int = 5) -> List[str]:
        """Get a portion of the map centered on the entity (plain view for LLM input)."""
        map_view = []
        for y in range(entity.y - vision_range, entity.y + vision_range + 1):
            row = ""
            for x in range(entity.x - vision_range, entity.x + vision_range + 1):
                entity_here = self.get_entity_at(x, y)
                if entity_here:
                    row += entity_here.char
                else:
                    row += self.get_cell(x, y)
            map_view.append(row)
        return map_view

    def move_entity(self, entity: Entity, direction: Direction) -> bool:
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
        dx = abs(attacker.x - defender.x)
        dy = abs(attacker.y - defender.y)
        if dx <= 1 and dy <= 1:
            damage = attacker.attack_power
            defender.health -= damage
            self.state.add_to_log(f"{format_entity(attacker)} attacks {format_entity(defender)} for {damage} damage!")
            if defender.health <= 0:
                defender.health = 0
                defender.is_alive = False
                self.state.add_to_log(f"{format_entity(defender)} is defeated!")
            return True
        else:
            self.state.add_to_log(f"{format_entity(attacker)} can't reach {format_entity(defender)}!")
            return False

    def entity_talk(self, speaker: Entity, listener: Entity, message: str) -> bool:
        dx = abs(speaker.x - listener.x)
        dy = abs(speaker.y - listener.y)
        if dx <= 2 and dy <= 2:
            self.state.add_to_log(f"{format_entity(speaker)} to {format_entity(listener)}: {message}")
            listener.chat_history.append(f"{format_entity(speaker)}: {message}")
            return True
        else:
            self.state.add_to_log(f"{format_entity(speaker)} is too far to talk to {format_entity(listener)}!")
            return False

    async def process_player_action(self, action: Action, **kwargs) -> None:
        player = self.state.player
        if action == Action.MOVE:
            direction = kwargs.get('direction')
            success = self.move_entity(player, direction)
            if success:
                self.state.add_to_log(f"{format_entity(player)} moved {direction.name.lower()}")
            else:
                self.state.add_to_log(f"{format_entity(player)} couldn't move that way")
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
            self.state.add_to_log(f"{format_entity(player)} waits...")

    async def process_npc_turn(self, entity: Entity) -> None:
        if not entity.is_alive:
            return
        if not hasattr(entity, 'agent_name'):
            return

        agent = self.flock.registry.get_agent(entity.agent_name)
        if not agent:
            self.state.add_to_log(f"Error: No agent found for {format_entity(entity)}")
            return

        nearby_entities = self.get_nearby_entities(entity)
        map_view = self.get_map_view(entity)
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
            "myself": entity,
            "nearby_entities": nearby_info,
            "map_view": map_view,
            "game_log": self.state.game_log
        }
        try:
            result = await agent.run_async(input_data)
            action_str = result.get("action", "wait").lower()
            direction_str = result.get("direction", "").lower()
            target_name = result.get("target", "")
            message = result.get("message", "")
            reasoning = result.get("reasoning", "")
            #self.state.add_to_log(f"{format_entity(entity)} thinks: {reasoning}")

            target = None
            if target_name:
                for other in self.state.entities:
                    if other.name.lower() == target_name.lower() and other.is_alive:
                        target = other
                        break

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
                        self.state.add_to_log(f"{format_entity(entity)} moved {direction_str}")
                else:
                    self.state.add_to_log(f"{format_entity(entity)} tries to move in an invalid direction")

            elif action_str == "attack":
                if target:
                    self.entity_attack(entity, target)
                else:
                    self.state.add_to_log(f"{format_entity(entity)} tries to attack but has no target")
            elif action_str == "talk":
                if target and message:
                    self.entity_talk(entity, target, message)
                else:
                    self.state.add_to_log(f"{format_entity(entity)} tries to talk but has no target or message")
            elif action_str == "wait":
                self.state.add_to_log(f"{format_entity(entity)} waits...")
            else:
                self.state.add_to_log(f"{format_entity(entity)} does something unexpected")
        except Exception as e:
            self.state.add_to_log(f"Error processing {format_entity(entity)}'s turn: {str(e)}")

    async def process_game_turn(self) -> None:
        for entity in self.state.entities:
            if entity.type == EntityType.NPC:
                await self.process_npc_turn(entity)
        self.state.turn += 1

    def render(self):
        """Render the game state using rich panels and tables with colored entities."""
        # Create a copy of the map and place entities with colored characters.
        render_map = self.state.map_data.copy()
        for entity in self.state.entities:
            if entity.is_alive:
                if 0 <= entity.y < len(render_map) and 0 <= entity.x < len(render_map[entity.y]):
                    row = render_map[entity.y]
                    colored_char = f"[{entity.color}]{entity.char}[/{entity.color}]"
                    render_map[entity.y] = row[:entity.x] + colored_char + row[entity.x+1:]

        header = Panel(f"[bold green]Turn: {self.state.turn}[/bold green]", title="Game Status")
        map_str = "\n".join(render_map)
        map_panel = Panel(map_str, title="Map", style="blue")

        # Build the entities table with colored names and characters.
        entity_table = Table(title="Entities", header_style="bold magenta")
        entity_table.add_column("Name", justify="left")
        entity_table.add_column("Char", justify="center")
        entity_table.add_column("Position", justify="center")
        entity_table.add_column("HP", justify="center")
        for entity in self.state.entities:
            if entity.is_alive:
                entity_table.add_row(
                    f"[{entity.color}]{entity.name}[/{entity.color}]",
                    f"[{entity.color}]{entity.char}[/{entity.color}]",
                    f"({entity.x}, {entity.y})",
                    f"{entity.health}/{entity.max_health}"
                )

        log_text = "\n".join(self.state.game_log) if self.state.game_log else "No logs yet."
        log_panel = Panel(log_text, title="Game Log", style="yellow")

        return Group(header, map_panel, entity_table, log_panel)

# Simple text-based interface using rich for beautiful output.
async def main():
    game = RoguelikeGame()
    player = game.state.player
    running = True
    game.console.print("[bold underline green]Welcome to the LLM-Powered Roguelike![/bold underline green]")
    game.console.print("Controls: [bold]w/a/s/d[/bold] to move, [bold]t[/bold] to talk, [bold]f[/bold] to attack, [bold]q[/bold] to quit")
    
    while running:
        game.console.clear()
        game.console.print("="*40)
        game.console.print(game.render())
        game.console.print("="*40)
        
        action = Prompt.ask("\nEnter action (w/a/s/d=move, t=talk, f=attack, q=quit)").lower()
        
        if action == 'q':
            running = False
            continue
        
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
        
        elif action == 't':
            nearby = game.get_nearby_entities(player, distance=2)
            if not nearby:
                game.console.print("[red]No one nearby to talk to.[/red]")
                await asyncio.sleep(1)
                continue
            game.console.print("Nearby entities:")
            for i, entity in enumerate(nearby):
                game.console.print(f"{i+1}. [{entity.color}]{entity.name}[/{entity.color}]")
            try:
                target_idx = int(Prompt.ask("Who do you want to talk to? (number)")) - 1
                if 0 <= target_idx < len(nearby):
                    message = Prompt.ask("What do you want to say?")
                    await game.process_player_action(Action.TALK, target=nearby[target_idx], message=message)
            except ValueError:
                game.console.print("[red]Invalid input[/red]")
        
        elif action == 'f':
            nearby = game.get_nearby_entities(player, distance=1)
            if not nearby:
                game.console.print("[red]No one nearby to attack.[/red]")
                await asyncio.sleep(1)
                continue
            game.console.print("Nearby entities:")
            for i, entity in enumerate(nearby):
                game.console.print(f"{i+1}. [{entity.color}]{entity.name}[/{entity.color}]")
            try:
                target_idx = int(Prompt.ask("Who do you want to attack? (number)")) - 1
                if 0 <= target_idx < len(nearby):
                    await game.process_player_action(Action.ATTACK, target=nearby[target_idx])
            except ValueError:
                game.console.print("[red]Invalid input[/red]")
        
        else:
            await game.process_player_action(Action.WAIT)
        
        await game.process_game_turn()
        
        if not player.is_alive:
            game.console.print("\n[bold red]Game Over - You were defeated![/bold red]")
            running = False
        
        npcs_alive = any(e.is_alive and e.type == EntityType.NPC for e in game.state.entities)
        if not npcs_alive:
            game.console.print("\n[bold green]Victory! All enemies defeated![/bold green]")
            running = False

if __name__ == "__main__":
    asyncio.run(main())
