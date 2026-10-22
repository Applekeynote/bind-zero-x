"""Narrow local CA and encrypted-key HTTPS certificates; no trust-store changes."""
from datetime import datetime, timedelta, timezone
import ipaddress
import json
from pathlib import Path
import secrets
import ssl
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from auth_security import SecretBox


def write_private(path, raw):
    import os
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)


def create_tls(directory, address):
    address = ipaddress.IPv4Address(address)
    if not address.is_private or address.is_loopback or address.is_link_local:
        raise ValueError('PRIVATE_WIFI_IPV4_REQUIRED')
    directory = Path(directory)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if any(directory.iterdir()):
        # Never silently replace an established CA/private key.
        return load_tls(directory, str(address))
    box = SecretBox(directory)
    now = datetime.now(timezone.utc)
    ca_key = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'BIND ZERO-X Local Wi-Fi CA')])
    constraints = x509.NameConstraints(permitted_subtrees=[x509.IPAddress(ipaddress.ip_network(str(address)+'/32')),
        x509.IPAddress(ipaddress.ip_network('127.0.0.1/32')), x509.DNSName('localhost')], excluded_subtrees=None)
    ca = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(ca_key.public_key())
          .serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=5))
          .not_valid_after(now+timedelta(days=365)).add_extension(x509.BasicConstraints(ca=True,path_length=0),critical=True)
          .add_extension(x509.KeyUsage(True,False,False,False,False,True,True,None,None),critical=True)
          .add_extension(constraints,critical=True).sign(ca_key,hashes.SHA256()))
    server_key = ec.generate_private_key(ec.SECP256R1())
    server_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, str(address))])
    server = (x509.CertificateBuilder().subject_name(server_name).issuer_name(ca.subject).public_key(server_key.public_key())
              .serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=5))
              .not_valid_after(now+timedelta(days=90)).add_extension(x509.BasicConstraints(ca=False,path_length=None),critical=True)
              .add_extension(x509.SubjectAlternativeName([x509.IPAddress(address),x509.IPAddress(ipaddress.ip_address('127.0.0.1')),x509.DNSName('localhost')]),critical=False)
              .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),critical=False)
              .add_extension(x509.KeyUsage(True,False,False,False,False,False,False,None,None),critical=True)
              .sign(ca_key,hashes.SHA256()))
    for name,key in [('ca',ca_key),('server',server_key)]:
        password = secrets.token_urlsafe(48).encode()
        write_private(directory/(name+'-key.pem'),key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.BestAvailableEncryption(password)))
        write_private(directory/(name+'-pass.protected'),box.seal(password))
    (directory/'ca-cert.cer').write_bytes(ca.public_bytes(serialization.Encoding.DER))
    (directory/'ca-cert.pem').write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    (directory/'server-cert.pem').write_bytes(server.public_bytes(serialization.Encoding.PEM)+ca.public_bytes(serialization.Encoding.PEM))
    (directory/'certificate-info.json').write_text(json.dumps(dict(address=str(address),
        ca_sha256=ca.fingerprint(hashes.SHA256()).hex(),server_sha256=server.fingerprint(hashes.SHA256()).hex(),
        expires_utc=server.not_valid_after_utc.isoformat(),trust_installed=False),indent=2),encoding='utf-8')
    return load_tls(directory,str(address))


def load_tls(directory, address):
    directory = Path(directory)
    cert = directory/'server-cert.pem'; key = directory/'server-key.pem'
    if any(path.is_symlink() for path in (directory,cert,key,directory/'server-pass.protected')):
        raise ValueError('SYMLINK_TLS_CONFIGURATION_REJECTED')
    certificate = x509.load_pem_x509_certificate(cert.read_bytes())
    now = datetime.now(timezone.utc)
    if not certificate.not_valid_before_utc <= now < certificate.not_valid_after_utc:
        raise ValueError('TLS_CERTIFICATE_EXPIRED_OR_NOT_YET_VALID')
    sans = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    if ipaddress.ip_address(address) not in sans.get_values_for_type(x509.IPAddress):
        raise ValueError('TLS_ADDRESS_MISMATCH')
    password = SecretBox(directory).open((directory/'server-pass.protected').read_bytes()).decode()
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(str(cert),str(key),password)
    return dict(ssl_certfile=str(cert),ssl_keyfile=str(key),ssl_keyfile_password=password,
                ssl_version=ssl.PROTOCOL_TLS_SERVER)
