def read_message(client_sock):
    buffer = b""
    try:
        while True:
            chunk = client_sock.recv(1024)
            if not chunk:
                if not buffer:
                    return None, RuntimeError("socket closed by peer")
                break
            buffer += chunk
            if b"\n" in chunk:
                break

        try:
            msg = buffer.decode("utf-8").strip()
            return msg, None
        except UnicodeDecodeError as e:
            return None, RuntimeError(f"decode_error: {e}")
    except OSError as e:
            return None, RuntimeError(f"recv_error: {e}")