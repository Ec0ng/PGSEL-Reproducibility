# PGSEL Reproducibility Materials

This repository provides reproducibility materials for the manuscript on short-video public opinion burst prediction under natural-disaster contexts.

The purpose of this repository is not to release the full raw social media dataset or the complete model implementation. Instead, it provides the key reproducibility materials requested during peer review, including the processed sample-level data format, data-field descriptions, preprocessing description, anonymized sample records, and Kleinberg-based burst label-generation code.

## Repository Contents

This repository contains the following files:

```text
PGSEL-Reproducibility/
│
├── README.md
├── data_dictionary.md
├── preprocessing_description.md
├── requirements.txt
│
├── label_generation/
│   └── kleinberg_label_generation.py
│
└── examples/
    └── anonymized_sample_records.csv