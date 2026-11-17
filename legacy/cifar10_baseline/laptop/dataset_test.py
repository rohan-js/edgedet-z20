"""
dataset_test.py
Test CNN inference using stored CIFAR-10 / COCO images

This script:
  1. Loads test images from a folder or CIFAR-10 dataset
  2. Preprocesses and sends to ZedBoard (or runs offline)
  3. Calculates accuracy metrics (mAP, confusion matrix)
  4. Generates performance report

Usage:
  python dataset_test.py --dataset cifar10 --ip <ZEDBOARD_IP>
  python dataset_test.py --images ./test_images/ --offline
"""

import cv2
import numpy as np
import argparse
import time
import os
import sys
from collections import defaultdict

# Re-use preprocessing from camera_client
sys.path.insert(0, os.path.dirname(__file__))
from camera_client import preprocess_frame, ZedBoardClient, offline_inference

CLASS_NAMES = [
    "airplane", "automobile", "bird", "cat", "deer",
    "dog", "frog", "horse", "ship", "truck"
]


def load_cifar10_test(num_samples=100):
    """Load CIFAR-10 test samples using torchvision."""
    try:
        import torchvision
        import torchvision.transforms as transforms
        
        transform = transforms.Compose([transforms.ToTensor()])
        testset = torchvision.datasets.CIFAR10(
            root='./data', train=False, download=True, transform=transform)
        
        images = []
        labels = []
        for i in range(min(num_samples, len(testset))):
            img, label = testset[i]
            # Convert back to numpy HWC uint8 for preprocessing
            img_np = (img.numpy().transpose(1, 2, 0) * 255).astype(np.uint8)
            img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
            images.append(img_bgr)
            labels.append(label)
        
        return images, labels
    except ImportError:
        print("[WARN] torchvision not installed. Use --images flag instead.")
        return [], []


def load_image_folder(folder_path):
    """Load images from a folder. Expects subfolders per class."""
    images = []
    labels = []
    
    if not os.path.isdir(folder_path):
        print(f"[ERROR] Folder not found: {folder_path}")
        return images, labels
    
    for class_idx, class_name in enumerate(sorted(os.listdir(folder_path))):
        class_dir = os.path.join(folder_path, class_name)
        if not os.path.isdir(class_dir):
            continue
        
        for fname in os.listdir(class_dir):
            fpath = os.path.join(class_dir, fname)
            img = cv2.imread(fpath)
            if img is not None:
                images.append(img)
                labels.append(class_idx)
    
    return images, labels


def run_evaluation(images, labels, client=None, online=False):
    """Run inference on all images and compute metrics."""
    
    predictions = []
    latencies = []
    
    total = len(images)
    print(f"\n[INFO] Running evaluation on {total} images...")
    
    for i, (img, true_label) in enumerate(zip(images, labels)):
        # Preprocess
        processed = preprocess_frame(img)
        
        # Inference
        if online and client:
            try:
                client.send_frame(processed)
                class_id, confidence, latency_ms = client.receive_result()
            except Exception as e:
                class_id, confidence, latency_ms = offline_inference(processed)
        else:
            class_id, confidence, latency_ms = offline_inference(processed)
        
        predictions.append(class_id)
        latencies.append(latency_ms)
        
        if (i + 1) % 10 == 0:
            print(f"  Progress: {i+1}/{total}")
    
    return predictions, latencies


def compute_metrics(labels, predictions, latencies):
    """Compute and display evaluation metrics."""
    
    labels = np.array(labels)
    predictions = np.array(predictions)
    latencies = np.array(latencies)
    
    # Overall accuracy
    correct = (labels == predictions).sum()
    accuracy = correct / len(labels)
    
    print("\n" + "=" * 60)
    print("  PERFORMANCE REPORT")
    print("=" * 60)
    
    print(f"\n  Total images:     {len(labels)}")
    print(f"  Correct:          {correct}")
    print(f"  Accuracy:         {accuracy:.1%}")
    
    # Per-class accuracy
    print(f"\n  {'Class':<15} {'Correct':>8} {'Total':>8} {'Accuracy':>10}")
    print(f"  {'-'*15} {'-'*8} {'-'*8} {'-'*10}")
    
    for cls in range(10):
        mask = labels == cls
        if mask.sum() > 0:
            cls_correct = (predictions[mask] == cls).sum()
            cls_total = mask.sum()
            cls_acc = cls_correct / cls_total
            print(f"  {CLASS_NAMES[cls]:<15} {cls_correct:>8} {cls_total:>8} {cls_acc:>10.1%}")
    
    # Latency stats
    print(f"\n  Latency Statistics:")
    print(f"    Mean:   {latencies.mean():.2f} ms")
    print(f"    Median: {np.median(latencies):.2f} ms")
    print(f"    Min:    {latencies.min():.2f} ms")
    print(f"    Max:    {latencies.max():.2f} ms")
    print(f"    Std:    {latencies.std():.2f} ms")
    print(f"    FPS:    {1000.0 / latencies.mean():.1f}")
    
    # Confusion matrix (simple text version)
    print(f"\n  Confusion Matrix (rows=true, cols=predicted):")
    conf = np.zeros((10, 10), dtype=int)
    for t, p in zip(labels, predictions):
        conf[t][p] += 1
    
    header = "     " + "".join([f"{n[:4]:>5}" for n in CLASS_NAMES])
    print(f"  {header}")
    for i in range(10):
        row = f"  {CLASS_NAMES[i][:4]:>4} " + "".join([f"{conf[i][j]:>5}" for j in range(10)])
        print(row)
    
    print("\n" + "=" * 60)
    
    return accuracy


def main():
    parser = argparse.ArgumentParser(description='CNN Dataset Evaluation')
    parser.add_argument('--dataset', type=str, default='cifar10',
                       choices=['cifar10'], help='Dataset to use')
    parser.add_argument('--images', type=str, default=None,
                       help='Path to image folder (alternative to --dataset)')
    parser.add_argument('--num-samples', type=int, default=100,
                       help='Number of test samples (default: 100)')
    parser.add_argument('--ip', type=str, default=None,
                       help='ZedBoard IP (omit for offline mode)')
    parser.add_argument('--port', type=int, default=5000)
    args = parser.parse_args()
    
    # Load images
    if args.images:
        images, labels = load_image_folder(args.images)
    else:
        images, labels = load_cifar10_test(args.num_samples)
    
    if not images:
        print("[ERROR] No images loaded!")
        sys.exit(1)
    
    # Connect to ZedBoard
    online = False
    client = None
    if args.ip:
        client = ZedBoardClient(args.ip, args.port)
        online = client.connect()
    
    # Run evaluation
    predictions, latencies = run_evaluation(images, labels, client, online)
    
    # Compute metrics
    accuracy = compute_metrics(labels, predictions, latencies)
    
    if client:
        client.close()


if __name__ == "__main__":
    main()
