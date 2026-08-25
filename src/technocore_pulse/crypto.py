"""Cryptographic utilities for Ed25519 DID creation, signing, and verification."""

from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

MULTICODEC_ED25519 = b"\xed\x01"
MULTIBASE_LENGTH = 48
SIGNATURE_LENGTH = 86

BASE58BTC_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
BASE58BTC_INDEX = {char: idx for idx, char in enumerate(BASE58BTC_ALPHABET)}
SIGNATURE_PATTERN = re.compile(rf"^[A-Za-z0-9_-]{{{SIGNATURE_LENGTH}}}$")
COMMIT_PATTERN = re.compile(r"^(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$")


class PulseCryptoError(ValueError):
    """Cryptographic operation or key validation failure."""


def base58btc_encode(data: bytes) -> str:
    """Encode raw bytes into Base58BTC string, preserving leading zero bytes."""
    zeroes = len(data) - len(data.lstrip(b"\x00"))
    num = int.from_bytes(data, "big")
    encoded = ""
    while num:
        num, rem = divmod(num, 58)
        encoded = BASE58BTC_ALPHABET[rem] + encoded
    return "1" * zeroes + encoded


def base58btc_decode(text: str) -> bytes:
    """Decode Base58BTC string into bytes."""
    num = 0
    for char in text:
        if char not in BASE58BTC_INDEX:
            raise PulseCryptoError(f"Invalid Base58 character: {char!r}")
        num = num * 58 + BASE58BTC_INDEX[char]
    decoded = num.to_bytes((num.bit_length() + 7) // 8, "big") if num else b""
    zeroes = len(text) - len(text.lstrip("1"))
    return b"\x00" * zeroes + decoded


def did_from_private_key(private_key: Ed25519PrivateKey) -> str:
    """Derive canonical did:key:z6Mk... identifier from an Ed25519 private key."""
    public_raw = private_key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    multibase = "z" + base58btc_encode(MULTICODEC_ED25519 + public_raw)
    if len(multibase) != MULTIBASE_LENGTH or not multibase.startswith("z6Mk"):
        raise PulseCryptoError("Failed to derive valid Ed25519 did:key")
    return f"did:key:{multibase}"


def public_key_from_did(did: str) -> Ed25519PublicKey:
    """Extract Ed25519PublicKey object from a canonical did:key string."""
    prefix = "did:key:"
    if not isinstance(did, str) or not did.startswith(prefix):
        raise PulseCryptoError("DID must start with 'did:key:'")
    multibase = did[len(prefix) :]
    if len(multibase) != MULTIBASE_LENGTH or not multibase.startswith("z6Mk"):
        raise PulseCryptoError("DID multibase must be 48 characters starting with z6Mk")
    raw = base58btc_decode(multibase[1:])
    if len(raw) != 34 or not raw.startswith(MULTICODEC_ED25519):
        raise PulseCryptoError("Decoded multicodec does not match Ed25519")
    try:
        return Ed25519PublicKey.from_public_bytes(raw[2:])
    except Exception as err:
        raise PulseCryptoError("Invalid public key material in DID") from err


def sign_bytes(private_key: Ed25519PrivateKey, payload: bytes) -> str:
    """Sign payload bytes and return unpadded base64url string."""
    sig = private_key.sign(payload)
    encoded = base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")
    if not SIGNATURE_PATTERN.match(encoded):
        raise PulseCryptoError("Invalid base64url signature encoding produced")
    return encoded


def verify_bytes(did: str, signature: str, payload: bytes) -> bool:
    """Verify unpadded base64url Ed25519 signature against DID."""
    if not SIGNATURE_PATTERN.match(signature or ""):
        raise PulseCryptoError("Signature must be 86 base64url characters")
    raw_sig = base64.urlsafe_b64decode(signature + "==")
    pub = public_key_from_did(did)
    try:
        pub.verify(raw_sig, payload)
        return True
    except InvalidSignature:
        return False


def create_identity(path: Path | str, passphrase: str) -> str:
    """Create a new PKCS#8 encrypted Ed25519 private key file and return its DID."""
    target = Path(path).expanduser().resolve()
    if target.exists():
        raise PulseCryptoError(f"Identity file already exists at: {target}")
    if not passphrase or len(passphrase) < 12:
        raise PulseCryptoError("Passphrase must contain at least 12 characters")

    private_key = Ed25519PrivateKey.generate()
    encrypted_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(passphrase.encode("utf-8")),
    )

    target.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(encrypted_pem)
        f.flush()
        os.fsync(f.fileno())

    return did_from_private_key(private_key)


def load_identity(path: Path | str, passphrase: str | bytes) -> Ed25519PrivateKey:
    """Load PKCS#8 encrypted Ed25519 identity key with passphrase."""
    target = Path(path).expanduser().resolve()
    if not target.exists():
        raise PulseCryptoError(f"Identity key file not found: {target}")

    raw_pem = target.read_bytes()
    pw_bytes = passphrase.encode("utf-8") if isinstance(passphrase, str) else passphrase

    try:
        loaded = serialization.load_pem_private_key(raw_pem, password=pw_bytes)
    except (ValueError, TypeError, UnsupportedAlgorithm) as err:
        raise PulseCryptoError("Incorrect passphrase or corrupted identity key") from err

    if not isinstance(loaded, Ed25519PrivateKey):
        raise PulseCryptoError("Loaded key is not an Ed25519 private key")
    return loaded


def contribution_payload(artifact_url: str, commit: str) -> bytes:
    """Generate canonical JSON bytes for contribution proof verification."""
    clean_url = artifact_url.strip()
    clean_commit = commit.strip().lower()
    if not clean_url.startswith("https://"):
        raise PulseCryptoError("Artifact URL must be a valid HTTPS URL")
    if not COMMIT_PATTERN.match(clean_commit):
        raise PulseCryptoError("Commit must be a full 40- or 64-hexadecimal revision hash")

    doc = {
        "artifact_url": clean_url,
        "commit": clean_commit,
        "schema": "technocore-contribution-v1",
    }
    return json.dumps(doc, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def create_contribution_proof(
    private_key: Ed25519PrivateKey,
    artifact_url: str,
    commit: str,
) -> dict[str, str]:
    """Generate signed contribution proof record."""
    payload = contribution_payload(artifact_url, commit)
    sig = sign_bytes(private_key, payload)
    return {
        "schema": "technocore-contribution-proof-v1",
        "did": did_from_private_key(private_key),
        "artifact_url": artifact_url.strip(),
        "commit": commit.strip().lower(),
        "signature": sig,
    }


def verify_contribution_proof(proof: dict[str, Any]) -> bool:
    """Verify signed contribution proof dictionary."""
    if proof.get("schema") != "technocore-contribution-proof-v1":
        raise PulseCryptoError("Invalid contribution proof schema")
    for key in ("did", "artifact_url", "commit", "signature"):
        if not isinstance(proof.get(key), str):
            raise PulseCryptoError(f"Missing or invalid field: {key}")

    payload = contribution_payload(proof["artifact_url"], proof["commit"])
    valid = verify_bytes(proof["did"], proof["signature"], payload)
    if not valid:
        raise PulseCryptoError("Contribution proof signature verification failed")
    return True
