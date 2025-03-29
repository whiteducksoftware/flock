"""Settings editor for the Flock CLI.

This module provides functionality to view, edit, add, and delete
environment variables in the .env file.
"""

import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import math

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from flock.core.util.cli_helper import init_console

# Constants
ENV_FILE = ".env"
ENV_TEMPLATE_FILE = ".env_template"
ENV_PROFILE_PREFIX = ".env_"
DEFAULT_PROFILE_COMMENT = "# Profile: {profile_name}"
SHOW_SECRETS_KEY = "SHOW_SECRETS"
VARS_PER_PAGE_KEY = "VARS_PER_PAGE"
DEFAULT_VARS_PER_PAGE = 20

console = Console()


def settings_editor():
    """Main entry point for the settings editor."""
    while True:
        init_console()
        console.print(Panel("[bold green]Environment Settings Editor[/]"), justify="center")
        
        # Get current profile name
        current_profile = get_current_profile()
        if current_profile:
            console.print(f"Current Profile: [bold cyan]{current_profile}[/]")
        else:
            console.print("No profile detected")

        console.line()
            
        choice = questionary.select(
            "What would you like to do?",
            choices=[
                questionary.Separator(line=" "),
                "View all environment variables",
                "Edit an environment variable",
                "Add a new environment variable",
                "Delete an environment variable",
                questionary.Separator(),
                "Manage environment profiles",
                questionary.Separator(),
                "Toggle show secrets",
                "Change variables per page",
                questionary.Separator(),
                "Back to main menu",
            ],
        ).ask()
        
        if choice == "View all environment variables":
            view_env_variables()
        elif choice == "Edit an environment variable":
            edit_env_variable()
        elif choice == "Add a new environment variable":
            add_env_variable()
        elif choice == "Delete an environment variable":
            delete_env_variable()
        elif choice == "Manage environment profiles":
            manage_profiles()
        elif choice == "Toggle show secrets":
            toggle_show_secrets()
        elif choice == "Change variables per page":
            change_vars_per_page()
        elif choice == "Back to main menu":
            break
        
        if choice != "Back to main menu":
            input("\nPress Enter to continue...")


def view_env_variables(page: int = 1, page_size: Optional[int] = None):
    """View all environment variables with pagination.
    
    Args:
        page: Page number to display
        page_size: Number of variables per page (if None, use the setting in .env)
    """
    env_vars = load_env_file()
    
    # If page_size is not specified, get it from settings
    if page_size is None:
        page_size = get_vars_per_page_setting(env_vars)
    
    # Calculate pagination
    total_vars = len(env_vars)
    total_pages = math.ceil(total_vars / page_size) if total_vars > 0 else 1
    
    # Validate page number
    page = min(max(1, page), total_pages)
    
    start_idx = (page - 1) * page_size
    end_idx = min(start_idx + page_size, total_vars)
    
    # Get current page variables
    current_page_vars = list(env_vars.items())[start_idx:end_idx]
    
    # Check if secrets should be shown
    show_secrets = get_show_secrets_setting(env_vars)
    
    # Create table
    table = Table(title=f"Environment Variables (Page {page}/{total_pages}, {page_size} per page)")
    table.add_column("Name", style="cyan")
    table.add_column("Value", style="green")
    
    # Show secrets status
    secrets_status = "[green]ON[/]" if show_secrets else "[red]OFF[/]"
    init_console()
    console.print(f"Show Secrets: {secrets_status}")
    
    for key, value in current_page_vars:
        # Skip lines that are comments or empty
        if key.startswith('#') or not key:
            continue
            
        # Mask sensitive values if show_secrets is False
        if is_sensitive(key) and not show_secrets:
            masked_value = mask_sensitive_value(value)
            table.add_row(key, masked_value)
        else:
            table.add_row(key, value)
    
    console.print(table)
    
    # Pagination controls with more intuitive shortcuts
    console.print("\nNavigation: ", end="")
    if page > 1:
        console.print("[bold]Previous (p)[/] | ", end="")
    if page < total_pages:
        console.print("[bold]Next (n)[/] | ", end="")
    if show_secrets:
        console.print("[bold]Hide secrets (h)[/] | ", end="")
    else:
        console.print("[bold]Show secrets (s)[/] | ", end="")
    console.print("[bold]Change variables per page (v)[/] | ", end="")
    console.print("[bold]Back (b)[/]")
    
    # Handle navigation
    while True:
        key = input("Enter option: ").lower()
        if key == 'p' and page > 1:
            view_env_variables(page - 1, page_size)
            break
        elif key == 'n' and page < total_pages:
            view_env_variables(page + 1, page_size)
            break
        elif key == 's' and not show_secrets:
            # Confirm showing secrets
            confirm = questionary.confirm("Are you sure you want to show sensitive values?").ask()
            if confirm:
                set_show_secrets_setting(True)
                view_env_variables(page, page_size)
            break
        elif key == 'h' and show_secrets:
            set_show_secrets_setting(False)
            view_env_variables(page, page_size)
            break
        elif key == 'v':
            new_page_size = change_vars_per_page()
            if new_page_size:
                view_env_variables(1, new_page_size)  # Reset to first page with new page size
            break
        elif key == 'b':
            break


def change_vars_per_page():
    """Change the number of variables displayed per page.
    
    Returns:
        The new page size or None if cancelled
    """
    env_vars = load_env_file()
    current_setting = get_vars_per_page_setting(env_vars)
    
    console.print(f"Current variables per page: [cyan]{current_setting}[/]")
    
    # Predefined options plus custom option
    page_size_options = ["10", "20", "30", "50", "Custom", "Cancel"]
    
    choice = questionary.select(
        "Select number of variables per page:",
        choices=page_size_options,
    ).ask()
    
    if choice == "Cancel":
        return None
    
    if choice == "Custom":
        while True:
            try:
                custom_size = questionary.text(
                    "Enter custom page size (5-100):",
                    default=str(current_setting)
                ).ask()
                
                if not custom_size:
                    return None
                
                new_size = int(custom_size)
                if 5 <= new_size <= 100:
                    break
                else:
                    console.print("[yellow]Page size must be between 5 and 100.[/]")
            except ValueError:
                console.print("[yellow]Please enter a valid number.[/]")
    else:
        new_size = int(choice)
    
    # Save the setting
    set_vars_per_page_setting(new_size)
    console.print(f"[green]Variables per page set to {new_size}.[/]")
    
    return new_size


def get_vars_per_page_setting(env_vars: Dict[str, str] = None) -> int:
    """Get the current variables per page setting.
    
    Args:
        env_vars: Optional dictionary of environment variables
        
    Returns:
        Number of variables per page
    """
    if env_vars is None:
        env_vars = load_env_file()
    
    if VARS_PER_PAGE_KEY in env_vars:
        try:
            page_size = int(env_vars[VARS_PER_PAGE_KEY])
            # Ensure the value is within reasonable bounds
            if 5 <= page_size <= 100:
                return page_size
        except ValueError:
            pass
    
    return DEFAULT_VARS_PER_PAGE


def set_vars_per_page_setting(page_size: int):
    """Set the variables per page setting.
    
    Args:
        page_size: Number of variables to display per page
    """
    env_vars = load_env_file()
    env_vars[VARS_PER_PAGE_KEY] = str(page_size)
    save_env_file(env_vars)


def toggle_show_secrets():
    """Toggle the show secrets setting."""
    env_vars = load_env_file()
    current_setting = get_show_secrets_setting(env_vars)
    
    if current_setting:
        console.print("Currently showing sensitive values. Do you want to hide them?")
        confirm = questionary.confirm("Hide sensitive values?").ask()
        if confirm:
            set_show_secrets_setting(False)
            console.print("[green]Sensitive values will now be masked.[/]")
    else:
        console.print("[yellow]Warning:[/] Showing sensitive values can expose sensitive information.")
        confirm = questionary.confirm("Are you sure you want to show sensitive values?").ask()
        if confirm:
            set_show_secrets_setting(True)
            console.print("[green]Sensitive values will now be shown.[/]")


def get_show_secrets_setting(env_vars: Dict[str, str] = None) -> bool:
    """Get the current show secrets setting.
    
    Args:
        env_vars: Optional dictionary of environment variables
        
    Returns:
        True if secrets should be shown, False otherwise
    """
    if env_vars is None:
        env_vars = load_env_file()
    
    if SHOW_SECRETS_KEY in env_vars:
        return env_vars[SHOW_SECRETS_KEY].lower() == 'true'
    
    return False


def set_show_secrets_setting(show_secrets: bool):
    """Set the show secrets setting.
    
    Args:
        show_secrets: Whether to show secrets
    """
    env_vars = load_env_file()
    env_vars[SHOW_SECRETS_KEY] = str(show_secrets)
    save_env_file(env_vars)


def edit_env_variable():
    """Edit an environment variable."""
    # Get list of variables
    env_vars = load_env_file()
    
    if not env_vars:
        console.print("[yellow]No environment variables found to edit.[/]")
        return
    
    # Filter out comments
    variables = [k for k in env_vars.keys() if not k.startswith('#') and k]
    
    # Display variables with selection
    init_console()
    console.print("Select a variable to edit:")
    
    # Let user select a variable to edit
    var_name = questionary.select(
        "Select a variable to edit:",
        choices=variables + ["Cancel"],
    ).ask()
    
    if var_name == "Cancel":
        return
    
    current_value = env_vars[var_name]
    is_sensitive_var = is_sensitive(var_name)
    
    if is_sensitive_var:
        console.print(f"[yellow]Warning:[/] You are editing a sensitive value: {var_name}")
        confirm = questionary.confirm("Are you sure you want to continue?").ask()
        if not confirm:
            return
    
    # Show current value (masked if sensitive and show_secrets is False)
    show_secrets = get_show_secrets_setting(env_vars)
    if is_sensitive_var and not show_secrets:
        console.print(f"Current value: {mask_sensitive_value(current_value)}")
    else:
        console.print(f"Current value: {current_value}")
    
    # Get new value with hint
    console.print("[italic]Enter new value (or leave empty to cancel)[/]")
    new_value = questionary.text("Enter new value:", default=current_value).ask()
    
    if new_value is None:
        console.print("[yellow]Edit cancelled.[/]")
        return
    
    if new_value == "":
        # Confirm if user wants to set an empty value or cancel
        confirm = questionary.confirm("Do you want to set an empty value? Select No to cancel.", default=False).ask()
        if not confirm:
            console.print("[yellow]Edit cancelled.[/]")
            return
    
    if new_value == current_value:
        console.print("[yellow]No changes made.[/]")
        return
    
    # Update the value
    env_vars[var_name] = new_value
    save_env_file(env_vars)
    console.print(f"[green]Updated {var_name} successfully.[/]")


def add_env_variable():
    """Add a new environment variable."""
    env_vars = load_env_file()
    
    console.print("[italic]Enter variable name (or leave empty to go back)[/]")
    
    # Get variable name
    while True:
        var_name = questionary.text("Enter variable name:").ask()
        
        if not var_name:
            # Ask if user wants to go back
            go_back = questionary.confirm("Do you want to go back to the settings menu?", default=True).ask()
            if go_back:
                return
            else:
                console.print("[italic]Please enter a variable name (or leave empty to go back)[/]")
                continue
            
        if var_name in env_vars and not var_name.startswith('#'):
            console.print(f"[yellow]Variable {var_name} already exists. Please use edit instead.[/]")
            continue
            
        break
    
    # Get variable value
    var_value = questionary.text("Enter variable value:").ask()
    
    # Add to env_vars
    env_vars[var_name] = var_value
    save_env_file(env_vars)
    console.print(f"[green]Added {var_name} successfully.[/]")


def delete_env_variable():
    """Delete an environment variable."""
    # Get list of variables
    env_vars = load_env_file()
    
    if not env_vars:
        console.print("[yellow]No environment variables found to delete.[/]")
        return
    
    # Filter out comments
    variables = [k for k in env_vars.keys() if not k.startswith('#') and k]
    
    # Display variables with selection
    init_console()
    console.print("Select a variable to delete:")
    
    # Let user select a variable to delete with hint
    var_name = questionary.select(
        "Select a variable to delete:",
        choices=variables + ["Cancel"],
    ).ask()
    
    if var_name == "Cancel":
        return
    
    # Confirm deletion
    confirm = questionary.confirm(f"Are you sure you want to delete {var_name}?").ask()
    if not confirm:
        console.print("[yellow]Deletion cancelled.[/]")
        return
    
    # Delete the variable
    del env_vars[var_name]
    save_env_file(env_vars)
    console.print(f"[green]Deleted {var_name} successfully.[/]")


def manage_profiles():
    """Manage environment profiles."""
    init_console()
    console.print(Panel("[bold green]Environment Profile Management[/]"), justify="center")
    
    # Get current profile and available profiles
    current_profile = get_current_profile()
    available_profiles = get_available_profiles()
    
    if current_profile:
        console.print(f"Current Profile: [bold cyan]{current_profile}[/]")
    
    if not available_profiles:
        console.print("[yellow]No profiles found.[/]")
    else:
        console.print("Available Profiles:")
        for profile in available_profiles:
            if profile == current_profile:
                console.print(f"  [bold cyan]{profile} (active)[/]")
            else:
                console.print(f"  {profile}")

    console.line()
    
    # Profile management options
    choice = questionary.select(
        "What would you like to do?",
        choices=[
            questionary.Separator(line=" "),
            "Switch to a different profile",
            "Create a new profile",
            "Rename a profile",
            "Delete a profile",
            "Back to settings menu",
        ],
    ).ask()
    
    if choice == "Switch to a different profile":
        switch_profile()
    elif choice == "Create a new profile":
        create_profile()
    elif choice == "Rename a profile":
        rename_profile()
    elif choice == "Delete a profile":
        delete_profile()


def switch_profile():
    """Switch to a different environment profile."""
    available_profiles = get_available_profiles()
    current_profile = get_current_profile()
    
    if not available_profiles:
        console.print("[yellow]No profiles available to switch to.[/]")
        return
    
    # Remove current profile from the list to avoid switching to the same profile
    selectable_profiles = [p for p in available_profiles if p != current_profile]
    
    if not selectable_profiles:
        console.print("[yellow]No other profiles available to switch to.[/]")
        return
    
    target_profile = questionary.select(
        "Select a profile to switch to:",
        choices=selectable_profiles + ["Cancel"],
    ).ask()
    
    if target_profile == "Cancel":
        return
    
    # Confirm switch
    confirm = questionary.confirm(f"Are you sure you want to switch to the {target_profile} profile?").ask()
    if not confirm:
        return
    
    # Backup current .env file
    backup_env_file()
    
    # Copy selected profile to .env
    source_file = f"{ENV_PROFILE_PREFIX}{target_profile}"
    if os.path.exists(source_file):
        shutil.copy2(source_file, ENV_FILE)
        console.print(f"[green]Switched to {target_profile} profile successfully.[/]")
    else:
        console.print(f"[red]Error: Could not find profile file {source_file}.[/]")


def create_profile():
    """Create a new environment profile."""
    profile_name = questionary.text("Enter new profile name:").ask()
    
    if not profile_name:
        console.print("[yellow]Profile name cannot be empty.[/]")
        return
    
    # Check if profile already exists
    target_file = f"{ENV_PROFILE_PREFIX}{profile_name}"
    if os.path.exists(target_file):
        console.print(f"[yellow]Profile {profile_name} already exists.[/]")
        return
    
    # Determine source file - use current .env or template
    source_choices = ["Current environment (.env)", ".env_template"]
    if os.path.exists(ENV_TEMPLATE_FILE):
        source_choices.append(ENV_TEMPLATE_FILE)
    
    source_choice = questionary.select(
        "Create profile based on:",
        choices=source_choices + ["Cancel"],
    ).ask()
    
    if source_choice == "Cancel":
        return
    
    source_file = ENV_FILE if source_choice == "Current environment (.env)" else ENV_TEMPLATE_FILE
    
    if not os.path.exists(source_file):
        console.print(f"[red]Error: Source file {source_file} not found.[/]")
        return
    
    # Create new profile file
    try:
        # Copy source file
        shutil.copy2(source_file, target_file)
        
        # Add profile header if it doesn't exist
        with open(target_file, 'r') as file:
            content = file.read()
        
        if not content.startswith("# Profile:"):
            with open(target_file, 'w') as file:
                profile_header = DEFAULT_PROFILE_COMMENT.format(profile_name=profile_name)
                file.write(f"{profile_header}\n{content}")
        
        console.print(f"[green]Created {profile_name} profile successfully.[/]")
    except Exception as e:
        console.print(f"[red]Error creating profile: {str(e)}[/]")


def rename_profile():
    """Rename an existing profile."""
    available_profiles = get_available_profiles()
    current_profile = get_current_profile()
    
    if not available_profiles:
        console.print("[yellow]No profiles available to rename.[/]")
        return
    
    # Let user select a profile to rename
    profile_to_rename = questionary.select(
        "Select a profile to rename:",
        choices=available_profiles + ["Cancel"],
    ).ask()
    
    if profile_to_rename == "Cancel":
        return
    
    # Get new name
    new_name = questionary.text("Enter new profile name:").ask()
    
    if not new_name:
        console.print("[yellow]New profile name cannot be empty.[/]")
        return
    
    if new_name in available_profiles:
        console.print(f"[yellow]Profile {new_name} already exists.[/]")
        return
    
    # Rename profile file
    source_file = f"{ENV_PROFILE_PREFIX}{profile_to_rename}"
    target_file = f"{ENV_PROFILE_PREFIX}{new_name}"
    
    try:
        # Read content of the source file
        with open(source_file, 'r') as file:
            content = file.readlines()
        
        # Update profile header if it exists
        if content and content[0].startswith("# Profile:"):
            content[0] = DEFAULT_PROFILE_COMMENT.format(profile_name=new_name) + "\n"
        
        # Write to new file
        with open(target_file, 'w') as file:
            file.writelines(content)
        
        # Remove old file
        os.remove(source_file)
        
        # If this was the current profile, update .env as well
        if profile_to_rename == current_profile:
            with open(ENV_FILE, 'r') as file:
                content = file.readlines()
            
            if content and content[0].startswith("# Profile:"):
                content[0] = DEFAULT_PROFILE_COMMENT.format(profile_name=new_name) + "\n"
            
            with open(ENV_FILE, 'w') as file:
                file.writelines(content)
        
        console.print(f"[green]Renamed {profile_to_rename} to {new_name} successfully.[/]")
    except Exception as e:
        console.print(f"[red]Error renaming profile: {str(e)}[/]")


def delete_profile():
    """Delete an existing profile."""
    available_profiles = get_available_profiles()
    current_profile = get_current_profile()
    
    if not available_profiles:
        console.print("[yellow]No profiles available to delete.[/]")
        return
    
    # Let user select a profile to delete
    profile_to_delete = questionary.select(
        "Select a profile to delete:",
        choices=available_profiles + ["Cancel"],
    ).ask()
    
    if profile_to_delete == "Cancel":
        return
    
    # Confirm deletion
    confirm = questionary.confirm(
        f"Are you sure you want to delete the {profile_to_delete} profile? This cannot be undone."
    ).ask()
    
    if not confirm:
        return
    
    # Delete profile file
    profile_file = f"{ENV_PROFILE_PREFIX}{profile_to_delete}"
    
    try:
        os.remove(profile_file)
        
        # Warn if deleting the current profile
        if profile_to_delete == current_profile:
            console.print(
                f"[yellow]Warning: You deleted the currently active profile. "
                f"The .env file still contains those settings but is no longer marked as a profile.[/]"
            )
            
            # Remove profile header from .env
            with open(ENV_FILE, 'r') as file:
                content = file.readlines()
            
            if content and content[0].startswith("# Profile:"):
                content = content[1:]
                with open(ENV_FILE, 'w') as file:
                    file.writelines(content)
        
        console.print(f"[green]Deleted {profile_to_delete} profile successfully.[/]")
    except Exception as e:
        console.print(f"[red]Error deleting profile: {str(e)}[/]")


def is_sensitive(key: str) -> bool:
    """Check if a variable is considered sensitive.
    
    Args:
        key: The variable name
        
    Returns:
        True if sensitive, False otherwise
    """
    sensitive_patterns = ['key', 'token', 'secret', 'password', 'api', 'pat']
    key_lower = key.lower()
    return any(pattern in key_lower for pattern in sensitive_patterns)


def mask_sensitive_value(value: str) -> str:
    """Mask a sensitive value.
    
    Args:
        value: The sensitive value
        
    Returns:
        Masked value
    """
    if not value:
        return value
    
    if len(value) <= 4:
        return "••••"
    
    # Show first 2 and last 2 characters
    return value[:2] + "•" * (len(value) - 4) + value[-2:]


def get_current_profile() -> Optional[str]:
    """Get the name of the current active profile.
    
    Returns:
        Profile name or None if no profile is active
    """
    if not os.path.exists(ENV_FILE):
        return None
    
    try:
        with open(ENV_FILE, 'r') as file:
            first_line = file.readline().strip()
            
        if first_line.startswith("# Profile:"):
            return first_line.replace("# Profile:", "").strip()
    except Exception:
        pass
    
    return None


def get_available_profiles() -> List[str]:
    """Get a list of available profiles.
    
    Returns:
        List of profile names
    """
    profiles = []
    
    for file in os.listdir():
        if file.startswith(ENV_PROFILE_PREFIX):
            profile_name = file[len(ENV_PROFILE_PREFIX):]
            profiles.append(profile_name)
    
    return profiles


def backup_env_file():
    """Create a backup of the current .env file."""
    if not os.path.exists(ENV_FILE):
        return
    
    backup_file = f"{ENV_FILE}.bak"
    shutil.copy2(ENV_FILE, backup_file)


def load_env_file() -> Dict[str, str]:
    """Load the .env file into a dictionary.
    
    Returns:
        Dictionary of environment variables
    """
    env_vars = {}
    
    if not os.path.exists(ENV_FILE):
        console.print(f"[yellow]Warning: {ENV_FILE} file not found.[/]")
        return env_vars
    
    try:
        with open(ENV_FILE, 'r') as file:
            lines = file.readlines()
            
        # Process each line
        for line in lines:
            line = line.strip()
            
            # Skip empty lines
            if not line:
                env_vars[""] = ""
                continue
            
            # Handle comments
            if line.startswith('#'):
                env_vars[line] = ""
                continue
            
            # Handle regular variables
            if '=' in line:
                key, value = line.split('=', 1)
                env_vars[key] = value
            else:
                # Handle lines without equals sign
                env_vars[line] = ""
                
    except Exception as e:
        console.print(f"[red]Error loading .env file: {str(e)}[/]")
    
    return env_vars


def save_env_file(env_vars: Dict[str, str]):
    """Save environment variables back to the .env file.
    
    Args:
        env_vars: Dictionary of environment variables
    """
    # Create backup
    backup_env_file()
    
    try:
        with open(ENV_FILE, 'w') as file:
            for key, value in env_vars.items():
                if key.startswith('#'):
                    # Write comments as is
                    file.write(f"{key}\n")
                elif not key:
                    # Write empty lines
                    file.write("\n")
                else:
                    # Write regular variables
                    file.write(f"{key}={value}\n")
                    
        console.print("[green]Settings saved successfully.[/]")
    except Exception as e:
        console.print(f"[red]Error saving .env file: {str(e)}[/]")
