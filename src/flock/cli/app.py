from textual.app import App, ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Footer, Header, Static, Tree

from flock.cli.agent_input_form import AgentInputForm


class AgentManagementApp(App):
    CSS = """
    Screen {
        layout: vertical;
    }
    #main-container {
        layout: horizontal;
        height: 1fr;
    }
    .sidebar {
        width: 30%;
        border: tall white;
        padding: 1 2;
    }
    .main-view {
        width: 70%;
        border: tall white;
        padding: 1 2;
    }
    #sidebar-title, #main-title {
        margin-bottom: 1;
        text-style: bold underline;
    }
    Input {
        border: round #666;
    }
    Button {
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="main-container"):
            # Sidebar: Tree view for categories and agents
            with Vertical(classes="sidebar"):
                yield Static("Agents", id="sidebar-title")
                self.tree_widget = Tree("Categories and Agents")
                yield self.tree_widget
            # Main view: Form for agent properties
            with Vertical(classes="main-view"):
                yield AgentInputForm()
        yield Footer()

    def on_mount(self) -> None:
        # Build the tree structure with categories and agents.
        root = self.tree_widget.root
        # Create sample categories.
        network_category = root.add("Network Agents")
        database_category = root.add("Database Agents")
        # Add agents to the categories with associated dummy data.
        network_category.add_leaf("Agent A", data={"id": "agent_a"})
        network_category.add_leaf("Agent B", data={"id": "agent_b"})
        database_category.add_leaf("Agent C", data={"id": "agent_c"})
        database_category.add_leaf("Agent D", data={"id": "agent_d"})
        # Expand all nodes by calling expand_all() on the root node.
        self.tree_widget.root.expand_all()

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        node = event.node
