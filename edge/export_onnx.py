"""
ONNX Model Export and INT8 Quantization Utility for Pratyaksha Edge.
Exports Ultralytics YOLO nano model to ONNX for CPU-accelerated inference.
"""

import argparse
from pathlib import Path
import sys
from ultralytics import YOLO


def export_model(
    model_path: str = "yolov8n.pt",
    output_path: str = "yolov8n.onnx",
    quantize_int8: bool = False,
    opset: int = 12,
) -> None:
    print("=" * 70)
    print("Pratyaksha ONNX Export & CPU Optimization Utility")
    print(f"Source Model : {model_path}")
    print(f"Target Output: {output_path}")
    print(f"INT8 Dynamic : {quantize_int8}")
    print("=" * 70)

    # 1. Load PyTorch model
    print(f"\n[1/3] Loading PyTorch model from '{model_path}'...")
    model = YOLO(model_path)

    # 2. Export to ONNX
    print(f"[2/3] Exporting to ONNX format (opset={opset}, dynamic=True)...")
    exported_file = model.export(
        format="onnx",
        opset=opset,
        dynamic=True,
        simplify=True,
    )
    print(f"Exported successfully to: {exported_file}")

    # Ensure target output path matches requested path
    if str(exported_file) != str(output_path):
        import shutil
        shutil.copyfile(exported_file, output_path)
        print(f"Saved to requested path: {output_path}")

    # 3. Optional INT8 Dynamic Quantization for CPU
    if quantize_int8:
        print("[3/3] Performing INT8 Dynamic Quantization...")
        try:
            import onnx
            from onnxruntime.quantization import QuantType, quantize_dynamic

            int8_output = str(Path(output_path).with_suffix(".int8.onnx"))
            quantize_dynamic(
                model_input=output_path,
                model_output=int8_output,
                weight_type=QuantType.QUInt8,
            )
            print(f"INT8 Quantized Model saved to: {int8_output}")
        except Exception as e:
            print(f"[WARNING] INT8 quantization skipped: {e}")
    else:
        print("[3/3] Export completed without INT8 quantization.")

    # 4. Verification with ONNX Runtime
    try:
        import onnxruntime as ort
        session = ort.InferenceSession(output_path, providers=["CPUExecutionProvider"])
        inputs = [i.name for i in session.get_inputs()]
        outputs = [o.name for o in session.get_outputs()]
        print("\n[VERIFICATION] ONNX Runtime CPU session loaded successfully.")
        print(f"Inputs : {inputs}")
        print(f"Outputs: {outputs}")
    except Exception as e:
        print(f"[WARNING] ONNX Runtime verification test: {e}")

    print("\n[SUCCESS] Model ready for low-power CPU edge deployment.")


def main():
    parser = argparse.ArgumentParser(description="Export YOLO to ONNX for CPU Edge Inference")
    parser.add_argument("--model", "-m", type=str, default="yolov8n.pt", help="Path to PyTorch YOLO weights")
    parser.add_argument("--output", "-o", type=str, default="yolov8n.onnx", help="Path to save ONNX model")
    parser.add_argument("--quantize-int8", action="store_true", help="Apply INT8 dynamic quantization")
    parser.add_argument("--opset", type=int, default=12, help="ONNX opset version")
    args = parser.parse_args()

    export_model(
        model_path=args.model,
        output_path=args.output,
        quantize_int8=args.quantize_int8,
        opset=args.opset,
    )


if __name__ == "__main__":
    main()
