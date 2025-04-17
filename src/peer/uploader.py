import os
from utils.logger import logger


class Uploader:
    def __init__(self, peer_id, peers, shared_files, size_limit = 1, max_upload_slots = 4, lock = None):
        # self.peer = peer
        self.peer_id = peer_id
        self.peers = peers
        self.shared_files = shared_files
        self.active_connections = {}  # {peer_id: {file_name: [chunk_indices]}}
        self.size_limit = size_limit
        self.max_upload_slots = max_upload_slots
        self.lock = lock  # Sử dụng lock chung từ PeerConnection
        
        # Khởi tạo active_connections từ peers hiện có
        with self.lock:
            for peer_id in self.peers:
                self.active_connections[peer_id] = {}

    def handle_upload_request(self, file_name, chunk_index,requesting_peer):
        # Ensure filename is bytes for lookup
        if isinstance(file_name, str):
            file_name = file_name.encode('utf-8')
            
        logger.debug(f"Request from {requesting_peer} for {file_name} chunk {chunk_index}")
        
        if file_name != self.shared_files[b'name']:
            print(self.shared_files)
            logger.error(f"{file_name} not in shared files")
            return False, b''
        
        try:
            # Add actual file handling logic
            chunk_data = self._get_chunk_data(file_name, chunk_index)
            return True, chunk_data
        except Exception as e:
            logger.error(f"Chunk retrieval failed: {str(e)}")
            return False, b''

    def get_upload_status(self):
        """
        Get current upload status and statistics.
        
        Returns:
            Dictionary containing upload statistics
        """
        upload_status = {
            'connected_peers': {},
            'total_peers': 0,
            'total_chunks': 0
        }
        for peer_id, files in self.active_connections.items():
            peer_info = {
                'files': {},
                'total_chunk': 0
            }
            for file, chunks in files.items():
                peer_info['files'][file] = {
                    'chunks': chunks,
                    'chunk_count' : len(chunks)
                }
                peer_info['total_chunk'] += len(chunks)
            upload_status['total_chunks'] += peer_info['total_chunk']
            upload_status['connected_peers'][peer_id] = peer_info
        upload_status['total_peers'] = len(self.active_connections)
        return upload_status

    def stop(self):
        """
        Gracefully close all active upload connections.
        """
        with self.lock:
            self.active_connections.clear()
            return True

    def _verify_chunk_available(self,chunk_index):
        try:
            info = self.shared_files
            if b"length" in info:
                total_pieces = len(info[b"pieces"]) // 20
                return chunk_index < total_pieces
            elif b"files" in info:
                total_size = sum(f[b"length"] for f in info[b"files"])
                piece_length = info[b"piece_length"]
                total_pieces = (total_size + piece_length - 1) // piece_length
                return chunk_index < total_pieces
                
        except KeyError as e:
            logger.error(f"Missing key: {e}")
        return False

    def _get_chunk_data(self, file_name, chunk_index):

        try:
            info = self.shared_files
            if not info:
                logger.error("No 'info' in shared_files")
                return None
            if b"length" in info:
                return self._get_single_file_chunk(file_name, chunk_index)
            elif b"files" in info:
                return self._get_multi_file_chunk(file_name, chunk_index)
                
        except Exception as e:
            logger.error(f"Error getting chunk: {e}")
        return None

    def _get_single_file_chunk(self,file_name, chunk_index):
        file_info = self.shared_files
        if not file_info:
            return None
        file_path = file_info.get(b'path').decode()
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return None

        piece_length = self.shared_files.get(b'piece_length')
        if not piece_length:
            logger.error("Missing 'piece_length' in shared_files")
            return None
        try:
            with open(file_path, 'rb') as f:
                f.seek(chunk_index * piece_length)
                # print(f"{min(piece_length,self.shared_files[b'length'] - chunk_index * piece_length)}")
                return f.read(min(piece_length,self.shared_files[b'length'] - chunk_index * piece_length))
        except Exception as e:
            logger.error(f"File read error: {str(e)}")
            return None
    def _get_multi_file_chunk(self,file_path, chunk_index):
        current_pos = 0
        piece_length = self.shared_files.get(b'piece_length',b'')
        chunk_start = chunk_index * piece_length
        chunk_end = chunk_start + piece_length
        chunk_data = bytearray()
        for file_info in self._get_all_files(file_path):
            file_size = file_info['size']
            file_start = current_pos
            file_end = current_pos + file_size
    
            if file_end > chunk_start and file_start < chunk_end:
                read_start = max(chunk_start - file_start, 0)
                read_end = min(chunk_end - file_start, file_size)
                
                with open(file_info['abs_path'], 'rb') as f:
                    f.seek(read_start)
                    chunk_data += f.read(read_end - read_start)
                    
            current_pos += file_size
            
            if current_pos >= chunk_end:
                break
                
        return bytes(chunk_data)

    def _get_all_files(self, root_path):
        """Helper to get all files with their metadata"""
        files = []
        try:
            for root, _, filenames in os.walk(root_path):
                for filename in filenames:
                    abs_path = os.path.join(root, filename)
                    if not os.path.exists(abs_path):
                        continue
                    files.append({
                        'abs_path': abs_path,
                        'rel_path': os.path.relpath(abs_path, root_path),
                        'size': os.path.getsize(abs_path)
                    })
        except Exception as e:
            logger.error(f"Error traversing files: {e}")
        return sorted(files, key=lambda x: x['rel_path'])
    def add_peer(self, peer_id,conn):
        self.peers[peer_id] = conn
    def remove_peer(self,peer_id):
        self.peers.pop(peer_id,None)