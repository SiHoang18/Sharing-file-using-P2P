import os

APP_NAME = "P2P-TORRENT-CLIENT"

TRACKER_HOST = "127.0.0.1"
TRACKER_PORT = 6881
PEER_PORT_RANGE = (6000,6999)
CLEANUP_INTERVAL = 60
TORRENT_FOLDER = "data/torrents"
DOWNLOAD_FOLDER = "data/downloads"
UPLOAD_FOLDER = "data/uploads"

for folder in [TORRENT_FOLDER,DOWNLOAD_FOLDER,UPLOAD_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)
LOG_LEVEL = "INFO"
LOG_FILE = "logs/app.log"

MAX_CONNECTIONS = 5
CHUNK_SIZE = 512 
