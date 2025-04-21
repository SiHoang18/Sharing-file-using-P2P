import argparse
import sys
import threading
import shlex
import cmd
from tracker.tracker import Tracker
from utils.config import CHUNK_SIZE, TRACKER_HOST, TRACKER_PORT, TORRENT_FOLDER, DOWNLOAD_FOLDER
from torrent.torrent_creator import TorrentCreator
from torrent.torrent_parser import TorrentParse
from peer.peer import Peer
from utils.logger import logger

class InteractiveCLI(cmd.Cmd):
    prompt = "<p2p> "
    intro  = "BitTorrent-style P2P CLI (type 'help' for commands)"
    
    def __init__(self, cli):
        super().__init__()
        self.cli = cli
        self.metadata = None
        self.active_peer = None
        self.active_tracker = None
        self.filepath = None
        self.tracker_url = None

    def do_start(self, arg: str):
        """Bring this peer up: start --host <host> --port <port>"""
        try:
            if self.active_tracker:
                print(f"Program is runnning on tracker mode")
                return
            args = self.cli._parse_start_args(shlex.split(arg))
            if self.active_peer:
                print(f"Peer already running at {self.active_peer.host}:{self.active_peer.port}")
                return
            self.active_peer = Peer(
                host=args.host,
                port=args.port,
                shared_files={},
                save_path=DOWNLOAD_FOLDER
            )
            threading.Thread(target=self.active_peer.start, daemon=True).start()
            print(f"Peer started at {args.host}:{args.port}")
        except SystemExit:
            pass

    def do_seed(self, arg: str):
        """Start seeding a file: seed -filepath <path> --tracker <url>"""
        if self.active_tracker:
            print(f"Program is runnning on tracker mode")
            return
        if not self.active_peer:
            print("Peer not running. Use: start --host <host> --port <port>")
            return
        try:
            args = self.cli._parse_seed_args(shlex.split(arg))
            print(f"Seeding file: {args.filepath}")
            torrent = TorrentParse(args.filepath)
            self.metadata = torrent.get_info()
            self.active_peer.update_shared_file(shared_file=self.metadata)
            if self.metadata is None:
                raise Exception("Invalid torrent metadata")
            self.tracker_url = args.tracker if args.tracker else torrent.get_announce_url()
            self.filepath = args.filepath
            peer_list = self.active_peer.announce_to_tracker(
                self.tracker_url,
                repr(self.metadata),
                self.active_peer.host,
                self.active_peer.port
            )
            if not self.active_peer.update_thread:
                threading.Thread(target=self.active_peer.update_loop,args=(self.tracker_url,repr(self.metadata)),daemon=True).start()
                self.active_peer.update_thread = True
            self.active_peer.get_peer_list(peer_list)
        except SystemExit:
            pass
        except Exception as e:
            logger.error(f"Failed to start seeding: {e}")

    def do_download(self, arg: str):
        """Download a file: download -filepath <torrent_file> [-s <save_dir>]"""
        if self.active_tracker:
            print(f"Program is runnning on tracker mode")
            return
        if not self.active_peer:
            print(" Peer not running. Use: start --host <host> --port <port>")
            return
        try:
            args = self.cli._parse_download_args(shlex.split(arg))
            print(f"Downloading from torrent: {args.filepath}")
            torrent = TorrentParse(args.filepath)
            self.metadata = torrent.get_info()
            self.active_peer.update_shared_file(shared_file=self.metadata)
            if self.metadata is None:
                raise Exception("Invalid torrent metadata")
            self.tracker_url = torrent.get_announce_url()
            self.filepath = args.filepath
            peer_list = self.active_peer.update_peer_list(
                self.tracker_url,
                repr(self.metadata),
                self.active_peer.host,
                self.active_peer.port
            )
            if (self.active_peer.host, self.active_peer.port) not in peer_list:
                self.active_peer.announce_to_tracker(
                    self.tracker_url,
                    repr(self.metadata),
                    self.active_peer.host,
                    self.active_peer.port
                )
            if not self.active_peer.update_thread:
                threading.Thread(target=self.active_peer.update_loop,args=(self.tracker_url,repr(self.metadata)),daemon=True).start()
                self.active_peer.update_thread = True
            self.active_peer.get_peer_list(peer_list)
            for peer in self.active_peer.peer_list:
                if (self.active_peer.host, self.active_peer.port) != tuple(peer):
                    self.active_peer.connect_to_peer(tuple(peer))
            self.active_peer.downloader.assembled = False
            self.active_peer.download(self.metadata[b'name'])
        except SystemExit:
            pass
        except Exception as e:
            logger.error(f"Failed to download: {e}")

    def do_create(self, arg: str):
        """Create torrent file: create -filepath <path> --tracker <url> [--piece_length <n>]"""
        try:
            args = self.cli._parse_create_args(shlex.split(arg))
            self.cli.create_torrent(args)
        except SystemExit:
            pass

    def do_run_tracker(self, arg: str):
        """Start tracker server: run-tracker [--host HOST] [--port PORT]"""
        try:
            args = self.cli._parse_tracker_args(shlex.split(arg))
            print(f"Starting tracker at {args.host}:{args.port}")
            self.active_tracker = Tracker(host=args.host, port=args.port)
            threading.Thread(target=self.active_tracker.run, daemon=True).start()
        except SystemExit:
            pass

    def do_status(self, args):
        """Show current status"""
        print("\n=== System Status ===")
        print(f"Tracker: {'Running' if self.active_tracker else 'Stopped'}")
        print(f"Peer: {'Active' if self.active_peer else 'Inactive'}")
        if self.active_peer:
            print(self.active_peer.get_network_status())

    def do_exit(self, args):
        """Exit the program"""
        print("Shutting down...")
        if self.active_peer:
            self.active_peer.stop_connect_to_tracker(self.tracker_url,self.filepath,self.active_peer.host,self.active_peer.port)
            self.active_peer.stop()
        if self.active_tracker:
            self.active_tracker.shutdown()
        return True

class CLI:
    def __init__(self):
        self.parser = self._create_main_parser()
        self.subparsers = self.parser.add_subparsers(dest="command", required=True)
        self._setup_parsers()

    def _create_main_parser(self):
        return argparse.ArgumentParser(
            description="P2P File Sharing - BitTorrent Style CLI",
            usage="%(prog)s [command] [options]"
        )

    def _setup_parsers(self):
        # start
        start_p = self.subparsers.add_parser("start", help="Start peer mode")
        start_p.add_argument("--host", type=str, default="127.0.0.1", required=True, help="Peer's host")
        start_p.add_argument("--port", type=int, default=6000, required=True, help="Peer's port")

        # seed (for interactive only)
        seed_p = self.subparsers.add_parser("seed", help=argparse.SUPPRESS)
        seed_p.add_argument("-filepath", required=True, help="Path to the file to seed")
        seed_p.add_argument("--tracker", help="Tracker URL")

        # download (for interactive only)
        dl_p = self.subparsers.add_parser("download", help=argparse.SUPPRESS)
        dl_p.add_argument("-filepath", required=True, help="Torrent file name")
        # dl_p.add_argument("-s", type=str, default=DOWNLOAD_FOLDER, help="Download directory")

        # create
        create_p = self.subparsers.add_parser("create", help="Create torrent file")
        create_p.add_argument("-filepath", type=str, required=True, help="File to share")
        create_p.add_argument("--tracker", type=str, required=True, help="Tracker URL")
        create_p.add_argument("--piece_length", type=int, default=CHUNK_SIZE)
        # create_p.add_argument("-s", type=str, default=TORRENT_FOLDER, help="Output directory")

        # run-tracker
        tracker_p = self.subparsers.add_parser(
            "run-tracker",
            aliases=["run_tracker"],
            help="Start tracker server"
        )
        tracker_p.add_argument("--host", type=str, default=TRACKER_HOST)
        tracker_p.add_argument("--port", type=int, default=TRACKER_PORT)

    def _get_parser(self, command: str) -> argparse.ArgumentParser:
        try:
            return self.subparsers.choices[command]
        except KeyError:
            raise argparse.ArgumentError(None, f"Unknown command '{command}'")

    def _parse_start_args(self, args):
        return self._get_parser("start").parse_args(args)

    def _parse_seed_args(self, args):
        return self._get_parser("seed").parse_args(args)

    def _parse_download_args(self, args):
        return self._get_parser("download").parse_args(args)

    def _parse_create_args(self, args):
        return self._get_parser("create").parse_args(args)

    def _parse_tracker_args(self, args):
        sub = "run-tracker" if "run-tracker" in self.subparsers.choices else "run_tracker"
        return self._get_parser(sub).parse_args(args)

    def create_torrent(self, args):
        print(f"Creating torrent for {args.filepath}")
        torrent = TorrentCreator(
            file_path=args.filepath,
            tracker_url=args.tracker,
            piece_length=args.piece_length
        )
        output_path = torrent.create_torrent(TORRENT_FOLDER)
        print(f"Torrent created: {output_path}")

    def run(self):
        if len(sys.argv) > 1:
            args = self.parser.parse_args()
            if args.command == "start":
                print("Invalid syntax")
            elif args.command == "create":
                self.create_torrent(args)
            elif args.command in ("run-tracker", "run_tracker"):
                print("Invalid syntax")
            elif args.command in ("seed", "download"):
                print("Invalid syntax")
        else:
            InteractiveCLI(self).cmdloop()
            
if __name__ == "__main__":
    CLI().run()
