"""Run the protocol-v1 virtual-board soak without invoking a neural network."""

from __future__ import annotations

import argparse
import gc
import json
import os
import socket
import threading
import time
from pathlib import Path

from client.edgedet.protocol import make_rgb_request, recv_response
from client.edgedet.reference import ReferenceResult
from client.edgedet.virtual_board import FaultConfig, VirtualBoardServer, VirtualBoardState


class ProtocolSoakBackend:
    name = "protocol-soak-noop (transport only)"

    def infer(self, rgb: bytes) -> ReferenceResult:
        if len(rgb) != 320 * 320 * 3:
            raise ValueError("unexpected frame size")
        return ReferenceResult((), 0)


def _rss_bytes() -> int:
    try:
        import psutil
    except ImportError:
        return 0
    return int(psutil.Process(os.getpid()).memory_info().rss)


def run(frames: int, fragment_size: int, max_growth_mb: float) -> dict[str, float | int]:
    state = VirtualBoardState(ProtocolSoakBackend(), FaultConfig(fragment_size=fragment_size))
    server = VirtualBoardServer(("127.0.0.1", 0), state, socket_timeout=5.0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    payload = bytes(320 * 320 * 3)
    start = time.perf_counter()
    before = _rss_bytes()
    try:
        with socket.create_connection(server.server_address, timeout=5.0) as sock:
            sock.settimeout(5.0)
            for frame_id in range(frames):
                sock.sendall(make_rgb_request(payload, frame_id))
                response = recv_response(sock)
                if response.frame_id != frame_id or response.status != 0:
                    raise AssertionError(
                        f"frame {frame_id}: status={response.status}, response={response.frame_id}"
                    )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5.0)
    gc.collect()
    elapsed = time.perf_counter() - start
    after = _rss_bytes()
    growth = max(0, after - before)
    if before and growth > max_growth_mb * 1024 * 1024:
        raise AssertionError(f"RSS grew by {growth / 1024 / 1024:.2f} MiB")
    return {
        "frames": frames,
        "elapsed_seconds": elapsed,
        "frames_per_second_host_transport": frames / max(elapsed, 1e-9),
        "rss_growth_bytes": growth,
        "dropped_frames": state.dropped,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=10_000)
    parser.add_argument("--fragment-size", type=int, default=7)
    parser.add_argument("--max-growth-mb", type=float, default=64.0)
    parser.add_argument(
        "--output", type=Path,
        default=Path("artifacts/work/verification/virtual_board_soak.json"),
    )
    args = parser.parse_args()
    if args.frames <= 0:
        parser.error("--frames must be positive")
    result = run(args.frames, args.fragment_size, args.max_growth_mb)
    report = {
        **result,
        "evidence": "host_virtual_transport",
        "hardware_measured": False,
        "backend": "protocol-soak-noop",
        "response_fragment_size": args.fragment_size,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for key, value in result.items():
        print(f"{key}={value}")
    print("VIRTUAL BOARD SOAK PASSED — NOT HARDWARE MEASUREMENT")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
