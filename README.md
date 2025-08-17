# GlypPRM

GlypPRM is a Python toolkit for processing glycopeptide PRM (parallel reaction monitoring) data and producing tables and figures used in analytical workflows and publications.

This repository contains the GUI and command-line scripts used to run PRM processing.

## Quick summary
- Purpose: process glycopeptide PRM data and generate reports/figures for downstream analysis and manuscript generation.
- Language: Python 3.11+
- License: MIT (see `LICENSE`)

## Install
Create and activate a virtual environment (recommended). Example for Windows PowerShell:

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Quick run (example)
`GlypPRM_App_v01.py` is the main standalone script and includes the GUI by default.
The same script also supports a command-line (headless) mode so users can switch between interactive GUI and scripted CLI runs.

Run the GUI (default):

```powershell
python GlypPRM_App_v01.py
```

Run processing in CLI mode (example):

```powershell
python GlypPRM_App_v01.py --input sample_data/example_input.prm --output results/
```

Use `python GlypPRM_App_v01.py --help` to see the available CLI flags and options.

Optional installation

You can install the application as a standalone package on supported platforms using the provided installer spec `GlypPRM_Spec_v01.SPEC`. Follow your platform's packaging/installer instructions to build or run the installer.

## Reproducing figures/tables for the manuscript
- The `sample_data/` folder contains small example files and a `README.md` describing their format.
- The `supplementary/` (optional) folder should include scripts that reproduce figures/tables used in the submitted manuscript. Add a short `README` there describing the commands to run.

## Citation
If you use this software in a publication, please cite the software and the associated paper if available. Example:

```
First Last (2025). GlypPRM. Version 0.1.0. https://github.com/yourusername/GlypPRM (DOI: TODO)
```

A machine-readable citation file is provided in `CITATION.cff`.

How to cite
-----------
If you use this software in your work, please cite the manuscript and this software release. Example (software):

First Last (2025). GlypPRM. Version 0.1.0. DOI: TODO. Repository: https://github.com/odaramola92/GlypPRM

## Development & tests
Run the test suite with pytest:

```powershell
pip install -r requirements.txt
pytest -q
```
