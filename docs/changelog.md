# 📝 Changelog

This document tracks **significant changes and additions** to the Flock framework. Think of it as our development journal! 📚

## [Unreleased]

### ✨ Added
- **⚙️ Settings Editor** – A comprehensive CLI-based settings editor that allows users to manage environment variables through a **user-friendly interface**
  - 👀 View, edit, add, and delete environment variables with intuitive UI
  - 🔒 Sensitive value masking with optional visibility toggle (API keys, tokens, secrets)
  - 📊 Environment profiles management (dev, test, prod, etc.) with safe switching
  - 📑 Customizable pagination settings
  - 💾 Backup system to prevent data loss during destructive operations
  - ✅ Validation for variable names and values

### 🔄 Changed
- **🖥️ CLI Interface Improvements** – Enhanced the CLI interface with **better navigation and feedback**
  - ⌨️ Added intuitive keyboard shortcuts for navigation
  - 🎨 Implemented clear visual feedback for operations
  - 🔔 Added confirmation dialogs for destructive actions

### 🔐 Security
- **🛡️ Enhanced Data Protection** – Added security features to **protect sensitive information**
  - 🕵️ Automatic detection and masking of sensitive values (API keys, passwords, tokens)
  - 👁️ Configurable setting to show/hide sensitive values with confirmation
  - ⚠️ Warning messages when editing critical settings 