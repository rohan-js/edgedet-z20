"""Byte-exact EDZ2 protocol v1 codec.

All multibyte fields, including IEEE-754 floats, use network byte order. CRC32
covers the encoded header without its final CRC field followed by the payload.
"""

from __future__ import annotations

from dataclasses import dataclass
import socket
import struct
import time
import zlib

MAGIC = b"EDZ2"
VERSION = 1
MESSAGE_FRAME = 1
PIXEL_RGB888 = 1
STATUS_OK = 0
STATUS_BAD_MAGIC = 1
STATUS_BAD_VERSION = 2
STATUS_BAD_MESSAGE = 3
STATUS_BAD_DIMENSIONS = 4
STATUS_BAD_LENGTH = 5
STATUS_BAD_CRC = 6
STATUS_ACCELERATOR_TIMEOUT = 7
STATUS_DMA_ERROR = 8
STATUS_INTERNAL_ERROR = 9

REQUEST_STRUCT = struct.Struct("!4sHHIQHHHHII")
RESPONSE_STRUCT = struct.Struct("!4sHHIQQHHIII")
DETECTION_STRUCT = struct.Struct("!HHfffff")
REQUEST_HEADER_SIZE = REQUEST_STRUCT.size
RESPONSE_HEADER_SIZE = RESPONSE_STRUCT.size
DETECTION_SIZE = DETECTION_STRUCT.size
MAX_PAYLOAD = 320 * 320 * 3
MAX_DETECTIONS = 100


class ProtocolError(RuntimeError):
    def __init__(self, message: str, status: int = STATUS_INTERNAL_ERROR, frame_id: int = 0):
        super().__init__(message)
        self.status = status
        self.frame_id = frame_id


@dataclass(frozen=True)
class FrameRequest:
    frame_id: int
    timestamp_us: int
    width: int
    height: int
    stride: int
    pixel_format: int
    payload: bytes


@dataclass(frozen=True)
class Detection:
    class_id: int
    flags: int
    score: float
    x1: float
    y1: float
    x2: float
    y2: float


@dataclass(frozen=True)
class InferenceResponse:
    status: int
    frame_id: int
    kernel_cycles: int
    total_cycles: int
    dropped_frames: int
    detections: tuple[Detection, ...]


def _crc(header_without_crc: bytes, payload: bytes) -> int:
    return zlib.crc32(payload, zlib.crc32(header_without_crc)) & 0xFFFFFFFF


def encode_request(request: FrameRequest) -> bytes:
    payload = bytes(request.payload)
    if len(payload) > MAX_PAYLOAD:
        raise ProtocolError("payload exceeds protocol maximum", STATUS_BAD_LENGTH, request.frame_id)
    header = REQUEST_STRUCT.pack(
        MAGIC, VERSION, MESSAGE_FRAME, request.frame_id, request.timestamp_us,
        request.width, request.height, request.stride, request.pixel_format,
        len(payload), 0,
    )
    crc = _crc(header[:-4], payload)
    return header[:-4] + struct.pack("!I", crc) + payload


def make_rgb_request(payload: bytes, frame_id: int, timestamp_us: int | None = None) -> bytes:
    return encode_request(FrameRequest(
        frame_id=frame_id,
        timestamp_us=timestamp_us if timestamp_us is not None else time.time_ns() // 1_000,
        width=320,
        height=320,
        stride=960,
        pixel_format=PIXEL_RGB888,
        payload=payload,
    ))


def _validate_request_fields(version: int, message_type: int, width: int,
                             height: int, stride: int, pixel_format: int,
                             payload_length: int, frame_id: int) -> None:
    if version != VERSION:
        raise ProtocolError(f"unsupported version {version}", STATUS_BAD_VERSION, frame_id)
    if message_type != MESSAGE_FRAME:
        raise ProtocolError(f"unsupported message type {message_type}", STATUS_BAD_MESSAGE, frame_id)
    if (width, height, stride, pixel_format) != (320, 320, 960, PIXEL_RGB888):
        raise ProtocolError("expected 320x320 packed RGB888", STATUS_BAD_DIMENSIONS, frame_id)
    if payload_length != stride * height or payload_length > MAX_PAYLOAD:
        raise ProtocolError("invalid payload length", STATUS_BAD_LENGTH, frame_id)


def decode_request(packet: bytes) -> FrameRequest:
    if len(packet) < REQUEST_HEADER_SIZE:
        raise ProtocolError("short request header", STATUS_BAD_LENGTH)
    fields = REQUEST_STRUCT.unpack_from(packet)
    magic, version, message_type, frame_id, timestamp_us, width, height, stride, pixel_format, payload_length, wire_crc = fields
    if magic != MAGIC:
        raise ProtocolError("bad request magic", STATUS_BAD_MAGIC, frame_id)
    _validate_request_fields(version, message_type, width, height, stride,
                             pixel_format, payload_length, frame_id)
    if len(packet) != REQUEST_HEADER_SIZE + payload_length:
        raise ProtocolError("truncated or trailing request payload", STATUS_BAD_LENGTH, frame_id)
    payload = packet[REQUEST_HEADER_SIZE:]
    if _crc(packet[: REQUEST_HEADER_SIZE - 4], payload) != wire_crc:
        raise ProtocolError("request CRC mismatch", STATUS_BAD_CRC, frame_id)
    return FrameRequest(frame_id, timestamp_us, width, height, stride, pixel_format, payload)


def encode_response(response: InferenceResponse) -> bytes:
    if len(response.detections) > MAX_DETECTIONS:
        raise ProtocolError("too many detections", STATUS_BAD_LENGTH, response.frame_id)
    payload = b"".join(DETECTION_STRUCT.pack(
        d.class_id, d.flags, d.score, d.x1, d.y1, d.x2, d.y2
    ) for d in response.detections)
    header = RESPONSE_STRUCT.pack(
        MAGIC, VERSION, response.status, response.frame_id,
        response.kernel_cycles, response.total_cycles, len(response.detections), 0,
        response.dropped_frames, len(payload), 0,
    )
    crc = _crc(header[:-4], payload)
    return header[:-4] + struct.pack("!I", crc) + payload


def decode_response(packet: bytes) -> InferenceResponse:
    if len(packet) < RESPONSE_HEADER_SIZE:
        raise ProtocolError("short response header", STATUS_BAD_LENGTH)
    fields = RESPONSE_STRUCT.unpack_from(packet)
    magic, version, status, frame_id, kernel_cycles, total_cycles, detection_count, reserved, dropped_frames, payload_length, wire_crc = fields
    if magic != MAGIC:
        raise ProtocolError("bad response magic", STATUS_BAD_MAGIC, frame_id)
    if version != VERSION:
        raise ProtocolError("unsupported response version", STATUS_BAD_VERSION, frame_id)
    if reserved != 0 or detection_count > MAX_DETECTIONS or payload_length != detection_count * DETECTION_SIZE:
        raise ProtocolError("invalid response lengths", STATUS_BAD_LENGTH, frame_id)
    if len(packet) != RESPONSE_HEADER_SIZE + payload_length:
        raise ProtocolError("truncated or trailing response payload", STATUS_BAD_LENGTH, frame_id)
    payload = packet[RESPONSE_HEADER_SIZE:]
    if _crc(packet[: RESPONSE_HEADER_SIZE - 4], payload) != wire_crc:
        raise ProtocolError("response CRC mismatch", STATUS_BAD_CRC, frame_id)
    detections = tuple(Detection(*DETECTION_STRUCT.unpack_from(payload, offset))
                       for offset in range(0, payload_length, DETECTION_SIZE))
    return InferenceResponse(status, frame_id, kernel_cycles, total_cycles,
                             dropped_frames, detections)


def recv_exact(sock: socket.socket, length: int) -> bytes:
    chunks: list[bytes] = []
    remaining = length
    while remaining:
        chunk = sock.recv(remaining)
        if not chunk:
            raise EOFError("peer closed connection")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def recv_request(sock: socket.socket) -> FrameRequest:
    header = recv_exact(sock, REQUEST_HEADER_SIZE)
    fields = REQUEST_STRUCT.unpack(header)
    magic, version, message_type, frame_id, timestamp_us, width, height, stride, pixel_format, payload_length, wire_crc = fields
    if magic != MAGIC:
        raise ProtocolError("bad request magic", STATUS_BAD_MAGIC, frame_id)
    _validate_request_fields(version, message_type, width, height, stride,
                             pixel_format, payload_length, frame_id)
    payload = recv_exact(sock, payload_length)
    if _crc(header[:-4], payload) != wire_crc:
        raise ProtocolError("request CRC mismatch", STATUS_BAD_CRC, frame_id)
    return FrameRequest(frame_id, timestamp_us, width, height, stride, pixel_format, payload)


def recv_response(sock: socket.socket) -> InferenceResponse:
    header = recv_exact(sock, RESPONSE_HEADER_SIZE)
    fields = RESPONSE_STRUCT.unpack(header)
    payload_length = fields[-2]
    if payload_length > MAX_DETECTIONS * DETECTION_SIZE:
        raise ProtocolError("response payload exceeds maximum", STATUS_BAD_LENGTH, fields[3])
    return decode_response(header + recv_exact(sock, payload_length))
