import os
import threading
from utils.logger import logger

class Downloader:
    def __init__(self, chunk_size, peers, save_path = "data/downloads", metadata = None, max_connection = 4):
        self.chunk_size = chunk_size * 1024
        self.peers = peers
        self.save_path = save_path
        self.metadata = metadata
        self.active_downloads = {}
        self.chunks_data = {}
        self.max_connection = max_connection
        self.lock = threading.Lock()
        os.makedirs(self.save_path, exist_ok=True)
    def handle_chunk_data(self, peer_id, file_name, chunk_data, chunk_index):
        try:
            with self.lock:
                if peer_id not in self.peers:
                    logger.error(f"{peer_id} not exist")
                    return False
                if peer_id not in self.active_downloads:
                    self.active_downloads[peer_id] = {}
                if file_name not in self.active_downloads[peer_id]:
                    self.active_downloads[peer_id][file_name] = []
                if file_name not in self.chunks_data:
                    self.chunks_data[file_name] = []
                if chunk_index not in self.active_downloads[peer_id][file_name]:
                    self.active_downloads[peer_id][file_name].append(chunk_index)
            if chunk_data and chunk_data not in self.chunks_data:
                self.chunks_data[file_name].append((chunk_index,chunk_data))
            if self._is_complete(file_name):
                self._assemble_file(file_name)
            logger.info(f"Downloading {chunk_index} completed")
            return True
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return False
    def _is_complete(self, file_name):
        file_meta = self.metadata
        expected_chunks = (file_meta[b"length"] + file_meta[b"piece_length"] - 1) // file_meta[b"piece_length"]
        return len(self.chunks_data[file_name]) >= expected_chunks

    def _assemble_file(self, file_name):
        file_meta = self.metadata
        output_path = os.path.join(self.save_path, file_name)
        sorted_chunks = sorted(self.chunks_data[file_name], key=lambda x: x[0])
        
        with open(output_path, "wb") as f:
            for _, chunk_data in sorted_chunks:
                f.write(chunk_data)
        
        logger.info(f"Assembled {file_name} ({file_meta[b'length']} bytes)")
    def add_peer(self, peer_id,conn):
        self.peers[peer_id] = conn
    def remove_peer(self,peer_id):
        self.peers.pop(peer_id,None)
    def get_download_status(self):
        status = {"files": {}, "active_peers": list(self.active_downloads.keys())}
        
        # Decode the file name from bytes to string
        file_name_bytes = self.metadata[b'name']
        file_name_str = file_name_bytes.decode('utf-8')
        file_size = self.metadata[b"length"]
        chunk_size = self.metadata[b"piece_length"]
            
        total_chunks = (file_size + chunk_size - 1) // chunk_size
        # Get the downloaded chunks for the current file
        downloaded_chunks = self.chunks_data.get(file_name_str, [])
        downloaded = len(downloaded_chunks)
        
        # Calculate progress
        progress = (downloaded / total_chunks * 100) if total_chunks > 0 else 0.0
            
        status["files"][file_name_str] = {
            "downloaded_bytes": downloaded * chunk_size,
            "total_bytes": file_size,
            "progress": round(progress, 2),
            "chunks": {
                "downloaded": downloaded,
                "total": total_chunks
            }
        }
        return status
    def stop(self):
        with self.stop:
            self.active_downloads.clear()
    def get_chunk_data(self, file_id, chunk_index):
        for chunk in self.chunks_data.get(file_id, []):
            if chunk[0] == chunk_index:
                return True,chunk[1]
        return False,None