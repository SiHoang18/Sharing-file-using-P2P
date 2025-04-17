import threading
import time
from peer.connections import PeerConnection
from utils.logger import logger
from torrent.torrent_parser import TorrentParse
from torrent.torrent_creator import TorrentCreator
from tracker.tracker import Tracker
from ui.cli import cli
def test_single_server_multi_clients():
    # Create server (max_connection=5 for testing)
    server = PeerConnection(port=6881, max_connection=5)
    server_thread = threading.Thread(target=server.start_server)
    server_thread.start()
    server.server_ready.wait()
    logger.info("Main server started on port 6881")

    # Create multiple clients
    clients = []
    test_messages = ["Hello1", "Hello2", "Hello3", "Hello4", "Hello5", "Hello6"]  # 6 messages (1 over limit)
    
    try:
        # Test connection limit
        for i in range(len(test_messages)):
            client = PeerConnection(port=6890 + i)  # Each client gets unique port
            clients.append(client)
            
            # Try connecting to main server
            if i < 6:  # First 5 should succeed
                if client.connect_to_peer('127.0.0.1', 6881):
                    logger.info(f"Client {i+1} connected successfully")
                    # Send test message
                    # if client.send_message(('127.0.0.1', 6881), test_messages[i]):
                    #     logger.info(f"Message {i+1} sent successfully")
                else:
                    logger.error(f"Client {i+1} failed to connect")
            else:  # 6th should fail (max_connection=5)
                if not client.connect_to_peer('127.0.0.1', 6881):
                    logger.warning(f"Client {i+1} correctly rejected (max connections)")
            
            time.sleep(0.2)  # Brief pause between connections

        # Verify server connections
        with server.lock:
            logger.info(f"\nServer connection status: {len(server.peer_pool)}/{server.max_connection}")
            for addr in server.peer_pool:
                logger.info(f"Server connected to: {addr}")

        time.sleep(2)  # Keep connections alive

    finally:
        # Cleanup
        server.stop()
        for client in clients:
            client.stop()
        logger.info("Test completed")
def run_tracker():
    track = Tracker()
    track.start()
    try:
        while track.running:
            time.sleep(1)
    except KeyboardInterrupt:
        track.shutdown()
    # print("HELLO")
    # time.sleep(100)

    
if __name__ == "__main__":
    # test_single_server_multi_clients()
    # b = TorrentCreator("D:/CO3093 -  Mạng máy tính/Slides/Slides_Nguyễn Lê Duy Lai_HK221/Chapter_1_v8.0.pdf","abc",512)
    # b.create_torrent()
    # a = TorrentParse("Slides_Nguyễn Lê Duy Lai_HK221.torrent")
    # a.load_torrent()
    # print(len(a.metadata[b'info'][b'pieces']) // 20)
    # print(math.ceil(a.metadata[b'info'][b'length'] / a.metadata[b'info'][b'piece_length']))
    # a.get_file_info()
    # a.print_metadata()
    # if os.path.exists(a.metadata.get(b'info').get(b'name')):
    #     print("Hello")
    # run_tracker()
    cli = cli()
    cli.run()
    