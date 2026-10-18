# Custom Skilling Infrastructure Dataset Layout

This folder defines the directory structure and annotation format required to fine-tune a custom YOLO model for Pratyaksha on vocational training infrastructure.

## Directory Structure

```text
data/custom_dataset/
├── dataset.yaml            # Ultralytics dataset definition
├── README.md               # Instructions & guidelines
├── images/
│   ├── train/              # Training images (.jpg / .png)
│   └── val/                # Validation images (.jpg / .png)
└── labels/
    ├── train/              # Training bounding box labels (.txt)
    └── val/                # Validation bounding box labels (.txt)
```

## Classes

| Class ID | Class Name | Description |
| :--- | :--- | :--- |
| `0` | `person` | Trainees, instructors, evaluators |
| `1` | `workbench` | Vocational workbenches, heavy tables, electrical lab stations |
| `2` | `lathe` | Metalworking/woodworking lathe machines |
| `3` | `welding_machine`| Arc/TIG/MIG welding units & ground clamps |
| `4` | `sewing_machine` | Industrial and domestic sewing/garment stations |
| `5` | `drill_press` | Pillar/bench drill presses |
| `6` | `computer` | Desktops, laptops, monitors in IT labs |
| `7` | `chair` | Trainee stools, classroom chairs, lab seating |
| `8` | `toolbox` | Portable toolboxes, kit chests, instrument trays |

## Annotation Format (Standard YOLO Format)
Each image file (e.g. `images/train/frame_001.jpg`) must have a corresponding label file (e.g. `labels/train/frame_001.txt`).
Each line contains:
```text
<class_id> <x_center> <y_center> <width> <height>
```
All coordinates are normalized between `0.0` and `1.0`.

## Fine-Tuning Instructions
```bash
# 1. Run the fine-tuning script
python scripts/train_custom_yolo.py --data data/custom_dataset/dataset.yaml --epochs 50 --batch 16

# 2. To swap in the trained model, update config.yaml:
# custom_detector:
#   model_path: "outputs/models/custom_skilling_yolo/weights/best.pt"
```
