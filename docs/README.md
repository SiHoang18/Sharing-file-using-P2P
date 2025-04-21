```markdown
# Torrent-Like P2P File-Sharing System

A lightweight BitTorrent-inspired application that enables decentralized, scalable file sharing. It consists of a tracker for peer coordination and a daemon for seeding and leeching content.

---

## 🚀 Features

- **Tracker**
  - Tracks active peers per torrent
  - Provides peer lists via HTTP endpoints

- **Peer Daemon**
  - **Seeding**: Split files into pieces, compute SHA-1 hashes, and upload to other peers
  - **Leeching**: Download pieces from multiple peers concurrently
  - **Auto-Seeding**: Switch to seeding upon download completion
  - **Integrity Checks**: Validate each piece against the torrent manifest
  - **Concurrent Torrents**: Handle multiple seed and leech tasks simultaneously
  - **Status Dashboard**: Monitor upload/download progress

---

## 📥 Getting Started

### Prerequisites

- Python 3.8+ installed
- `pip` package manager

### Installation

```bash
git clone https://github.com/tinta2510/torrent-like-application.git
cd torrent-like-application/src
pip install .
```

> It is recommended to use a virtual environment to isolate dependencies:
>
> ```bash
> python -m venv venv
> source venv/bin/activate   # macOS/Linux
> venv\Scripts\activate    # Windows
> ```

---

## ⚙️ Configuration

Edit `config.py` in the `src/utils/` directory to customize:

```ini
[tracker]
#TRACKER HOST
TRACKER_HOST = "127.0.0.1"
#TRACKER PORT
TRACKER_PORT = 6881

[peer]
# Tracker base URL (e.g. http://127.0.0.1:6881)
TRACKER_URL  = http://localhost:6881
# Directory to write generated torrent files
TORRENT_DIR  = ./data/torrents
# Download directory for incoming files
DOWNLOAD_DIR = ./data/downloads
# Announcement interval in seconds
CLEANUP_INTERVAL = 60
UPDATE_INTERVAL = 90
# Default port for peer daemon
PORT         = 6000
```

---

## 🏃 Usage
### 1.Start program
```bash
python main.py
```
### 1. Start the Tracker

```bash
run_tracker [--host <HOST>] [--port <PORT>]
```
- **Default**: host `127.0.0.1`, port `6881`
- **Flags**:
  - `--host`: Bind address (e.g., `0.0.0.0` to listen on all interfaces)
  - `--port`: Port number

### 2. Launch the Peer 

```bash
start [--host <HOST>] [--port <PORT>]
```
- **Default**: host `127.0.0.1`, port `6000`

---

## 💻 CLI Commands

Interact with the running daemon via the following tools:

| Command             | Description                                      |
|---------------------|--------------------------------------------------|
| `seed`              | Create and seed a torrent                        |
| `download`          | Download using a `.torrent` file                 |
| `status`            | Show current upload/download tasks               |

### Examples

- **Seed a File**:
  ```bash
  seed --filepath /path/to/file --tracker tracker_url
  ```

- **Leech a Torrent**:
  ```bash
  download -filepath /path/to/file 
  ```

- **Monitor Status**:
  ```bash
  status
  ```

---

## 🔄 Example Workflow

1. **Start Tracker** on a server:
   ```bash
   torrent-tracker --host 127.0.0.1 --port 6000
   ```
2. **Run Peer ** on each client:
   ```bash
   start --host 127.0.0.1 --port 6000
   ```
3. **Seed** a File from Client A:
   ```bash
   seed -filepath /data/myvideo.mp4.torrent
   ```
4. **Leech** on Client B:
   ```bash
   download --filepath /data/myvideo.mp4.torrent
   ```
5. **Monitor** Progress:
   ```bash
   status
   ```

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/YourFeature`)
3. Commit your changes (`git commit -m "Add feature"`)
4. Push to your branch (`git push origin feature/YourFeature`)
5. Open a Pull Request

---

