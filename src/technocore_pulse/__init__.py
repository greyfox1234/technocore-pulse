"""Technocore Pulse - Real-time stream monitor, DID manager, and webhook alert engine for Technocore."""

__version__ = "1.0.0"
__author__ = "greyfox1234"

from technocore_pulse.crypto import (
    create_identity,
    load_identity,
    did_from_private_key,
    public_key_from_did,
    sign_bytes,
    verify_bytes,
    create_contribution_proof,
    verify_contribution_proof,
)
from technocore_pulse.client import TechnocoreClient
from technocore_pulse.monitor import PulseMonitor

__all__ = [
    "__version__",
    "create_identity",
    "load_identity",
    "did_from_private_key",
    "public_key_from_did",
    "sign_bytes",
    "verify_bytes",
    "create_contribution_proof",
    "verify_contribution_proof",
    "TechnocoreClient",
    "PulseMonitor",
]
