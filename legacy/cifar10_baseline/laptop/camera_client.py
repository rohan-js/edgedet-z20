"""
camera_client.py
Laptop-side client for real-time CNN inference on ZedBoard

This script:
  1. Captures frames from laptop webcam
  2. Sends preprocessed frames to ZedBoard over TCP
  3. Receives classification results from ZedBoard
  4. Displays annotated frames with predictions

Usage: python camera_client.py --ip <ZEDBOARD_IP>

Requires: pip install opencv-python numpy
"""

import cv2
import numpy as np
import socket
import struct
import argparse
import time
import sys


# ============================================================
# CIFAR-10 Class Names and Colors
# ============================================================
CLASS_NAMES = [
    "airplane", "automobile", "bird", "cat", "deer",
    "dog", "frog", "horse", "ship", "truck"
]

CLASS_COLORS = [
    (255, 100, 100),  # airplane - blue
    (100, 255, 100),  # automobile - green
    (100, 100, 255),  # bird - red
    (255, 255, 100),  # cat - cyan
    (255, 100, 255),  # deer - magenta
    (100, 255, 255),  # dog - yellow
    (200, 200, 100),  # frog
    (100, 200, 200),  # horse
    (200, 100, 200),  # ship
    (150, 150, 255),  # truck
]


# ============================================================
# Image Preprocessing (matches HLS input format)
# ============================================================
def preprocess_frame(frame, size=(32, 32)):
    """
    Preprocess a camera frame for CNN input.
    - Resize to 32×32
    - Convert to float and normalize (CIFAR-10 stats)
    - Convert to CHW format (channels first)
    - Quantize to fixed-point int16
    """
    # Resize
    resized = cv2.resize(frame, size, interpolation=cv2.INTER_LINEAR)
    
    # Convert BGR → RGB and normalize to [0, 1]
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    
    # Normalize with CIFAR-10 mean/std
    mean = np.array([0.4914, 0.4822, 0.4465], dtype=np.float32)
    std  = np.array([0.2470, 0.2435, 0.2616], dtype=np.float32)
    rgb = (rgb - mean) / std
    
    # HWC → CHW format (3, 32, 32)
    chw = rgb.transpose(2, 0, 1)
    
    # Convert to fixed-point int16 (ap_fixed<16,6> has 10 fractional bits)
    FRAC_BITS = 10
    fixed_point = (chw * (1 << FRAC_BITS)).astype(np.int16)
    
    return fixed_point


# ============================================================
# ZedBoard Communication
# ============================================================
class ZedBoardClient:
    """TCP client for communicating with ZedBoard."""
    
    def __init__(self, ip, port=5000, timeout=5.0):
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.sock = None
    
    def connect(self):
        """Connect to ZedBoard."""
        print(f"[INFO] Connecting to ZedBoard at {self.ip}:{self.port}...")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        try:
            self.sock.connect((self.ip, self.port))
            print("[INFO] Connected!")
            return True
        except Exception as e:
            print(f"[ERROR] Connection failed: {e}")
            return False
    
    def send_frame(self, frame_data):
        """
        Send preprocessed frame to ZedBoard.
        Protocol: [4-byte length][frame data as int16 array]
        """
        data_bytes = frame_data.tobytes()
        header = struct.pack('>I', len(data_bytes))
        self.sock.sendall(header + data_bytes)
    
    def receive_result(self):
        """
        Receive classification result from ZedBoard.
        Protocol: [4-byte class_id][4-byte confidence][4-byte latency_ms]
        """
        data = b''
        while len(data) < 12:
            chunk = self.sock.recv(12 - len(data))
            if not chunk:
                raise ConnectionError("Connection closed")
            data += chunk
        
        class_id, confidence, latency_ms = struct.unpack('>IfF', data)
        return class_id, confidence, latency_ms
    
    def close(self):
        if self.sock:
            self.sock.close()


# ============================================================
# Offline Mode (no ZedBoard — for testing)
# ============================================================
def offline_inference(frame_data):
    """
    Simulated inference for testing without ZedBoard.
    Returns random prediction.
    """
    class_id = np.random.randint(0, 10)
    confidence = np.random.uniform(0.5, 1.0)
    latency = np.random.uniform(20, 50)
    return class_id, confidence, latency


# ============================================================
# Display Overlay
# ============================================================
def draw_overlay(frame, class_id, confidence, latency_ms, fps, mode="FPGA"):
    """Draw classification results and stats on frame."""
    h, w = frame.shape[:2]
    
    # Semi-transparent overlay bar at top
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 80), (0, 0, 0), -1)
    frame = cv2.addWeighted(overlay, 0.6, frame, 0.4, 0)
    
    # Classification result
    label = CLASS_NAMES[class_id] if 0 <= class_id < 10 else "unknown"
    color = CLASS_COLORS[class_id] if 0 <= class_id < 10 else (255, 255, 255)
    
    text = f"{label} ({confidence:.0%})"
    cv2.putText(frame, text, (10, 35), 
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2)
    
    # Stats line
    stats = f"Latency: {latency_ms:.1f}ms | FPS: {fps:.1f} | Mode: {mode}"
    cv2.putText(frame, stats, (10, 65),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
    
    # Show the preprocessed 32×32 thumbnail in corner
    return frame


# ============================================================
# Main Loop
# ============================================================
def main():
    parser = argparse.ArgumentParser(description='ZedBoard Camera Client')
    parser.add_argument('--ip', type=str, default=None,
                       help='ZedBoard IP address (omit for offline mode)')
    parser.add_argument('--port', type=int, default=5000,
                       help='ZedBoard port (default: 5000)')
    parser.add_argument('--camera', type=int, default=0,
                       help='Camera index (default: 0)')
    parser.add_argument('--width', type=int, default=640,
                       help='Camera width (default: 640)')
    parser.add_argument('--height', type=int, default=480,
                       help='Camera height (default: 480)')
    args = parser.parse_args()
    
    # Determine mode
    online = args.ip is not None
    client = None
    
    if online:
        client = ZedBoardClient(args.ip, args.port)
        if not client.connect():
            print("[WARN] Falling back to offline mode")
            online = False
    
    mode_str = "FPGA" if online else "OFFLINE (simulated)"
    print(f"[INFO] Mode: {mode_str}")
    
    # Open camera
    print(f"[INFO] Opening camera {args.camera}...")
    cap = cv2.VideoCapture(args.camera)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    
    if not cap.isOpened():
        print("[ERROR] Cannot open camera!")
        sys.exit(1)
    
    print("[INFO] Camera opened. Press 'q' to quit, 's' to save frame.\n")
    
    # FPS tracking
    frame_count = 0
    fps = 0.0
    fps_start = time.time()
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("[ERROR] Frame capture failed")
                break
            
            # Preprocess
            processed = preprocess_frame(frame)
            
            # Inference
            t_start = time.time()
            
            if online:
                try:
                    client.send_frame(processed)
                    class_id, confidence, latency_ms = client.receive_result()
                except Exception as e:
                    print(f"[WARN] Communication error: {e}")
                    class_id, confidence, latency_ms = offline_inference(processed)
            else:
                class_id, confidence, latency_ms = offline_inference(processed)
            
            t_end = time.time()
            
            # Update FPS
            frame_count += 1
            elapsed = time.time() - fps_start
            if elapsed >= 1.0:
                fps = frame_count / elapsed
                frame_count = 0
                fps_start = time.time()
            
            # Draw overlay
            display = draw_overlay(frame, class_id, confidence, latency_ms, fps,
                                  "FPGA" if online else "OFFLINE")
            
            # Show 32×32 thumbnail in corner
            thumb = cv2.resize(frame, (32, 32))
            thumb_large = cv2.resize(thumb, (96, 96), interpolation=cv2.INTER_NEAREST)
            display[10:106, display.shape[1]-106:display.shape[1]-10] = thumb_large
            
            cv2.imshow('ZedBoard CNN Accelerator', display)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('s'):
                filename = f"capture_{int(time.time())}.png"
                cv2.imwrite(filename, frame)
                print(f"[INFO] Saved {filename}")
    
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user")
    
    finally:
        cap.release()
        cv2.destroyAllWindows()
        if client:
            client.close()
        print("[INFO] Done.")


if __name__ == "__main__":
    main()
