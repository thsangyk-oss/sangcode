# SangCode Web Terminal Dashboard

SangCode is a modern, web-based terminal dashboard designed to seamlessly manage and interact with multiple coding environments directly from your browser. Whether you are running bash scripts, or specialized AI coding assistants like Claude, Codex, or OpenCode, SangCode provides an elegant, centralized interface for all your sessions.

## Features

- 🖥️ **Real-time Terminal Rendering**: Powered by `ttyd`, experience smooth, real-time streaming of terminal sessions via WebSockets.
- 🚀 **Multi-Session Management**: Create, view, and manage multiple terminal sessions simultaneously. Supported session types include:
  - `bash`
  - `claude`
  - `codex`
  - `opencode`
- 📱 **Mobile Optimized**: A responsive dashboard UI designed to work flawlessly across desktop and touch-enabled mobile devices.
- 🔐 **Secure Access**: Built-in authentication mechanism using environment variables (`SANGCODE_PASSWORD`).
- 🤖 **Auto-Approve Integration**: Built-in monitor to classify AI prompts and optionally auto-approve routine confirmations.
- 🔍 **Path Suggestions**: Intelligent path autocompletion when setting up new sessions.

## Architecture

- **Backend**: Python 3 with `aiohttp` for robust async web server and WebSocket proxying.
- **Terminal Backend**: `tmux` for session persistence and `ttyd` for WebSocket proxying.
- **Frontend**: Vanilla HTML/JS/CSS with modern, dynamic glassmorphism design.

## Prerequisites

To run SangCode, ensure you have the following installed on your system:
- Python 3.8+
- `tmux`
- `ttyd`
- `aiohttp`

## Installation & Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/sangcode.git
   cd sangcode
   ```

2. Install Python dependencies:
   ```bash
   pip install aiohttp
   ```

3. Set up the required environment variables:
   ```bash
   export SANGCODE_PASSWORD="your_secure_password"
   ```

4. Run the server:
   ```bash
   python app.py
   ```
   
5. Open your browser and navigate to the provided host and port (default is usually `http://localhost:8080`).

## Usage

- **Dashboard**: Access the main UI to spawn new sessions, view active terminals, and terminate completed ones.
- **Viewer**: A dedicated fullscreen view for your terminal sessions.

## Security

SangCode exposes a powerful terminal interface to your system. It is strongly recommended to:
- Always use a strong `SANGCODE_PASSWORD`.
- Run the server behind a secure reverse proxy like Caddy or Nginx with HTTPS enabled.
- Avoid exposing the server to the public internet without proper firewall and authentication safeguards.

## License

MIT License. See `LICENSE` for details.
