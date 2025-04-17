import os
import hashlib
import bencodepy

CHUNK_SIZE = 512 * 1024
HASH_ALGO = "sha1"

class FileHandler:
    @staticmethod
    def read_file(file_path,chunk_size = CHUNK_SIZE):
        if not os.path.exists(file_path):
            raise FileExistsError(f"File not found: {file_path}")
        with open(file_path, "rb") as file:
            while chunk := file.read(chunk_size):
                yield chunk
    @staticmethod
    def write_file(file_path,data,is_torrent = False,mode = "wb"):
        os.makedirs(os.path.dirname(file_path),exist_ok=True)
        with open(file_path,mode) as file:
            if(is_torrent):
                file.write(bencodepy.encode(data))
            else:
                file.write(data)
    @staticmethod
    def get_file_hash(file_path, hash_algo = HASH_ALGO):
        if not os.path.exists(file_path):
            raise FileExistsError(f"File not found: {file_path}")
        hash_func = hashlib.new(hash_algo)
        with open(file_path,"rb") as file:
            while chunk := file.read(4096):
                hash_func.update(chunk)
        return hash_func.hexdigest()
    @staticmethod
    def verify_file_integrity(file_path, expected_hash, hash_algo = HASH_ALGO):
        actual_hash = FileHandler.get_file_hash(file_path, hash_algo)
        return actual_hash == expected_hash

        