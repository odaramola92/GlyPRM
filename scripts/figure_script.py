#!/usr/bin/env python3
"""
Script to generate sample figures using GlypPRM analysis:
Representative extraction ion chromatogram (EIC) and MS/MS of quantified PRM N-glycopeptides.

This script uses GlypPRM_App_v01.py to analyze:
- RPTGEVYDIEIDTLETTCHVLDPTPLANCSVR-5603 
- LCPDCPLLAPLNDSR-5604

Input: Fetuin_PRM_1_6mz.raw + figure_targets.xlsx
Output: Sample EIC plots and MS/MS spectra (SVG format)

This script uses real GlypPRM analysis with built-in plotting functions.
"""

import sys
import os
import argparse
import pandas as pd
from pathlib import Path

# Add parent directory to path to import GlypPRM
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from GlypPRM_App_v01 import analyze_and_export_all_glycans
    print("✓ Successfully imported GlypPRM_App_v01")
except ImportError as e:
    print(f"❌ GlypPRM_App_v01 import failed: {e}")
    print("   This script requires GlypPRM_App_v01.py to be available for real analysis")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description='Generate sample figures using real GlypPRM analysis')
    parser.add_argument('--raw-file', required=True, help='Path to Fetuin_PRM_1_6mz.raw')
    parser.add_argument('--targets', required=True, help='Path to figure_targets.xlsx')
    parser.add_argument('--output-dir', required=True, help='Output directory for figures')
    
    args = parser.parse_args()
    
    # Verify input files exist
    raw_file = Path(args.raw_file)
    targets_file = Path(args.targets)
    output_dir = Path(args.output_dir)
    
    if not raw_file.exists():
        print(f"❌ Raw file not found: {raw_file}")
        sys.exit(1)
        
    if not targets_file.exists():
        print(f"❌ Targets file not found: {targets_file}")
        sys.exit(1)
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"📋 Loading targets from {targets_file}")
    targets_df = pd.read_excel(targets_file)
    print(f"   Found {len(targets_df)} targets")
    
    print("\n🎯 Target glycopeptides for sample figures:")
    for _, row in targets_df.iterrows():
        print(f"   {row['Peptide']}-{row['Glycan']} (RT: {row['RT']} min, m/z: {row['Precursor_mz']}, z: {row['Charge']})")
    
    print(f"\n🔬 Processing raw file: {raw_file}")
    print(f"📊 Output directory: {output_dir}")
    
    # Process each target individually with GlypPRM's built-in plotting
    for idx, row in targets_df.iterrows():
        peptide = row['Peptide']
        glycan = row['Glycan']
        rt = row['RT']
        mz = row['Precursor_mz']
        charge = row['Charge']
        rt_window = row['RT_window']
        
        target_name = f"{peptide}-{glycan}_{rt}"
        print(f"\n🧪 Processing {target_name}...")
        
        try:
            # Create a single-target Excel file
            temp_target_file = output_dir / f"temp_{target_name}.xlsx"
            temp_target_df = pd.DataFrame([row])
            temp_target_df.to_excel(temp_target_file, index=False)
            
            # Output files for this target
            temp_output_file = output_dir / f"temp_output_{target_name}.xlsx"
            
            print(f"   📊 Analyzing {target_name} with GlypPRM built-in plotting...")
            
            # Run GlypPRM analysis with comprehensive settings and plotting ENABLED
            output_path, cached_data, matched_fragments = analyze_and_export_all_glycans(
                excel_input_file=str(temp_target_file),
                excel_output_file=str(temp_output_file),
                input_file=str(raw_file),
                output_dir=str(output_dir),  # Specify where to save plots
                modification_type=6,  
                rt_window=5.0,
                max_rt_window=1.5,
                back_window_ratio=0.5,
                max_rt_difference=1.0,
                display_time_extension=5.0,
                fragment_types="all",
                fdr_grade_cutoff="C",
                use_excel_precursor=True,
                use_excel_rt_window=True,
                use_excel_pepmass=False,
                use_excel_peptide_mod=False,
                use_cam=True,
                fixed_mods=["CAM"],
                variable_mods=[""],
                glycan_type="N",  # N-glycans
                generate_eic_plots=True,  # ENABLE EIC plots
                generate_ms2_plots=True,  # ENABLE MS/MS plots
                max_fragments_displayed=20,
                generate_glycan_by_ions=True,
                generate_peptide_by_ions=True,
                generate_cz_peptide_fragment=False,
                generate_cz_glycan_fragment=False,
                save_excel=False,  # Don't need Excel output for figures
                prefer_fisher_py=True,
                intensity_threshold=1000
            )
            
            print(f"   ✅ GlypPRM analysis complete for {target_name}")
            print(f"   📈 Found {len(matched_fragments)} matched fragments")
            
            # Clean up temporary files
            if temp_target_file.exists():
                temp_target_file.unlink()
            if temp_output_file.exists():
                temp_output_file.unlink()
            
            print(f"   🎉 Successfully generated real GlypPRM plots for {target_name}")
            
        except Exception as e:
            print(f"   ❌ Error processing {target_name}: {e}")
            # Clean up on error
            if temp_target_file.exists():
                temp_target_file.unlink()
            if temp_output_file.exists():
                temp_output_file.unlink()
            raise Exception(f"Failed to process {target_name}: {e}")
    
    print(f"\n✅ Sample figure generation complete!")
    print(f"📁 Plot files saved to: {output_dir}")
    print(f"📂 Look for subdirectories with names like 'figures_Fetuin_PRM_1_6mz_*'")
    print("\n🎉 All plots generated using real GlypPRM analysis data!")
    print("   - EIC plots show actual fragment retention times vs intensities")
    print("   - MS/MS plots show actual fragment m/z vs intensities")
    print("   - SVG format plots as generated by GlypPRM")
  

if __name__ == "__main__":
    main()
