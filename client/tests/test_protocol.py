from __future__ import annotations

import socket
import threading

import pytest

from client.edgedet.protocol import (
    DETECTION_SIZE, REQUEST_HEADER_SIZE, RESPONSE_HEADER_SIZE, Detection,
    FrameRequest, InferenceResponse, ProtocolError, STATUS_BAD_CRC, decode_request,
    decode_response, encode_request, encode_response, recv_response,
)


def sample_request() -> FrameRequest:
    return FrameRequest(7, 123456789, 320, 320, 960, 1, bytes(320 * 320 * 3))


def test_wire_sizes_are_stable() -> None:
    assert REQUEST_HEADER_SIZE == 36
    assert RESPONSE_HEADER_SIZE == 44
    assert DETECTION_SIZE == 24


def test_request_round_trip_and_crc() -> None:
    packet = encode_request(sample_request())
    decoded = decode_request(packet)
    assert decoded.frame_id == 7
    assert decoded.timestamp_us == 123456789
    assert decoded.payload == sample_request().payload
    corrupt = packet[:-1] + bytes((packet[-1] ^ 1,))
    with pytest.raises(ProtocolError) as caught:
        decode_request(corrupt)
    assert caught.value.status == STATUS_BAD_CRC


def test_response_round_trip() -> None:
    response = InferenceResponse(0, 9, 100, 120, 2, (
        Detection(3, 0, 0.75, 0.1, 0.2, 0.8, 0.9),
    ))
    decoded = decode_response(encode_response(response))
    assert decoded.frame_id == 9
    assert decoded.kernel_cycles == 100
    assert decoded.dropped_frames == 2
    assert decoded.detections[0].class_id == 3
    assert decoded.detections[0].score == pytest.approx(0.75)


def test_fragmented_socket_response() -> None:
    left, right = socket.socketpair()
    packet = encode_response(InferenceResponse(0, 11, 1, 2, 0, ()))

    def writer() -> None:
        try:
            for byte in packet:
                right.sendall(bytes((byte,)))
        finally:
            right.close()

    thread = threading.Thread(target=writer)
    thread.start()
    try:
        assert recv_response(left).frame_id == 11
    finally:
        left.close()
        thread.join()
