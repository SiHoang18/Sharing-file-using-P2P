import socket
import threading
import json
from utils.logger import logger

class PeerConnection:
    def __init__(self, host='0.0.0.0', port=6881, max_connection=5, size_limit=1):
        self.host = host
        self.port = port
        self.size_limit = size_limit * 1024
        self.max_connection = max_connection
        
        # Connection management
        self.peer_pool = {}
        self.server_ready = threading.Event()
        self.running = False
        self.lock = threading.Lock()
        
        # Callback system
        self.chunk_received_callback = None
        self.chunk_request_callback = None
        self.connection_callbacks = {
            'new': None,
            'close': None
        }
        # Server infrastructure
        self.server_socket = None
        self.server_thread = None

    def start_server(self):
        """Start the server in a separate non-daemon thread."""
        try:
            if not self.running:
                self.running = True
                self.server_thread = threading.Thread(
                    target=self._run_server
                )
                self.server_thread.start()
            else:
                logger.warning("Server is already running")
        except KeyboardInterrupt:
            self.stop()
            logger.info(f"Shutting down")

    def register_callback(self, callback_type: str, callback_func):
        """Register external event handlers"""
        if callback_type in self.connection_callbacks:
            self.connection_callbacks[callback_type] = callback_func
        elif callback_type == 'chunk_request':
            self.chunk_request_callback = callback_func
        elif callback_type == 'chunk_received':
            self.chunk_received_callback = callback_func
        else:
            raise ValueError(f"Invalid callback type: {callback_type}")
        
    def _run_server(self):
        """Main server loop that accepts incoming connections."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.settimeout(1)
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(self.max_connection)
            logger.info(f"Peer server listening on {self.host}:{self.port}")
            self.server_ready.set()
            while self.running:
                try:
                    conn, addr = self.server_socket.accept()
                    if not self.running:
                        conn.close()
                        break

                    logger.info(f"Incoming connection from {addr}")
                    with self.lock:
                        if len(self.peer_pool) < self.max_connection:
                            self.peer_pool[addr] = conn
                            if self.connection_callbacks['new']:
                                self.connection_callbacks['new'](addr,conn)
                            threading.Thread(
                                target=self._handle_peer,
                                args=(conn, addr),
                                daemon=False  # Peer handler threads can remain daemon
                            ).start()
                        else:
                            logger.warning(f"Rejecting connection from {addr}, max peer_pool reached")
                            conn.close()
                except socket.timeout:
                    continue
                except OSError as e:
                    if self.running:
                        logger.error(f"Server error: {e}")
                    break
        finally:
            self._cleanup_server()

    def _cleanup_server(self):
        """Clean up server resources."""
        if self.server_socket:
            try:
                self.server_socket.close()
                logger.debug("Server socket closed")
            except Exception as e:
                logger.error(f"Error closing server socket: {e}")

    def _handle_peer(self, conn, addr):
        """Safe peer handling with proper error containment"""
        peer_id = addr
        try:
            if not self._perform_handshake(conn):
                return

            while self.running:
                header = self._receive_header(conn)
                if not header:
                    break  # Graceful exit
                try:
                    command = header.get('command', '')
                    if command == "REQUEST_CHUNK":
                        self._handle_chunk_request(conn, header, peer_id)
                    elif command == "CHUNK_DATA":
                        self._handle_incoming_chunk(conn, header)
                except socket.timeout():
                    continue
                except KeyError as e:
                    logger.error(f"Missing field {str(e)} in header")

        except Exception as e:
            logger.error(f"Connection failed: {str(e)}")
        finally:
            self._cleanup_peer_connection(conn, peer_id)


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

    def _receive_header(self, conn):
        """Safely receive and parse message header"""
        try:
            # Get header length
            header_len_bytes = conn.recv(4)
            if not header_len_bytes or len(header_len_bytes) != 4:
                return None

            header_len = int.from_bytes(header_len_bytes, 'big')
            if header_len <= 0 or header_len > 1024:  # Add reasonable limit
                return None

            # Receive full header
            header = b''
            while len(header) < header_len:
                chunk = conn.recv(header_len - len(header))
                if not chunk:
                    return None
                header += chunk

            # Safely decode with error handling
            decoded = json.loads(header.decode('utf-8', errors='replace'))
            
            # Convert only if it's a string
            if 'file_name' in decoded:
                if isinstance(decoded['file_name'], str):
                    decoded['file_name'] = decoded['file_name'].encode('utf-8')
            return decoded

        except Exception as e:
            logger.error(f"Header error: {str(e)}")
            return None

    def _handle_chunk_request(self, conn, header, peer_id):
        try:
            # Convert filename to bytes
            file_name = header['file_name']  # Direct bytes access
            success, chunk_data = self.chunk_request_callback(
                peer_id=peer_id,
                file_name=file_name,  # Pass bytes directly
                chunk_index=header['chunk_index']
            )
            # Keep response filename as string for JSON compatibility
            response_header = {
                'status': 'OK' if success else 'ERROR',
                'command': 'CHUNK_DATA',
                'file_name': file_name.decode('utf-8', errors='replace')  # Convert to string
            }
            if success:
                response_header['data_length'] = len(chunk_data)
                response_header['chunk_index'] = header['chunk_index']
                self._send_response(conn, response_header, chunk_data)
            else:
                self._send_response(conn, response_header)

        except Exception as e:
            logger.error(f"Request processing failed: {str(e)}")
            error_header = {'status': 'ERROR', 'reason': str(e)}
            self._send_response(conn, error_header)

    def _handle_incoming_chunk(self, conn, header):
        """Handle incoming chunk data."""
        try:
            required_fields = ['file_name', 'chunk_index', 'data_length']
            if not all(field in header for field in required_fields):
                raise ValueError("Invalid chunk header")

            chunk_data = self._receive_chunk_data(
                conn, 
                header['data_length']
            )
            if self.chunk_received_callback:
                success = self.chunk_received_callback(
                    file_name=header['file_name'],
                    chunk_index=header['chunk_index'],
                    chunk_data=chunk_data,
                    peer_id=conn.getpeername()
                )
                conn.sendall(b"ACK" if success else b"ERR")
            else:
                logger.error("No chunk backend registered")
                conn.sendall(b"ERR")

        except Exception as e:
            conn.sendall(b"ERR")
    def _send_response(self, conn: socket.socket, header, data=None):
        """Send response and wait for ACK"""
        try:
            header_bytes = json.dumps(header).encode()
            conn.sendall(len(header_bytes).to_bytes(4, 'big'))
            conn.sendall(header_bytes)
            
            if data:
                conn.sendall(data)  # Rely on TCP for delivery confirmation

        except Exception as e:
            logger.error(f"Send response failed: {str(e)}")
            raise

    def _receive_chunk_data(self, conn, data_length):
        """Receive data without sending ACK"""
        chunk_data = b''
        data_remaining = data_length
        
        while data_remaining > 0:
            chunk = conn.recv(min(data_remaining, self.size_limit))
            if not chunk:
                raise ConnectionError("Connection closed mid-transfer")
            chunk_data += chunk
            data_remaining -= len(chunk)
            
        return chunk_data

    def _cleanup_peer_connection(self, conn, peer_id):
        """Clean up peer connection resources."""
        with self.lock:
            if peer_id in self.peer_pool:
                del self.peer_pool[peer_id]
                if self.connection_callbacks['close']:
                    self.connection_callbacks['close'](peer_id)

        try:
            conn.close()
            logger.info(f"Connection to {peer_id} closed")
        except Exception as e:
            logger.error(f"Error closing connection: {e}")

    def connect_to_peer(self, peer_ip, peer_port, timeout=5):
        """Connect to another peer with verification."""
        peer_socket = None
        try:
            peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            peer_socket.settimeout(timeout)
            peer_socket.connect((peer_ip, peer_port))

            # Perform handshake
            peer_socket.sendall(b"PING")
            response = peer_socket.recv(4)
            if response != b"PONG":
                raise ConnectionError("Invalid handshake response")

            with self.lock:
                if len(self.peer_pool) >= self.max_connection:
                    raise ConnectionError("Max connections reached")
                if (peer_ip,peer_port) in self.peer_pool:
                    raise ConnectionRefusedError("Connection existed")
                self.peer_pool[(peer_ip, peer_port)] = peer_socket
                if self.connection_callbacks['new']:
                    self.connection_callbacks['new']((peer_ip, peer_port),peer_socket)
            logger.info(f"Connected to {peer_ip}:{peer_port}")
            return True
        except Exception as e:
            logger.error(f"Connection failed: {str(e)}")
            if peer_socket:
                try:
                    peer_socket.close()
                except Exception:
                    pass
            return False

    def stop(self):
        if not self.running:
            return

        self.running = False

        # Wake the server from accept()
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((self.host, self.port))
        except Exception:
            pass
        with self.lock:
            for addr in self.peer_pool:
                try:
                    sock = self.peer_pool[addr]
                    sock.shutdown(socket.SHUT_RDWR)
                    sock.close()
                    logger.info(f"Closed connection to {addr}")
                except Exception as e:
                    logger.error(f"Error closing peer connection {addr}: {e}")
            self.peer_pool.clear()

        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=5)
        logger.info("Peer server stopped")

        self._cleanup_server()
        
        # Wait for the server thread to finish
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=2)
            if self.server_thread.is_alive():
                logger.warning("Server thread did not terminate cleanly")

        logger.info("Peer connection manager fully stopped")

    def get_connection_status(self):
        """Get pure connection status"""
        with self.lock:
            return {
                'active_peers': list(self.peer_pool.keys()),
                'server_running': self.running,
                'max_connections': self.max_connection
            }
    def get_socket(self,peer_address):
        return self.peer_pool[peer_address] if peer_address in self.peer_pool else None
    def send_message_to_peer(
        self, 
        peer_address, 
        header: dict, 
        data: bytes = None, 
        expect_response=False  
    ):
        try:
            conn = self.get_socket(peer_address)
            if not conn:
                raise ConnectionError(f"No active connection to {peer_address}")

            # Send the header with 4-byte length prefix
            header_bytes = json.dumps(header).encode("utf-8")
            conn.sendall(len(header_bytes).to_bytes(4, "big"))
            conn.sendall(header_bytes)

            # Send optional data (e.g., chunk bytes)
            if data:
                conn.sendall(data)

            # Read the response if required (e.g., for tracker requests)
            if expect_response:
                # Read the 4-byte response header length
                header_length_bytes = conn.recv(4)
                if not header_length_bytes:
                    return None
                header_length = int.from_bytes(header_length_bytes, "big")

                # Read the full response header
                response_bytes = conn.recv(header_length)
                if not response_bytes:
                    return None

                # Parse and return the JSON response
                response = json.loads(response_bytes.decode("utf-8"))
                print("Received response:", response)  # Debug print
                return response

            return True

        except Exception as e:
            logger.error(f"Failed to send message to {peer_address}: {e}")
            return None
    def receive_chunk_data(self, peer_address, data_length):
        """Receive chunk data from specific peer"""
        conn = self.get_socket(peer_address)
        if not conn:
            raise ConnectionError("No active connection")
        
        return self._receive_chunk_data(conn, data_length)