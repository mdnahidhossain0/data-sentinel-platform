import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Generates a new Ed25519 signing keypair. Rotating keys invalidates every license key issued "
        "under the old keypair, since verification depends on the hardcoded public key matching the "
        "private key that signed it. After rotating, update VENDOR_PUBLIC_KEY_B64 in this project's "
        "licenses/crypto.py AND in the Data Sentinel app's licensing/crypto.py before issuing new licenses."
    )

    def handle(self, *args, **options):
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()

        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

        self.stdout.write("New keypair generated.\n")
        self.stdout.write(f"LICENSE_SIGNING_PRIVATE_KEY_B64={base64.b64encode(private_bytes).decode()}")
        self.stdout.write(f"VENDOR_PUBLIC_KEY_B64 = \"{base64.b64encode(public_bytes).decode()}\"")
        self.stdout.write(
            self.style.WARNING(
                "\nSet the private key as an env var here only. Paste the public key into "
                "VENDOR_PUBLIC_KEY_B64 in both licenses/crypto.py and the Data Sentinel app's "
                "licensing/crypto.py, then redeploy both before issuing licenses with the new key."
            )
        )
