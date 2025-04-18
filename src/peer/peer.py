import socket
import threading
import json
from utils.logger import logger
from peer.connections import PeerConnection
from peer.uploader import Uploader
from peer.downloader import Downloader
from utils.config import TRACKER_HOST,TRACKER_PORT, DOWNLOAD_FOLDER
class Peer:
    def __init__(self,
                 host: str = '127.0.0.1',
                 port: int = 6881,
                 max_connections = 5,
                 shared_files = None,
                 save_path = None,
                 is_seed = False
                 ):
        # Network configuration
        self.host = host
        self.port = port
        self.max_connections = max_connections
        self.peer_list = ()
        self.save_path = save_path 
        # self.is_seed = is_seed
        # File management
        self.shared_files = shared_files or {}
        self.shared_files = {
            k.encode('utf-8') if isinstance(k, str) else k: v 
            for k, v in (shared_files or {}).items()
        }
        self.file_mapping = {
            fname.decode('utf-8', errors='replace'): data 
            for fname, data in self.shared_files.items()
        }
        # Service modules
        self.connection = PeerConnection(
            host=host,
            port=port,
            size_limit= 512,
            max_connection=max_connections,
            # shared_files=shared_files
        )
        self.uploader = Uploader(
            peer_id=(host,port),
            peers=self.connection.peer_pool,
            shared_files=shared_files,
            size_limit=512,
            max_upload_slots=self.max_connections,
            lock=self.connection.lock
        )
        self.downloader = Downloader(
            chunk_size=512,
            peers=self.connection.peer_pool,
            metadata=shared_files if not is_seed else None,
            save_path=self.save_path
        )
        
        # Concurrency control
        self.lock = threading.Lock()
        self.running = False

        self.connection.register_callback(
            callback_type="chunk_request",
            callback_func=self._handle_chunk_request
        )
        self.connection.register_callback(
            callback_type="chunk_received",
            callback_func=self._handle_chunk_received
        )
        self.connection.register_callback(
            callback_type="new",
            callback_func=self._handle_new_connection
        )
        self.connection.register_callback(
            callback_type="close",
            callback_func=self._handle_close_connection
        )

    def start(self) -> None:
        """Start peer services and begin listening for connections"""
        if self.running:
            logger.warning("Peer is running")
        try:
            
            self.connection.start_server()
            self.running = True
            logger.info("Peer started successfully")
        except Exception as e:
            logger.error(f"Startup fail: {e}")
            self._shutdown()

    def _shutdown(self):
        # self.downloader.stop()
        # self.uploader.stop()
        self.connection.stop()
        self.running = False

    def stop(self) -> None:
        """Gracefully shutdown peer and clean up resources"""
        with self.lock:
            if not self.running:
                logger.debug("Peer already stopped")
                return
                
            logger.info("Initiating shutdown sequence...")
            self.running = False 
        self.connection.stop()
        logger.info("Peer shutdown complete")
        
    def connect_to_peer(self, address: tuple) -> bool:
        """
        Establish connection with another peer
        :param address: (IP, port) tuple of target peer
        :return: Connection success status
        """
        return self.connection.connect_to_peer(peer_ip=address[0],peer_port=address[1])
    def get_peer_list(self,peer_list):
        self.peer_list = peer_list
    def download(self, file_id):
        with self.lock:
            if not self.running:
                logger.error("Peer not running")
                return
                
            # Convert bytes to string if needed
            file_id_str = file_id.decode('utf-8') if isinstance(file_id, bytes) else file_id
            total_chunks = len(self.shared_files[b'pieces']) // 20
            
            for chunk_index in range(total_chunks):
                for peer_address in self.peer_list:
                    if tuple(peer_address) != (self.host,self.port):
                        self.request_chunk(file_id=file_id_str,chunk_index=chunk_index,peer_address=tuple(peer_address))
    def update_peer_list(self,torrent_id):
        with self.lock:
            if not self.running:
                logger.error("Peer is not running")
                return
            response = self.connection.send_message_to_peer(
                peer_address=(TRACKER_HOST,TRACKER_PORT),
                header={
                    'command': 'update',
                    'torrent_id': torrent_id
                },
                expect_response=True
            )
            if response and response.get('command') == 'MESSAGE':
                print(response)
                return response['peer_list']
            return None
    def request_chunk(self, file_id: str, chunk_index: int, peer_address: tuple) -> bool:
        try:
            # Ensure file_id is a string
            if isinstance(file_id, bytes):
                file_id = file_id.decode('utf-8', errors='replace')

            response = self.connection.send_message_to_peer(
                peer_address=peer_address,
                header={
                    'command': 'REQUEST_CHUNK',
                    'file_name': file_id,
                    'chunk_index': chunk_index
                },
                expect_response=True
            )

            if response and response.get('status') == 'OK':
                # print(f"response: {response['data_length']}")
                # Get chunk data immediately after header
                chunk_data = self.connection.receive_chunk_data(
                    peer_address=peer_address,
                    data_length=response['data_length'],
                )
                if len(chunk_data) != response['data_length']:
                    logger.error("Data length mismatch")
                    return False

                return self.downloader.handle_chunk_data(
                    peer_address,file_id, chunk_data, chunk_index
                )
            return False

        except socket.timeout:
            logger.error("Chunk transfer timeout")
            return False
        except Exception as e:
            logger.error(f"Chunk request failed: {str(e)}")
            return False
    def send_message_to_peer(self,peer_id,header,data=None,expect_rep = False):
        return self.connection.send_message_to_peer(
            peer_address=peer_id,
            header=header,
            data=data,
            expect_response=expect_rep
        )
    def announce_to_tracker(self,tracker_url, torrent_id, peer_ip, port):
        return self.connection.announce_to_tracker(
            tracker_url=tracker_url,
            torrent_id = torrent_id,
            peer_ip = peer_ip,
            port= port
        )
    def get_network_status(self) -> dict:
        """Return current network connection status"""
        return{
            'connection': self.connection.get_connection_status(),
            'upload': self.uploader.get_upload_status(),
            'downloader': self.downloader.get_download_status()
        }
    
    # Callback Processor
    def _handle_chunk_request(self, peer_id, file_name, chunk_index):
        if isinstance(file_name, bytes):
            file_name = file_name.decode('utf-8')
        success, _ = self.downloader.get_chunk_data(file_name,chunk_index)
        return self.downloader.get_chunk_data(file_name,chunk_index) if success else self.uploader.handle_upload_request(
            file_name=file_name,
            chunk_index=chunk_index,
            requesting_peer=peer_id
        )
    def _handle_chunk_received(self, peer_id: tuple, file_name: str, chunk_index: int, chunk_data: bytes):
        # Let the downloader assemble it
        return self.downloader.handle_chunk_data(
            peer_id=peer_id,
            file_name=file_name,
            chunk_data=chunk_data,
            chunk_index=chunk_index
        )
    def _handle_new_connection(self, peer_id,conn):
        self.uploader.add_peer(peer_id,conn)
        self.downloader.add_peer(peer_id,conn)

    def _handle_close_connection(self, peer_id):
        self.uploader.remove_peer(peer_id)
        self.downloader.remove_peer(peer_id)