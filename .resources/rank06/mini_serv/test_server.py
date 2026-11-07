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

def test_disconnect_notification(executable, port):
    with connected_clients(executable, port) as (client0, client1):
        # Disconnect client 1
        client1.close()
        expected = b"server: client 1 just left\n"
        received = receive_exact(client0, len(expected))
        assert received == expected, (f"Expected {expected!r}, got {received!r}")
        print("PASS: Client disconnect notification")


def test_fragmented_message(executable, port):
    with connected_clients(executable, port) as (client0, client1):
        # Nothing should be broadcast before newline.
        client0.sendall(b'Hel')
        client1.settimeout(0.3)
        try:
            unexpected = client1.recv(1024)
        except socket.timeout:
            pass
        else:
            raise AssertionError(f"Received data before newline: {unexpected!r}")

        # Complete the message.
        client0.sendall(b'lo\n')
        client1.settimeout(2)

        expected = b"client 0: Hello\n"
        received = receive_exact(client1, len(expected))
        assert received == expected, (f"Expected {expected!r}, got {received!r}")
        print("PASS: Fragmented message")


def test_multiline_message(executable, port):
    with connected_clients(executable, port) as (client0, client1):
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
    with connected_clients(executable, port) as (client0, client1):
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
def connected_clients(executable, port):
    with run_server(executable, port) as server:
        with connect_client(server, port) as client0:
            with connect_client(server, port) as client1:
                arrival = b"server: client 1 just arrived\n"
                received = receive_exact(client0, len(arrival))
                assert received == arrival
                yield client0, client1


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
    if len(sys.argv) not in (2, 3):
        print("Usage: python3 test_server.py <executable>")
        sys.exit(1)

    tests = {
        "connection": test_connection,
        "arrival": test_arrival_notification,
        "broadcast": test_message_broadcast,
        "multiline": test_multiline_message,
        "fragmented": test_fragmented_message,
        "disconnect": test_disconnect_notification,
    }
    executable = sys.argv[1]

    if len(sys.argv) == 3:
        test_name = sys.argv[2]
        if test_name not in tests:
            print(f'Unknown test: {test_name}', file=sys.stderr)
            print(f'Available tests: {", ".join(tests)}', file=sys.stderr)
            sys.exit(1)
        selected_tests = [tests[test_name]]
    else:
        selected_tests = tests.values()
    try:
        for test in selected_tests:
            test(executable, find_free_port())
    except Exception as error:
        print(f"FAIL: {error}", file=sys.stderr)
        sys.exit(1)

