# Evaluation Dataset Guidelines & Directory Layout

This directory is designed to hold both public benchmarking datasets and synthetically generated controlled scenario variants for Pratyaksha.

---

## 1. Directory Structure

```text
evaluation/data/
├── README.md                  # This file
├── raw/                       # Drop external benchmark datasets here
│   ├── crowdhuman/            # CrowdHuman dataset images and annotations
│   ├── coco_subset/           # COCO person and furniture subsets
│   └── classroom_footage/     # Public domain classroom / workshop video clips
├── scenarios/                 # Controlled synthetic degradation variants (generated)
│   ├── baseline/
│   ├── low_light/
│   ├── blur/
│   ├── downscaled/
│   ├── compression/
│   └── occlusion/
├── ground_truth.json          # Frame-level ground-truth counts (persons & infrastructure)
└── scenario_manifest.json     # Operational scenario claims vs reality for rules engine scoring
```

---

## 2. Recommended Public Datasets

When evaluating against larger external benchmarks, download and place them into `evaluation/data/raw/`:

### A. CrowdHuman Dataset
- **Description:** High-density crowd dataset specifically designed for detecting individuals under severe occlusion and crowded classroom scenarios.
- **Source:** [CrowdHuman Benchmark](https://www.crowdhuman.net/)
- **Expected Layout:**
  ```text
  evaluation/data/raw/crowdhuman/
  ├── Images/
  └── annotation_val.odgt
  ```

### B. COCO (Common Objects in Context) Subset
- **Description:** Multi-object scenes featuring relevant class labels: `person`, `chair`, `dining table` (workbench), `laptop`, `tv` (monitor).
- **Source:** [COCO Dataset](https://cocodataset.org/#download)
- **Filtered Classes:** Person (ID 0), Chair (ID 56), Dining Table (ID 60), Laptop (ID 63).
- **Expected Layout:**
  ```text
  evaluation/data/raw/coco_subset/
  ├── images/
  └── instances_val2017.json
  ```

### C. EPFL & Open Classroom/Workshop CCTV Footage
- **Description:** Overhead multi-camera video feeds in real-world educational workshops and lecture halls.
- **Source:** [EPFL Multi-Camera Lab / Pedestrian Tracking Datasets](https://www.epfl.ch/labs/cvlab/data/data-wildtrack/)
- **Expected Layout:**
  ```text
  evaluation/data/raw/classroom_footage/
  ├── camera_1.mp4
  └── camera_2.mp4
  ```

---

## 3. Synthetic Scenario Generator

To produce reproducible controlled variants with fixed random seeds without external network downloads, run:

```bash
python -m evaluation.dataset_generator
```

This takes base frames from `sample_data/` and systematically generates:
- **Low Light:** Gamma / illumination attenuation ($35\%$ ambient brightness)
- **Blur:** Gaussian defocus simulating cheap, smudged lenses ($k=15$)
- **Downscaled Resolution:** Downsampled to $320\text{px}$ wide simulating bandwidth constraints
- **Compression Artefacts:** Aggressive JPEG quantization (quality factor 20)
- **Partial Occlusion:** Randomized black blocks simulating pillar and furniture obstructions
- **Fraud Scenarios:** Manipulated scenes with ghost attendance claims and missing sanctioned equipment
