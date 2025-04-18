from peer.peer import Peer  # Assuming Peer wraps around PeerConnection
from utils.config import TRACKER_HOST, TRACKER_PORT
from torrent.torrent_creator import TorrentCreator
from torrent.torrent_parser import TorrentParse
import time
from ui.cli import CLI

def start_client1(peer_ip="127.0.0.1", peer_port=5002):
    # Instantiate the Peer (wrapper for PeerConnection)
    try:
        torrent = TorrentParse("Chapter_1_v8.0.pdf.torrent")
        info = torrent.get_info()
        # print(info)
        a = Peer(host=peer_ip, port=peer_port,shared_files=info)
        a.start()
        a.connect_to_peer((TRACKER_HOST,TRACKER_PORT))

        header = {
            "action": "announce",
            "torrent_id": "Chapter_1_v8.0.pdf.torrent",
            "peer_ip": peer_ip,
            "port": peer_port
        }
        a.send_message_to_peer((TRACKER_HOST,TRACKER_PORT),header,None,True)

        time.sleep(50)
        a.stop()
    except KeyboardInterrupt:
        a.stop()

if __name__ == "__main__":
    # start_client1()
    CLI().run()
