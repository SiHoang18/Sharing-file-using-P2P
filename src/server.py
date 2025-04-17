from peer.peer import Peer
from torrent.torrent_parser import TorrentParse
from utils.config import TRACKER_HOST,TRACKER_PORT
import time
def start_client2(peer_ip = '127.0.0.1', peer_port = 5001):
    try:
        torrent = TorrentParse("Chapter_1_v8.0.pdf.torrent")
        info = torrent.get_info()
        # print(info)
        a = Peer(host=peer_ip, port=peer_port,shared_files=info)
        a.start()
        a.connect_to_peer((TRACKER_HOST,TRACKER_PORT))
        # time.sleep(5)
        header = {
            "action": "announce",
            "torrent_id": "Chapter_1_v8.0.pdf.torrent",
            "peer_ip": peer_ip,
            "port": peer_port
        }
        # a.download("Chapter_1_v8.0.pdf",("127.0.0.1",5002))
        a.send_message_to_peer((TRACKER_HOST,TRACKER_PORT),header,None,True)
        time.sleep(1)
        update_header = {
            "action": "peer_list_update",
            "torrent_id": "Chapter_1_v8.0.pdf.torrent",
            "peer_ip": peer_ip,
            "port": peer_port
        }
        rep = a.send_message_to_peer((TRACKER_HOST,TRACKER_PORT),update_header,None,True)
        print(rep)
        a.get_peer_list(peer_list=tuple(rep["peer_list"]))

        for peer_id in a.peer_list:
            if tuple(peer_id) != (peer_ip,peer_port):
                a.connect_to_peer(peer_id)
        a.download("Chapter_1_v8.0.pdf")
        time.sleep(30)

        a.stop()
    except KeyboardInterrupt:
        a.stop()

if __name__ == "__main__":
    start_client2()