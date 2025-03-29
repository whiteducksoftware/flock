# CLI System Specification

## Overview

The Command Line Interface (CLI) system provides an interactive terminal-based user interface for the Flock framework. It allows users to manage agents, flocks, settings, and other aspects of the framework through a console application.

## Components

### 1. Main CLI Application

- **Entry Point**: `src/flock/__init__.py`
- **Purpose**: Provides the main menu and dispatches to specific CLI modules
- **Implementation**: Uses Rich for formatting and Questionary for interactive prompts
- **Main Menu Options**:
  - Load a flock file
  - Theme builder
  - Settings editor
  - Advanced mode (future)
  - Web server (future)
  - Release notes
  - Exit

### 2. Settings Editor

- **Module**: `src/flock/cli/settings.py`
- **Purpose**: View, edit, add, and delete environment variables in the `.env` file
- **Features**:
  - Pagination of environment variables
  - Masking of sensitive values (API keys, tokens, etc.)
  - Environment profile management (dev, test, prod, etc.)
  - Configurable variables per page

#### 2.1 Environment Variables Management

- View all environment variables with pagination
- Edit existing variables with proper validation
- Add new variables
- Delete existing variables
- Masking sensitive values (API keys, passwords, tokens)
- Toggle visibility of sensitive values

#### 2.2 Environment Profile System

- Multiple environment profiles (.env_dev, .env_prod, etc.)
- Active profile stored as .env
- Profile name stored as comment in first line: `# Profile: name`
- Profile operations:
  - Switch between profiles
  - Create new profiles
  - Rename existing profiles
  - Delete profiles
  - Safe backup system before profile operations

#### 2.3 Settings Configuration

- Configurable settings stored in the .env file:
  - `SHOW_SECRETS`: Controls visibility of sensitive values
  - `VARS_PER_PAGE`: Controls pagination size (5-100 variables)

### 3. Theme Builder

- **Module**: `flock/core/logging/formatters/theme_builder`
- **Purpose**: Customize the visual appearance of the CLI
- **Features**: [To be expanded]

### 4. Flock Loader

- **Module**: `src/flock/cli/load_flock.py`
- **Purpose**: Load and execute .flock files
- **Features**: [To be expanded]

## Design Principles

1. **User-Friendly Interface**: Clear navigation, intuitive controls, and helpful feedback
2. **Data Safety**: Backup operations before destructive actions, confirmation prompts
3. **Efficient Workflow**: Keyboard shortcuts, pagination, customizable settings
4. **Security Conscious**: Masking of sensitive values, confirmation for showing secrets
5. **Consistent UI**: Using Rich for formatted output, Questionary for inputs

## UI Components

### Panels and Tables

- **Rich Panels**: Used for section headers and menus
- **Rich Tables**: Used for displaying structured data
- **Color Coding**: Green for success, yellow for warnings, red for errors

### Interactive Elements

- **Selection Menus**: Using Questionary.select for menu navigation
- **Text Inputs**: Using Questionary.text for data entry
- **Confirmations**: Using Questionary.confirm for destructive actions

## Navigation System

- **Main Menu**: Select from multiple modules
- **Module Menus**: Select operations within a module
- **Keyboard Shortcuts**: Single-key commands for common operations
- **Back Button**: Return to previous screen
- **Cancel Option**: Abort current operation

## File Operations

- **Load Operations**: Reading from the .env file and profile files
- **Save Operations**: Writing to the .env file with proper backup
- **Backup System**: Creating .env.bak before destructive operations
- **Profile Files**: Managing .env_[profile_name] files

## Future Enhancements

1. **Command History**: Remember previous commands and inputs
2. **Autocomplete**: Tab completion for variable names and commands
3. **Search/Filter**: Find specific variables by name or value
4. **Import/Export**: Support for importing/exporting profiles
5. **Template System**: Pre-defined templates for common setups

## Implementation Status

The CLI system is currently being implemented with the Settings Editor being the first major component completed. Additional components will be developed according to the project roadmap. 