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

Note: `GlypPRM_App2.py` is an alternate script present in the repository but is not required for normal use — `GlypPRM_App_v01.py` contains the default GUI and CLI functionality.

Optional installation

You can install the application as a standalone package on supported platforms using the provided installer spec `GlypPRM_Spec_v01.SPEC`. Follow your platform's packaging/installer instructions to build or run the installer.

## Reproducing figures/tables for the manuscript
- The `sample_data/` folder contains small example files and a `README.md` describing their format.
- The `supplementary/` folder contains scripts that reproduce figures/tables used in the submitted manuscript.
- **Data Requirements**: Analysis scripts require the raw mass spectrometry data file `Fetuin_PRM_1_6mz_2.raw` (179MB), available for download from MassIVE repository (Dataset ID: MSV00001234).
- See `supplementary/README.md` for detailed instructions on downloading data and running analysis commands.

## Data Availability
Raw mass spectrometry data used in this study is publicly available:
- **Repository**: DRYAD
- **Direct Link**:https://doi.org/10.5061/dryad.4tmpg4fpz 
- **Reviewer Access**: http://datadryad.org/share/79oK8nNAOLVf2oQccjhLag6jEb1vIv9q1s4KpXOxg2k.  

## Citation
If you use this software in a publication, please cite the software and the associated paper if available. Example:

```
Oluwatosin Daramola, Sherifdeen Onigbinde, Moyinoluwa Adeniyi, Cristian D. Gutierrez-Reyes, Mojibola Fowowe, Vishal Sadilya, Yehia Mechref (2025). GlypPRM. Version 0.1.0. https://github.com/yourusername/GlypPRM (DOI: TODO)
```

A machine-readable citation file is provided in `CITATION.cff`.

How to cite
-----------
If you use this software in your work, please cite the manuscript and this software release. Example (software):

Oluwatosin Daramola, Sherifdeen Onigbinde, Moyinoluwa Adeniyi, Cristian D. Gutierrez-Reyes, Mojibola Fowowe, Vishal Sadilya, Yehia Mechref (2025). GlypPRM. Version 0.1.0. DOI: TODO. Repository: https://github.com/yourusername/GlypPRM

## Development & tests
Run the test suite with pytest:

```powershell
pip install -r requirements.txt
pytest -q
```

# Supplementary: Sample Scripts for GlypPRM Analysis

This folder contains runnable scripts to generate sample figures and tables using GlypPRM analysis. These scripts demonstrate the software capabilities and provide examples of typical glycopeptide analysis workflows.

## 🎯 **What this generates:**

### **Sample Figures**: Representative EIC and MS/MS of PRM N-glycopeptides
- **Target A**: RPTGEVYDIEIDTLETTCHVLDPTPLANCSVR-5603 
- **Target B**: LCPDCPLLAPLNDSR-5604
- **Input**: `Fetuin_PRM_1_6mz_2.raw` + `figure_targets.xlsx`
- **Output**: EIC plots and MS/MS spectra (SVG format)

### **Sample Table**: Complete analysis results
- **All glycopeptides** from bovine fetuin analysis with real fragment detection
- **Input**: `Fetuin_PRM_1_6mz_2.raw` + `table_targets.xlsx`
- **Output**: Excel file with matched fragments, areas, and intensities (non-scientific notation)

## 📁 **Contents**

- `run_all.ps1` — Windows PowerShell runbook to reproduce everything
- `run_all.sh` — POSIX shell runbook (Linux/macOS)
- `requirements.txt` — pinned minimal dependencies for reproduction
- `Fetuin_PRM_1_6mz_2.raw` — actual raw MS data file used in manuscript
- `scripts/` — scripts that reproduce individual figures/tables
- `data/` — input target lists and parameters
- `expected_outputs/` — expected outputs produced by the scripts
- `metadata.yaml` — parameters, seeds, and software versions

## 🚀 **Quick PowerShell reproduction**

```powershell
# From repository root
cd supplementary
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
.\run_all.ps1
```

## 🐧 **Quick Linux/macOS reproduction**

```bash
# From repository root
cd supplementary
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./run_all.sh
```

## 📋 **Individual Script Usage**

### **Generate Sample Figures**

```powershell
# Windows PowerShell
cd supplementary
python scripts/figure_script.py --raw-file Fetuin_PRM_1_6mz_2.raw --targets data/figure_targets.xlsx --output-dir outputs
```

```bash
# Linux/macOS
cd supplementary
python scripts/figure_script.py --raw-file Fetuin_PRM_1_6mz_2.raw --targets data/figure_targets.xlsx --output-dir outputs
```

**Output:** SVG plots saved in `outputs/figures_Fetuin_PRM_1_6mz_2/` directory with real GlypPRM analysis:
- Multiple EIC and MS/MS plots for detected glycopeptides
- Plots named with format: `EIC_[glycan]_[mz]_[rt]_all.svg` and `MS2_[glycan]_[mz]_[rt].svg`
- Comprehensive fragment detection with charge states 1+, 2+, and 3+

### **Generate Sample Table**

```powershell
# Windows PowerShell  
cd supplementary
python scripts/table_script.py --raw-file Fetuin_PRM_1_6mz_2.raw --targets data/table_targets.xlsx --output table_outputs/table.xlsx
```

```bash
# Linux/macOS
cd supplementary
python scripts/table_script.py --raw-file Fetuin_PRM_1_6mz_2.raw --targets data/table_targets.xlsx --output table_outputs/table.xlsx
```

**Output:** Excel file with comprehensive analysis results:
- Target names use RT format: `PEPTIDE-GLYCAN_[RT]` (e.g., `LCPDCPLLAPLNDSR-4501_62.1`)
- Fragment counts, total areas, and average intensities in readable numbers (not scientific notation)
- Detailed fragment analysis with m/z, retention times, and quality scores
- Separate summary and detailed analysis sheets

## 📊 **Input Data Files**

### **RAW Data File**
- **File**: `Fetuin_PRM_1_6mz.raw` (179MB)
- **Location**: Should be placed in the `supplementary/` directory
- **Note**: Due to GitHub's 100MB file size limit, this file is not included in the repository
- **Direct Link**:https://doi.org/10.5061/dryad.4tmpg4fpz 
- **Reviewer Access**: http://datadryad.org/share/79oK8nNAOLVf2oQccjhLag6jEb1vIv9q1s4KpXOxg2k.  
- **Usage**: Download and place in the `supplementary/` directory before running analysis scripts

### **Figure Targets** (`data/figure_targets.xlsx`)
Focused subset for sample figure generation:
- RPTGEVYDIEIDTLETTCHVLDPTPLANCSVR-5603 (multiple charge states)
- LCPDCPLLAPLNDSR-5604 (multiple charge states)

### **Table Targets** (`data/table_targets.xlsx`)
Complete target list of glycopeptides with:
- Glycan codes (4501, 4502, 5602, 5603, 5604, etc.)
- Peptide sequences 
- Retention times (RT)
- Precursor m/z values
- Charge states
- RT windows

### **Raw MS Data** (`Fetuin_PRM_1_6mz_2.raw`)
Actual Thermo RAW file from experimental data:
- Bovine fetuin PRM analysis
- Multiple targeted glycopeptides
- Real experimental data for analysis

## 📈 **Expected Outputs**

After running the analysis scripts:

```
outputs/
├── figures_Fetuin_PRM_1_6mz_2/          # Figure script output
│   ├── EIC_*.svg                      # Extracted ion chromatograms
│   └── MS2_*.svg                      # MS/MS spectra
└── table_outputs/
    ├── table.xlsx                     # Detailed analysis results
    └── summary_table.xlsx             # Summary results
```

### **Sample Table Results Format:**
- **Target**: Uses RT-based naming (e.g., `LCPDCPLLAPLNDSR-4501_62.1`)
- **Fragments_Found**: Integer count of detected fragments
- **Total_Area**: Readable numbers (e.g., `251000` not `2.51E+05`)
- **Average_Intensity**: Readable numbers (e.g., `15200` not `1.52E+04`)
- **Status**: "Successfully Analyzed" or "No Fragments Detected"

## 🔧 **Requirements**

- Python 3.11+ 
- GlypPRM_App_v01.py (main analysis application in parent directory)
- Required Python packages (see requirements.txt):
  - pandas
  - openpyxl
  - matplotlib
  - scipy
  - pyteomics
  - networkx
  - PyQt5

## 📚 **Analysis Context**

These scripts demonstrate GlypPRM analysis capabilities using real experimental data from bovine fetuin. Key features:

- **Real Analysis**: Uses actual GlypPRM analysis functions (no placeholder data)
- **Multi-charge Detection**: Fragments detected across charge states 1+, 2+, and 3+  
- **Comprehensive Settings**: Uses optimized parameters for fragment detection and quantification
- **Quality Control**: FDR grading and filtering for high-quality results
- **SVG Output**: Vector graphics in same format as main GlypPRM application

## � **Technical Details**

### **Analysis Parameters Used:**
- **MS2 tolerance**: 25 ppm (optimized for multi-charge detection)
- **Intensity threshold**: 500 (lowered to detect higher charge state fragments)
- **FDR grade cutoff**: "C" (balanced quality vs sensitivity)
- **Fragment types**: "all" (comprehensive fragment coverage)
- **RT window**: Variable by target (1-2 minutes)

### **Script Features:**
- **Figure script**: RT-based target naming, saves to user-specified output directory
- **Table script**: Filters fragments by m/z and RT matching, readable number formatting
- **Both scripts**: Use real GlypPRM analysis without fallback placeholder data

## 📝 **Notes**

- Scripts now use **real experimental data** with actual fragment detection
- Target naming uses retention time for better identification
- Numbers displayed in readable format (not scientific notation)
- SVG plots generated by GlypPRM's built-in plotting functions
- Analysis results show actual fragment counts and quantification data

## 📧 **Contact**

For questions about reproduction or data, contact the manuscript authors.


