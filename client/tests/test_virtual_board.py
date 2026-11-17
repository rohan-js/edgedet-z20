from __future__ import annotations

import socket
import threading

import pytest

from client.edgedet.protocol import (
    STATUS_ACCELERATOR_TIMEOUT, STATUS_BAD_CRC, ProtocolError,
    make_rgb_request, recv_response,
)
from client.edgedet.reference import BuiltinIntegerReference
from client.edgedet.virtual_board import FaultConfig, VirtualBoardServer, VirtualBoardState


def run_server(faults: FaultConfig) -> tuple[VirtualBoardServer, threading.Thread]:
    state = VirtualBoardState(BuiltinIntegerReference(), faults)
    server = VirtualBoardServer(("127.0.0.1", 0), state, socket_timeout=0.2)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    return server, thread


def stop_server(server: VirtualBoardServer, thread: threading.Thread) -> None:
    server.shutdown()
    server.server_close()
    thread.join()


def test_end_to_end_with_fragmentation() -> None:
    server, thread = run_server(FaultConfig(fragment_size=1))
    try:
        with socket.create_connection(server.server_address, timeout=2.0) as sock:
            sock.sendall(make_rgb_request(bytes(320 * 320 * 3), 55))
            response = recv_response(sock)
            assert response.frame_id == 55
            assert response.status == 0
            assert response.detections == ()
    finally:
        stop_server(server, thread)


def test_crc_fault_is_observable() -> None:
    server, thread = run_server(FaultConfig(corrupt_crc_every=1))
    try:
        with socket.create_connection(server.server_address, timeout=2.0) as sock:
            sock.sendall(make_rgb_request(bytes(320 * 320 * 3), 1))
            with pytest.raises(ProtocolError):
                recv_response(sock)
    finally:
        stop_server(server, thread)


def test_bad_request_crc_returns_protocol_status() -> None:
    server, thread = run_server(FaultConfig())
    try:
        packet = bytearray(make_rgb_request(bytes(320 * 320 * 3), 27))
        packet[-1] ^= 1
        with socket.create_connection(server.server_address, timeout=2.0) as sock:
            sock.sendall(packet)
            response = recv_response(sock)
            assert response.frame_id == 27
            assert response.status == STATUS_BAD_CRC
            assert response.dropped_frames == 1
    finally:
        stop_server(server, thread)


def test_timeout_fault_returns_timeout_status() -> None:
    server, thread = run_server(FaultConfig(timeout_every=1))
    try:
        with socket.create_connection(server.server_address, timeout=2.0) as sock:
            sock.settimeout(2.0)
            sock.sendall(make_rgb_request(bytes(320 * 320 * 3), 3))
            response = recv_response(sock)
            assert response.frame_id == 3
            assert response.status == STATUS_ACCELERATOR_TIMEOUT
    finally:
        stop_server(server, thread)


def test_disconnect_fault_closes_connection() -> None:
    server, thread = run_server(FaultConfig(disconnect_every=1))
    try:
        with socket.create_connection(server.server_address, timeout=2.0) as sock:
            sock.sendall(make_rgb_request(bytes(320 * 320 * 3), 4))
            with pytest.raises(EOFError):
                recv_response(sock)
    finally:
        stop_server(server, thread)
