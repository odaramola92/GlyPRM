#!/usr/bin/env python3
"""
Script to generate sample table showing all matched fragments and quantifications:
Excel output demonstrating GlypPRM's analytical capabilities across replicate samples.

This script uses GlypPRM_App_v01.py to analyze all targets from the sample data
and generate a comprehensive results table.

Input: Fetuin_PRM_1_6mz.raw + table_targets.csv
Output: Sample Table (Excel format with all fragments and quantifications)
"""

import sys
import os
import argparse
import pandas as pd
from pathlib import Path

# Add parent directory to path to import GlypPRM
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    # Import your main GlypPRM application
    from GlypPRM_App_v01 import (
        GlycanAnalysisGUI, 
        main_cli,
        GlycanMassCalculator,
        analyze_and_export_all_glycans
    )
    print("✓ Successfully imported GlypPRM_App_v01")
except ImportError as e:
    print(f"❌ GlypPRM_App_v01 import failed: {e}")
    print("   GlypPRM is required for this script to function")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description='Generate sample table with comprehensive GlypPRM analysis')
    parser.add_argument('--raw-file', required=True, help='Path to Fetuin_PRM_1_6mz.raw')
    parser.add_argument('--targets', required=True, help='Path to table_targets.xlsx')
    parser.add_argument('--output', required=True, help='Output Excel file for sample table')
    
    args = parser.parse_args()
    
    # Verify input files exist
    raw_file = Path(args.raw_file)
    targets_file = Path(args.targets)
    output_file = Path(args.output)
    
    if not raw_file.exists():
        print(f"❌ Raw file not found: {raw_file}")
        sys.exit(1)
        
    if not targets_file.exists():
        print(f"❌ Targets file not found: {targets_file}")
        sys.exit(1)
    
    # Create output directory
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Load target list from Excel
    print(f"📋 Loading targets from {targets_file}")
    try:
        targets_df = pd.read_excel(targets_file)
        print(f"   Found {len(targets_df)} targets")
    except Exception as e:
        print(f"❌ Error reading Excel file: {e}")
        sys.exit(1)
    
    print(f"\n🔬 Processing raw file: {raw_file}")
    print(f"📊 Output file: {output_file}")
    
    # Initialize results storage
    all_results = []
    
    # Process each target
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
            # Run actual GlypPRM analysis for all targets at once
            print(f"   🔬 Running GlypPRM analysis for {target_name}...")
            
            # For the table generation, we can run the full analysis on all targets
            # This is more efficient than processing each target individually
            if idx == 0:  # Only run once for all targets
                print(f"\n🔬 Running comprehensive GlypPRM analysis on all {len(targets_df)} targets...")
                
                # Run GlypPRM analysis on the entire target file with comprehensive settings
                try:
                    output_path, cached_data, matched_fragments = analyze_and_export_all_glycans(
                        excel_input_file=str(targets_file),
                        excel_output_file=str(output_file),
                        input_file=str(raw_file),
                        modification_type=6,  # Glycopeptides
                        mass_modification=0,
                        rt_window=5.0, 
                        max_rt_window=1.5,
                        back_window_ratio=0.5,
                        max_rt_difference=1.0,
                        display_time_extension=5.0,
                        ms1_ppm_tolerance=10,
                        ms2_ppm_tolerance=20,
                        fragment_types="all",
                        fdr_grade_cutoff="C",
                        use_strict_rt_window=True,
                        use_provided_rt=True,
                        use_excel_rt_window=True,
                        use_excel_precursor=True,
                        use_excel_pepmass=False,
                        use_excel_peptide_mod=False,
                        use_cam=True,
                        fixed_mods=["CAM"],
                        variable_mods=[""],
                        glycan_type="N",  # N-glycans
                        generate_eic_plots=False,
                        generate_ms2_plots=False,
                        max_fragments_displayed=20,
                        generate_glycan_by_ions=True,
                        generate_peptide_by_ions=True,
                        generate_cz_peptide_fragment=False,
                        generate_cz_glycan_fragment=False,
                        save_excel=True,  # Save the full Excel output
                        prefer_fisher_py=True,
                        intensity_threshold=1000,
                        use_intensity_instead_of_area=False
                    )
                    
                    print(f"   ✅ GlypPRM analysis complete!")
                    print(f"   📊 Results saved to: {output_path}")
                    print(f"   📈 Found {len(matched_fragments)} total matched fragments")
                    
                    # Store the results for use in individual target processing
                    global_analysis_results = {
                        'output_path': output_path,
                        'cached_data': cached_data,
                        'matched_fragments': matched_fragments,
                        'success': True
                    }
                    
                except Exception as e:
                    print(f"   ❌ GlypPRM analysis failed: {e}")
                    raise Exception(f"GlypPRM analysis failed: {e}")
            
            # Process individual target results
            if 'global_analysis_results' in locals() and global_analysis_results['success']:
                # Filter results for this specific target
                target_fragments = global_analysis_results['matched_fragments']
                if not target_fragments.empty:
                    # Debug: Print available columns
                    print(f"   🔍 DEBUG: Available columns in matched_fragments: {list(target_fragments.columns)}")
                    print(f"   🔍 DEBUG: Sample of first few rows:")
                    print(target_fragments.head(2).to_string())
                    
                    # Find fragments for this specific target by matching precursor m/z and RT
                    # This is more reliable than trying to match by name
                    mz_tolerance = 0.01  # m/z tolerance for matching
                    rt_tolerance = 2.0   # RT tolerance in minutes
                    
                    mz_mask = abs(target_fragments['Precursor_mz'] - mz) < mz_tolerance
                    rt_mask = abs(target_fragments['precursor_rt'] - rt) < rt_tolerance
                    target_mask = mz_mask & rt_mask
                    
                    target_specific_fragments = target_fragments[target_mask]
                    
                    print(f"   🔍 DEBUG: Filtering by m/z={mz:.4f} (±{mz_tolerance}) and RT={rt:.1f} (±{rt_tolerance})")
                    print(f"   🔍 DEBUG: Found {len(target_specific_fragments)} fragments for this target")
                    
                    if not target_specific_fragments.empty:
                        # Calculate summary statistics
                        num_fragments = len(target_specific_fragments)
                        total_area = target_specific_fragments['Area'].sum() if 'Area' in target_specific_fragments.columns else 0
                        avg_intensity = target_specific_fragments['Intensity'].mean() if 'Intensity' in target_specific_fragments.columns else 0
                        
                        result = {
                            'Target': target_name,
                            'Peptide': peptide,
                            'Glycan': glycan,
                            'RT': rt,
                            'Precursor_mz': mz,
                            'Charge': charge,
                            'RT_window': rt_window,
                            'Status': 'Successfully Analyzed',
                            'Fragments_Found': num_fragments,
                            'Total_Area': int(total_area) if total_area > 0 else 'N/A',
                            'Average_Intensity': int(avg_intensity) if avg_intensity > 0 else 'N/A',
                            'Analysis_Method': 'GlypPRM_v01'
                        }
                    else:
                        result = {
                            'Target': target_name,
                            'Peptide': peptide,
                            'Glycan': glycan,
                            'RT': rt,
                            'Precursor_mz': mz,
                            'Charge': charge,
                            'RT_window': rt_window,
                            'Status': 'No Fragments Detected',
                            'Fragments_Found': 0,
                            'Total_Area': 'N/A',
                            'Average_Intensity': 'N/A',
                            'Analysis_Method': 'GlypPRM_v01'
                        }
                else:
                    result = {
                        'Target': target_name,
                        'Peptide': peptide,
                        'Glycan': glycan,
                        'RT': rt,
                        'Precursor_mz': mz,
                        'Charge': charge,
                        'RT_window': rt_window,
                        'Status': 'Analysis Complete - No Data',
                        'Fragments_Found': 'N/A',
                        'Total_Area': 'N/A',
                        'Average_Intensity': 'N/A',
                        'Analysis_Method': 'GlypPRM_v01'
                    }
            else:
                # Analysis failed
                error_msg = global_analysis_results.get('error', 'Unknown error') if 'global_analysis_results' in locals() else 'Analysis not attempted'
                raise Exception(f"Analysis failed: {error_msg}")
            
            all_results.append(result)
            print(f"   ✓ Processed {target_name}")
            
        except Exception as e:
            print(f"   ❌ Error processing {target_name}: {e}")
            raise Exception(f"Failed to process {target_name}: {e}")
    
    # Create results DataFrame
    results_df = pd.DataFrame(all_results)
    
    # Save to Excel (sample table format)
    print(f"\n💾 Saving summary results to {output_file}")
    
    # Check if GlypPRM analysis was successful and created a detailed Excel file
    if 'global_analysis_results' in locals() and global_analysis_results['success']:
        detailed_output = global_analysis_results['output_path']
        if detailed_output and os.path.exists(detailed_output):
            print(f"📊 Full GlypPRM analysis results available at: {detailed_output}")
            print(f"   This contains detailed fragment analysis, theoretical fragments, and quantification data")
        
        # Create a summary table in addition to the detailed GlypPRM output
        summary_file = output_file.parent / f"summary_{output_file.name}"
        with pd.ExcelWriter(summary_file, engine='openpyxl') as writer:
            # Summary results sheet
            results_df.to_excel(writer, sheet_name='Summary_Results', index=False)
            # Input targets sheet for reference
            targets_df.to_excel(writer, sheet_name='Input_Targets_S1', index=False)
        
        print(f"📋 Summary results saved to: {summary_file}")
        print(f"📊 Detailed GlypPRM analysis saved to: {detailed_output}")
        
    else:
        # If GlypPRM analysis failed or wasn't available, create placeholder table
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            # Main results sheet
            results_df.to_excel(writer, sheet_name='SupplementaryTable_S3', index=False)
            # Input targets sheet for reference
            targets_df.to_excel(writer, sheet_name='Input_Targets_S1', index=False)
        
        print(f"📋 Placeholder results saved to: {output_file}")
    
    print(f"\n✅ Sample table generation complete!")
    print(f"� Processed {len(results_df)} targets")
    
    if 'global_analysis_results' in locals() and global_analysis_results['success']:
        print("\n🎉 Real GlypPRM analysis completed successfully!")
        print("   The detailed Excel file contains:")
        print("   • All theoretical fragments for each glycopeptide")
        print("   • Matched experimental fragments with m/z, RT, and intensities")
        print("   • Fragment areas and quantification data")
        print("   • Multiple sheets with different analysis perspectives")
    else:
        print("\n📝 Note: Placeholder results generated.")
        print("   To generate actual fragment analysis and quantification data,")
        print("   ensure GlypPRM_App_v01.py is available and the RAW file is accessible.")

if __name__ == "__main__":
    main()
