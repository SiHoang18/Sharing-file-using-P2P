import time
import threading

class Peer_DB:
    def __init__(self,timeout = 180):
        self.torrent = {}
        self.lock = threading.Lock()
        self.timeout = timeout
    def add_peer(self,info_hash,peer_id):
        with self.lock:
            if info_hash not in self.torrent:
                self.torrent[info_hash] = {}
            if self.peer_exist(info_hash,peer_id):
                raise BufferError("Peer has been in buffer")
            else:
                self.torrent[info_hash][peer_id] = time.time()
    def remove_peer(self,info_hash,peer_id):
        with self.lock:
            if info_hash in self.torrent:
                self.torrent[info_hash].pop(peer_id, None)
    def get_peers(self,info_hash):
        with self.lock:
            if info_hash in self.torrent:
                return list(self.torrent[info_hash].keys())
            return None
    def peer_exist(self,info_hash,peer_id):
        return peer_id in self.torrent[info_hash]
    def update_last_seen(self,info_hash,peer_id):
        with self.lock:
            if self.peer_exist(info_hash,peer_id):
                self.torrent[info_hash][peer_id] = time.time()
    def cleanup_inactive_peers(self):
        current_time = time.time()
        for info_hash in list(self.torrent.keys()):
            for peer_id in list(self.torrent[info_hash].keys()):
                if current_time - self.torrent[info_hash][peer_id] >= self.timeout:
                    del self.torrent[info_hash][peer_id]
            if not self.torrent[info_hash]:
                del self.torrent[info_hash]