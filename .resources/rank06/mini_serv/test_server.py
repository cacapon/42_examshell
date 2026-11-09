from contextlib import contextmanager, ExitStack
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

def assert_received(client, expected):
    received = receive_exact(client, len(expected))
    assert received == expected, (f"Expected {expected!r}, got {received!r}")


def assert_no_message(client, timeout=0.3):
    original_timeout = client.gettimeout()
    client.settimeout(timeout)

    try:
        unexpected = client.recv(1024)
    except socket.timeout:
        pass
    else:
        if not unexpected:
            raise AssertionError("Connection closed unexpectedly")
        raise AssertionError(
            f"Received unexpected data: {unexpected!r}"
        )
    finally:
        client.settimeout(original_timeout)


def test_partial_message_buffer(executable, port):
    with connected_clients(executable, port) as (_, clients):
        client0, client1 = clients

        # One complete line and one incomplete line.
        client0.sendall(b"Hello\nWor")
        assert_received(client1, b"client 0: Hello\n")

        assert_no_message(client1)

        # Complete the remaining line.
        client0.sendall(b"ld\n")
        assert_received(client1, b"client 0: World\n")

        print("PASS: Partial message buffer")


def test_repeated_messages(executable, port):
    with connected_clients(executable, port) as (_, clients):
        client0, client1 = clients

        # First message.
        client0.sendall(b"Hello\n")
        assert_received(client1, b"client 0: Hello\n")

        # Second message.
        client0.sendall(b"World\n")
        assert_received(client1, b"client 0: World\n")
        assert_no_message(client1)

        print("PASS: Repeated messages")


def test_multi_client_broadcast(executable, port):
    with connected_clients(executable, port, count=3) as (_, clients):
        client0, client1, client2 = clients

        client0.sendall(b"Hello everyone\n")

        expected = b"client 0: Hello everyone\n"
        assert_received(client1, expected)
        assert_received(client2, expected)

        print("PASS: Multi-client broadcast")


def test_reconnect_after_disconnect(executable, port):
    with connected_clients(executable, port) as (server, clients):
        client0, client1 = clients

        client1.close()
        assert_received(client0, b"server: client 1 just left\n")

        with connect_client(server, port) as client2:
            assert_received(client0, b"server: client 2 just arrived\n")

            client2.sendall(b"Hello\n")
            assert_received(client0, b"client 2: Hello\n")

        print("PASS: Reconnect after disconnect")


def test_disconnect_notification(executable, port):
    with connected_clients(executable, port) as (_, clients):
        client0, client1 = clients
        # Disconnect client 1
        client1.close()
        assert_received(client0, b'server: client 1 just left\n')
        print("PASS: Client disconnect notification")


def test_fragmented_message(executable, port):
    with connected_clients(executable, port) as (_, clients):
        client0, client1 = clients
        # Nothing should be broadcast before newline.
        client0.sendall(b'Hel')
        assert_no_message(client1)

        # Complete the message.
        client0.sendall(b'lo\n')
        assert_received(client1, b"client 0: Hello\n")
        print("PASS: Fragmented message")


def test_multiline_message(executable, port):
    with connected_clients(executable, port) as (_, clients):
        client0, client1 = clients
        # send 2 lines in one call.
        client0.sendall(b'Hello\nWorld\n')

        # Each line must have its own prefix.
        expected = (
            b"client 0: Hello\n"
            b"client 0: World\n"
        )
        assert_received(client1, expected)
        print("PASS: Multiline message")

def test_message_broadcast(executable, port):
    with connected_clients(executable, port) as (_, clients):
        client0, client1 = clients
        client0.sendall(b"Hello\n")
        assert_received(client1, b"client 0: Hello\n")
        assert_no_message(client0)
        print("PASS: Message broadcast")

def test_arrival_notification(executable, port):
    with run_server(executable, port) as server:
        with connect_client(server, port) as client0:
            with connect_client(server, port):
                assert_received(
                    client0, b"server: client 1 just arrived\n"
                )
                print("PASS: Client arrival notification")

def test_connection(executable, port):
    with run_server(executable, port) as server:
        with connect_client(server, port):
            print("PASS: Server accepts TCP connections")


@contextmanager
def connected_clients(executable, port, count=2):
    if count < 1:
        raise ValueError("Client count must be at least 1")

    with run_server(executable, port) as server:
        with ExitStack() as stack:
            clients = []
            for client_id in range(count):
                client = stack.enter_context(connect_client(server, port))

                # Existing clients receive the arrival notice.
                expected = f"server: client {client_id} just arrived\n".encode()
                for existing_client in clients:
                    assert_received(existing_client, expected)
                clients.append(client)
            yield server, clients

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
        "reconnect": test_reconnect_after_disconnect,
        "multi_broadcast": test_multi_client_broadcast,
        "repeated": test_repeated_messages,
        "partial_buffer": test_partial_message_buffer,
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

