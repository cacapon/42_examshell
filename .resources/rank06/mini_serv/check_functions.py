#!/usr/bin/env python3
import re
import subprocess
import sys

ALLOWED = {
    "write", "close", "select", "socket", "accept", "listen",
    "send", "recv", "bind", "strstr", "malloc", "realloc",
    "free", "calloc", "bzero", "atoi", "sprintf", "strlen",
    "exit", "strcpy", "strcat", "memset", "htons", "htonl",
}

# Symbols added by the compiler/runtime
IGNORED = {
    "_ITM_deregisterTMCloneTable",
    "_ITM_registerTMCloneTable",
    "__cxa_finalize",
    "__gmon_start__",
    "__libc_start_main",
    "__stack_chk_fail",
    "__stack_chk_guard",
}

RUNTIME_SYMBOLS = {"abort"}

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 check_functions.py <compiled_binary>")
        return 2

    result = subprocess.run(
        ["nm", "-u", sys.argv[1]],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print("ERROR: nm failed:", result.stderr.strip())
        return 2

    forbidden = set()

    for line in result.stdout.splitlines():
        match = re.search(r"\b[Uw] ([^\s]+)$", line.strip())
        if not match:
            continue

        symbol = match.group(1).split("@", 1)[0]
        
        if symbol in RUNTIME_SYMBOLS:
            print(f"INFO: Runtime-related symbol detected: {symbol}")
        elif symbol not in ALLOWED and symbol not in IGNORED:
            forbidden.add(symbol)

    if forbidden:
        print("FAIL: Disallowed external functions/symbols:")
        for symbol in sorted(forbidden):
            print("  -", symbol)
        return 1

    print("PASS: No disallowed external symbols detected (nm check).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

