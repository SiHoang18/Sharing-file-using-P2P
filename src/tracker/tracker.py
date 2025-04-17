import socket
import json
import time
import threading
from utils.config import TRACKER_HOST, TRACKER_PORT, CHUNK_SIZE, MAX_CONNECTIONS
from utils.logger import logger
from tracker.peers_db import Peer_DB

# How often to check for inactive peers, in seconds.
CLEANUP_INTERVAL = 60

class Tracker:
    def __init__(self,host=TRACKER_HOST,port=TRACKER_PORT):
        self.host = host
        self.port = port
        self.peer_db = Peer_DB()
        self.socket = None
        self.running = False
        self.cleanup_thread = None
        self.server_thread = threading.Event()
        self.shutdown_event = threading.Event()  # Signal for shutting down threads
        self.lock = threading.Lock()  # Lock to synchronize access to shared peer_db

    def start(self):
        if not self.running:
            self.running = True

            # Create and start the cleanup thread once.
            self.cleanup_thread = threading.Thread(target=self.remove_inactive_peers, daemon=True)
            self.cleanup_thread.start()

            self.server_thread = threading.Thread(target=self._run_server)
            self.server_thread.start()
        else:
            logger.warning("Server is already running")

    def _run_server(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.settimeout(1)
        try:
            self.socket.bind((self.host, self.port))
            self.socket.listen(MAX_CONNECTIONS)
            logger.info(f"Tracker started on {self.host}:{self.port}")

            while self.running:
                try:
                    client_socket, addr = self.socket.accept()
                    if not self.running:
                        client_socket.close()
                        break
                    logger.info(f"Connection from {addr}")
                    with self.lock:
                        threading.Thread(target=self.handle_request, args=(client_socket,),daemon=True).start()
                except socket.timeout:
                    continue
                except Exception as e:
                    logger.error(f"Exception in tracker server loop: {e}")
                    break
        except Exception as e:
            logger.error(f"Failed to start tracker: {e}")
        # finally:
        #     # Ensure socket is closed or proper cleanup is done.
        #     self.shutdown()

    def handle_request(self, client_socket):
        try:
            if not self._perform_handshake(client_socket):
                return
            while self.running:
                header_length_bytes = client_socket.recv(4)
                if not header_length_bytes:
                    return

                header_length = int.from_bytes(header_length_bytes, byteorder='big')
                header_bytes = client_socket.recv(header_length)
                if not header_bytes:
                    return
                try:
                    request = json.loads(header_bytes.decode("utf-8"))
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {e}")
                    err_msg = json.dumps({"error": "Invalid JSON format"})
                    client_socket.sendall(err_msg.encode("utf-8"))
                    return 
                action = request.get("action")
                if action == "announce":
                    # Sử dụng lock khi truy cập và cập nhật dữ liệu peer
                    with self.lock:
                        peer_list = self.handle_announce(request)
                    if peer_list is None:
                        response = {
                            "warning": "Peer has been announced"
                        }
                    else:
                        response = {
                            "command": "MESSAGE",
                            "peer_list": peer_list
                        }
                elif action == "peer_list_update":
                    with self.lock:
                        peer_list = self.peer_db.get_peers(request["torrent_id"])
                    response = {
                        "command": "MESSAGE",
                        "peer_list": peer_list
                    }
                elif action == "stop":
                    with self.lock:
                        self.peer_db.remove_peer(request["torrent_id"],(request["peer_ip"],request["port"]))
                elif action == "time_update":
                    with self.lock:
                        self.peer_db.update_last_seen(request["torrent_id"],(request["peer_ip"],request["port"]))
                else:
                    response = {"error": "Unsupported action"}
                try:
                    response = json.dumps(response).encode("utf-8")
                    client_socket.sendall(len(response).to_bytes(4, "big"))
                    client_socket.sendall(response)
                except (socket.error, ConnectionResetError) as e:
                    logger.error(f"Failed to send response to {client_socket.getpeername()}: {e}")

        except Exception as e:
            logger.error(f"Error handling request: {e}")
        finally:
            client_socket.close()

    def _perform_handshake(self, conn):
        """Perform initial handshake protocol."""
        try:
            handshake = conn.recv(4)
            if handshake != b"PING":
                raise ConnectionAbortedError("Invalid handshake code")
            conn.sendall(b"PONG")
            logger.info("Handshake completed")
            return True
        except socket.timeout:
            logger.warning("Handshake timeout")
            return False
        except ConnectionResetError:
            logger.warning("Connection reset during handshake")
            return False
        except Exception as e:
            logger.error(f"Handshake failed: {str(e)}")
            return False

    def handle_announce(self, params):
        torrent_id = params.get("torrent_id")
        peer_ip = params.get("peer_ip")
        peer_port = params.get("port")

        # Basic validation of required parameters.
        if not torrent_id or not peer_ip or not peer_port:
            return {"error": "Missing required fields: torrent_id, peer_ip, or port"}

        # Register or update the peer using torrent_id as the info_hash.
        try:
            self.peer_db.add_peer(torrent_id, (peer_ip, peer_port))
        except BufferError as be:
            logger.info(f"Duplicate peer for torrent {torrent_id}: {be}")
            return None
        except Exception as e:
            logger.error(f"Error adding peer: {e}")
            return {"error": "Error adding peer"}

        logger.info(f"Announce processed for peer {peer_ip} on torrent {torrent_id}")

        # Return the list of currently active peers for the torrent.
        peers = self.peer_db.get_peers(torrent_id)
        return peers if peers else None

    def remove_inactive_peers(self):
        """
        Periodically call the Peer_DB method to clean up inactive peers.
        Dùng lock để tránh việc đồng thời duyệt và xóa các phần tử trong peer_db.
        """
        while self.running:
            try:
                with self.lock:
                    self.peer_db.cleanup_inactive_peers()
                logger.info("Inactive peers removed")
            except Exception as e:
                logger.error(f"Error cleaning inactive peers: {e}")
            self.shutdown_event.wait(CLEANUP_INTERVAL)

    def shutdown(self):
        if self.running:
            logger.info("Shutting down tracker...")
            self.running = False
            self.shutdown_event.set()  # Signal waiting threads to wake up.
            
            try:
                if self.socket:
                    self.socket.close()
            except Exception as e:
                logger.error(f"Error closing tracker socket: {e}")
            
            # Join threads with a timeout.
            if self.cleanup_thread and self.cleanup_thread.is_alive():
                self.cleanup_thread.join(timeout=5)
            if self.server_thread and self.server_thread.is_alive():
                self.server_thread.join(timeout=5)
            
            logger.info("Tracker shut down successfully.")

