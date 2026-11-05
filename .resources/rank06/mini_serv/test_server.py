from contextlib import contextmanager
import socket
import subprocess
import sys
import time

HOST = "127.0.0.1"

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, 0))
        return sock.getsockname()[1]

def receive_exact(client, size):
    received = b""
    while len(received) < size:
        chunk = client.recv(size - len(received))
        if not chunk:
            raise RuntimeError("Connection closed unexpectedly")
        received += chunk
    return received

def test_multiline_message(executable, port):
    with run_server(executable, port) as server:
        with connect_client(server, port) as client0:
            with connect_client(server, port) as client1:
                arrival = b"server: client 1 just arrived\n"
                received = receive_exact(client0, len(arrival))
                assert received == arrival

                # send 2 lines in one call.
                client0.sendall(b'Hello\nWorld\n')

                # Each line must have its own prefix.
                expected = (
                    b"client 0: Hello\n"
                    b"client 0: World\n"
                )
                received = receive_exact(client1, len(expected))
                assert received == expected, (f"Expected {expected!r}, got {received!r}")
                print("PASS: Multiline message")

def test_message_broadcast(executable, port):
    with run_server(executable, port) as server:
        with connect_client(server, port) as client0:
            with connect_client(server, port) as client1:
                expected_arrival = b"server: client 1 just arrived\n"
                received = receive_exact(client0, len(expected_arrival))
                assert received == expected_arrival

                client0.sendall(b"Hello\n")

                expected = b"client 0: Hello\n"
                received = receive_exact(client1, len(expected))
                assert received == expected, (f"Expected {expected!r}, got {received!r}")

                # Verify that the sender does not receive its own message.
                client0.settimeout(0.3)
                try:
                    unexpected = client0.recv(1024)
                except socket.timeout:
                    pass # No message received, as expected.
                else:
                    if unexpected:
                        raise AssertionError(f"Sender received unexpected data: {unexpected!r}")

                    raise AssertionError("Sender connection closed unexpectedly")

                print("PASS: Message broadcast")

def test_arrival_notification(executable, port):
    with run_server(executable, port) as server:
        with connect_client(server, port) as client0:
            with connect_client(server, port):
                expected = b"server: client 1 just arrived\n"
                received = receive_exact(client0, len(expected))
                assert received == expected, (
                    f"Expected {expected!r}, got {received!r}"
                )
                print("PASS: Client arrival notification")


def test_connection(executable, port):
    with run_server(executable, port) as server:
        with connect_client(server, port):
            print("PASS: Server accepts TCP connections")

@contextmanager
def run_server(executable, port):
    server = subprocess.Popen(
        [executable, str(port)],
        stdout=subprocess.DEVNULL,
        stderr=None,
    )

    try:
        yield server
    finally:
        server.terminate()
        try:
            server.wait(timeout=2)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()

def connect_client(server, port):
    deadline = time.monotonic() + 3

    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise RuntimeError("Server exited unexpectedly")

        try:
            client = socket.create_connection((HOST, port), timeout=0.2)
            client.settimeout(2)
            return client
        except OSError:
            time.sleep(0.05)
    raise RuntimeError("Server did not accept connections")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 test_server.py <executable>")
        sys.exit(1)

    try:
        port = find_free_port()
        test_connection(sys.argv[1], port)
        port = find_free_port()
        test_arrival_notification(sys.argv[1], port)
        port = find_free_port()
        test_message_broadcast(sys.argv[1], port)
        port = find_free_port()
        test_multiline_message(sys.argv[1], port)
    except Exception as error:
        print(f"FAIL: {error}", file=sys.stderr)
        sys.exit(1)

