"""
Hardware Benchmarking Utility for Pratyaksha Edge.
Measures inference latency, FPS, memory consumption, and CPU load across profiles (ultra_low, low, normal).
"""

import argparse
from pathlib import Path
import sys
import time
from typing import Dict, List

# Ensure project root is in sys.path for direct script execution
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import cv2
import numpy as np
import psutil

from edge.config import PROFILES
from edge.detector_runtime import EdgeDetectorRuntime


def run_benchmark(
    iterations: int = 25,
    sample_image: str = "sample_data/000000397133.jpg",
    model_path: str = "yolov8n.pt",
    onnx_path: str = "yolov8n.onnx",
) -> None:
    print("=" * 80)
    print("Pratyaksha Edge Hardware & Profile Inference Benchmark")
    print(f"Iterations per Profile: {iterations}")
    print(f"Test Image            : {sample_image}")
    print("=" * 80)

    # Load test image
    if Path(sample_image).exists():
        frame = cv2.imread(sample_image)
    else:
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)

    # Initialize runtimes
    runtime_pytorch = EdgeDetectorRuntime(model_path=model_path, prefer_onnx=False)
    has_onnx = Path(onnx_path).exists()
    runtime_onnx = EdgeDetectorRuntime(model_path=model_path, onnx_path=onnx_path, prefer_onnx=True) if has_onnx else None

    runtimes = [("PyTorch (CPU)", runtime_pytorch)]
    if runtime_onnx and runtime_onnx.is_onnx:
        runtimes.append(("ONNX Runtime (CPU)", runtime_onnx))

    results = []

    for runtime_name, detector in runtimes:
        print(f"\nEvaluating: {runtime_name}")
        print("-" * 80)

        for p_name, profile in PROFILES.items():
            imgsz = profile.input_resolution

            # Warmup
            for _ in range(3):
                detector.detect(frame, imgsz=imgsz)

            latencies: List[float] = []
            process = psutil.Process()
            mem_before = process.memory_info().rss / (1024 * 1024)

            for _ in range(iterations):
                t0 = time.perf_counter()
                dets = detector.detect(frame, imgsz=imgsz)
                t1 = time.perf_counter()
                latencies.append((t1 - t0) * 1000.0)

            mem_after = process.memory_info().rss / (1024 * 1024)

            lat_avg = np.mean(latencies)
            lat_p50 = np.median(latencies)
            lat_p95 = np.percentile(latencies, 95)
            fps = 1000.0 / lat_avg if lat_avg > 0 else 0.0

            results.append({
                "runtime": runtime_name,
                "profile": p_name,
                "resolution": f"{imgsz}x{imgsz}",
                "sample_interval": f"{profile.sample_interval_sec}s",
                "avg_ms": lat_avg,
                "p50_ms": lat_p50,
                "p95_ms": lat_p95,
                "fps": fps,
                "mem_mb": mem_after,
            })

            print(
                f"  [{p_name.upper():<9}] Res: {imgsz}x{imgsz} | Avg: {lat_avg:6.1f} ms | "
                f"P95: {lat_p95:6.1f} ms | FPS: {fps:5.1f} | RAM: {mem_after:5.1f} MB"
            )

    # Print Formatted Markdown Table
    print("\n" + "=" * 80)
    print("SUMMARY BENCHMARK REPORT")
    print("=" * 80)
    print("| Runtime | Profile | Resolution | Sample Interval | Avg Latency | P95 Latency | Throughput | Memory |")
    print("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    for r in results:
        print(
            f"| {r['runtime']} | `{r['profile']}` | {r['resolution']} | {r['sample_interval']} | "
            f"{r['avg_ms']:.1f} ms | {r['p95_ms']:.1f} ms | {r['fps']:.1f} FPS | {r['mem_mb']:.1f} MB |"
        )
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Benchmark Pratyaksha Edge Profiles")
    parser.add_argument("--iterations", "-n", type=int, default=20, help="Iterations per profile")
    parser.add_argument("--image", type=str, default="sample_data/000000397133.jpg", help="Sample image path")
    parser.add_argument("--model", type=str, default="yolov8n.pt", help="Path to PyTorch YOLO weights")
    parser.add_argument("--onnx", type=str, default="yolov8n.onnx", help="Path to ONNX model")
    args = parser.parse_args()

    run_benchmark(
        iterations=args.iterations,
        sample_image=args.image,
        model_path=args.model,
        onnx_path=args.onnx,
    )


if __name__ == "__main__":
    main()
