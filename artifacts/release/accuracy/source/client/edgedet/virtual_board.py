"""Protocol-compatible EdgeDet-Z20 virtual board with deterministic fault modes."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import socket
import socketserver
import threading
import time

from .protocol import (
    InferenceResponse, ProtocolError, STATUS_ACCELERATOR_TIMEOUT, STATUS_INTERNAL_ERROR,
    STATUS_OK, encode_response, recv_request,
)
from .reference import ReferenceBackend, load_backend


@dataclass
class FaultConfig:
    delay_ms: int = 0
    fragment_size: int = 0
    disconnect_every: int = 0
    corrupt_crc_every: int = 0
    timeout_every: int = 0


class VirtualBoardState:
    def __init__(self, backend: ReferenceBackend, faults: FaultConfig):
        self.backend = backend
        self.faults = faults
        self.frames = 0
        self.dropped = 0
        self.lock = threading.Lock()

    def next_frame(self) -> tuple[int, int]:
        with self.lock:
            self.frames += 1
            return self.frames, self.dropped

    def drop(self) -> None:
        with self.lock:
            self.dropped += 1


def _send_fragmented(sock: socket.socket, packet: bytes, fragment_size: int) -> None:
    if fragment_size <= 0:
        sock.sendall(packet)
        return
    for offset in range(0, len(packet), fragment_size):
        sock.sendall(packet[offset: offset + fragment_size])


class RequestHandler(socketserver.BaseRequestHandler):
    server: "VirtualBoardServer"

    def handle(self) -> None:
        self.request.settimeout(self.server.socket_timeout)
        while True:
            try:
                request = recv_request(self.request)
            except EOFError:
                return
            except (ConnectionError, socket.timeout):
                return
            except ProtocolError as error:
                self.server.state.drop()
                response = InferenceResponse(error.status, error.frame_id, 0, 0,
                                             self.server.state.dropped, ())
                _send_fragmented(self.request, encode_response(response),
                                 self.server.state.faults.fragment_size)
                return

            ordinal, dropped = self.server.state.next_frame()
            faults = self.server.state.faults
            if faults.disconnect_every and ordinal % faults.disconnect_every == 0:
                self.server.state.drop()
                return
            if faults.timeout_every and ordinal % faults.timeout_every == 0:
                time.sleep(self.server.socket_timeout + 0.1)
                response = InferenceResponse(STATUS_ACCELERATOR_TIMEOUT,
                                             request.frame_id, 0, 0, dropped, ())
            else:
                if faults.delay_ms:
                    time.sleep(faults.delay_ms / 1000.0)
                total_start = time.perf_counter_ns()
                try:
                    result = self.server.state.backend.infer(request.payload)
                    total_ns = time.perf_counter_ns() - total_start
                    # Cycle fields emulate a 100 MHz counter and are never hardware measurements.
                    response = InferenceResponse(
                        STATUS_OK, request.frame_id, result.elapsed_ns // 10,
                        total_ns // 10, dropped, result.detections,
                    )
                except Exception as error:  # Keep protocol errors observable to the client.
                    self.server.log(f"backend error: {error}")
                    response = InferenceResponse(STATUS_INTERNAL_ERROR,
                                                 request.frame_id, 0, 0, dropped, ())
            packet = encode_response(response)
            if faults.corrupt_crc_every and ordinal % faults.corrupt_crc_every == 0:
                packet = packet[:40] + bytes((packet[40] ^ 1,)) + packet[41:]
            try:
                _send_fragmented(self.request, packet, faults.fragment_size)
            except ConnectionError:
                return


class VirtualBoardServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address: tuple[str, int], state: VirtualBoardState,
                 socket_timeout: float = 3.0):
        self.state = state
        self.socket_timeout = socket_timeout
        super().__init__(address, RequestHandler)

    @staticmethod
    def log(message: str) -> None:
        print(f"[virtual-board] {message}", flush=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5001)
    parser.add_argument("--backend", default="builtin",
                        help="builtin or package.module:factory")
    parser.add_argument("--delay-ms", type=int, default=0)
    parser.add_argument("--fragment-size", type=int, default=0)
    parser.add_argument("--disconnect-every", type=int, default=0)
    parser.add_argument("--corrupt-crc-every", type=int, default=0)
    parser.add_argument("--timeout-every", type=int, default=0)
    parser.add_argument("--socket-timeout", type=float, default=3.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    backend = load_backend(args.backend)
    faults = FaultConfig(args.delay_ms, args.fragment_size, args.disconnect_every,
                         args.corrupt_crc_every, args.timeout_every)
    state = VirtualBoardState(backend, faults)
    with VirtualBoardServer((args.host, args.port), state, args.socket_timeout) as server:
        print("VIRTUAL BOARD — NOT HARDWARE MEASUREMENT", flush=True)
        print(f"Listening on {args.host}:{args.port}; backend={backend.name}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
