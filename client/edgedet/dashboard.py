"""Live EdgeDet-Z20 client with PySide6 UI and an automatic CLI fallback."""

from __future__ import annotations

import argparse
import socket
import sys
import time
from typing import Any

from .protocol import InferenceResponse, ProtocolError, make_rgb_request, recv_response
from .reference import load_backend

CLASS_NAMES = ("person", "bicycle", "motorcycle", "car", "bus", "truck")
COLORS = ((75, 220, 90), (230, 180, 40), (255, 110, 30),
          (60, 180, 255), (180, 90, 255), (60, 80, 230))
VIRTUAL_BANNER = "VIRTUAL BOARD — NOT HARDWARE MEASUREMENT"


class BoardClient:
    def __init__(self, host: str, port: int, timeout: float):
        self.address = (host, port)
        self.timeout = timeout
        self.sock: socket.socket | None = None

    def close(self) -> None:
        if self.sock is not None:
            self.sock.close()
            self.sock = None

    def connect(self) -> None:
        self.close()
        self.sock = socket.create_connection(self.address, timeout=self.timeout)
        self.sock.settimeout(self.timeout)

    def infer(self, rgb: bytes, frame_id: int) -> InferenceResponse:
        if self.sock is None:
            self.connect()
        assert self.sock is not None
        try:
            self.sock.sendall(make_rgb_request(rgb, frame_id))
            response = recv_response(self.sock)
        except (OSError, EOFError, ProtocolError):
            self.close()
            raise
        if response.frame_id != frame_id:
            self.close()
            raise ProtocolError(f"stale response {response.frame_id}, expected {frame_id}")
        return response


def _load_cv() -> tuple[Any, Any]:
    try:
        import cv2
        import numpy as np
    except ImportError as error:
        raise SystemExit("Dashboard/CLI capture requires: pip install -e 'client[dashboard]'") from error
    return cv2, np


def letterbox_320(frame: Any, cv2: Any, np: Any) -> tuple[Any, tuple[float, int, int]]:
    height, width = frame.shape[:2]
    scale = min(320.0 / width, 320.0 / height)
    resized_width = max(1, round(width * scale))
    resized_height = max(1, round(height * scale))
    # Bilinear matches the canonical training letterbox; the following 2x2
    # 320->160 reduction remains the explicitly exact integer area operation.
    resized = cv2.resize(frame, (resized_width, resized_height), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((320, 320, 3), 114, dtype=np.uint8)
    left = (320 - resized_width) // 2
    top = (320 - resized_height) // 2
    canvas[top:top + resized_height, left:left + resized_width] = resized
    return canvas, (scale, left, top)


def draw_detections(frame: Any, response: InferenceResponse, cv2: Any) -> Any:
    height, width = frame.shape[:2]
    output = frame.copy()
    for detection in response.detections:
        class_id = detection.class_id
        color = COLORS[class_id] if class_id < len(COLORS) else (255, 255, 255)
        name = CLASS_NAMES[class_id] if class_id < len(CLASS_NAMES) else f"class-{class_id}"
        x1 = max(0, min(width - 1, round(detection.x1 * width)))
        y1 = max(0, min(height - 1, round(detection.y1 * height)))
        x2 = max(0, min(width - 1, round(detection.x2 * width)))
        y2 = max(0, min(height - 1, round(detection.y2 * height)))
        cv2.rectangle(output, (x1, y1), (x2, y2), color, 2)
        diagnostic = " diagnostic" if detection.flags & 0x8000 else ""
        label = f"{name} {detection.score:.2f}{diagnostic}"
        cv2.putText(output, label, (x1, max(16, y1 - 5)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)
    return output


def _open_capture(source: str, cv2: Any) -> Any:
    resolved: int | str = int(source) if source.isdecimal() else source
    capture = cv2.VideoCapture(resolved)
    if not capture.isOpened():
        raise SystemExit(f"cannot open source {source!r}")
    return capture


def run_cli(args: argparse.Namespace) -> int:
    cv2, np = _load_cv()
    capture = _open_capture(args.source, cv2)
    client = BoardClient(args.host, args.port, args.timeout)
    float_backend = load_backend(args.float_backend) if args.float_backend else None
    print(VIRTUAL_BANNER if not args.hardware_target else
          "HARDWARE TARGET — measurements require physical validation", flush=True)
    print(f"model_profile={args.profile}", flush=True)
    frame_id = 0
    try:
        while args.max_frames == 0 or frame_id < args.max_frames:
            ok, frame = capture.read()
            if not ok:
                break
            framed, _ = letterbox_320(frame, cv2, np)
            rgb = cv2.cvtColor(framed, cv2.COLOR_BGR2RGB).tobytes()
            try:
                float_result = float_backend.infer(rgb) if float_backend else None
                start = time.perf_counter()
                response = client.infer(rgb, frame_id)
                elapsed_ms = (time.perf_counter() - start) * 1000.0
                comparison = (f" float_detections={len(float_result.detections)}"
                              f" float_ms={float_result.elapsed_ns / 1e6:.2f}"
                              if float_result else "")
                print(f"frame={frame_id} status={response.status} "
                      f"detections={len(response.detections)} host_rtt_ms={elapsed_ms:.2f} "
                      f"reported_cycles={response.total_cycles}{comparison}", flush=True)
            except (OSError, EOFError, ProtocolError) as error:
                print(f"frame={frame_id} error={error}; reconnecting", flush=True)
                time.sleep(args.reconnect_delay)
            frame_id += 1
    finally:
        client.close()
        capture.release()
    return 0


def run_gui(args: argparse.Namespace) -> int:
    cv2, np = _load_cv()
    try:
        from PySide6.QtCore import QThread, Signal, Qt
        from PySide6.QtGui import QImage, QPixmap
        from PySide6.QtWidgets import (QApplication, QGridLayout, QLabel,
                                       QMainWindow, QWidget)
    except ImportError:
        print("PySide6 unavailable; using CLI fallback", file=sys.stderr)
        return run_cli(args)

    class CaptureThread(QThread):
        frame_ready = Signal(object, object, object, float, float)
        status_changed = Signal(str)

        def run(self) -> None:
            capture = _open_capture(args.source, cv2)
            client = BoardClient(args.host, args.port, args.timeout)
            float_backend = load_backend(args.float_backend) if args.float_backend else None
            frame_id = 0
            try:
                while not self.isInterruptionRequested():
                    ok, frame = capture.read()
                    if not ok:
                        self.status_changed.emit("Input ended")
                        return
                    framed, _ = letterbox_320(frame, cv2, np)
                    rgb = cv2.cvtColor(framed, cv2.COLOR_BGR2RGB).tobytes()
                    try:
                        float_result = float_backend.infer(rgb) if float_backend else None
                        start = time.perf_counter()
                        response = client.infer(rgb, frame_id)
                        elapsed_ms = (time.perf_counter() - start) * 1000.0
                        shown = draw_detections(framed, response, cv2)
                        float_shown = None
                        float_ms = 0.0
                        if float_result is not None:
                            float_response = InferenceResponse(
                                0, frame_id, 0, 0, 0, float_result.detections)
                            float_shown = draw_detections(framed, float_response, cv2)
                            float_ms = float_result.elapsed_ns / 1e6
                        self.frame_ready.emit(shown, float_shown, response,
                                              elapsed_ms, float_ms)
                        self.status_changed.emit("Connected")
                    except (OSError, EOFError, ProtocolError) as error:
                        self.status_changed.emit(f"Reconnecting: {error}")
                        time.sleep(args.reconnect_delay)
                    frame_id += 1
            finally:
                client.close()
                capture.release()

    class Window(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("EdgeDet-Z20")
            root = QWidget()
            layout = QGridLayout(root)
            self.banner = QLabel(VIRTUAL_BANNER if not args.hardware_target else
                                 "HARDWARE TARGET — VALIDATE ON PHYSICAL BOARD")
            self.banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.banner.setStyleSheet("font-size:18px;font-weight:700;color:#ffb74d;padding:10px")
            self.video = QLabel("Remote quantized: waiting for frames…")
            self.float_video = QLabel("Float comparison: no local backend configured")
            for panel in (self.video, self.float_video):
                panel.setMinimumSize(360, 360)
                panel.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.metrics = QLabel(f"Profile: {args.profile}\nFloat comparison: optional --float-backend")
            self.metrics.setStyleSheet("font-family:monospace;font-size:14px;padding:8px")
            self.connection = QLabel("Connecting…")
            layout.addWidget(self.banner, 0, 0, 1, 2)
            layout.addWidget(self.video, 1, 0)
            layout.addWidget(self.float_video, 1, 1)
            layout.addWidget(self.metrics, 2, 0)
            layout.addWidget(self.connection, 2, 1)
            self.setCentralWidget(root)
            self.worker = CaptureThread()
            self.worker.frame_ready.connect(self.update_frame)
            self.worker.status_changed.connect(self.connection.setText)
            self.worker.start()

        @staticmethod
        def pixmap(frame: Any) -> Any:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            height, width, channels = rgb.shape
            image = QImage(rgb.data, width, height, channels * width,
                           QImage.Format.Format_RGB888).copy()
            return QPixmap.fromImage(image)

        def update_frame(self, frame: Any, float_frame: Any,
                         response: InferenceResponse, elapsed_ms: float,
                         float_ms: float) -> None:
            self.video.setPixmap(self.pixmap(frame).scaled(
                self.video.size(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
            if float_frame is not None:
                self.float_video.setPixmap(self.pixmap(float_frame).scaled(
                    self.float_video.size(), Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation))
                comparison = f"Float latency: {float_ms:.2f} ms"
            else:
                comparison = "Float comparison: optional --float-backend"
            cycle_label = "Reported hardware cycles" if args.hardware_target else "Simulated 100MHz-equivalent cycles"
            self.metrics.setText(
                f"Frame: {response.frame_id}\nStatus: {response.status}\n"
                f"Profile: {args.profile}\n"
                f"Detections: {len(response.detections)}\nHost RTT: {elapsed_ms:.2f} ms\n"
                f"{cycle_label}: {response.total_cycles}\nDropped: {response.dropped_frames}\n"
                + comparison
            )

        def closeEvent(self, event: Any) -> None:
            self.worker.requestInterruption()
            self.worker.wait(int((args.timeout + 1.0) * 1000))
            event.accept()

    app = QApplication(sys.argv)
    window = Window()
    window.resize(800, 820)
    window.show()
    return app.exec()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1",
                        help="virtual server or ZedBoard IP; no code change required")
    parser.add_argument("--port", type=int, default=5001)
    parser.add_argument("--source", default="0", help="camera index or video path")
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--reconnect-delay", type=float, default=0.5)
    parser.add_argument("--hardware-target", action="store_true",
                        help="change truth-label only when connected to a physical board")
    parser.add_argument("--cli", action="store_true")
    parser.add_argument("--float-backend", default="",
                        help="optional package.module:factory for side-by-side float output")
    parser.add_argument("--profile", choices=("accuracy", "eco", "unknown"), default="unknown")
    parser.add_argument("--max-frames", type=int, default=0,
                        help="CLI only; zero processes until input ends")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return run_cli(args) if args.cli else run_gui(args)


if __name__ == "__main__":
    raise SystemExit(main())
