#!/usr/bin/env python3
"""
Pratyaksha: Custom Infrastructure YOLO Fine-Tuning Script.
Trains or fine-tunes Ultralytics YOLO models (e.g. YOLOv8 nano / small or YOLO-World)
on domain-specific vocational training equipment:
- Workbench, Lathe, Welding Machine, Sewing Machine, Drill Press, Computer, Chair, Toolbox

Usage:
    python scripts/train_custom_yolo.py --data data/custom_dataset/dataset.yaml --epochs 50 --batch 16
    python scripts/train_custom_yolo.py --model yolov8s.pt --epochs 100 --imgsz 640
"""

import argparse
import os
import sys
from pathlib import Path
from ultralytics import YOLO


def parse_args():
    parser = argparse.ArgumentParser(description="Fine-tune YOLO on custom vocational training equipment.")
    parser.add_argument(
        "--data",
        type=str,
        default="data/custom_dataset/dataset.yaml",
        help="Path to dataset.yaml describing train/val splits and custom class names.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="yolov8n.pt",
        help="Base pretrained YOLO model or checkpoint to fine-tune from (e.g. yolov8n.pt, yolov8s.pt).",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=50,
        help="Number of training epochs.",
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=16,
        help="Training batch size.",
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        default=640,
        help="Image size in pixels.",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="",
        help="Device to train on ('cpu', 'cuda', 'mps', or '' for auto-detection).",
    )
    parser.add_argument(
        "--project",
        type=str,
        default="outputs/models",
        help="Directory to save trained model runs and weights.",
    )
    parser.add_argument(
        "--name",
        type=str,
        default="custom_skilling_yolo",
        help="Experiment name.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    print("=" * 70)
    print("  Pratyaksha: Custom Infrastructure Detector Fine-Tuning")
    print("=" * 70)
    print(f"Base Pretrained Model : {args.model}")
    print(f"Dataset Config YAML   : {args.data}")
    print(f"Target Epochs         : {args.epochs}")
    print(f"Batch Size            : {args.batch}")
    print(f"Image Resolution      : {args.imgsz}x{args.imgsz}")
    print(f"Output Directory      : {args.project}/{args.name}")
    print("-" * 70)

    if not os.path.exists(args.data):
        print(f"[ERROR] Dataset configuration '{args.data}' not found!")
        print("Please prepare your dataset following data/custom_dataset/README.md.")
        sys.exit(1)

    # Initialize model from base checkpoint
    print(f"[INFO] Initializing model from '{args.model}'...")
    model = YOLO(args.model)

    # Start training
    print("[INFO] Launching training pipeline...")
    results = model.train(
        data=args.data,
        epochs=args.epochs,
        batch=args.batch,
        imgsz=args.imgsz,
        device=args.device if args.device else None,
        project=args.project,
        name=args.name,
        exist_ok=True,
        verbose=True,
    )

    best_weights_path = Path(args.project) / args.name / "weights" / "best.pt"
    print("\n" + "=" * 70)
    print("  Training Completed Successfully!")
    print(f"  Best Model Weights: {best_weights_path}")
    print("=" * 70)
    print("\nTo swap this model into Pratyaksha:")
    print("1. Update config.yaml under 'custom_detector.model_path':")
    print(f"   model_path: '{best_weights_path}'")
    print("2. (Optional) Export to ONNX for ultra-low latency edge CPU deployment:")
    print(f"   yolo export model={best_weights_path} format=onnx")
    print("-" * 70)


if __name__ == "__main__":
    main()
