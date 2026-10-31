
import socket
import subprocess
import sys
import time

HOST = "127.0.0.1"

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, 0))
        return sock.getsockname()[1]

def test_connection(executable, port):
    server = subprocess.Popen(
        [executable, str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    try:
        deadline = time.monotonic() + 3

        while time.monotonic() < deadline:
            if server.poll() is not None:
                raise RuntimeError("Server exited unexpectedly")

            try:
                with socket.create_connection((HOST, port), timeout=0.2):
                    print("PASS: Server accepts TCP connections")
                    return
            except OSError:
                time.sleep(0.05)

        raise RuntimeError("Server did not accept connections")

    finally:
        server.terminate()
        try:
            server.wait(timeout=2)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 test_server.py <executable>")
        sys.exit(1)

    try:
        port = find_free_port()
        test_connection(sys.argv[1], port)
    except Exception as error:
        print(f"FAIL: {error}", file=sys.stderr)
        sys.exit(1)

