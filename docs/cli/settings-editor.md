# ⚙️ Settings Editor

The **Settings Editor** is a **powerful CLI tool** that allows you to manage your environment variables with ease. No more manually editing `.env` files! 🎉

## 🌟 Overview

The Settings Editor provides a **user-friendly interface** for:

- 👀 **Viewing** all your environment variables
- ✏️ **Editing** existing environment variables
- ➕ **Adding** new environment variables
- 🗑️ **Deleting** environment variables
- 💾 **Saving** your changes to the `.env` file
- 📊 **Managing profiles** for different environments

## 🚀 Getting Started

To access the Settings Editor, select **"Settings"** from the main menu. You'll be presented with a screen that looks like this:

```
┌─ Settings ───────────────────────────────────────────────────┐
│                                                              │
│ 🔍 Environment Variables:                                     │
│                                                              │
│  ❯ OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxx            │
│    ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxx            │
│    COHERE_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxx              │
│    LOG_LEVEL=INFO                                            │
│    DEBUG=False                                               │
│                                                              │
│ [n] New variable    [e] Edit    [d] Delete    [q] Back       │
└──────────────────────────────────────────────────────────────┘
```

## 🔧 Features

### 👀 Viewing Environment Variables

The main screen displays all your environment variables with their current values. Long values are truncated for display purposes, but don't worry—they're preserved in full when saved.

Use the **arrow keys** to highlight different variables. **Super simple!**

### ✏️ Editing Variables

To edit a variable:

1. Highlight the variable you want to edit
2. Press **e** or select "Edit"
3. Update the value in the input field
4. Press **Enter** to save your changes

For sensitive values like API keys, the editor will show only the first few characters followed by asterisks for security. **Your secrets stay secret!**

### ➕ Adding New Variables

To add a new variable:

1. Press **n** or select "New variable"
2. Enter the variable name
3. Enter the variable value
4. Press **Enter** to save

The new variable will immediately appear in the list. **Quick and painless!**

### 🗑️ Deleting Variables

To delete a variable:

1. Highlight the variable you want to delete
2. Press **d** or select "Delete"
3. Confirm the deletion when prompted

Be careful! Deleted variables can't be recovered unless you have them backed up elsewhere. **But we do ask to confirm first!**

## 📊 Profile Management

The Settings Editor supports **multiple environment profiles**, allowing you to quickly switch between different sets of environment variables (e.g., development, testing, production).

### 💼 Creating a Profile

To create a new profile:

1. Press **p** or select "Profiles"
2. Select "Create new profile"
3. Enter a name for the profile
4. Choose whether to copy variables from the current profile

### 🔄 Switching Profiles

To switch to a different profile:

1. Press **p** or select "Profiles"
2. Select the profile you want to use
3. Confirm the switch when prompted

All changes are automatically saved to the current profile before switching. **No data loss!**

## 🔒 Security Considerations

- **API keys** and other sensitive values are masked when displayed
- **Profiles** are stored as separate `.env` files in a `.profiles` directory
- Environment variables are **only stored locally** on your machine

## 💡 Tips and Tricks

- Use **Tab** to navigate between input fields
- Press **Esc** to cancel any operation
- Use the **arrow keys** to navigate the menu
- Variables are **automatically saved** when exiting the Settings Editor

## 🧭 Navigation

- **e** - Edit the highlighted variable
- **n** - Create a new variable
- **d** - Delete the highlighted variable
- **p** - Manage profiles
- **q** - Return to the main menu 