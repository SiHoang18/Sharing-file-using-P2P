from flask import Flask, request, jsonify
import threading
from utils.config import TRACKER_HOST, TRACKER_PORT, CLEANUP_INTERVAL
from utils.logger import logger
from tracker.peers_db import Peer_DB
import os
import time
class Tracker:
    def __init__(self, host=TRACKER_HOST, port=TRACKER_PORT):
        self.host = host
        self.port = port
        self.app = Flask(__name__)
        self.peer_db = Peer_DB()
        self.lock = threading.Lock()
        self.shutdown_event = threading.Event()
        self.running = True
        self._register_routes()

    def _register_routes(self):
        @self.app.route('/announce', methods=['POST'])
        def announce():
            data = request.get_json()
            torrent_id = data.get("torrent_id")
            peer_ip = data.get("peer_ip")
            peer_port = data.get("port")
            if not torrent_id or not peer_ip or not peer_port:
                return jsonify({"error": "Missing fields"}), 400

            try:
                with self.lock:
                    self.peer_db.add_peer(torrent_id, (peer_ip, peer_port))
                    peers = self.peer_db.get_peers(torrent_id)
                return jsonify({"peers": peers})
            except BufferError:
                return jsonify({"warning": "Already announced"}), 200
            except Exception as e:
                logger.error(f"Announce error: {e}")
                return jsonify({"error": "Server error"}), 500

        @self.app.route('/peer_list_update', methods=['POST'])
        def peer_list_update():
            data = request.get_json()
            torrent_id = data.get("torrent_id")
            if not torrent_id:
                return jsonify({"error": "Missing torrent_id"}), 400
            with self.lock:
                peers = self.peer_db.get_peers(torrent_id)
            return jsonify({"peers": peers})

        @self.app.route('/stop', methods=['POST'])
        def stop():
            data = request.get_json()
            torrent_id = data.get("torrent_id")
            peer_ip = data.get("peer_ip")
            peer_port = data.get("port")
            with self.lock:
                self.peer_db.remove_peer(torrent_id, (peer_ip, peer_port))
            return jsonify({"message": "Peer removed"})

        @self.app.route('/time_update', methods=['POST'])
        def time_update():
            data = request.get_json()
            torrent_id = data.get("torrent_id")
            peer_ip = data.get("peer_ip")
            peer_port = data.get("port")
            with self.lock:
                self.peer_db.update_last_seen(torrent_id, (peer_ip, peer_port))
            return jsonify({"message": "Last seen updated"})
    def _cleanup_loop(self):
        while not self.shutdown_event.is_set():
            with self.lock:
                self.peer_db.cleanup_inactive_peers()
                logger.info("Cleaned up inactive peers")
            self.shutdown_event.wait(CLEANUP_INTERVAL)
    def run(self):
        logger.info(f"Starting tracker on {self.host}:{self.port}")
        cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        cleanup_thread.start()
        self.running = True
        self.app.run(host=self.host, port=self.port)

    def shutdown(self):
        logger.info("Shutting down tracker...")
        self.running = False
        self.shutdown_event.set()
