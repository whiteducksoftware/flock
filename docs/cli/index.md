# 🖥️ Flock CLI

The Flock Command Line Interface (CLI) provides an **interactive terminal-based user interface** for managing and interacting with the Flock framework. The CLI is designed to make it **super easy** to configure, run, and monitor Flock applications.

## ✨ Features

- **🔧 Settings Management** – View, edit, add, and delete environment variables with ease
- **🔄 Environment Profiles** – Switch between different environments (dev, test, prod) with a single command
- **🎨 Theme Customization** – Customize the appearance of the CLI using the theme builder
- **📂 Flock Loader** – Load and execute .flock files directly from the CLI

## 🚀 Getting Started

To start the Flock CLI, run:

```bash
python -m flock
```

This will launch the main menu, from which you can access all the CLI features. **Simple as that!**

## 📋 Main Menu

The main menu provides access to all the CLI features:

```
Flock Management Console

What do you want to do?
 
 ❯ Load a *.flock file
   Theme builder
   Settings
   Start advanced mode (coming soon)
   Start web server (coming soon)
   'Hummingbird' release notes
   Exit
```

Use the arrow keys to navigate the menu and press Enter to select an option. **Clean and intuitive!**

## 🧩 CLI Modules

The CLI is organized into several modules, each providing **specific functionality**:

- [⚙️ Settings Editor](settings-editor.md) – Manage environment variables and profiles
- 🎨 Theme Builder – Customize the appearance of the CLI
- 📂 Flock Loader – Load and execute .flock files
- 📝 Release Notes – View the latest release notes

## 🔍 Navigation

Throughout the CLI, you can use these navigation patterns:

- 🔼🔽 Arrow keys to move between options
- ↩️ Enter to select an option
- ⌨️ Keyboard shortcuts (shown in parentheses) for quick navigation
- ↩️ "Back" or "Cancel" options to return to previous screens

## ⚙️ Configuration

The CLI uses the `.env` file in the project root for configuration. You can manage this file through the Settings Editor. **No more manual .env editing!** 