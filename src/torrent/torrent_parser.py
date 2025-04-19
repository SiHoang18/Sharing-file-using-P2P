import os
import bencodepy
import hashlib
from utils.logger import logger
from utils.config import TORRENT_FOLDER
class TorrentParse:
    def __init__(self, torrent_file):
        self.torrent_file = torrent_file
        self.metadata = {}
        self.metadata = self.load_torrent()
    def load_torrent(self,filepath = TORRENT_FOLDER):
        path_to_torrent_file = os.path.join(filepath, f"{self.torrent_file}")
        if not os.path.exists(path_to_torrent_file):
            logger.error(f"There is no file: {self.torrent_file}")
            return None 
        try:
            with open(path_to_torrent_file, 'rb') as f:
                data = bencodepy.decode(f.read())
            # info = data[b'info']
            return data
            # return {
            #     b'info': {
            #         b'name': info[b'name'],  
            #         b'pieces': info[b'pieces'],
            #         b'piece_length': info[b'piece_length'],
            #         b'length': info[b'length'],
            #         b'path': info[b'path']
            #     }
            # }
        except Exception as e:
            logger.error(f"Fail to read file {e}")
            return None
    def get_announce_url(self):
        return self.metadata.get(b'announce', b'').decode() if self.metadata else None
    def get_info(self):
        return self.metadata.get(b'info',b'') if self.metadata else None
    def get_piece_length(self):
        return self.get_info().get(b'piece_length',b'') if self.get_info() else None
    def get_pieces(self):
        info = self.get_info()
        if not info:
            return None
        if b'length' in info:
            return info.get(b'pieces',b'')
        elif b'files' in info:
            return [{"path": [p.decode('utf-8') for p in f[b'path']], "pieces": f[b'pieces']} for f in info[b'files']]
        return None
    def get_file_info(self):
        info = self.get_info()
        if not info:
            return None
        if b'length' in info:
            return [{"name": info[b'name'].decode('utf-8'), "length": info[b'length'], "full_path": info[b'full_path'].decode("utf-8")}]
        elif b'files' in info:
            return [{"path": [p.decode('utf-8') for p in f[b'path']], "length": f[b'length']} for f in info[b'files']]
        return None
    def print_metadata(self):
        print("Tracker URL:", self.get_announce_url())
        print("Piece Length:", self.get_piece_length())
        print("Files:", self.get_file_info())