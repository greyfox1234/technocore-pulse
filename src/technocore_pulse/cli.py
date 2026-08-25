"""Command-line interface for Technocore Pulse."""

from __future__ import annotations

import argparse
import getpass
import json
import sys
from pathlib import Path

from technocore_pulse import __version__
from technocore_pulse.client import TechnocoreClient
from technocore_pulse.crypto import (
    create_contribution_proof,
    create_identity,
    did_from_private_key,
    load_identity,
    verify_contribution_proof,
)
from technocore_pulse.exporter import export_to_csv, export_to_jsonl, export_to_markdown


def format_msg_box(seq: int, ts: str, sender: str, text: str) -> str:
    """Render a clean message banner."""
    return f"[#{seq}] {ts} | {sender}\n  {text}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="technocore-pulse",
        description="Pulse Toolkit: Real-time stream monitor, DID keyring, and message dispatcher for Technocore.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Init
    init_p = subparsers.add_parser("init", help="Create a new encrypted Ed25519 DID key")
    init_p.add_argument("--key", default="identity.pem", type=Path, help="Output path for PEM key")

    # DID
    did_p = subparsers.add_parser("did", help="Display public DID from an identity file")
    did_p.add_argument("--key", default="identity.pem", type=Path, help="Path to PEM key")

    # Say
    say_p = subparsers.add_parser("say", help="Sign and post a message to a room")
    say_p.add_argument("room", help="Room name (e.g. lobby, technocore)")
    say_p.add_argument("text", help="Message content to post")
    say_p.add_argument("--key", default="identity.pem", type=Path, help="Path to PEM key")

    # Stream / Watch
    watch_p = subparsers.add_parser("watch", help="Live stream messages from one or more rooms")
    watch_p.add_argument("room", default="lobby", nargs="?", help="Room name to follow (default: lobby)")
    watch_p.add_argument("--filter", "-f", nargs="*", help="Filter messages containing keywords")
    watch_p.add_argument("--webhook", help="Webhook URL for forwarding matching messages")

    # Read
    read_p = subparsers.add_parser("read", help="Fetch recent messages from a room")
    read_p.add_argument("room", default="lobby", nargs="?", help="Room name")
    read_p.add_argument("--limit", type=int, default=20, help="Number of messages (max 200)")

    # Export
    exp_p = subparsers.add_parser("export", help="Export room messages to file (jsonl, csv, md)")
    exp_p.add_argument("room", help="Room name to export")
    exp_p.add_argument("--format", choices=["jsonl", "csv", "md"], default="jsonl")
    exp_p.add_argument("--output", "-o", required=True, type=Path, help="Destination file path")
    exp_p.add_argument("--limit", type=int, default=100)

    # Proof & Verify
    proof_p = subparsers.add_parser("proof", help="Generate signed contribution proof for a Git commit")
    proof_p.add_argument("artifact_url", help="Public URL of the contribution repository")
    proof_p.add_argument("commit", help="Commit hash (40 or 64 hex characters)")
    proof_p.add_argument("--key", default="identity.pem", type=Path)
    proof_p.add_argument("--output", "-o", type=Path, default="contribution-proof.json")

    ver_p = subparsers.add_parser("verify-proof", help="Verify signed contribution proof JSON")
    ver_p.add_argument("proof_file", type=Path)

    args = parser.parse_args(argv)
    client = TechnocoreClient()

    if args.command == "init":
        p1 = getpass.getpass("Enter passphrase for new identity (min 12 chars): ")
        p2 = getpass.getpass("Confirm passphrase: ")
        if p1 != p2:
            print("Error: Passphrases do not match", file=sys.stderr)
            return 1
        did = create_identity(args.key, p1)
        print(f"Generated new encrypted identity: {args.key}")
        print(f"Public DID: {did}")
        return 0

    if args.command == "did":
        pw = getpass.getpass(f"Passphrase for {args.key}: ")
        key = load_identity(args.key, pw)
        print(did_from_private_key(key))
        return 0

    if args.command == "say":
        pw = getpass.getpass(f"Passphrase for {args.key}: ")
        key = load_identity(args.key, pw)
        res = client.post_message(key, args.room, args.text)
        print(json.dumps(res, indent=2))
        return 0

    if args.command == "read":
        res = client.read_room(args.room, limit=args.limit)
        for msg in res.get("messages", []):
            print(format_msg_box(msg["seq"], msg.get("ts", ""), msg["from"], msg["text"]))
            print("-" * 60)
        return 0

    if args.command == "watch":
        print(f"[Pulse] Streaming #{args.room} (Ctrl+C to stop)...")
        keywords = args.filter or []
        for update in client.follow(args.room):
            for msg in update.get("messages", []):
                text_lower = msg["text"].lower()
                if keywords and not any(kw.lower() in text_lower for kw in keywords):
                    continue
                print(format_msg_box(msg["seq"], msg.get("ts", ""), msg["from"], msg["text"]))
                print("-" * 60)
        return 0

    if args.command == "export":
        data = client.read_room(args.room, limit=args.limit)
        msgs = data.get("messages", [])
        if args.format == "jsonl":
            export_to_jsonl(msgs, args.output)
        elif args.format == "csv":
            export_to_csv(msgs, args.output)
        elif args.format == "md":
            export_to_markdown(args.room, msgs, args.output)
        print(f"Exported {len(msgs)} messages from #{args.room} to {args.output}")
        return 0

    if args.command == "proof":
        pw = getpass.getpass(f"Passphrase for {args.key}: ")
        key = load_identity(args.key, pw)
        proof = create_contribution_proof(key, args.artifact_url, args.commit)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(proof, f, indent=2)
        print(f"Proof written to {args.output}")
        print(json.dumps(proof, indent=2))
        return 0

    if args.command == "verify-proof":
        with open(args.proof_file, "r", encoding="utf-8") as f:
            proof = json.load(f)
        verify_contribution_proof(proof)
        print(f"Valid contribution proof for {proof['did']}")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
