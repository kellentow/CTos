import json,socket

def coder(data, encode=True) -> bytes:
    if encode:
        try:
            packet = json.dumps(data)
        except Exception as e:
            raise TypeError("Could not encode packet") from e
        packet = packet.encode("utf-8")
        packet_len = len(packet).to_bytes(8,byteorder="big") #oh nooo i can't send 18446744073709551616 long messages
        return (packet_len,packet)
    else:
        try:
            packet = data.decode("utf-8")
            packet = json.loads(packet)
            return packet
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            print(f"Error decoding packet: {e}")
            return None

def send(conn:socket.socket,data):
    packet_len, packet = coder(data,encode=True)
    conn.send(packet_len+packet)

def recv(conn: socket.socket):
    try:
        conn.settimeout(0.001)  # Short timeout for non-blocking behavior
        len_bytes = conn.recv(8)
        conn.settimeout(None)
        if len(len_bytes) < 8:
            return None  # No data available
        data_len = int.from_bytes(len_bytes, "big")
        if data_len == 0:
            return None # No data to read
        else:
            received = b""
            while len(received) < data_len:
                chunk = conn.recv(data_len - len(received))
                if not chunk:
                    return None  # Socket closed unexpectedly
                received += chunk
            packet = received  
    except (OSError, socket.timeout):
        conn.settimeout(None)
        return None  # No data available or timeout

    return coder(packet,encode=False)

def create_pem(pub_path,priv_path):
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    import datetime

    # Generate private key
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    # Build certificate
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, u"US"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"California"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, u"San Francisco"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"Personal"),
        x509.NameAttribute(NameOID.COMMON_NAME, u"Personal"),
    ])
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.utcnow()
    ).not_valid_after(
        # Certificate valid for 1 year
        datetime.datetime.utcnow() + datetime.timedelta(days=365)
    ).sign(key, hashes.SHA256())

    # Write private key to PEM file
    with open(pub_path, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))

    # Write certificate to PEM file
    with open(priv_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
