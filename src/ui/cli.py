import argparse
import sys
import os
import time
import threading
from tracker.tracker import Tracker
from utils.config import CHUNK_SIZE,TRACKER_HOST,TRACKER_PORT, TORRENT_FOLDER
from torrent.torrent_creator import TorrentCreator
class cli:
    def __init__(self):
        self.parser = argparse.ArgumentParser(
            description="P2P File Sharing - BitTorrent Style CLI"
        )
        self.subparsers = self.parser.add_subparsers(dest="command", required=True)
        self._register_commands()
        self.track = None
    def _register_commands(self):
        # Seed command
        seed_parser = self.subparsers.add_parser("seed", help="Start seeding a file")
        seed_parser.add_argument("filepath", help="Path to the file to seed")
        seed_parser.add_argument("--tracker", required=True, help="Tracker URL or address")
        seed_parser.set_defaults(func=self.seed)

        # Download command
        download_parser = self.subparsers.add_parser("download", help="Download a file from peers")
        download_parser.add_argument("torrent_file", help="Path to .torrent-like metadata file")
        download_parser.set_defaults(func=self.download)

        # Create torrent metadata
        create_parser = self.subparsers.add_parser("create", help="Create a .torrent-like file for sharing")
        create_parser.add_argument("filepath",type=str, help="Path to the file to package")
        create_parser.add_argument("piece_length", type=int, default=CHUNK_SIZE, help="Size of chunk")
        create_parser.add_argument("-s", type=str, default=TORRENT_FOLDER, help="Save path")
        create_parser.add_argument("--tracker", required=True, help="Tracker address to include")
        create_parser.set_defaults(func=self.create_torrent)

        # Status command
        status_parser = self.subparsers.add_parser("status", help="Show current peer connections and file pieces")
        status_parser.set_defaults(func=self.status)

        # Run Tracker
        run_tracker_parser = self.subparsers.add_parser("run-tracker", help="Start the tracker server")
        run_tracker_parser.add_argument("--host",type=str, default=TRACKER_HOST, help="Input tracker's host")
        run_tracker_parser.add_argument("--port",type=int, default=TRACKER_PORT, help="Input tracker's port")
        run_tracker_parser.set_defaults(func=self.run_tracker)

        # Stop Tracker
        stop_tracker_parser = self.subparsers.add_parser("stop-tracker", help="Stop the tracker server")
        stop_tracker_parser.set_defaults(func=self.stop_tracker)

        # Stop Peer
        stop_peer_parser = self.subparsers.add_parser("stop-peer", help="Stop a running peer")
        stop_peer_parser.set_defaults(func=self.stop_peer)

    def seed(self, args):
        print(f"[SEED] Seeding file: {args.filepath} using tracker: {args.tracker}")
        # TODO: Start seeding file, announce to tracker

    def download(self, args):
        print(f"[DOWNLOAD] Downloading using torrent file: {args.torrent_file}")
        # TODO: Start downloading process

    def create_torrent(self, args):
        print(f"[CREATE] Creating torrent metadata for: {args.filepath}")
        # TODO: Generate metadata file
        if args.filepath == None or args.tracker == None:
            print(f"Syntax failed!!")
        torrent = TorrentCreator(file_path=args.filepath, tracker_url=args.tracker, piece_length=args.piece_length if args.piece_length else CHUNK_SIZE)
        torrent.create_torrent()

    def status(self, args):
        print("[STATUS] Showing peer and file status:")
        # TODO: Show live stats

    def run_tracker(self, args):
        print("[TRACKER] Starting tracker server...")
        # TODO: Start tracker server (e.g., launch tracker_server.py)

        self.track = Tracker(host=args.host,port=args.port)
        self.track.start()

        # Background input thread
        def watch_input():
            while self.track.running:
                cmd = input(">> ").strip().lower()
                if cmd == "exit":
                    self.stop_tracker()
                    break
                else:
                    print(f"Error command")

        threading.Thread(target=watch_input, daemon=True).start()

        try:
            while self.track.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.track.shutdown()

    def stop_tracker(self):
        print("[TRACKER] Stopping tracker server...")
        # TODO: Gracefully shutdown the tracker (e.g., send shutdown command or signal)
        self.track.shutdown()

    def stop_peer(self, args):
        print("[PEER] Stopping peer client...")
        # TODO: Gracefully shutdown current peer (e.g., via IPC or stop flag)

    def run(self):
        args = self.parser.parse_args()
        args.func(args)
