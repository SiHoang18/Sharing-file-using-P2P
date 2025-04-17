import os
import hashlib
from utils.file_handler import FileHandler
from utils.logger import logger

class TorrentCreator:
    def __init__(self, file_path, tracker_url, piece_length=512, private=0):
        self.file_path = file_path
        self.tracker_url = tracker_url
        self.private = int(private)
        self.piece_length = piece_length * 1024  # Convert KB to bytes
        self.file_handler = FileHandler()

    def create_torrent(self, output_dir="data/torrents"):
        if not os.path.exists(self.file_path):
            logger.error(f"File path does not exist: {self.file_path}")
            return None
        
        os.makedirs(output_dir, exist_ok=True)

        torrent_info = {
            "announce": self.tracker_url,
            "info": self._create_info_dict(self.file_path, self.private),
        }

        if torrent_info["info"] is None:
            return None  # Error already logged

        torrent_file_path = os.path.join(
            output_dir, f"{os.path.basename(self.file_path)}.torrent"
        )

        try:
            self.file_handler.write_file(torrent_file_path, torrent_info, True)
            logger.info(f"Torrent file created successfully: {torrent_file_path}")
        except Exception as e:
            logger.error(f"Error writing torrent file: {e}")
            return None

        return torrent_file_path

    def _create_info_dict(self, file_path, private):
        if os.path.isfile(file_path):
            return self._create_info_single_file(file_path, private)
        elif os.path.isdir(file_path):
            return self._create_info_multi_file(file_path, private)
        else:
            logger.error(f"Invalid file path: {file_path}")
            return None

    def _create_info_single_file(self, file_path, private):
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        pieces = self._calculate_pieces(file_path)

        return {
            "name": file_name,
            "length": file_size,
            "piece_length": self.piece_length,
            "pieces": pieces,
            "private": private,
            "path": file_path
        }

    def _create_info_multi_file(self, file_path, private):
        files = []
        pieces = b""
        buffer = bytearray()
        piece_length = self.piece_length
        file_size = 0
        # Collect all files in sorted order to ensure consistent piece generation
        all_files = []
        for root, dirs, filenames in os.walk(file_path):
            dirs.sort()  # Ensure deterministic order of directory traversal
            for filename in sorted(filenames):
                full_path = os.path.join(root, filename)
                rel_path = os.path.relpath(full_path, file_path)
                all_files.append((rel_path, full_path))

        # Process each file to collect metadata and generate pieces
        for rel_path, full_path in all_files:
            file_size += os.path.getsize(full_path)
            # files.append({
            #     "path": rel_path.split(os.sep),
            #     "length": file_size,
            # })
            with open(full_path, "rb") as f:
                while True:
                    data = f.read(self.piece_length)  # Read in chunks to manage memory
                    if not data:
                        break
                    buffer.extend(data)
                    # Process complete pieces from the buffer
                    while len(buffer) >= piece_length:
                        piece = bytes(buffer[:piece_length])
                        pieces += hashlib.sha1(piece).digest()
                        buffer = buffer[piece_length:]

        # Process remaining data as the last piece
        if buffer:
            pieces += hashlib.sha1(bytes(buffer)).digest()

        return {
            "name": os.path.basename(file_path),
            "length": file_size,
            "piece_length": piece_length,
            "pieces": pieces,
            "private": private,
            "full_path": file_path
        }

    def _calculate_pieces(self, file_path):
        pieces = b""
        try:
            with open(file_path, "rb") as file:
                while True:
                    piece_data = file.read(self.piece_length)
                    if not piece_data:
                        break
                    piece_hash = hashlib.sha1(piece_data).digest()
                    pieces += piece_hash
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
        return pieces