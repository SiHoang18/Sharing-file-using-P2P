import socket
import threading
import hashlib

def handle_peer(conn, addr):
    """Handle a single peer connection."""
    print(f"Connected by {addr}")
    try:
        handshake = conn.recv(4)
        if handshake != b"PING":
            print(f"Invalid handshake from {addr}")
            conn.close()
            return
        conn.sendall(b"PONG")
        while True:
            # First read the checksum (40 bytes for SHA1 hexdigest)
            checksum = conn.recv(40)
            if not checksum or len(checksum) != 40:
                break
                
            # Read the pipe separator
            pipe = conn.recv(1)
            if pipe != b'|':
                break
                
            # Read the chunk
            chunk = conn.recv(2*1024)
            if not chunk:
                break
                
            # Verify checksum
            expected_checksum = hashlib.sha1(chunk).hexdigest().encode()
            if checksum == expected_checksum:
                conn.sendall(b"ACK")
                print(f"Valid chunk from {addr} - {len(chunk)} bytes")
            else:
                print(checksum)
                print(expected_checksum)
                print(f"Checksum mismatch from {addr}")
                break
                
    except Exception as e:
        print(f"Error with {addr}: {e}")
    finally:
        conn.close()

def mock_peer_server(host="127.0.0.1", port=6882):
    """Mock peer server that runs indefinitely, accepting multiple peers."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((host, port))
    server_socket.listen(5)  # Allow multiple connections
    print(f"Mock peer listening on {host}:{port}")

    try:
        while True:
            conn, addr = server_socket.accept()
            threading.Thread(target=handle_peer, args=(conn, addr), daemon=True).start()
    except KeyboardInterrupt:
        print("Mock peer shutting down.")
    finally:
        server_socket.close()

# Run the mock peer
mock_peer_server()