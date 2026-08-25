"""Unit tests for Pulse cryptographic operations."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import tempfile
import unittest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from technocore_pulse.crypto import (
    base58btc_decode,
    base58btc_encode,
    contribution_payload,
    create_contribution_proof,
    create_identity,
    did_from_private_key,
    load_identity,
    public_key_from_did,
    sign_bytes,
    verify_bytes,
    verify_contribution_proof,
)


class TestCrypto(unittest.TestCase):
    def test_base58_roundtrip(self):
        data = b"hello technocore pulse"
        encoded = base58btc_encode(data)
        decoded = base58btc_decode(encoded)
        self.assertEqual(decoded, data)

    def test_did_derivation(self):
        key = Ed25519PrivateKey.generate()
        did = did_from_private_key(key)
        self.assertTrue(did.startswith("did:key:z6Mk"))
        pub = public_key_from_did(did)
        self.assertIsNotNone(pub)

    def test_sign_and_verify(self):
        key = Ed25519PrivateKey.generate()
        did = did_from_private_key(key)
        payload = b"room|123456789|test message"
        sig = sign_bytes(key, payload)
        self.assertEqual(len(sig), 86)
        self.assertTrue(verify_bytes(did, sig, payload))

    def test_identity_creation_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            key_path = Path(tmpdir) / "test_identity.pem"
            passphrase = "supersecretpassphrase123"
            did = create_identity(key_path, passphrase)
            self.assertTrue(key_path.exists())

            loaded_key = load_identity(key_path, passphrase)
            derived = did_from_private_key(loaded_key)
            self.assertEqual(derived, did)

    def test_contribution_proof_lifecycle(self):
        key = Ed25519PrivateKey.generate()
        did = did_from_private_key(key)
        url = "https://github.com/greyfox1234/technocore-pulse"
        commit = "a" * 40

        proof = create_contribution_proof(key, url, commit)
        self.assertEqual(proof["did"], did)
        self.assertEqual(proof["artifact_url"], url)
        self.assertTrue(verify_contribution_proof(proof))


if __name__ == "__main__":
    unittest.main()
