```text
README.md
---------

<div align="center">

# 🔧 XenForo CLI Client

<img src="https://img.shields.io/badge/Python-3.7+-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python">
<img src="https://img.shields.io/badge/XenForo-API-orange?style=for-the-badge" alt="XenForo">
<img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License">
<img src="https://img.shields.io/badge/CLI-Tool-purple?style=for-the-badge" alt="CLI">

**A powerful command-line interface for managing XenForo forums via API**

[Features](#-features) • [Installation](#-installation) • [Usage](#-usage) • [Configuration](#%EF%B8%8F-configuration) • [Contributing](#-contributing)

---

<img src="https://raw.githubusercontent.com/devicons/devicon/master/icons/python/python-original.svg" width="100" alt="Python Logo">

</div>

## 📋 Description

**XenForo CLI** is a lightweight and user-friendly command-line tool that allows you to interact with your XenForo forum directly from the terminal. No need to open a browser — create threads, post replies, and browse your forum structure with simple commands!

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🏗️ **Forum Structure** | View complete forum hierarchy with IDs |
| 📝 **Create Threads** | Start new discussions in any forum section |
| 💬 **Post Replies** | Reply to existing threads instantly |
| 🔐 **Secure API** | Your API key stays local and secure |
| 🎨 **Beautiful UI** | Clean and intuitive terminal interface |
| ⚡ **Fast & Lightweight** | Minimal dependencies, maximum speed |

## 📦 Installation

### Option 1: Clone Repository (Recommended)

```bash
git clone https://github.com/yourusername/xenforo-cli.git
cd xenforo-cli
pip install -r requirements.txt
python main.py
```

### Option 2: Download ZIP

1. Click the green **"Code"** button above
2. Select **"Download ZIP"**
3. Extract the archive
4. Open terminal in the extracted folder
5. Run:
```bash
pip install -r requirements.txt
python main.py
```

## 🚀 Usage

### Starting the Application

```bash
python main.py
```

### First Launch

When you start the application for the first time, you'll be prompted to enter:

1. **Forum URL** — Your XenForo forum address (e.g., `https://forum.example.com`)
2. **API Key** — Your XenForo API key (see [Configuration](#%EF%B8%8F-configuration))

### Main Menu

```
╔═══════════════════════════════════════════╗
║   XenForo API - Forum Management          ║
╚═══════════════════════════════════════════╝

────────────────────────────────────────────
MAIN MENU
────────────────────────────────────────────
1. Show forum structure
2. Create new thread
3. Reply to thread
0. Exit
────────────────────────────────────────────
```

### Example Workflow

```bash
# View all forums
> 1

# Create a new thread
> 2
> Select forum number: 3
> Enter thread title: Hello World!
> Enter message: This is my first post via CLI!

# Reply to existing thread
> 3
> Select forum number: 3
> Select thread number: 1
> Enter reply: Great discussion!
```

## ⚙️ Configuration

### Getting Your API Key

1. Log in to your XenForo **Admin Panel**
2. Navigate to: `Setup` → `API Keys`
3. Click **"Add API key"**
4. Configure permissions:
   - ✅ `forum:read`
   - ✅ `thread:write`
   - ✅ `post:write`
5. Copy the generated key

### Required Permissions

| Permission | Purpose |
|------------|---------|
| `forum:read` | View forum structure |
| `thread:read` | List threads |
| `thread:write` | Create new threads |
| `post:write` | Post replies |

## 📁 Project Structure

```
xenforo-cli/
├── 📄 main.py              # Main application file
├── 📄 requirements.txt     # Python dependencies
└── 📄 README.md            # Documentation

## 🔧 Requirements

- **Python** 3.7 or higher
- **requests** library
- Active **XenForo** forum with API enabled

## 🤝 Contributing

Contributions are welcome! Here's how you can help:

1. 🍴 Fork the repository
2. 🌿 Create a feature branch (`git checkout -b feature/amazing-feature`)
3. 💾 Commit your changes (`git commit -m 'Add amazing feature'`)
4. 📤 Push to the branch (`git push origin feature/amazing-feature`)
5. 🔃 Open a Pull Request

## 💖 Support

If you find this project useful, please consider:

- ⭐ Giving it a star on GitHub
- 🐛 Reporting bugs and issues
- 💡 Suggesting new features

---

<div align="center">

**Made with ❤️ for the XenForo Community**

[![GitHub](https://img.shields.io/badge/GitHub-Follow-black?style=social&logo=github)](https://github.com/MrTofYfY)

</div>
