import argparse
import sys
import os
import threading
import cmd
from tracker.tracker import Tracker
from utils.config import CHUNK_SIZE, TRACKER_HOST, TRACKER_PORT, TORRENT_FOLDER, DOWNLOAD_FOLDER
from torrent.torrent_creator import TorrentCreator
from torrent.torrent_parser import TorrentParse
from peer.peer import Peer 

class InteractiveCLI(cmd.Cmd):
    prompt = "<p2p> "
    intro  = "BitTorrent-style P2P CLI (type 'help' for commands)"
    
    def __init__(self, cli):
        super().__init__()
        self.cli = cli
        self.metadata = None
        self.active_peer = None
        self.active_tracker = None
        self.peer_list = None

    def do_seed(self, arg: str):
        """Start seeding a file: seed <filepath> --tracker <tracker_url>"""
        try:
            args = self.cli._parse_seed_args(arg.split())
            self._start_seeding(args)
        except SystemExit:
            pass

    def _start_seeding(self, args):
        print(f"Seeding file: {args.filepath}")
        torrent = TorrentParse(args.filepath)
        self.metadata = torrent.get_info()
        print(self.metadata)
        self.active_peer = Peer(
            host=args.host,
            port=args.port,
            shared_files=self.metadata,
            save_path=DOWNLOAD_FOLDER
            # is_seed=True
        )
        threading.Thread(target=self.active_peer.start, daemon=True).start()
        self.active_peer.get_peer_list(self.active_peer.announce_to_tracker(args.tracker,args.filepath,args.host,args.port))
    def do_download(self, arg: str):
        """Download a file: download <torrent_file>"""
        try:
            args = self.cli._parse_download_args(arg.split())
            self._start_download(args)
        except SystemExit:
            pass

    def _start_download(self, args):
        print(f"Downloading from torrent: {args.filepath}")
        torrent = TorrentParse(args.filepath)
        self.metadata = torrent.get_info()
        if not self.active_peer:
            self.active_peer = Peer(
                host=args.host,
                port=args.port,
                shared_files=self.metadata,
                save_path=args.s
            )
        threading.Thread(target=self.active_peer.start, daemon=True).start()
        self.active_peer.get_peer_list(self.active_peer.announce_to_tracker(torrent.get_announce_url(),args.filepath,args.host,args.port))
        for peer in self.active_peer.peer_list:
            if (self.active_peer.host,self.active_peer.port) != tuple(peer):
                self.active_peer.connect_to_peer(tuple(peer))
        self.active_peer.download(self.metadata[b'name'])

    def do_create(self, arg: str):
        """Create torrent file: create -filepath <path> --tracker <url> [options]"""
        try:
            args = self.cli._parse_create_args(arg.split())
            self.cli.create_torrent(args)
        except SystemExit:
            pass

    def do_run_tracker(self, arg: str):
        """Start tracker server: run-tracker [--host HOST] [--port PORT]"""
        try:
            args = self.cli._parse_tracker_args(arg.split())
            self._start_tracker(args)
        except SystemExit:
            pass

    def _start_tracker(self, args):
        print(f"Starting tracker at {args.host}:{args.port}")
        self.active_tracker = Tracker(host=args.host, port=args.port)
        threading.Thread(target=self.active_tracker.run, daemon=True).start()

    def do_status(self,args):
        """Show current status"""
        print("\n=== System Status ===")
        if self.active_tracker:
            print(f"Tracker: {'Running' if self.active_tracker else 'Stopped'}")
        if self.active_peer:
            print(f"Peer: {'Active' if self.active_peer else 'Inactive'}")
            print(self.active_peer.get_network_status())

    def do_exit(self,args):
        """Exit the program"""
        print("Shutting down...")
        if self.active_peer:
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
        # seed
        seed_p = self.subparsers.add_parser("seed", help="Start seeding a file")
        seed_p.add_argument("-filepath",required=True, help="Path to the file to seed")
        seed_p.add_argument("--host",type=str,default="127.0.0.1",required=True,help="Peer's host")
        seed_p.add_argument("--port",type=int,default=6000,required=True,help="Peer's port")
        seed_p.add_argument("--tracker", required=True, help="Tracker URL")

        # download
        dl_p = self.subparsers.add_parser("download", help="Download a file")
        dl_p.add_argument("-filepath",type=str, required=True, help="Torrent file name")
        dl_p.add_argument("--host",type=str, default="127.0.0.1", help="Peer's host")
        dl_p.add_argument("--port",type=int, default=6000, help="Peer's port")
        dl_p.add_argument("-s",type=str, default=DOWNLOAD_FOLDER, help="Download directory")

        # create
        create_p = self.subparsers.add_parser("create", help="Create torrent file")
        create_p.add_argument("-filepath",type=str, required=True, help="File to share")
        create_p.add_argument("--tracker", required=True, help="Tracker URL")
        create_p.add_argument("-piece_length", type=int, default=CHUNK_SIZE)
        create_p.add_argument("-s", default=TORRENT_FOLDER, help="Output directory")

        # run-tracker (also alias run_tracker)
        tracker_p = self.subparsers.add_parser(
            "run-tracker",
            aliases=["run_tracker"],
            help="Start tracker server"
        )
        tracker_p.add_argument("--host", default=TRACKER_HOST)
        tracker_p.add_argument("--port", type=int, default=TRACKER_PORT)

    def _get_parser(self, command: str) -> argparse.ArgumentParser:
        """
        Directly look up the subparser by its key (the same string used in add_parser).
        """
        try:
            return self.subparsers.choices[command]
        except KeyError:
            raise argparse.ArgumentError(
                None,
                f"Unknown command '{command}'. Choices are: {list(self.subparsers.choices)}"
            )

    def _parse_seed_args(self, args):
        return self._get_parser("seed").parse_args(args)

    def _parse_download_args(self, args):
        return self._get_parser("download").parse_args(args)

    def _parse_create_args(self, args):
        return self._get_parser("create").parse_args(args)

    def _parse_tracker_args(self, args):
        # accept either "run-tracker" or "run_tracker"
        sub = "run-tracker" if "run-tracker" in self.subparsers.choices else "run_tracker"
        return self._get_parser(sub).parse_args(args)

    def create_torrent(self, args):
        print(f"Creating torrent for {args.filepath}")
        torrent = TorrentCreator(
            file_path=args.filepath,
            tracker_url=args.tracker,
            piece_length=args.piece_length
        )
        output_path = torrent.create_torrent(args.s)
        print(f"Torrent created: {output_path}")

    def run(self):
        if len(sys.argv) > 1:
            args = self.parser.parse_args()
            if args.command == "seed":
                self._start_seeding(args)
            elif args.command == "download":
                self._start_download(args)
            elif args.command == "create":
                self.create_torrent(args)
            elif args.command in ("run-tracker"):
                self._start_tracker(args)
        else:
            InteractiveCLI(self).cmdloop()

    # def _start_seeding(self, args):
    #     print(f"Seeding file: {args.filepath}")
    #     peer = Peer(file_path=args.filepath, tracker_url=args.tracker)
    #     peer.start()

    # def _start_download(self, args):
    #     print(f"Downloading from torrent: {args.torrent_file}")
    #     peer = Peer(is_seeder=False)
    #     peer.start_download(args.torrent_file)

    # def _start_tracker(self, args):
    #     print(f"Starting tracker at {args.host}:{args.port}")
    #     tracker = Tracker(host=args.host, port=args.port)
    #     tracker.run()


