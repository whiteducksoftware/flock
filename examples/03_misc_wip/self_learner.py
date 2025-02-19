import os
import json
import ast
import cloudpickle  # Allows function serialization
from functools import wraps
from typing import Callable, Dict
import litellm  # LLM wrapper for inference

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TOOL_DB_PATH = "tools.json"

# Track function calls
_num_calls = {}

def track_num_calls(func):
    """Decorator to track function calls dynamically."""
    func_name = func.__name__

    @wraps(func)
    def wrapped_func(*args, **kwargs):
        _num_calls[func_name] = _num_calls.get(func_name, 0) + 1
        return func(*args, **kwargs)

    return wrapped_func

class Tool:
    """Minimal tool class for execution."""
    def __init__(self, name: str, description: str, func_bytes=None):
        self.name = name
        self.description = description
        self.func = self._load_func() if func_bytes is None else self._deserialize_func(func_bytes)

    def _load_func(self) -> Callable:
        """Compiles and returns the function from the generated code."""
        local_scope = {}
        exec(self.code, {}, local_scope)  # Execute in an isolated scope
        func_name = next(iter(local_scope))  # Get the function name
        return track_num_calls(local_scope[func_name])

    def _serialize_func(self) -> str:
        """Serializes the function correctly."""
        return cloudpickle.dumps(self.func).hex()

    def _deserialize_func(self, func_bytes: str) -> Callable:
        """Deserializes the function correctly."""
        return cloudpickle.loads(bytes.fromhex(func_bytes))

    def run(self, *args, **kwargs):
        """Executes the tool's function."""
        return self.func(*args, **kwargs)

    def serialize(self):
        """Serializes the tool into a JSON-compatible format."""
        return {
            "name": self.name,
            "description": self.description,
            "code": self.code,
            "func_bytes": self._serialize_func(),  # Serialize function
        }

    @staticmethod
    def deserialize(data):
        """Deserializes a tool from JSON-compatible format."""
        return Tool(
            name=data["name"],
            description=data["description"],
            code=data["code"],
            func_bytes=data["func_bytes"]
        )

class ToolManager:
    """Manages tools and persists them in a JSON file."""
    def __init__(self, db_path=TOOL_DB_PATH):
        self.db_path = db_path
        self.tools: Dict[str, Tool] = self._load_tools()

    def _load_tools(self) -> Dict[str, Tool]:
        """Loads tools from the JSON database."""
        if not os.path.exists(self.db_path):
            return {}

        with open(self.db_path, "r") as f:
            tool_data = json.load(f)

        return {name: Tool.deserialize(data) for name, data in tool_data.items()}

    def _save_tools(self):
        """Saves tools to the JSON database."""
        with open(self.db_path, "w") as f:
            json.dump({name: tool.serialize() for name, tool in self.tools.items()}, f, indent=4)

    def add_tool(self, tool: Tool):
        """Adds a tool and saves it."""
        self.tools[tool.name] = tool
        self._save_tools()

    def retrieve_best_tool(self, query: str) -> Tool:
        """Finds the best matching tool based on query substring search."""
        for tool in self.tools.values():
            if query.lower() in tool.description.lower():
                return tool
        return None

class Agent:
    """Core agent that generates, retrieves, and executes tools."""
    def __init__(self, tool_manager: ToolManager, model="gpt-4-turbo"):
        self.tool_manager = tool_manager
        self.model = model

    def run(self, query: str, *args, **kwargs):
        """Finds or generates a tool and executes it."""
        tool = self.tool_manager.retrieve_best_tool(query)
        if tool:
            print(f"Using existing tool: {tool.name} - {tool.description}")
            return tool.run(*args, **kwargs)

        print(f"No tool found. Generating a new one for: {query}")
        new_tool = self.generate_tool(query)
        self.tool_manager.add_tool(new_tool)
        return new_tool.run(*args, **kwargs)

    def generate_tool(self, query: str) -> Tool:
        """Uses an LLM to generate a Python function as a new tool."""
        prompt = f"""
        Generate a standalone Python function for the following task:
        "{query}"
        The function should be clear, modular, and include a one-line docstring.
        Output only the function code.
        """

        response = litellm.completion(
            model=self.model,
            messages=[{"role": "system", "content": "You are an AI that generates reusable Python functions."},
                      {"role": "user", "content": prompt}],
            api_key=OPENAI_API_KEY
        )["choices"][0]["message"]["content"]

        # Extract function code
        func_code = self.extract_function_code(response)
        func_name = self.get_function_name(func_code)

        return Tool(func_name, query, func_code)

    def extract_function_code(self, text: str) -> str:
        """Extracts Python function code from LLM response."""
        code_block = text.split("```python")[-1].split("```")[0].strip()
        return code_block if "def " in code_block else None

    def get_function_name(self, code: str) -> str:
        """Parses the function name from the generated code."""
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                return node.name
        return "generated_function"

# Example usage
if __name__ == "__main__":
    tool_manager = ToolManager()
    agent = Agent(tool_manager)

    #print(agent.run("Get the last N paper on arxiv as a pdf that are about LLMs", 3))  # Generates & runs new tool
    print(agent.run("Calculate the area of a circle", 10))  # Uses the saved tool
