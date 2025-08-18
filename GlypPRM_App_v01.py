# Add this at the very top, before any other imports
import sys
import os
import matplotlib

# Force matplotlib backend for PyInstaller builds
if getattr(sys, 'frozen', False):
    # Running as PyInstaller executable
    matplotlib.use('Agg')
    os.environ['MPLBACKEND'] = 'Agg'
    print("DEBUG: Using Agg backend for PyInstaller build")
else:
    # Running as script
    try:
        matplotlib.use('Qt5Agg')
        print("DEBUG: Using Qt5Agg backend for development")
    except ImportError:
        matplotlib.use('Agg')
        print("DEBUG: Fallback to Agg backend")

import matplotlib.pyplot as plt
plt.ioff()
import io
import numpy as np
import traceback
from scipy.signal import savgol_filter, find_peaks
from scipy.integrate import simpson
from numpy import trapz
import os.path
import pandas as pd
from datetime import datetime
import networkx as nx
from itertools import combinations
import copy
import re 
from pyteomics import mzml
import glob
import multiprocessing
import os
import logging
import traceback 
import matplotlib.pyplot as plt
from scipy.signal import savgol_filter
import traceback
import multiprocessing
import gc
import os
import time
import glob
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import re
import gc
from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache
import traceback  
import warnings
warnings.filterwarnings("ignore")    
try:
    matplotlib.use('Agg')  
except Exception as e:
    print(f"Warning: Failed to set matplotlib backend: {str(e)}")
import matplotlib as mpl
mpl.rcParams['font.family'] = 'Arial'  # Or another font like 'Helvetica', 'Times New Roman', etc.
mpl.rcParams['font.size'] = 14
mpl.rcParams['font.weight'] = 'bold'  # This makes all font bold by default
mpl.rcParams['axes.labelweight'] = 'bold'  # Bold axis labels
mpl.rcParams['axes.titleweight'] = 'bold'  # Bold titles
mpl.rcParams['axes.linewidth'] = 1.5  # Thicker axes lines
mpl.rcParams['xtick.major.width'] = 1.5  # Thicker x ticks
mpl.rcParams['ytick.major.width'] = 1.5  # Thicker y ticks

logging.basicConfig(
    level=logging.INFO,  # Set to logging.DEBUG for more detailed logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def debug_startup():
    print("Starting application...")
    print(f"Python executable: {sys.executable}")
    print(f"Python path: {sys.path}")
    try:
        # Test critical imports
        print("Testing imports...")
        import fisher_py
        print("✓ fisher_py imported")
        import pandas
        print("✓ pandas imported")
        import numpy
        print("✓ numpy imported")
        import PyQt5
        print("✓ PyQt5 imported")
        import matplotlib
        print("✓ matplotlib imported")
        print("All imports successful!")
    except Exception as e:
        print(f"Import error: {e}")
        traceback.print_exc()
        input("Press Enter to exit...")
        sys.exit(1)

if __name__ == "__main__":
    debug_startup()


#Glycan Structure Prediction and Mass Calculation
class GlycanMassCalculator:
    def __init__(self, modification_type=6, use_cam=True, fixed_mods=None, variable_mods=None, mod_string=None, peptide=None):
        # Initialize existing properties
        self.BASE_MASSES = {
            'HexNAc': 203.0794,
            'Hex': 162.0528,
            'Fuc': 146.0579,
            'NeuAc': 291.0954,
            'NeuGc': 307.0903
        }
        
        # Initialize attributes with default values
        self.MONO_MASSES = self.BASE_MASSES.copy()
        self.OH_GROUPS = {
            'HexNAc': 3,
            'Hex': 3,
            'Fuc': 2,
            'NeuAc': 5,
            'NeuGc': 6
        }
        self.MOD_MASSES = {
            'Permethylation': 14.0157,
        }
        self.REDUCING_END_MASSES = {
            0:18.0153,  # Free end (H2O)
            1: 20.0262,  # Reduced end (H2 + 2H)
            2:18.0153,  # Permethylated free end (H2O, before permethylation)
            3: 20.0262,  # Permethylated reduced end (H2 + 2H, before permethylation)
            4:18.0153,  # 2AB labeled (H2O, before 2AB)
            5:18.0153,   # 2AB labeled and permethylated (H2O, before 2AB and permethylation)
            6: 0.0   # PEP (default to water, replaced by peptide mass)
        }
        self.ADDITIONAL_MODIFICATIONS = {
            0: 0.0,      # Free end - no additional mod
            1: 0.0,      # Reduced end - no additional mod
            2: 28.0314,  # Permethylated free end - 2 extra methyl groups (approximate)
            3: 28.0314,   # Permethylated reduced end - 3 extra methyl groups (approximate)
            4: 120.0688, # 2AB labeled - 2AB mass minus water
            5: 190.1451, # 2AB labeled and permethylated - 2AB plus permethylation
            6:18.0153       # PEP - peptide mass replaces water, no additional modification
        }
        self.PROTON_MASS = 1.0073
        self.PEPTIDE_MASSES = {}  # To store peptide masses
        
        # Convert input parameters to safe types
        self.modification_type = modification_type
        self.use_cam = bool(use_cam)
        
        # Ensure fixed_mods and variable_mods are lists of strings
        self.fixed_mods = [str(mod) for mod in (fixed_mods or [])]
        self.variable_mods = [str(mod) for mod in (variable_mods or [])]
        
        self.mod_string = mod_string        
        self.peptide = peptide  # Store the peptide sequence
          # Initialize monosaccharide masses based on the modification type
        self.calculate_MONO_MASSES(modification_type)
        
    def calculate_MONO_MASSES(self, modification_type):
        self.MONO_MASSES = self.BASE_MASSES.copy()
        for mono in self.MONO_MASSES:
            base_mass = self.MONO_MASSES[mono]
            if modification_type in [0, 1, 4, 6]:  # Free end, Reduced end, 2AB labeled, or PEP
                self.MONO_MASSES[mono] = base_mass
            elif modification_type in [2, 3, 5]:  # Permethylated cases
                oh_groups = self.OH_GROUPS[mono]
                self.MONO_MASSES[mono] = base_mass + (oh_groups * self.MOD_MASSES['Permethylation'])    
    
    def parse_glycan_code(self, code):
        """
        Parse a glycan code and return the counts of different monosaccharides.
        
        Supports formats:
        - Numeric (e.g., '5401')
        - Oxford notation (e.g., 'HexNAc(4)Hex(5)Fuc(1)NeuAc(2)')
        
        Returns:
            Tuple of (HexNAc, Hex, Fuc, NeuAc, NeuGc) counts
        """
        code = str(code).replace(" ", "")
        
        # Check if the code starts with a letter (indicates named format)
        if code and code[0].isalpha():
            # Create a dictionary to track monosaccharide counts
            mono_counts = {
                'HexNAc': 0,
                'Hex': 0,
                'Fuc': 0,
                'NeuAc': 0,
                'NeuGc': 0
            }
            
            # Handle various monosaccharide naming conventions
            name_mappings = {
                'HEXNAC': 'HexNAc',
                'HEXN': 'HexNAc',
                'GLCNAC': 'HexNAc',
                'GALNAC': 'HexNAc',
                'HEX': 'Hex',
                'HEXOSE': 'Hex',
                'GLC': 'Hex',
                'GAL': 'Hex',
                'MAN': 'Hex',
                'FUC': 'Fuc',
                'FUCOSE': 'Fuc',
                'NEUAC': 'NeuAc',
                'SIA': 'NeuAc',
                'SIALIC': 'NeuAc',
                'NEUGC': 'NeuGc'
            }
            
            # Use regex to find patterns like "HexNAc(3)" or "Hex(4)"
            pattern = r'([A-Za-z]+)\((\d+)\)'
            matches = re.findall(pattern, code)
            
            for mono_name, count in matches:
                # Convert to uppercase for case-insensitive comparison
                mono_upper = mono_name.upper()
                
                # Map to standard name if possible
                if mono_upper in name_mappings:
                    standard_name = name_mappings[mono_upper]
                    mono_counts[standard_name] += int(count)
                else:
                    # If not recognized, try to match by prefix
                    matched = False
                    for known_name in name_mappings:
                        if mono_upper.startswith(known_name):
                            standard_name = name_mappings[known_name]
                            mono_counts[standard_name] += int(count)
                            matched = True
                            break
                    
                    if not matched:
                        print(f"Warning: Unknown monosaccharide '{mono_name}' in glycan code. Ignoring.")
            
            # Extract final counts
            return mono_counts['HexNAc'], mono_counts['Hex'], mono_counts['Fuc'], mono_counts['NeuAc'], mono_counts['NeuGc']
        else:
            # Check if the code is a multi-digit number
            if code.isdigit() and len(code) >= 4:
                # For multi-digit numeric codes like 4501, 4502
                # Each digit represents a different monosaccharide count
                hexnac = int(code[0])
                hex_count = int(code[1])
                fuc = int(code[2])
                neuac = int(code[3])
                # Add NeuGc if code is longer
                neugc = int(code[4]) if len(code) > 4 else 0
                
                print(f"Processing numeric glycan code {code} as HexNAc({hexnac})Hex({hex_count})Fuc({fuc})NeuAc({neuac})NeuGc({neugc})")
                return hexnac, hex_count, fuc, neuac, neugc
            else:
                # Original logic for other formats
                pattern = r'\((\d+)\)|(\d)'
                matches = re.findall(pattern, code)
                components = [int(match[0] or match[1]) for match in matches]
                if len(components) == 5:
                    return components[0], components[1], components[2], components[3], components[4]
                elif len(components) == 4:
                    return components[0], components[1], components[2], components[3], 0
                else:
                    raise ValueError(f"Invalid glycan code length: {len(components)}")
           
    def calculate_mz(self, mass, charge):
        return (mass + (charge * self.PROTON_MASS)) / charge

    def get_amino_acid_mass(self, aa, position, peptide_sequence=None):
        """
        Get the mass of an amino acid at a specific position, including modifications.
        
        Args:
            aa: The amino acid (single letter code)
            position: Position in the peptide (0-indexed)
            peptide_sequence: Full peptide sequence for context
            
        Returns:
            Float: Mass of the amino acid with any applicable modifications
        """
        # Define standard amino acid masses
        amino_acid_masses = {
            'A': 71.0371, 'C': 103.0092, 'D': 115.0269, 'E': 129.0426,
            'F': 147.0684, 'G': 57.0215, 'H': 137.0589, 'I': 113.0841,
            'K': 128.0950, 'L': 113.0841, 'M': 131.0405, 'N': 114.0429,
            'P': 97.0528, 'Q': 128.0586, 'R': 156.1011, 'S': 87.0320,
            'T': 101.0477, 'V': 99.0684, 'W': 186.0793, 'Y': 163.0633
        }
        
        # Define common modification masses
        mod_masses = {
            'CAM': 57.02146,      # Carbamidomethylation (Cys) - iodoacetamide
            'PAM': 71.03711,      # Propionamide (Cys) - acrylamide    
            'Palm': 238.2297,     # Palmitoylation (Cys)
            'Carbamyl': 43.0058,  # Carbamylation (N-term, Lys)
            'TMT6': 229.16293,    # TMT 6-plex (Lys/N-term)
            'TMT10': 229.16293,   # TMT 10-plex (Lys/N-term)
            'TMT16': 304.20710,   # TMTpro 16-plex (Lys/N-term)
            'iTRAQ4': 144.10206,  # iTRAQ 4-plex (Lys/N-term)
            'iTRAQ8': 304.20536,  # iTRAQ 8-plex (Lys/N-term)
                
            # Variable modifications
            'Ox': 15.99491,       # Oxidation (Met)
            'Deam': 0.98402,      # Deamidation (Asn/Gln)
            'Phos': 79.96633,     # Phosphorylation (Ser/Thr/Tyr)
            'Ac': 42.01056,       # Acetylation (Lys/N-term)
            'Methyl': 14.0157,    # Methylation (Lys/Arg)
            'DiMethyl': 28.0313,  # Dimethylation (Lys/Arg)
            'TriMethyl': 42.0470, # Trimethylation (Lys)
            'Pyro-glu': -17.0265, # Pyroglutamic acid from N-term Gln
            'Pyro-cmC': -17.0265, # Pyroglutamic acid from N-term carbamidomethyl Cys
            'GG': 114.0429,       # GlyGly (Lys) - ubiquitination remnant
            'HexNAc': 203.0794,   # O-GlcNAc (Ser/Thr)
        }
        
        # Get base mass for amino acid
        base_mass = amino_acid_masses.get(aa.upper(), 0.0)
        
        # Track modifications applied
        mod_applied = None
        
        # Check if this position has a modification from our calculated modifications
        # First check if we have stored the applied modifications
        if hasattr(self, 'applied_mods'):
            mod_key = f"{aa}{position+1}"  # Convert to 1-indexed position for key
            for mod_name, positions in self.applied_mods.items():
                if mod_key in positions:
                    mod_applied = mod_name
                    mod_mass = mod_masses.get(mod_name, 0.0)
                    base_mass += mod_mass
                    break
        
        # Check special cases for terminal positions
        if peptide_sequence and position == 0:  # N-terminus
            if hasattr(self, 'applied_mods'):
                for mod_name, positions in self.applied_mods.items():
                    if 'N-term' in positions:
                        mod_mass = mod_masses.get(mod_name, 0.0)
                        base_mass += mod_mass
        
        if peptide_sequence and position == len(peptide_sequence) - 1:  # C-terminus
            if hasattr(self, 'applied_mods'):
                for mod_name, positions in self.applied_mods.items():
                    if 'C-term' in positions:
                        mod_mass = mod_masses.get(mod_name, 0.0)
                        base_mass += mod_mass
        
        return base_mass

    def calculate_peptide_mass(self, peptide, auto_modifications=True, custom_mods=None, use_cam=None, 
                        fixed_mods=None, variable_mods=None, mod_string=None, debug=False):
        """Calculate the monoisotopic mass of a peptide sequence with modifications"""
        
        # Ensure peptide is a string, not None
        peptide = str(peptide or "")
        
        # if debug:
        #     print(f"\n=== DEBUG: calculate_peptide_mass ===")
        #     print(f"Peptide: {peptide}")
        #     print(f"use_cam parameter: {use_cam}")
        #     print(f"use_cam from instance: {self.use_cam}")
        #     print(f"fixed_mods parameter: {fixed_mods}")
        #     print(f"fixed_mods from instance: {self.fixed_mods}")
        
        # Use instance values if parameters not provided and attributes exist
        use_cam = use_cam if use_cam is not None else getattr(self, 'use_cam', True)
        fixed_mods = fixed_mods or getattr(self, 'fixed_mods', []) or []
        variable_mods = variable_mods or getattr(self, 'variable_mods', []) or []
        mod_string = mod_string or getattr(self, 'mod_string', None)
        
        # if debug:
        #     print(f"Final use_cam value: {use_cam}")
        #     print(f"Final fixed_mods value: {fixed_mods}")
        #     print(f"Contains 'CAM:C' in fixed_mods: {'CAM:C' in fixed_mods}")
        #     print(f"Contains 'CAM' in fixed_mods: {'CAM' in fixed_mods}")
        
        # Create a comprehensive cache key that includes ALL modifications
        cache_key = create_comprehensive_peptide_cache_key(
            peptide, 
            use_cam=use_cam,
            fixed_mods=fixed_mods,
            variable_mods=variable_mods,
            mod_string=mod_string
        )
        
        # Check if in cache
        if cache_key in self.PEPTIDE_MASSES:
            cached_mass = self.PEPTIDE_MASSES[cache_key]
            # if debug:
            #     print(f"Using cached peptide mass for {cache_key}")
            #     print(f"Cached mass: {cached_mass:.4f} Da")
                
            # Always print explicit cache hits for the problematic peptide
            # if peptide == "LCPDCPLLAPLNDSR":
            #     print(f"PEPTIDE CACHE HIT in calculate_peptide_mass() for {peptide}: {cached_mass:.4f} Da")
                
            return cached_mass
        
        # Initialize modifications dictionary
        modifications = {}
        applied_mods = {}
        mod_masses_applied = 0.0
        
        # Define common modification masses
        mod_masses = {
            # Fixed modifications
            'CAM': 57.02146,      # Carbamidomethylation (Cys) - iodoacetamide
            'PAM': 71.03711,      # Propionamide (Cys) - acrylamide    
            'Palm': 238.2297,     # Palmitoylation (Cys)
            'Carbamyl': 43.0058,  # Carbamylation (N-term, Lys)
            'TMT6': 229.16293,    # TMT 6-plex (Lys/N-term)
            'TMT10': 229.16293,   # TMT 10-plex (Lys/N-term)
            'TMT16': 304.20710,   # TMTpro 16-plex (Lys/N-term)
            'iTRAQ4': 144.10206,  # iTRAQ 4-plex (Lys/N-term)
            'iTRAQ8': 304.20536,  # iTRAQ 8-plex (Lys/N-term)
                
            # Variable modifications
            'Ox': 15.99491,       # Oxidation (Met)
            'Deam': 0.98402,      # Deamidation (Asn/Gln)
            'Phos': 79.96633,     # Phosphorylation (Ser/Thr/Tyr)
            'Ac': 42.01056,       # Acetylation (Lys/N-term)
            'Methyl': 14.0157,    # Methylation (Lys/Arg)
            'DiMethyl': 28.0313,  # Dimethylation (Lys/Arg)
            'TriMethyl': 42.0470, # Trimethylation (Lys)
            'Pyro-glu': -17.0265, # Pyroglutamic acid from N-term Gln
            'Pyro-cmC': -17.0265, # Pyroglutamic acid from N-term carbamidomethyl Cys
            'GG': 114.0429,       # GlyGly (Lys) - ubiquitination remnant
            'HexNAc': 203.0794,   # O-GlcNAc (Ser/Thr)
            'Formyl': 27.99492,   # Formylation (Lys/N-term)
            'Nitration': 44.98508,# Nitration (Tyr)
            'Sulf': 79.95682,     # Sulfation (Tyr)
            'Biotin': 226.0776,   # Biotinylation (Lys)
            'Malonyl': 86.00039,  # Malonylation (Lys)
            'Succinyl': 100.01604,# Succinylation (Lys)
            'Myristoyl': 210.19837,# Myristoylation (N-term Gly)
            'Farnesyl': 204.18780,# Farnesylation (Cys)
            'SUMO1-GG': 213.14430 # SUMOylation remnant (Lys)
        }
        
        # Define target amino acids for each modification
        mod_targets = {
            # Variable modifications
            'Ox': ['M'],                          # Oxidation primarily on Met
            'Deam': ['N', 'Q'],                   # Deamidation on Asn and Gln
            'Phos': ['S', 'T', 'Y'],              # Phosphorylation on Ser, Thr, Tyr
            'Ac': ['K', 'N-term'],                # Acetylation on Lys and N-terminus
            'Methyl': ['K', 'R'],                 # Methylation on Lys and Arg
            'DiMethyl': ['K', 'R'],               # Dimethylation on Lys and Arg
            'TriMethyl': ['K'],                   # Trimethylation on Lys
            'Pyro-glu': ['N-term-Q'],             # Pyroglutamic acid from N-terminal Gln
            'Pyro-cmC': ['N-term-C-CAM'],         # Pyroglutamic acid from N-term CAM-Cys
            'GG': ['K'],                          # GlyGly (ubiquitination remnant) on Lys
            'HexNAc': ['S', 'T'],                 # O-GlcNAc on Ser and Thr
            'Formyl': ['K', 'N-term'],            # Formylation on Lys and N-term
            'Nitration': ['Y'],                   # Nitration on Tyr
            'Sulf': ['Y'],                        # Sulfation on Tyr
            'Biotin': ['K'],                      # Biotinylation on Lys
            'Malonyl': ['K'],                     # Malonylation on Lys
            'Succinyl': ['K'],                    # Succinylation on Lys
            'Myristoyl': ['N-term-G'],            # Myristoylation on N-term Gly
            'Farnesyl': ['C'],                    # Farnesylation on Cys
            'SUMO1-GG': ['K'],                    # SUMOylation remnant on Lys
                
            # Fixed modifications
            'CAM': ['C'],                         # Carbamidomethylation on Cys
            'PAM': ['C'],                         # Propionamide on Cys
            'Palm': ['C'],                        # Palmitoylation on Cys
            'Carbamyl': ['K', 'N-term'],          # Carbamylation on Lys and N-terminus
            'TMT6': ['K', 'N-term'],              # TMT 6-plex on Lys and N-term
            'TMT10': ['K', 'N-term'],             # TMT 10-plex on Lys and N-term
            'TMT16': ['K', 'N-term'],             # TMTpro 16-plex on Lys and N-term
            'iTRAQ4': ['K', 'N-term'],            # iTRAQ 4-plex on Lys and N-term
            'iTRAQ8': ['K', 'N-term']             # iTRAQ 8-plex on Lys and N-term
        }

        # Process modification string if provided (first priority)
        if mod_string:
            print(f"\n[PRIORITY 1] Processing Excel modifications: {mod_string}")
            parsed_mods = parse_modification_string(mod_string)
            for mod_name, position in parsed_mods:
                # Check if this is a custom mass modification (+XX.XX or -XX.XX)
                custom_mass = parse_custom_mass_mod(mod_name)
                
                if position and isinstance(position, str) and len(position) >= 2 and position[0].isalpha() and position[1:].isdigit():
                    # This is a format like "D4" - amino acid followed by position
                    amino_acid = position[0].upper()
                    pos = int(position[1:]) - 1  # Convert to 0-indexed
                    
                    # Verify the amino acid matches the sequence
                    if 0 <= pos < len(peptide) and peptide[pos].upper() == amino_acid:
                        if custom_mass is not None:
                            # Store custom mass value directly
                            modifications[pos] = ('CUSTOM', custom_mass)
                            print(f"  Custom mass mod: {custom_mass:+.2f} Da at position {pos+1} ({amino_acid})")
                        else:
                            # Regular named modification
                            modifications[pos] = mod_name
                            print(f"  Excel mod: {mod_name} at position {pos+1} ({amino_acid})")
                    else:
                        print(f"  Warning: Position {position} doesn't match sequence or is out of bounds")
                elif position and position.isdigit():
                    pos = int(position) - 1  # Convert to 0-indexed
                    if custom_mass is not None:
                        # Store custom mass value directly
                        modifications[pos] = ('CUSTOM', custom_mass)
                        print(f"  Custom mass mod: {custom_mass:+.2f} Da at position {pos+1}")
                    else:
                        modifications[pos] = mod_name
                        print(f"  Excel mod: {mod_name} at position {position}")
                elif position in ['N-term', 'C-term']:
                    if custom_mass is not None:
                        # Store custom mass value directly
                        modifications[position] = ('CUSTOM', custom_mass)
                        print(f"  Custom mass mod: {custom_mass:+.2f} Da at {position}")
                    else:
                        modifications[position] = mod_name
                        print(f"  Excel mod: {mod_name} at {position}")
                elif position and len(position) == 1 and position.isalpha():
                    # THIS IS THE FIX: Handle amino acid targets like "M" in "Ox:M"
                    target_aa = position.upper()
                    print(f"  Excel mod {mod_name}:{target_aa}")
                    
                    # Apply to all occurrences of this amino acid
                    for i, aa in enumerate(peptide.upper()):
                        if aa == target_aa and i not in modifications:
                            if custom_mass is not None:
                                modifications[i] = ('CUSTOM', custom_mass)
                                print(f"    Applied custom mod {custom_mass:+.2f} Da to {aa}{i+1}")
                            else:
                                modifications[i] = mod_name
                                if mod_name not in applied_mods:
                                    applied_mods[mod_name] = []
                                applied_mods[mod_name].append(f"{target_aa}{i+1}")
                                print(f"    Applied {mod_name} to {aa}{i+1} (mass +{mod_masses.get(mod_name, 0):.4f} Da)")

        if fixed_mods:
            #print(f"\n[PRIORITY 2] Processing {len(fixed_mods)} fixed modifications")
            
            # Special handling for CAM when use_cam is True
            if use_cam and any(mod == 'CAM:C' or mod == 'CAM' for mod in fixed_mods):
                cam_processed = False
                
                # First process explicit CAM:C fixed mods
                for mod in fixed_mods:
                    if mod == 'CAM:C':
                        cam_processed = True
                        #print(f"  Fixed mod CAM:C")
                        # Apply to all cysteines
                        target_count = peptide.upper().count('C')
                        #print(f"  Found {target_count} C amino acids in sequence")
                        
                        for i, aa in enumerate(peptide.upper()):
                            if aa == 'C' and i not in modifications:
                                modifications[i] = 'CAM'
                                if 'CAM' not in applied_mods:
                                    applied_mods['CAM'] = []
                                applied_mods['CAM'].append(f"C{i+1}")
                                #print(f"    Applied CAM to {aa}{i+1} (mass +{mod_masses.get('CAM', 0):.4f} Da)")
                
                # If no explicit CAM:C was found but use_cam is True, apply CAM to all cysteines
                if not cam_processed and use_cam:
                    #print(f"  Auto-applying CAM to cysteines (use_cam=True)")
                    target_count = peptide.upper().count('C')
                    #print(f"  Found {target_count} C amino acids in sequence")
                    
                    for i, aa in enumerate(peptide.upper()):
                        if aa == 'C' and i not in modifications:
                            modifications[i] = 'CAM'
                            if 'CAM' not in applied_mods:
                                applied_mods['CAM'] = []
                            applied_mods['CAM'].append(f"C{i+1}")
                            #print(f"    Applied CAM to {aa}{i+1} (mass +{mod_masses.get('CAM', 0):.4f} Da)")
            #
            # Process all other fixed modifications
            for mod in fixed_mods:
                # Skip CAM:C since we already processed it
                if mod == 'CAM:C':
                    continue
                    
                if ':' in mod:
                    mod_type, target = mod.split(':')
                    #print(f"  Fixed mod {mod_type}:{target}")
                    # Handle amino acid targets
                    if len(target) == 1 and target.isalpha():
                        # Apply to all occurrences of this amino acid
                        target_count = peptide.upper().count(target)
                        #print(f"  Found {target_count} {target} amino acids in sequence")
                        
                        for i, aa in enumerate(peptide.upper()):
                            if aa == target and i not in modifications:
                                modifications[i] = mod_type
                                if mod_type not in applied_mods:
                                    applied_mods[mod_type] = []
                                applied_mods[mod_type].append(f"{target}{i+1}")
                                #print(f"    Applied {mod_type} to {aa}{i+1} (mass +{mod_masses.get(mod_type, 0):.4f} Da)")
                else:
                    # Handle mods without explicit targets by using default targets
                    mod_type = mod
                    if mod_type in mod_targets:
                        default_targets = mod_targets[mod_type]
                        #print(f"  Fixed mod {mod_type} with default targets: {default_targets}")
                        
                        for target in default_targets:
                            if len(target) == 1:  # Single amino acid target
                                target_count = peptide.upper().count(target)
                                #print(f"  Found {target_count} {target} amino acids in sequence")
                                
                                for i, aa in enumerate(peptide.upper()):
                                    if aa == target and i not in modifications:
                                        modifications[i] = mod_type
                                        if mod_type not in applied_mods:
                                            applied_mods[mod_type] = []
                                        applied_mods[mod_type].append(f"{target}{i+1}")
                                        #print(f"    Applied {mod_type} to {aa}{i+1} (mass +{mod_masses.get(mod_type, 0):.4f} Da)")
        
        # Process variable modifications (third priority)
        if variable_mods:
            #print(f"\n[PRIORITY 3] Processing {len(variable_mods)} variable modifications")
            for mod in variable_mods:
                if ':' in mod:
                    mod_type, target = mod.split(':')
                    #print(f"  Variable mod {mod_type}:{target}")
                    
                    # Handle amino acid targets
                    if len(target) == 1 and target.isalpha():
                        # Count potential targets first
                        target_count = peptide.upper().count(target)
                        #print(f"  Found {target_count} {target} amino acids in sequence")
                        
                        for i, aa in enumerate(peptide.upper()):
                            if aa == target:
                                #print(f"    Target {target} found at position {i+1}")
                                if i not in modifications:
                                    modifications[i] = mod_type
                                    if mod_type not in applied_mods:
                                        applied_mods[mod_type] = []
                                    applied_mods[mod_type].append(f"{aa}{i+1}")
                                    #print(f"    APPLIED {mod_type} to {aa}{i+1} (mass +{mod_masses.get(mod_type, 0):.4f} Da)")
                                #else:
                                    #print(f"    SKIPPED {aa}{i+1} - already modified with {modifications[i]}")
                    
                    # Handle terminal modifications
                    elif target in ['N-term', 'C-term'] and target not in modifications:
                        modifications[target] = mod_type
                        if mod_type not in applied_mods:
                            applied_mods[mod_type] = []
                        applied_mods[mod_type].append(target)
                        #print(f"    Applied {mod_type} to {target} (mass +{mod_masses.get(mod_type, 0):.4f} Da)")
                else:
                    # Handle variable mods without explicit targets using default targets
                    mod_type = mod
                    if mod_type in mod_targets:
                        default_targets = mod_targets[mod_type]
                        #print(f"  Variable mod {mod_type} with default targets: {default_targets}")
                        
                        for target in default_targets:
                            if len(target) == 1:  # Single amino acid target
                                target_count = peptide.upper().count(target)
                                #print(f"  Found {target_count} {target} amino acids in sequence")
                                
                                for i, aa in enumerate(peptide.upper()):
                                    if aa == target:
                                        #print(f"    Target {target} found at position {i+1}")
                                        if i not in modifications:
                                            modifications[i] = mod_type
                                            if mod_type not in applied_mods:
                                                applied_mods[mod_type] = []
                                            applied_mods[mod_type].append(f"{aa}{i+1}")
                                            #print(f"    APPLIED {mod_type} to {aa}{i+1} (mass +{mod_masses.get(mod_type, 0):.4f} Da)")
                                        #else:
                                            #print(f"    SKIPPED {aa}{i+1} - already modified with {modifications[i]}")
              # Print summary of applied modifications
        #print("\n=== SUMMARY OF APPLIED MODIFICATIONS ===")
        # if applied_mods:
        #     for mod_type, positions in applied_mods.items():
        #         #print(f"  {mod_type}: {', '.join(positions)}")
        # else:
        #     print("  No modifications applied to peptide")
        
        # Store the applied modifications for later use in fragment generation
        self.applied_mods = applied_mods

        # Calculate peptide mass
        mass = 18.0153  # Add water mass for peptide
        #print(f"\n=== PEPTIDE MASS CALCULATION ===")
        #print(f"Starting with water mass: {mass:.4f} Da")
        
        # Process each amino acid
        amino_acid_masses = {
            'A': 71.0371, 'C': 103.0092, 'D': 115.0269, 'E': 129.0426,
            'F': 147.0684, 'G': 57.0215, 'H': 137.0589, 'I': 113.0841,
            'K': 128.0950, 'L': 113.0841, 'M': 131.0405, 'N': 114.0429,
            'P': 97.0528, 'Q': 128.0586, 'R': 156.1011, 'S': 87.0320,
            'T': 101.0477, 'V': 99.0684, 'W': 186.0793, 'Y': 163.0633
        }
        
        for i, aa in enumerate(peptide.upper()):
            # Add amino acid mass
            if aa in amino_acid_masses:
                aa_mass = amino_acid_masses[aa]
                mass += aa_mass
                #print(f"  Added {aa} at position {i+1}: +{aa_mass:.4f} Da (subtotal: {mass:.4f} Da)")
            
            # Apply modification if any
            if i in modifications:
                mod_type = modifications[i]
                
                # Check if this is a custom mass modification
                if isinstance(mod_type, tuple) and mod_type[0] == 'CUSTOM':
                    custom_mass_value = mod_type[1]
                    mass += custom_mass_value
                    mod_masses_applied += custom_mass_value
                    #print(f"  Added custom modification to {aa}{i+1}: {custom_mass_value:+.4f} Da (subtotal: {mass:.4f} Da)")
                elif mod_type in mod_masses:
                    mod_mass = mod_masses[mod_type]
                    mass += mod_mass
                    mod_masses_applied += mod_mass
                    #print(f"  Added {mod_type} modification to {aa}{i+1}: +{mod_mass:.4f} Da (subtotal: {mass:.4f} Da)")
        
        # Handle terminal modifications
        if 'N-term' in modifications:
            mod_type = modifications['N-term']
            
            # Check if this is a custom mass modification
            if isinstance(mod_type, tuple) and mod_type[0] == 'CUSTOM':
                custom_mass_value = mod_type[1]
                mass += custom_mass_value
                mod_masses_applied += custom_mass_value
                #print(f"  Added custom modification to N-term: {custom_mass_value:+.4f} Da (subtotal: {mass:.4f} Da)")
            elif mod_type in mod_masses:
                mod_mass = mod_masses[mod_type]
                mass += mod_mass
                mod_masses_applied += mod_mass
                #print(f"  Added {mod_type} modification to N-term: +{mod_mass:.4f} Da (subtotal: {mass:.4f} Da)")
                
        if 'C-term' in modifications:
            mod_type = modifications['C-term']
            
            # Check if this is a custom mass modification
            if isinstance(mod_type, tuple) and mod_type[0] == 'CUSTOM':
                custom_mass_value = mod_type[1]
                mass += custom_mass_value
                mod_masses_applied += custom_mass_value
                #print(f"  Added custom modification to C-term: {custom_mass_value:+.4f} Da (subtotal: {mass:.4f} Da)")
            elif mod_type in mod_masses:
                mod_mass = mod_masses[mod_type]
                mass += mod_mass 
                mod_masses_applied += mod_mass
                #print(f"  Added {mod_type} modification to C-term: +{mod_mass:.4f} Da (subtotal: {mass:.4f} Da)")
        
        # Store base peptide mass (without modifications) for reporting
        base_mass = mass - mod_masses_applied
        total_mod_mass = mod_masses_applied
        final_mass = mass
        
        # # Detailed debugging output
        # if debug:
        #     # Print a detailed summary of all modifications applied
        #     print("\n=== DETAILED MODIFICATION SUMMARY ===")
        #     for i, aa in enumerate(peptide.upper()):
        #         pos_mods = []
        #         if i in modifications:
        #             mod_name = modifications[i]
        #             mod_mass = mod_masses.get(mod_name, 0)
        #             pos_mods.append(f"{mod_name} (+{mod_mass:.4f} Da)")
                
        #         mod_str = ", ".join(pos_mods) if pos_mods else "None"
        #         print(f"Position {i+1} [{aa}]: {mod_str}")
                
        #     # Print terminal modifications if any
        #     for term in ['N-term', 'C-term']:
        #         if term in modifications:
        #             mod_name = modifications[term]
        #             mod_mass = mod_masses.get(mod_name, 0)
        #             print(f"{term}: {mod_name} (+{mod_mass:.4f} Da)")
        #   # Cache the result with the comprehensive key
        self.PEPTIDE_MASSES[cache_key] = final_mass
        
        # # Always log calculation for problematic peptide
        # if peptide == "LCPDCPLLAPLNDSR":
        #     print(f"PEPTIDE CACHE MISS: Calculated new mass for {peptide}: {final_mass:.4f} Da")
        #     print(f"PEPTIDE CACHE: Stored with key {cache_key[:30]}...")
        
        # # Log mass summary for debugging
        # if debug:
        #     print("\n=== FINAL MASS CALCULATION ===")
        #     print(f"Base peptide mass (no modifications): {base_mass:.4f} Da")
        #     print(f"Total modification mass: {total_mod_mass:.4f} Da")
        #     print(f"Final peptide mass: {final_mass:.4f} Da")
            
        #     # Show cache entry created
        #     print(f"Cache entry created: {cache_key} -> {final_mass:.4f} Da")
        
        return final_mass

    def print_mass_debug_info(self, peptide, glycan_code, peptide_mass, glycan_base_mass, modified_mass, modified_mass_for_search):
        """
        Print debug information about mass calculations for a glycopeptide.
        
        Parameters:
        ----------
        peptide : str
            Peptide sequence
        glycan_code : str
            Glycan composition code
        peptide_mass : float
            Calculated peptide mass
        glycan_base_mass : float
            Calculated glycan mass
        modified_mass : float
            Total modified mass (peptide + glycan - water)
        modified_mass_for_search : float
            Modified mass used for database searching
        """
        print("\n=== Mass Calculation Details ===")
        print(f"Peptide: {peptide}")
        print(f"Glycan: {glycan_code}")
        print(f"Peptide mass: {peptide_mass:.4f} Da")
        print(f"Glycan mass: {glycan_base_mass:.4f} Da")
        print(f"Combined mass: {modified_mass:.4f} Da")
        print(f"Search mass: {modified_mass_for_search:.4f} Da")
        
        # Print m/z values for common charge states
        print("\nCalculated m/z values:")
        for charge in range(1, 6):
            mz = (modified_mass_for_search + charge * 1.00727) / charge
            print(f"  z={charge}: {mz:.4f} m/z")
        print("===========================\n")

    def reset_calculator_state(self):
        """Reset calculator state between calculations to prevent memory carryover"""
        # Clear peptide mass cache
        if hasattr(self, 'PEPTIDE_MASSES'):
            self.PEPTIDE_MASSES.clear()
        
        # Clear applied modifications
        if hasattr(self, 'applied_mods'):
            self.applied_mods.clear()
        
        # Reset modification parameters to defaults
        self.use_cam = True
        self.fixed_mods = []
        self.variable_mods = []
        self.mod_string = None
        self.peptide = None
        
        print("Calculator state reset for next calculation")

    @lru_cache(maxsize=1024)
    def _calculate_base_fragment_mass(self, composition_tuple):
        """Calculate base Fragment_mz with caching for frequently used compositions"""
        composition = dict(composition_tuple)  # Convert back to dict
        base_mass = 0
        for mono in ['HexNAc', 'Hex', 'Fuc', 'NeuAc', 'NeuGc']:
            if mono in composition:
                base_mass += self.MONO_MASSES[mono] * composition[mono]
        return base_mass    
    
    def calculate_fragment_mass(self, composition, fragment_type, peptide=None, debug=False):
        # Add debugging at beginning of function
        # print(f"\n=== DEBUG: calculate_fragment_mass ===")
        # print(f"Fragment type: {fragment_type}")
        # print(f"Peptide: {peptide}")
        # print(f"use_cam setting: {self.use_cam}")
        # print(f"fixed_mods: {self.fixed_mods}")
        
        # Get the peptide mass with explicit use_cam parameter
        peptide_mass = self.calculate_peptide_mass(
            peptide, 
            use_cam=self.use_cam,
            fixed_mods=self.fixed_mods,
            variable_mods=self.variable_mods,
            mod_string=self.mod_string,
            debug=True  # Force debug mode to see calculation details
        )
        #print(f"Calculated peptide mass: {peptide_mass}")
        
        # STAGE 1: INITIALIZATION AND INPUT VALIDATION
        # if debug:
        #     print(f"\n==== Fragment_mz CALCULATION: START ====")
        #     print(f"Input composition: {composition}")
        #     print(f"Fragment type: {fragment_type}")
        
        # Use self.peptide if peptide parameter is None
        peptide = peptide or self.peptide
        # if debug:
        #     print(f"Peptide: {peptide}")
        #     print(f"Modification type: {self.modification_type}")
        #     print(f"Use CAM: {self.use_cam}")
        #     print(f"Fixed mods: {self.fixed_mods}")

        # Convert composition to hashable tuple for caching
        comp_tuple = tuple(sorted((k, v) for k, v in composition.items() if not k.startswith('_')))
        
        # STAGE 2: BASE GLYCAN MASS CALCULATION
        # Get base mass with caching
        base_mass = self._calculate_base_fragment_mass(comp_tuple)
        # if debug:
        #     print(f"STAGE 2: Base glycan mass calculation")
        #     print(f"  Base glycan mass: {base_mass:.4f} Da")
        #     print(f"  Composition tuple: {comp_tuple}")
        
        original_base_mass = base_mass
        
        # Special case: Check for _glycan_only flag
        is_glycan_only = '_glycan_only' in composition and composition['_glycan_only']
        
        # Special case: Handle custom mass adjustment
        if '_mass_adjustment' in composition:
            mass_adjustment = composition['_mass_adjustment']
            base_mass += mass_adjustment
            # if debug:
            #     print(f"  Applied custom mass adjustment: {mass_adjustment:.4f} Da")
            #     print(f"  Mass after adjustment: {base_mass:.4f} Da")
        
        # STAGE 3: Y/YY ION MASS ADJUSTMENTS
        # if debug:
        #     print(f"STAGE 3: Y/YY ion mass adjustments")
        #     print(f"  Processing for fragment type: {fragment_type}")
        #     print(f"  Glycan-only flag: {is_glycan_only}")
        #     print(f"  Original base mass before adjustment: {original_base_mass:.4f} Da")

        if is_glycan_only:
            # For glycan-only fragments, add reducing end mass but don't add peptide
            base_mass += self.REDUCING_END_MASSES[self.modification_type]
            # if debug:
            #     print(f"  Glycan-only fragment detected, applying reducing end mass only.")
            #     print(f"  Added reducing end mass: {self.REDUCING_END_MASSES[self.modification_type]:.4f}")
            #     print(f"  Base mass after adjustment: {base_mass:.4f} Da")
        
        # Handle reducing end for Y and YY ions
        elif fragment_type in ['y_ions', 'yy_ions']:
            # if debug:
            #     print(f"  Y/YY ion detected - processing special rules")
                    
            # Check if we're in glycopeptide mode AND have a valid peptide
            if self.modification_type == 6:
                if peptide and not is_glycan_only:  # Only add peptide if not glycan-only
                    # Calculate peptide mass with modifications
                    cache_key = self._create_peptide_cache_key(
                        peptide, 
                        use_cam=self.use_cam,
                        fixed_mods=self.fixed_mods,
                        variable_mods=self.variable_mods,
                        mod_string=self.mod_string
                    )
                    
                    if cache_key in self.PEPTIDE_MASSES:
                        peptide_mass = self.PEPTIDE_MASSES[cache_key]
                        #if debug:
                            #print(f"  Found peptide mass in cache: {peptide_mass:.4f} Da")
                    else:
                        peptide_mass = self.calculate_peptide_mass(
                            peptide,
                            use_cam=self.use_cam,
                            fixed_mods=self.fixed_mods,
                            variable_mods=self.variable_mods,
                            mod_string=self.mod_string
                        )
                        #if debug:
                            #print(f"  Calculated peptide mass: {peptide_mass:.4f} Da")
                    
                    # Add peptide mass to base mass
                    base_mass += peptide_mass
                    # if debug:
                    #     print(f"  Added peptide mass: {peptide_mass:.4f} Da")
                    #     print(f"  Mass after adding peptide: {base_mass:.4f} Da")
                else:
                    # No peptide provided, add basic peptide end mass
                    base_mass += self.REDUCING_END_MASSES[self.modification_type]
                    # if debug:
                    #     print(f"  No peptide provided or glycan-only flag set, adding reducing end mass: {self.REDUCING_END_MASSES[self.modification_type]:.4f} Da")
                    #     print(f"  Mass after adding reducing end: {base_mass:.4f} Da")
            
        # STAGE 5: FINAL MASS CALCULATION
        # if debug:
        #     print(f"STAGE 5: Final Fragment_mz calculation complete")
        #     print(f"  Original base mass: {original_base_mass:.4f} Da")
        #     print(f"  Final Fragment_mz: {base_mass:.4f} Da")
        #     print(f"  Delta (adjustments): {base_mass - original_base_mass:.4f} Da")
        #     print(f"==== Fragment_mz CALCULATION: END ====\n")
        
        return base_mass   

    def _create_peptide_cache_key(self, peptide, use_cam=None, fixed_mods=None, variable_mods=None, mod_string=None):
        """Create a unique cache key for peptide mass calculations.
        
        Args:
            peptide (str): Peptide sequence
            use_cam (bool): Whether to use carbamidomethylation for cysteines
            fixed_mods (list): List of fixed modifications
            variable_mods (list): List of variable modifications
            mod_string (str): String representation of modifications
            
        Returns:
            tuple: A hashable tuple to use as cache key
        """
        # Use the provided parameters, or fall back to instance attributes
        use_cam = use_cam if use_cam is not None else self.use_cam
        fixed_mods = fixed_mods or self.fixed_mods or []
        variable_mods = variable_mods or self.variable_mods or []
        mod_string = mod_string or self.mod_string
        peptide = str(peptide or "")  # Ensure peptide is a string
        
        # Create tuple components for the key
        key_parts = [
            peptide,
            bool(use_cam),
            tuple(sorted(fixed_mods)) if fixed_mods else (),
            tuple(sorted(variable_mods)) if variable_mods else (),
            str(mod_string) if mod_string else ""
        ]
        
        return tuple(key_parts)

def create_comprehensive_peptide_cache_key(peptide, use_cam=True, fixed_mods=None, variable_mods=None, mod_string=None):
    """
    Create a comprehensive cache key that includes ALL modification information
    """
    fixed_mods = fixed_mods or []
    variable_mods = variable_mods or []
      
    # Ensure peptide is a string, not None
    peptide = str(peptide or "")
    
    # Sort modifications to ensure consistent keys
    fixed_sorted = sorted([str(mod) for mod in fixed_mods])
    var_sorted = sorted([str(mod) for mod in variable_mods])
    
    # Build key components
    components = [peptide]
    
    # Always include CAM status in the key whether True or False
    components.append(f"cam:{use_cam}")
    
    if fixed_sorted:
        components.append("fixed:" + ",".join(fixed_sorted))
    
    if var_sorted:
        components.append("var:" + ",".join(var_sorted))
    
    # Add mod_string with full detail to ensure different custom mass mods get different keys
    if mod_string:
        components.append("mod:" + mod_string)
    
    # Join with double pipe as separator
    return "||".join(components)

def create_comprehensive_fragment_cache_key(glycan_code, peptide, modification_type=6, use_cam=False, fixed_mods=None, variable_mods=None, mod_string=None, glycan_type=None):
    """
    Create a comprehensive cache key for fragment tables that includes ALL parameters affecting fragment generation
    
    Args:
        glycan_code: The glycan code
        peptide: The peptide sequence
        modification_type: Type of modification (e.g., 6 for glycopeptide)
        use_cam: Whether carbamidomethylation is enabled
        fixed_mods: List of fixed modifications
        variable_mods: List of variable modifications
        mod_string: Excel-provided modification string
        glycan_type: Type of glycan (N or O)
        
    Returns:
        A comprehensive cache key string that uniquely identifies all parameters
    """
    fixed_mods = fixed_mods or []
    variable_mods = variable_mods or []
      # Sort modifications to ensure consistent keys
    fixed_sorted = sorted([str(mod) for mod in fixed_mods])
    var_sorted = sorted([str(mod) for mod in variable_mods])
      # Build key components
    components = [str(glycan_code), peptide or ""]
    
    # Add modification type
    components.append(f"mod_type:{modification_type}")
    
    # Add glycan type if available
    if glycan_type:
        components.append(f"glycan_type:{glycan_type}")
    
    # Always include CAM status in the key whether True or False
    components.append(f"cam:{use_cam}")
    
    if fixed_sorted:
        components.append("fixed:" + ",".join(fixed_sorted))
    
    if var_sorted:
        components.append("var:" + ",".join(var_sorted))
    
    if mod_string:
        components.append("mod:" + mod_string)
    
    # Join with double pipe as separator
    return "||".join(components)

def create_peptide_cache_key(peptide, mod_string=None, fixed_mods=None, variable_mods=None, use_cam=True, calculator=None):
        """
        Create a unique cache key for a peptide that includes its modifications.
        This function has been updated to match create_comprehensive_peptide_cache_key
        to ensure consistent cache lookups.
        
        Args:
            peptide: The peptide sequence
            mod_string: Excel-provided modification string
            fixed_mods: List of fixed modifications
            variable_mods: List of variable modifications
            use_cam: Whether carbamidomethylation is enabled
            calculator: GlycanMassCalculator instance to access PEPTIDE_MASSES
            
        Returns:
            A unique string key that identifies this peptide with its specific modifications
        """
        # Simply forward to create_comprehensive_peptide_cache_key to ensure consistency
        # This ensures both functions generate identical keys for the same inputs
        return create_comprehensive_peptide_cache_key(
            peptide, 
            use_cam=use_cam,
            fixed_mods=fixed_mods, 
            variable_mods=variable_mods, 
            mod_string=mod_string
        )

def parse_modification_string(mod_string):
    """
    Parse a modification string in the format "ModName:Position" or "(+15.01):D4"
    
    Args:
        mod_string: String in format "ModName:Position", "(+mass):Position", or multiple mods separated by semicolons
    
    Returns:
        List of tuples of (modification name/mass, position)
    """
    if not mod_string or pd.isna(mod_string):
        return []
        
    mod_string = str(mod_string).strip()
    result = []
    
    # Split multiple modifications (separated by semicolons)
    for mod_part in mod_string.split(';'):
        mod_part = mod_part.strip()
        if not mod_part:
            continue
            
        if ':' in mod_part:
            parts = mod_part.split(':', 1)
            mod_name, position = parts
            mod_name = mod_name.strip()
            position = position.strip()
            
            # Handle special terminus indicators
            if position.lower() in ['n-term', 'nterm', 'n']:
                position = 'N-term'
            elif position.lower() in ['c-term', 'cterm', 'c']:
                position = 'C-term'
            # Handle combined amino acid + position format like 'M6'
            elif len(position) > 1 and position[0].isalpha() and position[1:].isdigit():
                # Extract the position number, keeping the amino acid letter for verification
                amino_acid = position[0]
                position_num = position[1:]
                position = f"{amino_acid}{position_num}"  # Keep the format as "D4"
            # If position is a number, convert to int
            elif position.isdigit():
                position = int(position)
                
            result.append((mod_name, position))
    
    return result

def parse_custom_mass_mod(mod_string):
    """
    Parse a custom mass modification in the format "(+15.01)" or "(-2.1)"
    
    Args:
        mod_string: String containing a custom mass modification
    
    Returns:
        Float value of the modification mass, or None if not a custom mass
    """
    if not mod_string:
        return None
        
    # Check if the string is enclosed in parentheses and contains a sign
    if mod_string.startswith('(') and mod_string.endswith(')') and ('+' in mod_string or '-' in mod_string):
        # Extract the mass value
        try:
            # Remove parentheses and convert to float
            mass_str = mod_string[1:-1].strip()
            return float(mass_str)
        except ValueError:
            print(f"Warning: Could not parse custom mass modification: {mod_string}")
            return None
    
    return None

class Glycan:
    def __init__(self, code, glycan_type="N", max_structures=100):
        # Add max_structures parameter and store it
        self._max_structures = max_structures
        
        # Create a calculator object to use its parse_glycan_code method
        calculator = GlycanMassCalculator()
        
        # Use the existing method to parse the glycan code
        self.hexnac_total, self.hex_total, self.fuc_total, self.neuac_total, neuGc = calculator.parse_glycan_code(code)
        
        # Initialize tracking variables for iteration limiting
        self._iteration_count = 0
        self._last_log_time = time.time()  # Add this line to initialize the time tracking
        
        self.glycan_type = glycan_type.upper()  # Store glycan type (N or O)
        
        # Set core values based on glycan type
        if self.glycan_type == "O":
            self.core_hexnac = 1  # O-glycan starts with one HexNAc
            self.core_hex = 0     # Will be determined by core type
        else:  # Default to N-glycan
            self.core_hexnac = 2
            self.core_hex = 3
            
        self.remaining_hexnac = self.hexnac_total - self.core_hexnac
        self.remaining_hex = self.hex_total - self.core_hex
        self.remaining_fuc = self.fuc_total
        self.remaining_neuac = self.neuac_total
        self.possible_structures = []
        self.structure_fingerprints = set()
    
     # First implementation of _build_complete_o_glycan_structures removed

    def _build_n_glycan_core(self):
        """Build the N-glycan core structure: HexNAc2Hex3"""
        # Existing N-glycan core building code
        G = nx.DiGraph()
        
        # Add core structure (bottom to top)
        # First HexNAc (reducing end)
        G.add_node(1, type='HexNAc', position='core_reducing', label='HexNAc')
        
        # Second HexNAc
        G.add_node(2, type='HexNAc', position='core', label='HexNAc')
        G.add_edge(1, 2)
        
        # First branching Hex (central mannose)
        G.add_node(3, type='Hex', position='core_central', label='Hex')
        G.add_edge(2, 3)
        
        # Left and right core Hex (alpha 3 and alpha 6 mannose)
        G.add_node(4, type='Hex', position='core_branch', label='Hex')
        G.add_node(5, type='Hex', position='core_branch', label='Hex')
        G.add_edge(3, 4)
        G.add_edge(3, 5)
        
        return G
    
    def _build_o_glycan_core(self):
        """Build the core structures for O-glycans"""
        core_structures = []
        
        # Core 1: HexNAc-Hex (GalNAc-Gal)
        if self.hex_total >= 1 and self.hexnac_total >= 1:  # FIXED: Added HexNAc requirement
            G1 = nx.DiGraph()
            G1.add_node(1, type='HexNAc', position='core_reducing', label='HexNAc')
            G1.add_node(2, type='Hex', position='core', label='Hex')
            G1.add_edge(1, 2)
            core_structures.append({
                'graph': G1,
                'core_hexnac': 1,
                'core_hex': 1,
                'remaining_hexnac': self.hexnac_total - 1,
                'remaining_hex': self.hex_total - 1
            })
        
        # Core 2: HexNAc with two branching HexNAc
        if self.hexnac_total >= 3:
            G2 = nx.DiGraph()
            G2.add_node(1, type='HexNAc', position='core_reducing', label='HexNAc')
            G2.add_node(2, type='HexNAc', position='core_branch', label='HexNAc')
            G2.add_node(3, type='HexNAc', position='core_branch', label='HexNAc')
            G2.add_edge(1, 2)
            G2.add_edge(1, 3)
            core_structures.append({
                'graph': G2,
                'core_hexnac': 3,
                'core_hex': 0,
                'remaining_hexnac': self.hexnac_total - 3,
                'remaining_hex': self.hex_total
            })
        
        # Core 3: HexNAc with single branching HexNAc
        if self.hexnac_total >= 2:
            G3 = nx.DiGraph()
            G3.add_node(1, type='HexNAc', position='core_reducing', label='HexNAc')
            G3.add_node(2, type='HexNAc', position='core_branch', label='HexNAc')
            G3.add_edge(1, 2)
            core_structures.append({
                'graph': G3,
                'core_hexnac': 2,
                'core_hex': 0,
                'remaining_hexnac': self.hexnac_total - 2,
                'remaining_hex': self.hex_total
            })
        
        # NEW: Core for single Hex (e.g., Galactose alone)
        if self.hex_total >= 1:
            G_hex = nx.DiGraph()
            G_hex.add_node(1, type='Hex', position='core_reducing', label='Hex')
            core_structures.append({
                'graph': G_hex,
                'core_hexnac': 0,
                'core_hex': 1,
                'remaining_hexnac': self.hexnac_total,
                'remaining_hex': self.hex_total - 1
            })
            print(f"Added single Hex core structure")
        
        # Core 0: Single HexNAc (Tn antigen)
        if self.hexnac_total >= 1:
            G0 = nx.DiGraph()
            G0.add_node(1, type='HexNAc', position='core_reducing', label='HexNAc')
            core_structures.append({
                'graph': G0,
                'core_hexnac': 1,
                'core_hex': 0, 
                'remaining_hexnac': self.hexnac_total - 1,
                'remaining_hex': self.hex_total
            })
            print(f"Added single HexNAc core structure")
        
        return core_structures

    def predict_structures(self):
        """Generate all possible complete structures for the given glycan code"""
        print(f"\n{self.glycan_type}-Glycan Structure Prediction Strategy:")
        print(f"Limiting prediction to maximum {self._max_structures} structures")
        print("-------------------------------------")
    
        self.structure_fingerprints.clear()
        self.possible_structures.clear()
        
        # Special case handling for simple O-glycans
        if self.glycan_type == "O":
            # Special case for HexNAc (Tn antigen) - glycan code 1000
            if self.hexnac_total == 1 and self.hex_total == 0 and self.fuc_total == 0 and self.neuac_total == 0:
                print("Special case: Simple HexNAc (Tn antigen)")
                G = nx.DiGraph()
                G.add_node(1, type='HexNAc', position='core_reducing', label='HexNAc')
                self.possible_structures.append(G)
                print("Generated 1 fixed structure for HexNAc (1000)")
                return self.possible_structures
                
            # Special case for HexNAc-Hex (T antigen) - glycan code 1100
            if self.hexnac_total == 1 and self.hex_total == 1 and self.fuc_total == 0 and self.neuac_total == 0:
                print("Special case: Simple HexNAc-Hex (T antigen)")
                G = nx.DiGraph()
                G.add_node(1, type='HexNAc', position='core_reducing', label='HexNAc')
                G.add_node(2, type='Hex', position='core', label='Hex')
                G.add_edge(1, 2)
                self.possible_structures.append(G)
                print("Generated 1 fixed structure for HexNAc-Hex (1100)")
                return self.possible_structures
          # Continue with normal structure prediction for other cases
        if self.glycan_type == "O":
            # O-glycan specific path
            core_graphs = self._build_o_glycan_core()
            print(f"Core graphs generated: {len(core_graphs)}")
            
            for i, core_data in enumerate(core_graphs):
                print(f"Processing core {i+1}")
                core_graph = core_data['graph']
                self.remaining_hexnac = core_data['remaining_hexnac']
                self.remaining_hex = core_data['remaining_hex']
                self.remaining_neuac = self.neuac_total  # Ensure all sugars are set correctly
                self.remaining_fuc = self.fuc_total
                
                # Only proceed if we can build a valid structure with this core
                if self.remaining_hexnac >= 0 and self.remaining_hex >= 0:
                    # Debug info about available sugars
                    print(f"Starting with: HexNAc={self.remaining_hexnac}, Hex={self.remaining_hex}, NeuAc={self.remaining_neuac}, Fuc={self.remaining_fuc}")
                    
                    # Build complete structures recursively - only save when ALL sugars are used
                    self._build_complete_o_glycan_structures(copy.deepcopy(core_graph), list(core_graph.nodes()))
                    print(f"Structures after core {i+1}: {len(self.possible_structures)}")
        else:
            # Original N-glycan logic - COMPLETELY PRESERVED
            core_graph = self._build_n_glycan_core()
            self._build_structures(core_graph, [4, 5])
        
        if len(self.possible_structures) >= self._max_structures:
            print(f"Reached maximum limit of {self._max_structures} structures. Prediction stopped early.")
        print(f"Total unique structures generated: {len(self.possible_structures)}")
        return self.possible_structures

    def _count_node_types(self, graph):
        """Count nodes by type for debugging"""
        counts = {'HexNAc': 0, 'Hex': 0, 'NeuAc': 0, 'Fuc': 0}
        for node in graph.nodes():
            node_type = graph.nodes[node]['type']
            if node_type in counts:
                counts[node_type] += 1
        return counts

    def _build_complete_o_glycan_structures(self, graph, available_nodes):
        """Build complete O-glycan structures using all remaining sugars"""
        # Add iteration counting and progress reporting
        self._iteration_count += 1
        
        # Log progress every 1000 iterations or 3 seconds, whichever comes first
        current_time = time.time()
        if self._iteration_count % 20 == 0 or (current_time - self._last_log_time) > 3:
            print(f"Processing glycan {self.hexnac_total}{self.hex_total}{self.fuc_total}{self.neuac_total}: "
                  #f"Iteration {self._iteration_count}, "
                  f"Structures found: {len(self.possible_structures)}, "
                  f"Remaining: HexNAc={self.remaining_hexnac}, Hex={self.remaining_hex}, "
                  f"Fuc={self.remaining_fuc}, NeuAc={self.remaining_neuac}")
            self._last_log_time = current_time
            
        # Add safety check to prevent excessive recursion
        if self._iteration_count > 200:
            #print("WARNING: Exceeded 200 iterations, stopping to prevent excessive processing.")
            return
    
        # Only save structures when all sugars are used
        if (self.remaining_hexnac == 0 and 
            self.remaining_hex == 0 and 
            self.remaining_fuc == 0 and 
            self.remaining_neuac == 0):
            fingerprint = self._structure_fingerprint(graph)
            if fingerprint not in self.structure_fingerprints:
                self.structure_fingerprints.add(fingerprint)
                self.possible_structures.append(copy.deepcopy(graph))
            return
        
        # Find valid attachment points (nodes with fewer than 2 branches)
        # IMPORTANT NEW CONSTRAINT: NeuAc and Fuc can only be terminal
        valid_parents = []
        for n in graph.nodes():
            # Only consider nodes with fewer than 2 branches
            if graph.out_degree(n) < 2:
                node_type = graph.nodes[n]['type']
                # Enforce NeuAc can only connect to another NeuAc, and Fuc must be terminal
                if node_type == 'NeuAc' and self.remaining_neuac > 0:
                    # NeuAc can only connect to another NeuAc
                    valid_parents.append(n)
                elif node_type == 'Fuc':
                    # Fuc must be terminal - cannot attach anything to it
                    continue
                else:
                    # HexNAc and Hex can connect to anything
                    valid_parents.append(n)
        
        # Try attaching each remaining sugar type to every valid position
        if self.remaining_hexnac > 0:
            for parent in valid_parents:
                # Skip NeuAc parents unless attaching to another NeuAc
                if graph.nodes[parent]['type'] == 'NeuAc':
                    continue
                    
                new_graph = copy.deepcopy(graph)
                new_node_id = max(new_graph.nodes()) + 1
                new_graph.add_node(new_node_id, type='HexNAc', position='branch', label='HexNAc')
                new_graph.add_edge(parent, new_node_id)
                new_available = available_nodes + [new_node_id]
                self.remaining_hexnac -= 1
                self._build_complete_o_glycan_structures(new_graph, new_available)
                self.remaining_hexnac += 1
                
        if self.remaining_hex > 0:
            for parent in valid_parents:
                # Skip NeuAc and Fuc parents for Hex attachments
                if graph.nodes[parent]['type'] in ['NeuAc', 'Fuc']:
                    continue
                    
                new_graph = copy.deepcopy(graph)
                new_node_id = max(new_graph.nodes()) + 1
                new_graph.add_node(new_node_id, type='Hex', position='branch', label='Hex')
                new_graph.add_edge(parent, new_node_id)
                new_available = available_nodes + [new_node_id]
                self.remaining_hex -= 1
                self._build_complete_o_glycan_structures(new_graph, new_available)
                self.remaining_hex += 1
                
        if self.remaining_neuac > 0:
            for parent in valid_parents:
                # NeuAc can attach to anything EXCEPT Fuc
                if graph.nodes[parent]['type'] == 'Fuc':
                    continue
                    
                new_graph = copy.deepcopy(graph)
                new_node_id = max(new_graph.nodes()) + 1
                new_graph.add_node(new_node_id, type='NeuAc', position='terminal', label='NeuAc')
                new_graph.add_edge(parent, new_node_id)
                new_available = available_nodes + [new_node_id]
                self.remaining_neuac -= 1
                self._build_complete_o_glycan_structures(new_graph, new_available)
                self.remaining_neuac += 1
                
        if self.remaining_fuc > 0:
            for parent in valid_parents:
                # Fuc cannot attach to NeuAc or another Fuc
                if graph.nodes[parent]['type'] in ['NeuAc', 'Fuc']:
                    continue
                    
                new_graph = copy.deepcopy(graph)
                new_node_id = max(new_graph.nodes()) + 1
                new_graph.add_node(new_node_id, type='Fuc', position='terminal', label='Fuc')
                new_graph.add_edge(parent, new_node_id)
                new_available = available_nodes + [new_node_id]
                self.remaining_fuc -= 1
                self._build_complete_o_glycan_structures(new_graph, new_available)
                self.remaining_fuc += 1

    def _build_structures(self, graph, available_nodes, node_id=6, build_stage=0):
            # Check if we've reached the maximum structures
            if len(self.possible_structures) >= self._max_structures:
                return

            if (self.remaining_hexnac == 0 and 
                self.remaining_hex == 0 and 
                self.remaining_fuc == 0 and 
                self.remaining_neuac == 0):
                fingerprint = self._structure_fingerprint(graph)
                if fingerprint not in self.structure_fingerprints:
                    self.structure_fingerprints.add(fingerprint)
                    self.possible_structures.append(copy.deepcopy(graph))
                return
            
            # Stage 0: Add all HexNAc to core Hex (4 and 5)
            if build_stage == 0 and self.remaining_hexnac > 0:
                core_hex_info = [(n, sum(1 for succ in graph.successors(n) 
                                    if graph.nodes[succ]['type'] == 'HexNAc')) 
                            for n in [4, 5]]
                max_hexnac_per_core = 1 if (self.hexnac_total - 2 < 3) else 3  # Corrected condition
                core_hex_info = [(n, c) for n, c in core_hex_info if c < max_hexnac_per_core]
                core_hex_info.sort(key=lambda x: x[1])
                
                if core_hex_info:
                    for parent, _ in core_hex_info:
                        new_graph = copy.deepcopy(graph)
                        new_graph.add_node(node_id, type='HexNAc', position='branch', label='HexNAc')
                        new_graph.add_edge(parent, node_id)
                        new_available = available_nodes.copy()
                        if parent in new_available:
                            new_available.remove(parent)
                        new_available.append(node_id)
                        self.remaining_hexnac -= 1
                        self._build_structures(new_graph, new_available, node_id + 1, 0)  # Stay in Stage 0
                        self.remaining_hexnac += 1
                else:
                    if self.remaining_hexnac == 0:  # Only move to Stage 1 if all HexNAc placed
                        self._build_structures(graph, available_nodes, node_id, 1)
            elif build_stage == 0:
                if self.remaining_hexnac == 0:
                    self._build_structures(graph, available_nodes, node_id, 1)

            # Stage 1: Add all Hex
            elif build_stage == 1 and self.remaining_hex > 0:
                    
                if self.hexnac_total == 2:  
                    # High mannose
                    available_hex = [n for n in graph.nodes() 
                                if graph.nodes[n]['type'] == 'Hex' and
                                    n != 3 and
                                    graph.out_degree(n) < 2]
                    if available_hex:
                        for parent in sorted(available_hex):
                            new_graph = copy.deepcopy(graph)
                            new_graph.add_node(node_id, type='Hex', position='branch', label='Hex')
                            new_graph.add_edge(parent, node_id)
                            new_available = available_nodes.copy()
                            new_available.append(node_id)
                            self.remaining_hex -= 1
                            self._build_structures(new_graph, new_available, node_id + 1, 1)
                            self.remaining_hex += 1
                    else:
                        self._build_structures(graph, available_nodes, node_id, 2)
                elif self.hexnac_total == 3 or (self.hex_total - self.hexnac_total > 1):   
                    # Hybrid
                    branch_hexnac = [n for n in graph.nodes() 
                                if graph.nodes[n]['type'] == 'HexNAc' and 
                                    graph.nodes[n]['position'] == 'branch' and
                                    not any(graph.nodes[succ]['type'] == 'Hex' 
                                            for succ in graph.successors(n))]
                    core_hex = [n for n in graph.nodes() 
                            if graph.nodes[n]['type'] == 'Hex' and 
                                n != 3 and 
                                graph.out_degree(n) < 2 and
                                not any(graph.nodes[succ]['type'] == 'HexNAc' 
                                        for succ in graph.successors(n))]
                    all_targets = sorted(core_hex + branch_hexnac, key=lambda x: (graph.nodes[x]['position'], x))
                    if all_targets:
                        for parent in all_targets:
                            new_graph = copy.deepcopy(graph)
                            new_graph.add_node(node_id, type='Hex', position='branch', label='Hex')
                            new_graph.add_edge(parent, node_id)
                            new_available = available_nodes.copy()
                            new_available.append(node_id)
                            self.remaining_hex -= 1
                            self._build_structures(new_graph, new_available, node_id + 1, 1)
                            self.remaining_hex += 1
                    else:
                        self._build_structures(graph, available_nodes, node_id, 2)
                else:  
                    # Complex (HexNAc > 3)
                    branch_hexnac = [n for n in graph.nodes() 
                                if graph.nodes[n]['type'] == 'HexNAc' and 
                                    graph.nodes[n]['position'] == 'branch' and
                                    not any(graph.nodes[succ]['type'] == 'Hex' 
                                            for succ in graph.successors(n))]
                    if branch_hexnac:
                        for parent in sorted(branch_hexnac):
                            new_graph = copy.deepcopy(graph)
                            new_graph.add_node(node_id, type='Hex', position='branch', label='Hex')
                            new_graph.add_edge(parent, node_id)
                            new_available = available_nodes.copy()
                            new_available.append(node_id)
                            self.remaining_hex -= 1
                            self._build_structures(new_graph, new_available, node_id + 1, 1)
                            self.remaining_hex += 1
                    else:
                        self._build_structures(graph, available_nodes, node_id, 2)
            elif build_stage == 1:
                self._build_structures(graph, available_nodes, node_id, 2)

            # Stage 2: Add NeuAc (modified to allow extra NeuAc on HexNAc when NeuAc > Hex - 3)
            elif build_stage == 2 and self.remaining_neuac > 0:
                branch_hexnac = [n for n in graph.nodes() 
                                if graph.nodes[n]['type'] == 'HexNAc' and 
                                graph.nodes[n]['position'] == 'branch']
                hex_with_hexnac_parent = [succ for hexnac in branch_hexnac 
                                        for succ in graph.successors(hexnac) 
                                        if graph.nodes[succ]['type'] == 'Hex' and 
                                            not any(graph.nodes[child]['type'] == 'NeuAc' 
                                                    for child in graph.successors(succ)) and
                                            not any(graph.nodes[child]['type'] == 'Hex' 
                                                    for child in graph.successors(succ))]
                
                if hex_with_hexnac_parent:
                    for parent in sorted(hex_with_hexnac_parent):
                        new_graph = copy.deepcopy(graph)
                        new_graph.add_node(node_id, type='NeuAc', position='terminal', label='NeuAc')
                        new_graph.add_edge(parent, node_id)
                        new_available = available_nodes.copy()
                        self.remaining_neuac -= 1
                        self._build_structures(new_graph, new_available, node_id + 1, 2)
                        self.remaining_neuac += 1
                else:
                    # Check if NeuAc > branch Hex (Hex - 3)
                    branch_hex_count = self.hex_total - 3  # Total Hex minus 3 core Hex
                    if self.neuac_total > branch_hex_count:
                        hexnac_without_neuac = [n for n in branch_hexnac 
                                            if not any(graph.nodes[succ]['type'] == 'NeuAc' 
                                                        for succ in graph.successors(n))]
                        if hexnac_without_neuac:
                            for parent in sorted(hexnac_without_neuac):
                                new_graph = copy.deepcopy(graph)
                                new_graph.add_node(node_id, type='NeuAc', position='terminal', label='NeuAc')
                                new_graph.add_edge(parent, node_id)
                                new_available = available_nodes.copy()
                                self.remaining_neuac -= 1
                                self._build_structures(new_graph, new_available, node_id + 1, 2)
                                self.remaining_neuac += 1
                    self._build_structures(graph, available_nodes, node_id, 3)
            elif build_stage == 2:
                self._build_structures(graph, available_nodes, node_id, 3)

            # Stage 3: Removed (all HexNAc placed in Stage 0)
            elif build_stage == 3:
                self._build_structures(graph, available_nodes, node_id, 4)

            # Stage 4: Add Fuc
            elif build_stage == 4 and self.remaining_fuc > 0:
                hexnac_nodes = [n for n in graph.nodes()
                            if graph.nodes[n]['type'] == 'HexNAc' and
                                (n == 1 or graph.nodes[n]['position'] == 'branch') and
                                n != 2 and
                                not any(graph.nodes[succ]['type'] == 'Fuc'
                                        for succ in graph.successors(n))]
                if hexnac_nodes:
                    for parent in sorted(hexnac_nodes):
                        new_graph = copy.deepcopy(graph)
                        new_graph.add_node(node_id, type='Fuc', position='terminal', label='Fuc')
                        new_graph.add_edge(parent, node_id)
                        new_available = available_nodes.copy()
                        self.remaining_fuc -= 1
                        self._build_structures(new_graph, new_available, node_id + 1, 4)
                        self.remaining_fuc += 1
                else:
                    if self.remaining_hexnac == 0 and self.remaining_hex == 0 and self.remaining_neuac == 0:
                        fingerprint = self._structure_fingerprint(graph)
                        if fingerprint not in self.structure_fingerprints:
                            self.structure_fingerprints.add(fingerprint)
                            self.possible_structures.append(copy.deepcopy(graph))
            elif build_stage == 4:
                if self.remaining_hexnac == 0 and self.remaining_hex == 0 and self.remaining_neuac == 0:
                    fingerprint = self._structure_fingerprint(graph)
                    if fingerprint not in self.structure_fingerprints:
                        self.structure_fingerprints.add(fingerprint)
                        self.possible_structures.append(copy.deepcopy(graph))

    def _create_structure_fingerprint(self, graph):
        """Create a basic structure fingerprint for a glycan graph (initial version)"""
        root = 1
        canonical_labels = {root: 0}
        next_label = 1
        queue = [root]
        visited = {root}
        
        while queue:
            node = queue.pop(0)
            children_by_type = {}
            for succ in graph.successors(node):
                node_type = graph.nodes[succ]['type']
                position = graph.nodes[succ]['position']
                if succ in [1, 2, 3, 4, 5]:
                    key = (node_type, position, succ)
                else:
                    key = (node_type, position)
                children_by_type.setdefault(key, []).append(succ)
            
            for key in sorted(children_by_type.keys()):
                children = children_by_type[key]
                children_with_subtree = [(child, self._get_subtree_hash(graph, child, visited)) 
                                    for child in children]
                children_with_subtree.sort(key=lambda x: x[1])
                for child, _ in children_with_subtree:
                    if child not in visited:
                        canonical_labels[child] = next_label
                        next_label += 1
                        queue.append(child)
                        visited.add(child)
        
        canonical_adj_list = []
        for orig_node, canon_label in sorted(canonical_labels.items(), key=lambda x: x[1]):
            node_type = graph.nodes[orig_node]['type']
            position = graph.nodes[orig_node].get('position', '')
            parent = list(graph.predecessors(orig_node))[0] if graph.in_degree(orig_node) > 0 else None
            parent_label = canonical_labels[parent] if parent else -1
            successors = sorted([canonical_labels[succ] for succ in graph.successors(orig_node)])
            # Include depth for linear chain distinction
            depth = nx.shortest_path_length(graph.to_undirected(), root, orig_node) if orig_node != root else 0
            canonical_adj_list.append((canon_label, node_type, position, parent_label, depth, tuple(successors)))
        
        return str(canonical_adj_list)

    def _get_subtree_hash(self, graph, node, already_visited):
        """Generate a hash for the subtree rooted at node"""
        if node in already_visited:
            return "visited"
        
        node_type = graph.nodes[node]['type']
        position = graph.nodes[node]['position']
        hash_parts = [f"{node_type}-{position}"]
        
        succ_by_type = {}
        for succ in graph.successors(node):
            succ_type = graph.nodes[succ]['type']
            succ_by_type.setdefault(succ_type, []).append(succ)
        
        for succ_type in sorted(succ_by_type.keys()):
            successors = succ_by_type[succ_type]
            sub_hashes = []
            for succ in successors:
                if succ not in already_visited:
                    already_visited.add(succ)
                    sub_hashes.append(self._get_subtree_hash(graph, succ, already_visited))
                    already_visited.remove(succ)
            sub_hashes.sort()  # Sort to ensure consistent ordering
            hash_parts.append(f"{succ_type}:{len(successors)}[{','.join(sub_hashes)}]")
        
        return "(" + "-".join(hash_parts) + ")"
    
    def _determine_structure_type(self):
        """Determine the likely structure type based on remaining sugars"""
        if self.hexnac_total == 2:
            return "High Mannose"
        elif self.hexnac_total == 3:
            return "Hybrid"
        else:
            return "Complex"
            
    def classify_structure(self, graph):
        """Classify the glycan structure based on composition and type"""
        if self.glycan_type == "O":
            # Determine O-glycan subtypes
            if self.hex_total == 0 and self.hexnac_total >= 2:
                return "O-GalNAc (Tn/STn)"
            elif self.hex_total >= 1 and self.hexnac_total >= 1:
                return "O-GalNAc-Gal (T/ST)"
            elif self.hexnac_total == 3 and self.hex_total == 0:
                return "O-GalNAc with HexNAc branches"
            else:
                return "Complex O-glycan"
        else:
            # Existing N-glycan classification
            if self.hexnac_total == 2:
                return "High Mannose"
            elif self.hexnac_total == 3:
                return "Hybrid"
            elif self.hexnac_total > 3:
                return "Complex"
            else:
                return "Unknown"

    def generate_fragments(self, graph, modification_type=6, use_cam=True, 
                        fixed_mods=None, variable_mods=None, mod_string=None, peptide=None):
        
        # NEW: Special handling for single monosaccharide O-glycans
        if self.glycan_type == "O":
            # Count total monosaccharides in the structure  
            total_monosaccharides = len([n for n in graph.nodes() if n != 1])  # Exclude reducing end
            
            # FIXED: Only apply special case for TRUE single monosaccharides (like HexNAc(1) or Hex(1))
            # NOT for multi-monosaccharide O-glycans like HexNAc(1)Fuc(1)
            if total_monosaccharides == 1:  # This should ONLY be for HexNAc(1) OR Hex(1) alone
                calculator = GlycanMassCalculator(
                    modification_type=modification_type, 
                    use_cam=use_cam,
                    fixed_mods=fixed_mods,
                    variable_mods=variable_mods,
                    mod_string=mod_string
                )
                
                # Get the monosaccharide composition
                counts = self._count_residues(graph)
                
                # ADDITIONAL CHECK: Ensure it's truly a single type of monosaccharide
                # Count how many different monosaccharide types are present
                monosac_types_present = sum(1 for mono in ['HexNAc', 'Hex', 'Fuc', 'NeuAc', 'NeuGc'] 
                                        if counts.get(mono, 0) > 0)
                
                if monosac_types_present == 1:  # ONLY if it's truly a single monosaccharide type
                    # Create the full glycopeptide fragment
                    fragments = {
                        'b_ions': [],
                        'y_ions': [counts],
                        'by_ions': [],
                        'yy_ions': []
                    }
                    
                    # Create cleavage info for the single fragment
                    cleavage_info = {
                        'b_ions': {},
                        'y_ions': {self._format_string(counts, 'y', has_reducing_end=True): 'full_glycopeptide'},
                        'by_ions': {},
                        'yy_ions': {}
                    }
                    
                    # Enhanced message to show which type was handled
                    monosac_type = 'HexNAc' if counts.get('HexNAc', 0) > 0 else 'Hex'
                    print(f"Generated single {monosac_type} O-glycan fragment: {self._format_string(counts, 'y', has_reducing_end=True)}")
                    return fragments, cleavage_info
                else:
                    print(f"Multi-monosaccharide O-glycan detected - proceeding with normal fragmentation")
        
        # Continue with existing fragmentation logic for complex structures INCLUDING HexNAc(1)Fuc(1)
        # Initialize fragments dictionary for complex O-glycans and N-glycans
        fragments = {
            'b_ions': [],
            'y_ions': [],
            'by_ions': [],
            'yy_ions': []
        }
        
        # Initialize cleavage_info dictionary
        cleavage_info = {
            'b_ions': {},
            'y_ions': {},
            'by_ions': {},
            'yy_ions': {}
        }
        
        # Get the reducing end node (node 1)
        reducing_end = 1
        
        # Sets for deduplication (using tuples of formatted strings and masses)
        unique_b_ions = set()
        unique_y_ions = set()
        unique_by_ions = set()
        unique_yy_ions = set()
        
        # Track fragments by their composition for cross-validation
        composition_registry = {
            'b': set(),
            'y': set(),
            'by': set(),
            'yy': set()
        }
        
        # Helper to get all edges in order (core first, then branches), excluding self-loops
        all_edges = [(u, v) for u, v in graph.edges() if u != v]
        all_edges.sort(key=lambda x: (x[0], x[1]))
        
        # B and Y ions: Single cleavages (core and branches)
        for edge in all_edges:
            u, v = edge
            temp_graph = copy.deepcopy(graph)
            temp_graph.remove_edge(u, v)
            
            components = list(nx.weakly_connected_components(temp_graph))
            for component in components:
                if reducing_end in component:
                    # This is a Y-ion (contains reducing end)
                    y_subgraph = temp_graph.subgraph(component).copy()
                    y_counts = self._count_residues(y_subgraph)
                    y_fragment = self._format_fragment(y_counts, has_reducing_end=True)
                    
                    if y_fragment and sum(y_fragment.values()) > 0:
                        y_string = self._format_string(y_fragment, 'y', has_reducing_end=True)
                        if y_string not in unique_y_ions:
                            unique_y_ions.add(y_string)
                            fragments['y_ions'].append(y_fragment)
                            cleavage_info['y_ions'][y_string] = f"Cleavage at {u}-{v}"
                            composition_registry['y'].add(tuple(sorted((k, v) for k, v in y_fragment.items())))
                else:
                    # This is a B-ion (does not contain reducing end)
                    b_subgraph = temp_graph.subgraph(component).copy()
                    b_counts = self._count_residues(b_subgraph)
                    b_fragment = self._format_fragment(b_counts, has_reducing_end=False)
                    
                    if b_fragment and sum(b_fragment.values()) > 0:
                        b_string = self._format_string(b_fragment, 'b', has_reducing_end=False)
                        if b_string not in unique_b_ions:
                            unique_b_ions.add(b_string)
                            fragments['b_ions'].append(b_fragment)
                            cleavage_info['b_ions'][b_string] = f"Cleavage at {u}-{v}"
                            composition_registry['b'].add(tuple(sorted((k, v) for k, v in b_fragment.items())))
        
        # Generate BY ions with improved logic
        # Identify path components for internal fragments
        structure_paths = self._identify_structure_paths(graph, reducing_end)
        
        # Only generate BY ions from nodes in the middle of paths (not terminal and not reducing end)
        for node in graph.nodes():
            # Skip reducing end and terminal nodes
            if node == reducing_end or graph.out_degree(node) == 0:
                continue
                
            node_type = graph.nodes[node]['type']
            # Only consider HexNAc and Hex internal nodes
            if node_type in ['HexNAc', 'Hex']:
                # Check if node is in a path > 2 nodes long (to ensure it's actually internal)
                is_internal = False
                for path in structure_paths:
                    if node in path and len(path) > 2 and path.index(node) > 0 and path.index(node) < len(path) - 1:
                        is_internal = True
                        break
                
                if is_internal:
                    # Create internal fragment by removing this node and its children
                    temp_graph = copy.deepcopy(graph)
                    # Remove all edges from this node to create BY fragment
                    for child in list(temp_graph.successors(node)):
                        temp_graph.remove_edge(node, child)
                    
                    # Find component with reducing end (this becomes the BY fragment)
                    components = list(nx.weakly_connected_components(temp_graph))
                    for component in components:
                        if reducing_end in component:
                            by_subgraph = temp_graph.subgraph(component).copy()
                            by_counts = self._count_residues(by_subgraph)
                            by_fragment = self._format_fragment(by_counts, has_reducing_end=True)
                            
                            if by_fragment and sum(by_fragment.values()) > 0:
                                by_string = self._format_string(by_fragment, 'by', has_reducing_end=True)
                                if by_string not in unique_by_ions:
                                    unique_by_ions.add(by_string)
                                    fragments['by_ions'].append(by_fragment)
                                    cleavage_info['by_ions'][by_string] = f"Internal cleavage at node {node}"
                                    composition_registry['by'].add(tuple(sorted((k, v) for k, v in by_fragment.items())))
                            break
        
        # Generate all legitimate BY ions from double cleavages
        edge_combinations = list(combinations(all_edges, 2))
        for edge1, edge2 in edge_combinations:
            u1, v1 = edge1
            u2, v2 = edge2
            
            # Skip if edges are the same or connected to the same node
            if edge1 == edge2 or v1 == v2 or u1 == u2:
                continue
                
            # Skip invalid terminal monosaccharide combinations
            if self._is_invalid_terminal_pair(graph, v1, v2):
                continue
                
            # Process this edge pair
            temp_graph = copy.deepcopy(graph)
            try:
                temp_graph.remove_edge(u1, v1)
                temp_graph.remove_edge(u2, v2)
                
                # Check component count - need at least 3 for BY ions
                components = list(nx.weakly_connected_components(temp_graph))
                if len(components) < 3:
                    continue
                    
                # Find reducing end component
                reducing_end_component = None
                for idx, component in enumerate(components):
                    if reducing_end in component:
                        reducing_end_component = idx
                        break
                
                if reducing_end_component is None:
                    continue
                    
                for idx, component in enumerate(components):
                    if idx != reducing_end_component:
                        # This is a potential BY ion (internal fragment)
                        by_subgraph = temp_graph.subgraph(component).copy()
                        
                        # Validate as internal fragment
                        if self._is_valid_internal_fragment(graph, component):
                            by_counts = self._count_residues(by_subgraph)
                            by_fragment = self._format_fragment(by_counts, has_reducing_end=False)
                            
                            if by_fragment and sum(by_fragment.values()) > 0:
                                by_string = self._format_string(by_fragment, 'by', has_reducing_end=False)
                                if by_string not in unique_by_ions:
                                    unique_by_ions.add(by_string)
                                    fragments['by_ions'].append(by_fragment)
                                    cleavage_info['by_ions'][by_string] = f"Double cleavage at {u1}-{v1} and {u2}-{v2}"
                                    composition_registry['by'].add(tuple(sorted((k, v) for k, v in by_fragment.items())))
            except nx.NetworkXError:
                pass
        
        # Generate YY ions with accurate structural validation
        # First get Fuc location - core or branch
        has_core_fuc = False
        has_branch_fuc = False
        for node in graph.nodes():
            if graph.nodes[node]['type'] == 'Fuc':
                parent = list(graph.predecessors(node))[0]  # Get Fuc parent
                if parent == 1:
                    has_core_fuc = True
                else:
                    has_branch_fuc = True
        
        # Generate YY ions with structure-specific validation
        for edge1, edge2 in edge_combinations:
            u1, v1 = edge1
            u2, v2 = edge2
            
            # Skip if edges are the same
            if edge1 == edge2:
                continue
            
            # Skip invalid edge combinations for YY ion generation
            if self._is_invalid_yy_combination(graph, edge1, edge2, has_core_fuc):
                continue
                
            # Process this edge pair
            temp_graph = copy.deepcopy(graph)
            try:
                temp_graph.remove_edge(u1, v1)
                temp_graph.remove_edge(u2, v2)
                
                components = list(nx.weakly_connected_components(temp_graph))
                
                # Find the component with the reducing end
                for component in components:
                    if reducing_end in component:
                        yy_subgraph = temp_graph.subgraph(component).copy()
                        yy_counts = self._count_residues(yy_subgraph)
                        yy_fragment = self._format_fragment(yy_counts, has_reducing_end=True)
                        
                        if yy_fragment and sum(yy_fragment.values()) > 0:
                            yy_string = self._format_string(yy_fragment, 'yy', has_reducing_end=True)
                            if yy_string not in unique_yy_ions:
                                unique_yy_ions.add(yy_string)
                                fragments['yy_ions'].append(yy_fragment)
                                cleavage_info['yy_ions'][yy_string] = f"Double cleavage at {u1}-{v1} and {u2}-{v2}"
                                composition_registry['yy'].add(tuple(sorted((k, v) for k, v in yy_fragment.items())))
                        break
            except nx.NetworkXError:
                pass
        
        # Generate YY ions specifically from core fucose cleavage
        self._generate_core_fucose_yy_ions(graph, fragments, cleavage_info, unique_yy_ions, composition_registry)
        
        # Generate specific core BY ions that might be missed
        self._generate_core_by_ions(graph, fragments, cleavage_info, unique_by_ions, composition_registry)

        # Ensure branch-specific Y-ions are captured
        self._generate_branch_specific_y_ions(graph, fragments, cleavage_info, unique_y_ions, composition_registry)

        # In the generate_fragments method, add after the other YY ion generation calls:
        if self.glycan_type == "O":
            self._generate_oglycan_yy_ions(graph, fragments, cleavage_info, unique_yy_ions, composition_registry)
            
        # Final validation: Remove duplicate fragments between b/by and y/yy types
        # Apply improved validation to correctly classify fragments
        fragments = self._validate_fragment_types(fragments, composition_registry)

        # Return both fragments and cleavage info
        return fragments, cleavage_info

    def _generate_oglycan_yy_ions(self, graph, fragments, cleavage_info, unique_yy_ions, composition_registry, modification_type=6, use_cam=True, 
                        fixed_mods=None, variable_mods=None, mod_string=None, peptide=None):
        """Generate YY ions specifically for O-glycans with different rules than N-glycans"""
        calculator = GlycanMassCalculator(
        modification_type=modification_type, 
        use_cam=use_cam,
        fixed_mods=fixed_mods,
        variable_mods=variable_mods,
        mod_string=mod_string
    )
        
        if self.glycan_type != "O":
            return  # Only run for O-glycans
            
        # Get all edges in the graph
        all_edges = [(u, v) for u, v in graph.edges() if u != v]
        
        # Find all valid pairs of edges for YY fragmentation
        for edge1, edge2 in combinations(all_edges, 2):
            u1, v1 = edge1
            u2, v2 = edge2
            
            # Skip if edges are the same
            if edge1 == edge2:
                continue
                
            # Process this edge pair
            temp_graph = copy.deepcopy(graph)
            try:
                temp_graph.remove_edge(u1, v1)
                temp_graph.remove_edge(u2, v2)
                
                # Find connected components
                components = list(nx.weakly_connected_components(temp_graph))
                
                # Find component with reducing end
                for component in components:
                    if 1 in component:
                        # Generate YY-ion from this component
                        yy_subgraph = temp_graph.subgraph(component).copy()
                        counts = self._count_residues(yy_subgraph)
                        
                        # Only consider if there's at least one monosaccharide
                        if sum(counts.values()) > 0:
                            fragment = self._format_fragment(counts, has_reducing_end=True)
                            
                            if isinstance(fragment, dict):
                                # For O-glycans, allow all YY ions
                                comp_key = tuple(sorted((k, v) for k, v in fragment.items()))
                                composition_registry['yy'].add(comp_key)
                                
                                fragment_str = self._format_string(fragment, 'yy', has_reducing_end=True)
                                fragment_mass = calculator.calculate_fragment_mass(fragment, 'yy_ions',peptide=peptide)
                                fragment_tuple = (fragment_str, fragment_mass)
                                
                                if fragment_tuple not in unique_yy_ions:
                                    unique_yy_ions.add(fragment_tuple)
                                    fragments['yy_ions'].append(fragment)
                                    cleavage_info['yy_ions'][fragment_str] = f"O-glycan YY: {u1}-{v1} and {u2}-{v2}"
                        break  # We found the reducing end component
                        
            except nx.NetworkXError:
                pass

    def _identify_structure_paths(self, graph, root):
        """Identify all paths from root to terminal nodes for internal fragment validation"""
        paths = []
        terminal_nodes = [n for n in graph.nodes() if graph.out_degree(n) == 0]
        
        for terminal in terminal_nodes:
            try:
                # Get path from root to terminal node
                path = nx.shortest_path(graph, root, terminal)
                paths.append(path)
                
                # Also track branching points for potential internal fragments
                for i in range(len(path) - 2):
                    # Check if this node is a branching point (has >1 successor)
                    node = path[i]
                    if graph.out_degree(node) > 1:
                        # For branching nodes, capture subpaths
                        for succ in graph.successors(node):
                            if succ in path:
                                continue  # Skip if already in path
                            try:
                                # Find paths from branch to terminals
                                branch_terminals = nx.descendants(graph, succ)
                                terminal_branch = [t for t in branch_terminals if graph.out_degree(t) == 0]
                                for tb in terminal_branch:
                                    branch_path = nx.shortest_path(graph, node, tb)
                                    # Add this branch path
                                    paths.append(branch_path)
                            except nx.NetworkXNoPath:
                                pass
            except nx.NetworkXNoPath:
                pass
        
        return paths
    
    def _is_invalid_terminal_pair(self, graph, node1, node2):
        """Check if a pair of nodes would create an invalid BY ion"""
        # Invalid if both are terminal Fuc or NeuAc nodes
        if graph.out_degree(node1) == 0 and graph.out_degree(node2) == 0:
            type1 = graph.nodes[node1]['type']
            type2 = graph.nodes[node2]['type']
            if type1 in ['Fuc', 'NeuAc'] and type2 in ['Fuc', 'NeuAc']:
                return True
        return False

    def _is_valid_internal_fragment(self, graph, component):
        """Determine if a component represents a valid internal fragment"""
        # A valid internal fragment must have at least one node that's not a terminal node
        # and not be solely composed of Fuc or NeuAc
        node_types = [graph.nodes[n]['type'] for n in component]
        
        # Check if this contains either HexNAc or Hex
        if 'HexNAc' not in node_types and 'Hex' not in node_types:
            return False
            
        # Count total monosaccharide units in this component
        counts = {'HexNAc': 0, 'Hex': 0, 'Fuc': 0, 'NeuAc': 0}
        for node in component:
            node_type = graph.nodes[node]['type']
            if node_type in counts:
                counts[node_type] += 1
        
        total_monosaccharides = sum(counts.values())
        
        # If fragment contains NeuAc, only allow it as a BY ion if it's a larger fragment
        if 'NeuAc' in node_types:
            # Allow NeuAc-containing fragments if they have at least 5 total monosaccharides
            # This covers compositions like HexNAc3Hex4NeuAc1
            if total_monosaccharides >= 5:
                # For specialized case of HexNAc3Hex4NeuAc1
                if counts['HexNAc'] == 3 and counts['Hex'] == 4 and counts['NeuAc'] == 1:
                    return True
                elif counts['HexNAc'] + counts['Hex'] >= 5:  # Ensure substantial non-NeuAc content
                    return True
            return False
        
        # Count terminal and non-terminal nodes
        terminal_count = 0
        internal_count = 0
        
        for node in component:
            if graph.out_degree(node) == 0:  # Terminal node
                terminal_count += 1
                # If terminal node is not Fuc, this is not a valid internal fragment
                if graph.nodes[node]['type'] != 'Fuc':
                    return False
            else:
                internal_count += 1
        
        # Valid internal fragment needs at least one internal node
        if internal_count == 0:
            return False
        
        # For complex components, validate the structure forms a realistic internal fragment
        # An internal fragment should not have too many terminal nodes
        if terminal_count > internal_count + 1:  # Allowing some flexibility for branched structures
            return False
        
        # If we get here, the fragment is valid
        return True

    def _is_invalid_yy_combination(self, graph, edge1, edge2, has_core_fuc):
        """Validate edge combinations for YY ion generation with strict rules"""
        u1, v1 = edge1
        u2, v2 = edge2
        
            # For O-glycans, we need different rules than N-glycans
        if self.glycan_type == "O":
            # For O-glycans, we allow YY with just the reducing end HexNAc
            # and we allow NeuAc in YY ions
            
            # Only do basic validation to avoid empty/invalid fragments
            temp_graph = copy.deepcopy(graph)
            try:
                temp_graph.remove_edge(u1, v1)
                temp_graph.remove_edge(u2, v2)
                components = list(nx.weakly_connected_components(temp_graph))
                
                # Find the component with the reducing end
                reducing_end_component = None
                for idx, component in enumerate(components):
                    if 1 in component:  # Reducing end is node 1
                        reducing_end_component = component
                        break
                        
                if reducing_end_component is None:
                    return True  # Invalid if reducing end component not found
                        
                # Only basic validation for O-glycans - ensure at least one node remains 
                # in the reducing end component
                return len(reducing_end_component) == 0
                    
            except nx.NetworkXError:
                return True
                
        else:
        
            # For YY-HexNAc1-redend and YY-HexNAc2-redend, only valid in structure with core fucosylation
            if not has_core_fuc:
                # Check if edges would form a HexNAc1/2-redend fragment
                if (u1 == 1 or u2 == 1) and (graph.nodes[v1]['type'] == 'HexNAc' or graph.nodes[v2]['type'] == 'HexNAc'):
                    return True
            
            # Get the potential YY fragment nodes (nodes that would remain when these edges are cut)
            temp_graph = copy.deepcopy(graph)
            try:
                temp_graph.remove_edge(u1, v1)
                temp_graph.remove_edge(u2, v2)
                components = list(nx.weakly_connected_components(temp_graph))
                
                # Find the component with the reducing end
                reducing_end_component = None
                for idx, component in enumerate(components):
                    if 1 in component:  # Reducing end is node 1
                        reducing_end_component = component
                        break
                        
                if reducing_end_component is None:
                    return True  # Invalid if reducing end component not found
                        
                # Check for terminal nodes in the reducing end component
                for node in reducing_end_component:
                    node_type = graph.nodes[node]['type']
                    
                    # Rule 1: NeuAc is always a terminal node and can't be in YY ions
                    if node_type == 'NeuAc':
                        return True
                        
                    # Rule 2: Check for other terminal nodes (except Fuc)
                    if node_type != 'Fuc' and self._is_terminal_monosaccharide(graph, node):
                        return True
                        
            except nx.NetworkXError:
                return True
                
            return False

    def _is_terminal_monosaccharide(self, graph, node):
        """Check if a node is a terminal monosaccharide (no outgoing edges)"""
        # A terminal node has no successors
        return graph.out_degree(node) == 0

    def _validate_fragment_types(self, fragments, composition_registry):
        """Validate and correct fragment type assignments with revised rules"""
        corrected_fragments = {
            'b_ions': [],
            'y_ions': [],
            'by_ions': [],
            'yy_ions': []
        }
        
        # Track complementary B/Y ion pairs
        b_compositions = set()
        y_compositions = set()
        
        # First pass - collect all compositions
        for frag_type in ['b_ions', 'y_ions']:
            for fragment in fragments[frag_type]:
                comp_key = tuple(sorted((k, v) for k, v in fragment.items()))
                if frag_type == 'b_ions':
                    b_compositions.add(comp_key)
                else:
                    y_compositions.add(comp_key)
        
        # Process all fragments with balanced classification
        all_fragments = {}
        for frag_type in ['b_ions', 'y_ions', 'by_ions', 'yy_ions']:
            for fragment in fragments[frag_type]:
                comp_key = tuple(sorted((k, v) for k, v in fragment.items()))
                
                # Main classification logic remains the same
                # ...existing logic...
                
                # Ensure B/Y ion symmetry for single cleavage fragments
                #if frag_type == 'b_ions' and comp_key not in y_compositions:
                    # Also create corresponding Y-ion if missing
                    #print(f"Adding missing Y-ion for composition: {dict(comp_key)}")
                    # Add logic to create corresponding Y-ion
                
                # Add to corrected fragments with appropriate category
                corrected_fragments[frag_type].append(fragment)
        
        return corrected_fragments

    def _could_be_internal_fragment(self, fragment):
        """Determine if a fragment composition could be an internal fragment"""
        # Simple heuristic - internal fragments typically don't have many residues
        total_residues = sum(fragment.values())
        
        # Internal fragments typically can't have more than ~4 residues
        if total_residues > 4:
            return False
        
        # If there's NeuAc, it's likely not an internal fragment
        if 'NeuAc' in fragment:
            return False
            
        # More complex logic could check for specific composition patterns
        return True

    def _format_fragment(self, counts, has_reducing_end=False):
        """Format fragment composition as a dictionary with numeric counts and reducing end flag"""
        fragment = {}
        if counts['HexNAc'] > 0:
            fragment['HexNAc'] = counts['HexNAc']  # Store numeric count
        if counts['Hex'] > 0:
            fragment['Hex'] = counts['Hex']
        if counts['Fuc'] > 0:
            fragment['Fuc'] = counts['Fuc']
        if counts['NeuAc'] > 0:
            fragment['NeuAc'] = counts['NeuAc']
        
        if not fragment:
            return {}
        return fragment  # Return dictionary with numeric counts

    def _format_string(self, fragment, ion_type, has_reducing_end=False):
        """Format fragment dictionary into a string for output with specific naming conventions"""
        parts = []
        if 'HexNAc' in fragment:
            parts.append(f"HexNAc{fragment['HexNAc']}")
        if 'Hex' in fragment:
            parts.append(f"Hex{fragment['Hex']}")
        if 'Fuc' in fragment:
            parts.append(f"Fuc{fragment['Fuc']}")
        if 'NeuAc' in fragment:
            parts.append(f"NeuAc{fragment['NeuAc']}")
        
        if not parts:
            return ""
        
        # Add -redend last for y and yy ions
        if ion_type in ['y', 'yy'] and has_reducing_end:
            parts.append("redend")
        
        # Join with hyphens
        composition = "-".join(parts)
        
        # Apply naming conventions 
        if ion_type == 'by':
            return f"Y-{composition.replace('-redend', '')}-B"
        elif ion_type == 'y':
            return f"Y-{composition}"  # Always add Y- prefix for y ions
        elif ion_type == 'yy':
            return f"YY-{composition}"
        else:  # b ions
            return f"{composition}-B"
        
    def _count_residues(self, graph):
        counts = {'HexNAc': 0, 'Hex': 0, 'Fuc': 0, 'NeuAc': 0}
        has_reducing_end = 1 in graph.nodes()
        for node in graph.nodes():
            node_type = graph.nodes[node]['type']
            if node_type in counts:
                counts[node_type] += 1
        return counts
    
    def _structure_fingerprint(self, graph, modification_type=6):
        """Create a truly canonical fingerprint for a glycan structure"""
        # Start with node 1 (reducing end)
        root = 1
        
        # Create a canonical labeling based on monosaccharide type and topology
        canonical_labels = {}
        canonical_labels[root] = 0
        next_label = 1
        
        # Queue for BFS
        queue = [root]
        visited = {root}
        
        # BFS traversal to assign canonical labels
        while queue:
            node = queue.pop(0)
            
            # Group children by type and position before assigning labels
            children_by_type = {}
            for succ in graph.successors(node):
                node_type = graph.nodes[succ]['type']
                position = graph.nodes[succ]['position']
                key = (node_type, position)
                if key not in children_by_type:
                    children_by_type[key] = []
                children_by_type[key].append(succ)
            
            # Process each group of same-type children
            for (node_type, position), children in sorted(children_by_type.items()):
                # Sort children of same type by their subtree structure
                children_with_subtree = []
                for child in children:
                    # Create a temporary subtree hash based on the child's descendants
                    subtree_hash = self._get_subtree_hash(graph, child, visited)
                    children_with_subtree.append((child, subtree_hash))
                
                # Sort by the subtree hash for consistent ordering of identical subtrees
                children_with_subtree.sort(key=lambda x: x[1])
                
                # Assign labels to the sorted children
                for child, _ in children_with_subtree:
                    if child not in visited:
                        canonical_labels[child] = next_label
                        next_label += 1
                        queue.append(child)
                        visited.add(child)
        
        # Create a canonical adjacency list representation
        canonical_adj_list = []
        
        # For each node in canonical order
        for orig_node, canon_label in sorted(canonical_labels.items(), key=lambda x: x[1]):
            node_type = graph.nodes[orig_node]['type']
            position = graph.nodes[orig_node].get('position', '')
            
            # Get canonical labels of neighbors
            successors = [canonical_labels[succ] for succ in graph.successors(orig_node)]
            successors.sort()
            
            # Add to adjacency list
            canonical_adj_list.append((canon_label, node_type, position, tuple(successors)))
        
        # Generate a unique fingerprint
        return str(canonical_adj_list)

    def _generate_core_by_ions(self, graph, fragments, cleavage_info, unique_by_ions, composition_registry, modification_type=6,use_cam=True, 
                        fixed_mods=None, variable_mods=None, mod_string=None, peptide=None):
        """Generate BY ions from the core mannose structure, specifically focusing on Hex2 and other core-related fragments"""

        calculator = GlycanMassCalculator(
        modification_type=modification_type, 
        use_cam=use_cam,
        fixed_mods=fixed_mods,
        variable_mods=variable_mods,
        mod_string=mod_string
        )
        # Get the core mannose nodes (usually nodes 3, 4, 5 in our structure)
        core_nodes = [n for n in graph.nodes() if graph.nodes[n]['type'] == 'Hex' and 
                    (graph.nodes[n]['position'] == 'core' or graph.nodes[n]['position'] == 'core_central')]
        
        # Get all edges in the graph
        all_edges = [(u, v) for u, v in graph.edges() if u != v]
        
        # Find all valid pairs of edges for internal fragmentation
        for edge1, edge2 in combinations(all_edges, 2):
            u1, v1 = edge1
            u2, v2 = edge2
            
            # Skip if edges are the same
            if edge1 == edge2:
                continue
                
            # We want specifically core-related cleavages
            # At least one edge should be connected to a core node
            core_related = False
            for node in [u1, v1, u2, v2]:
                if node in core_nodes or node == 2:  # Include the core HexNAc (node 2)
                    core_related = True
                    break
                    
            if not core_related:
                continue
                
            # Process this edge pair for internal fragmentation
            temp_graph = copy.deepcopy(graph)
            temp_graph.remove_edge(u1, v1)
            temp_graph.remove_edge(u2, v2)
            
            # Analyze components
            components = list(nx.weakly_connected_components(temp_graph))
            if len(components) < 3:
                continue  # Need at least 3 components for internal fragment
            
            # Find the reducing end component
            reducing_end_component = None
            for idx, component in enumerate(components):
                if 1 in component:  # Reducing end node
                    reducing_end_component = idx
                    break
                    
            if reducing_end_component is None:
                continue
                    
            # Look for internal fragments (non-reducing end components)
            for idx, component in enumerate(components):
                # Skip the reducing end component
                if idx == reducing_end_component:
                    continue
                    
                # Check if this component could be a core fragment
                by_subgraph = temp_graph.subgraph(component).copy()
                
                # Check if this component contains any core mannose
                has_core_mannose = False
                for node in component:
                    if node in core_nodes:
                        has_core_mannose = True
                        break
                
                if has_core_mannose:
                    counts = self._count_residues(by_subgraph)
                    
                    # Skip fragments that don't have HexNAc or Hex
                    if counts['HexNAc'] == 0 and counts['Hex'] == 0:
                        continue
                    
                    # Format the fragment
                    fragment = self._format_fragment(counts, has_reducing_end=False)
                    
                    # Check if it's a valid fragment
                    if isinstance(fragment, dict) and sum(fragment.values()) > 0:
                        # Create the fragment key for validation and deduplication
                        comp_key = tuple(sorted((k, v) for k, v in fragment.items()))
                        composition_registry['by'].add(comp_key)
                        
                        # Format as string for display and create mass
                        fragment_str = self._format_string(fragment, 'by', has_reducing_end=False)
 
                        fragment_mass = calculator.calculate_fragment_mass(fragment, 'by_ions', peptide=peptide)
                        fragment_tuple = (fragment_str, fragment_mass)
                        
                        # Add if not already present
                        if fragment_tuple not in unique_by_ions:
                            unique_by_ions.add(fragment_tuple)
                            fragments['by_ions'].append(fragment)
                            cleavage_info['by_ions'][fragment_str] = f"Core BY: {u1}-{v1} and {u2}-{v2}"

    def _generate_core_fucose_yy_ions(self, graph, fragments, cleavage_info, unique_yy_ions, composition_registry, modification_type=6, peptide=None, 
                                      use_cam=False, fixed_mods=None, variable_mods=None, mod_string=None):
        """Generate YY ions specifically from core fucose cleavage combinations"""
        
        calculator = GlycanMassCalculator(
        modification_type=modification_type,
        use_cam=use_cam,
        fixed_mods=fixed_mods,
        variable_mods=variable_mods,
        mod_string=mod_string
        )
        
        # Check if structure has core fucosylation
        has_core_fuc = False
        core_fuc_node = None
        
        # Identify core fucose node
        for node in graph.nodes():
            if graph.nodes[node]['type'] == 'Fuc':
                parent = list(graph.predecessors(node))[0]
                if parent == 1:  # Attached to reducing end
                    has_core_fuc = True
                    core_fuc_node = node
                    break
        
        # Only proceed if core fucose is present
        if not has_core_fuc or not core_fuc_node:
            return
        
        # Get the edge connecting fucose to the reducing end
        fuc_edge = (1, core_fuc_node)
        
        # Get all other edges that could pair with the fucose cleavage
        all_edges = [(u, v) for u, v in graph.edges() if u != v and (u, v) != fuc_edge]
        
        # Specifically find edges in the mannose branches
        mannose_branch_edges = []
        
        # Add edges for mannose tree
        for edge in all_edges:
            u, v = edge
            # Check if the edge is in the mannose tree structure (nodes 3, 4, 5)
            if u in [3, 4, 5] or v in [3, 4, 5]:
                mannose_branch_edges.append(edge)
            # Also add edges for the NeuAc branch (nodes 6, 7, 8)
            if u in [6, 7] or v in [6, 7, 8]:
                mannose_branch_edges.append(edge)
        
        # Generate YY ions for each fucose + mannose branch edge combination
        for edge in mannose_branch_edges:
            u2, v2 = edge
            
            # Create temporary graph for this cleavage combination
            temp_graph = copy.deepcopy(graph)
            try:
                # Remove the fucose edge and the branch edge
                temp_graph.remove_edge(1, core_fuc_node)
                temp_graph.remove_edge(u2, v2)
                
                # Find connected components
                components = list(nx.weakly_connected_components(temp_graph))
                
                # Find component with reducing end
                reducing_end_component = None
                for component in components:
                    if 1 in component:
                        reducing_end_component = component
                        break
                
                if reducing_end_component:
                    # Create YY ion from the reducing end component
                    yy_subgraph = temp_graph.subgraph(reducing_end_component).copy()
                    counts = self._count_residues(yy_subgraph)
                    
                    # Only consider if there's at least one monosaccharide
                    if sum(counts.values()) > 0:
                        fragment = self._format_fragment(counts, has_reducing_end=True)
                        
                        if isinstance(fragment, dict):
                            # Format and add to YY ions
                            comp_key = tuple(sorted((k, v) for k, v in fragment.items()))
                            composition_registry['yy'].add(comp_key)
                            
                            fragment_str = self._format_string(fragment, 'yy', has_reducing_end=True)
                            fragment_mass = calculator.calculate_fragment_mass(fragment, 'yy_ions', peptide=peptide)
                            fragment_tuple = (fragment_str, fragment_mass)
                            
                            if fragment_tuple not in unique_yy_ions:
                                unique_yy_ions.add(fragment_tuple)
                                fragments['yy_ions'].append(fragment)
                                cleavage_info['yy_ions'][fragment_str] = f"Core Fuc YY: 1-{core_fuc_node} and {u2}-{v2}"
            
            except nx.NetworkXError:
                pass

    def _generate_branch_specific_y_ions(self, graph, fragments, cleavage_info, unique_y_ions, composition_registry, modification_type=6, peptide=None, 
                                         use_cam=False, fixed_mods=None, variable_mods=None, mod_string=None):
        """Ensure branch-specific Y-ions are captured, particularly for complex glycans with branch HexNAc"""
        
        calculator = GlycanMassCalculator(
        modification_type=modification_type,
        use_cam=use_cam,
        fixed_mods=fixed_mods,
        variable_mods=variable_mods,
        mod_string=mod_string
        )
        # Get the reducing end node
        reducing_end = 1
        
        # For each edge in the graph that could create a Y-ion
        for u, v in graph.edges():
            # Skip self-loops
            if u == v:
                continue
                
            # For glycan 4502, consider ALL possible cleavage points, not just mannose-HexNAc connections
            temp_graph = copy.deepcopy(graph)
            temp_graph.remove_edge(u, v)
            
            # Find connected components
            components = list(nx.weakly_connected_components(temp_graph))
            
            # Find component with reducing end (this is our Y-ion)
            for component in components:
                if reducing_end in component:
                    # Generate Y-ion from this component
                    y_subgraph = temp_graph.subgraph(component).copy()
                    counts = self._count_residues(y_subgraph)
                    
                    # Check for the specific composition we're looking for
                    has_specific_comp = (counts['HexNAc'] == 3 and 
                                        counts['Hex'] == 4 and 
                                        counts['NeuAc'] == 1)
                    
                    # Format the fragment
                    fragment = self._format_fragment(counts, has_reducing_end=True)
                    
                    if isinstance(fragment, dict):
                        # Create fragment key for validation
                        comp_key = tuple(sorted((k, v) for k, v in fragment.items()))
                        composition_registry['y'].add(comp_key)
                        
                        # Format string and mass for this fragment
                        fragment_str = self._format_string(fragment, 'y', has_reducing_end=True)
                        fragment_mass = calculator.calculate_fragment_mass(fragment, 'y_ions', peptide=peptide)
                        fragment_tuple = (fragment_str, fragment_mass)
                        
                        # Debug special case for HexNAc3Hex4NeuAc1-redend
                        #if has_specific_comp:
                           # print(f"DEBUG: Adding Y-ion HexNAc3Hex4NeuAc1-redend to fragments list with ID: {fragment_str}")
                            #print(f"DEBUG: Fragment tuple for deduplication: {fragment_tuple}")
                        
                        # Add to y_ions if unique
                        if fragment_tuple not in unique_y_ions:
                            unique_y_ions.add(fragment_tuple)
                            fragments['y_ions'].append(fragment)
                            cleavage_info['y_ions'][fragment_str] = f"Edge Cleavage Y: {u}-{v} ({graph.nodes[u]['type']}-{graph.nodes[v]['type']})"
                            
                            # Force add our problematic fragment
                            #if has_specific_comp:
                                #print(f"DEBUG: Successfully added HexNAc3Hex4NeuAc1-redend to y_ions")

class GlycanStructurePredictor:
    def __init__(self, hexnac=0, hex=0, fuc=0, neuac=0, neugc=0):
        """Initialize glycan structure predictor with monosaccharide counts"""
        self.hexnac = hexnac
        self.hex = hex
        self.fuc = fuc
        self.neuac = neuac
        self.neugc = neugc
        self.possible_structures = []
    
    def generate_oglycan_cores(self):
        """Generate possible O-glycan core structures"""
        cores = []
        
        # Core 1: GalNAc-Gal (T antigen)
        if self.hex >= 1:
            core = nx.DiGraph()
            core.add_node(1, type='HexNAc', position='core_reducing', label='HexNAc')
            core.add_node(2, type='Hex', position='core', label='Hex')
            core.add_edge(1, 2)
            cores.append(core)
        
        # Core 2: GalNAc with two branching HexNAc
        if self.hexnac >= 3:
            core = nx.DiGraph()
            core.add_node(1, type='HexNAc', position='core_reducing', label='HexNAc')
            core.add_node(2, type='HexNAc', position='core_branch', label='HexNAc')
            core.add_node(3, type='HexNAc', position='core_branch', label='HexNAc')
            core.add_edge(1, 2)
            core.add_edge(1, 3)
            cores.append(core)
        
        # Core 3: GalNAc with single branching HexNAc
        if self.hexnac >= 2:
            core = nx.DiGraph()
            core.add_node(1, type='HexNAc', position='core_reducing', label='HexNAc')
            core.add_node(2, type='HexNAc', position='core_branch', label='HexNAc')
            core.add_edge(1, 2)
            cores.append(core)
        
        # Core 0: Single GalNAc (Tn antigen)
        core = nx.DiGraph()
        core.add_node(1, type='HexNAc', position='core_reducing', label='HexNAc')
        cores.append(core)
        
        return cores
    
    def count_nodes(self, graph, node_type):
        """Count the number of nodes of a specific type in the graph"""
        return sum(1 for node in graph.nodes() if graph.nodes[node]['type'] == node_type)
    
    def predict_structures(self):
        """Base method for predicting glycan structures - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement predict_structures()")
    
class OGlycanStructurePredictor(GlycanStructurePredictor):
    def __init__(self, hexnac=0, hex=0, fuc=0, neuac=0, neugc=0):
        super().__init__(hexnac, hex, fuc, neuac, neugc)
        self.seen_structures = set()  # Track canonical representations of structures
        
    def predict_structures(self):
        """Predict O-glycan structures based on composition with improved efficiency"""
        # Generate core structures
        core_graphs = self.generate_oglycan_cores()
        print(f"Core graphs generated: {len(core_graphs)}")
        
        all_results = []
        self.seen_structures.clear()  # Reset seen structures for this prediction
        
        for i, core in enumerate(core_graphs):
            print(f"Processing core {i+1}")
            
            # Calculate remaining monosaccharides
            remaining_hexnac = self.hexnac - self.count_nodes(core, 'HexNAc')
            remaining_hex = self.hex - self.count_nodes(core, 'Hex')
            remaining_fuc = self.fuc - self.count_nodes(core, 'Fuc')
            remaining_neuac = self.neuac - self.count_nodes(core, 'NeuAc')
            remaining_neugc = self.neugc - self.count_nodes(core, 'NeuGc')
            
            print(f"Starting with: HexNAc={remaining_hexnac}, Hex={remaining_hex}, NeuAc={remaining_neuac}, Fuc={remaining_fuc}")
            
            # Skip if any remaining count is negative (impossible structure)
            if any(count < 0 for count in [remaining_hexnac, remaining_hex, remaining_fuc, remaining_neuac, remaining_neugc]):
                continue
            
            # Track structures to process
            structures_to_process = [(core.copy(), remaining_hexnac, remaining_hex, remaining_fuc, remaining_neuac, remaining_neugc)]
            core_results = []
            
            while structures_to_process:
                # Get next structure to process
                current_graph, hexnac_left, hex_left, fuc_left, neuac_left, neugc_left = structures_to_process.pop(0)
                
                # If all residues used, we have a complete structure
                # If all residues used, we have a complete structure
                if hexnac_left == 0 and hex_left == 0 and fuc_left == 0 and neuac_left == 0 and neugc_left == 0:
                    # Check if we've seen an equivalent structure
                    canonical_rep = self.get_canonical_representation(current_graph)
                    if canonical_rep not in self.seen_structures:
                        self.seen_structures.add(canonical_rep)
                        structure_type = self.classify_structure(current_graph)
                        core_results.append({
                            'structure': current_graph,
                            'type': structure_type,
                            'canonical_id': canonical_rep  # Store the canonical ID for debug
                        })
                    continue
                # Get valid attachment points for current structure
                attachment_points = []
                for node in current_graph.nodes():
                    # Only consider nodes with fewer than 2 outgoing edges
                    if current_graph.out_degree(node) < 2:
                        node_type = current_graph.nodes[node]['type']
                        # Apply attachment constraints
                        if node_type == 'Fuc':
                            # Fuc is terminal - no attachments allowed
                            continue
                        elif node_type == 'NeuAc' and neuac_left == 0:
                            # NeuAc can only connect to another NeuAc if there are any left
                            continue
                        else:
                            attachment_points.append(node)
                
                # Try each type of remaining monosaccharide at each attachment point
                if hexnac_left > 0:
                    self._try_attachments(current_graph, attachment_points, 'HexNAc', 
                                         [hexnac_left, hex_left, fuc_left, neuac_left, neugc_left],
                                         structures_to_process, excluded_parents=['NeuAc', 'Fuc'])
                    
                if hex_left > 0:
                    self._try_attachments(current_graph, attachment_points, 'Hex', 
                                         [hexnac_left, hex_left, fuc_left, neuac_left, neugc_left],
                                         structures_to_process, excluded_parents=['NeuAc', 'Fuc'])
                    
                if fuc_left > 0:
                    self._try_attachments(current_graph, attachment_points, 'Fuc', 
                                         [hexnac_left, hex_left, fuc_left, neuac_left, neugc_left],
                                         structures_to_process, excluded_parents=['NeuAc', 'Fuc'])
                    
                if neuac_left > 0:
                    self._try_attachments(current_graph, attachment_points, 'NeuAc', 
                                         [hexnac_left, hex_left, fuc_left, neuac_left, neugc_left],
                                         structures_to_process, excluded_parents=['Fuc'])
                
                # Limit size of the queue to prevent memory issues
                if len(structures_to_process) > 500:
                    # Sort by fewest remaining residues to prioritize structures closer to completion
                    structures_to_process.sort(key=lambda x: sum(x[1:]))
                    structures_to_process = structures_to_process[:250]
            
            print(f"Structures after core {i+1}: {len(all_results) + len(core_results)}")
            all_results.extend(core_results)
            
            # Cut off if we have too many structures
            if len(all_results) > 100:
                print(f"Reached limit of 100 structures, stopping.")
                break
        
        print(f"Total unique structures generated: {len(all_results)}")
        return all_results
    
    def _try_attachments(self, graph, attachment_points, mono_type, remaining, structures_list, excluded_parents=None):
        """Try attaching a monosaccharide to valid attachment points"""
        hexnac_left, hex_left, fuc_left, neuac_left, neugc_left = remaining
        
        for parent in attachment_points:
            # Skip excluded parent types
            if excluded_parents and graph.nodes[parent]['type'] in excluded_parents:
                continue
                
            # Create a new graph with this attachment
            new_graph = graph.copy()
            node_id = max(new_graph.nodes()) + 1
            position = 'terminal' if mono_type in ['Fuc', 'NeuAc'] else 'branch'
            new_graph.add_node(node_id, type=mono_type, position=position)
            new_graph.add_edge(parent, node_id)
            
            # Check if we've seen this structure pattern before
            canonical_rep = self.get_canonical_representation(new_graph)
            if canonical_rep not in self.seen_structures:
                # Mark as "seen" to avoid duplicate work, but don't store in results yet
                self.seen_structures.add(canonical_rep)
                
                # Update remaining counts
                new_remaining = list(remaining)
                if mono_type == 'HexNAc':
                    new_remaining[0] -= 1
                elif mono_type == 'Hex':
                    new_remaining[1] -= 1
                elif mono_type == 'Fuc':
                    new_remaining[2] -= 1
                elif mono_type == 'NeuAc':
                    new_remaining[3] -= 1
                elif mono_type == 'NeuGc':
                    new_remaining[4] -= 1
                
                # Add to processing queue
                structures_list.append((new_graph, *new_remaining))
    
    def get_canonical_representation(self, graph):
        """Generate a truly canonical representation that's invariant to node numbering"""
        # Get composition fingerprint
        composition = {}
        for node in graph.nodes():
            node_type = graph.nodes[node]['type']
            composition[node_type] = composition.get(node_type, 0) + 1
        
        # Perform a more rigorous canonicalization
        # Start by creating a more detailed structure description
        nodes_by_type = {}
        for node in graph.nodes():
            node_type = graph.nodes[node]['type']
            if node_type not in nodes_by_type:
                nodes_by_type[node_type] = []
            nodes_by_type[node_type].append(node)
        
        # Create unique node identifiers based on connectivity profile
        node_profiles = {}
        for node in graph.nodes():
            # Create a profile based on node type and its connections
            node_type = graph.nodes[node]['type']
            parent_types = [graph.nodes[p]['type'] for p in graph.predecessors(node)]
            child_types = [graph.nodes[c]['type'] for c in graph.successors(node)]
            # Sort for consistency
            parent_types.sort()
            child_types.sort()
            # Store node's "connection signature"
            node_profiles[node] = (node_type, tuple(parent_types), tuple(child_types))
        
        # Group nodes with identical profiles
        profile_groups = {}
        for node, profile in node_profiles.items():
            if profile not in profile_groups:
                profile_groups[profile] = []
            profile_groups[profile].append(node)
        
        # For each profile group, sort nodes based on descendant structures
        # This ensures consistent selection of equivalent nodes
        for profile, nodes in profile_groups.items():
            if len(nodes) > 1:
                # Sort nodes by "subtree fingerprint"
                nodes.sort(key=lambda n: self._get_subtree_fingerprint(graph, n))
        
        # Create final canonical representation from sorted profile groups
        # Sort profiles by (node_type, parent count, child count)
        sorted_profiles = sorted(profile_groups.keys(), 
                                key=lambda p: (p[0], len(p[1]), len(p[2]), p[1], p[2]))
        
        canonical_parts = []
        canonical_parts.append(str(sorted(composition.items())))
        
        # Add detailed structure information
        for profile in sorted_profiles:
            nodes = profile_groups[profile]
            canonical_parts.append(f"{profile}:{len(nodes)}")
        
        return "||".join(canonical_parts)

    def _get_subtree_fingerprint(self, graph, root):
        """Generate a fingerprint for the subtree rooted at the given node"""
        visited = set()
        
        def dfs(node, depth=0):
            if node in visited:
                return []
            visited.add(node)
            
            node_type = graph.nodes[node]['type']
            children = list(graph.successors(node))
            children.sort(key=lambda c: graph.nodes[c]['type'])
            
            result = [(depth, node_type)]
            for child in children:
                result.extend(dfs(child, depth + 1))
            return result
        
        fingerprint = dfs(root)
        fingerprint.sort()  # Ensure consistent ordering
        return tuple(fingerprint)

    def test_canonical_representation(self, structure1, structure2):
        """Test if two structures have the same canonical representation"""
        repr1 = self.get_canonical_representation(structure1)
        repr2 = self.get_canonical_representation(structure2)
        same = repr1 == repr2
        print(f"Same structure: {same}")
        return same

    def classify_structure(self, graph):
        """Classify the O-glycan structure"""
        # Count nodes by type
        counts = {}
        for node in graph.nodes():
            node_type = graph.nodes[node]['type']
            counts[node_type] = counts.get(node_type, 0) + 1
        
        hexnac_count = counts.get('HexNAc', 0)
        hex_count = counts.get('Hex', 0)
        
        # Determine O-glycan subtypes
        if hex_count == 0 and hexnac_count >= 2:
            return "O-GalNAc (Tn/STn)"
        elif hex_count >= 1 and hexnac_count >= 1:
            return "O-GalNAc-Gal (T/ST)"
        elif hexnac_count == 3 and hex_count == 0:
            return "O-GalNAc with HexNAc branches"
        else:
            return "Complex O-glycan"

def predict_glycan_structure(glycan_code, glycan_type="N", peptide=None):
    """Main function to predict glycan structures from a code with type specification"""
    print(f"\nPredicting structures for {glycan_code} as {glycan_type}-glycan type")
    
    glycan = Glycan(glycan_code, glycan_type)
    possible_structures = glycan.predict_structures()
    
    # Debug print to show glycan type and predicted structures
    print(f"\nPredicting structures for {glycan_code} (Type: {glycan_type}-glycan):")
    print(f"Generated {len(possible_structures)} possible structures")
    
    results = []
    for i, structure in enumerate(possible_structures):
        structure_type = glycan.classify_structure(structure)
        fragments_tuple = glycan.generate_fragments(structure, peptide=peptide)
        
        # Print a debug visualization of the structure
        #print(f"\n=== STRUCTURE {i+1} of {len(possible_structures)}: {structure_type} ===")
        
        # Count node types
        node_types = {}
        for node in structure.nodes:
            node_type = structure.nodes[node]['type']
            node_types[node_type] = node_types.get(node_type, 0) + 1
        
        #print(f"Composition: {', '.join([f'{count} {sugar}' for sugar, count in node_types.items()])}")
        
        # Print a text-based graph visualization
        #print("\nGraph structure:")
        #print("---------------")
        
        # First print the core structure
        #print("Core nodes:")
        for node in sorted([n for n in structure.nodes if structure.nodes[n]['position'] == 'core']):
            node_type = structure.nodes[node]['type']
            successors = list(structure.successors(node))
            predecessors = list(structure.predecessors(node))
            parent = predecessors[0] if predecessors else "None"
            
            # Format the node's connections
            if successors:
                children = [f"{s}({structure.nodes[s]['type']})" for s in successors]
            #    print(f"  Node {node}({node_type}) ← Parent: {parent} → Children: {', '.join(children)}")
            #else:
            #    print(f"  Node {node}({node_type}) ← Parent: {parent} → No children")
        
        # Then print branch nodes
        branch_nodes = [n for n in structure.nodes if structure.nodes[n]['position'] == 'branch']
        if branch_nodes:
            #print("\nBranch nodes:")
            for node in sorted(branch_nodes):
                node_type = structure.nodes[node]['type']
                successors = list(structure.successors(node))
                predecessors = list(structure.predecessors(node))
                parent = predecessors[0] if predecessors else "None"
                
                # Format the node's connections
                if successors:
                    children = [f"{s}({structure.nodes[s]['type']})" for s in successors]
               #     print(f"  Node {node}({node_type}) ← Parent: {parent}({structure.nodes[parent]['type']}) → Children: {', '.join(children)}")
               # else:
                #    print(f"  Node {node}({node_type}) ← Parent: {parent}({structure.nodes[parent]['type']}) → No children")
        
        # Print terminal nodes (those with no successors)
        terminal_nodes = [n for n in structure.nodes if not list(structure.successors(n))]
        if terminal_nodes:
            #print("\nTerminal nodes:")
            for node in sorted(terminal_nodes):
                node_type = structure.nodes[node]['type']
                predecessors = list(structure.predecessors(node))
                parent = predecessors[0] if predecessors else "None"
                parent_type = structure.nodes[parent]['type'] if parent != "None" else "None"
               # print(f"  Node {node}({node_type}) ← Parent: {parent}({parent_type})")
        
        # Print edge connections (more detailed view)
        """
        print("\nConnections (edges):")
        for edge in structure.edges():
            source, target = edge
            source_type = structure.nodes[source]['type']
            target_type = structure.nodes[target]['type']
            print(f"  {source}({source_type}) → {target}({target_type})")
        
        print("\n" + "-" * 40)
        """
        # Store both fragments and cleavage_info
        if isinstance(fragments_tuple, tuple):
            fragments, cleavage_info = fragments_tuple
            
            results.append({
                'structure_id': i + 1,
                'structure': structure,
                'type': structure_type,
                'fragments': fragments,
                'cleavage_info': cleavage_info
            })
        else:
            # Backward compatibility
            results.append({
                'structure_id': i + 1,
                'structure': structure,
                'type': structure_type,
                'fragments': fragments_tuple
            })
    
    # Return both results and the glycan object
    return results, glycan

def print_structure_details(results, glycan):
    """Print detailed information about each structure"""
    for i, result in enumerate(results):
        structure = result['structure']
        #print(f"\n=== STRUCTURE {i+1} - Type: {result['type']} ===")
        
        # Core structure
        #print("Core structure:")
        for node in [1, 2, 3, 4, 5]:
            successors = list(structure.successors(node))
            # Fix the f-string syntax by concatenating the list representation separately
            succ_info = [f"{s} ({structure.nodes[s]['type']})" for s in successors]
            #print(f"  Node {node} ({structure.nodes[node]['type']}) → {succ_info}")
        
        # Branch HexNAc and their attachments
        branch_hexnac = [n for n in structure.nodes() 
                        if structure.nodes[n]['type'] == 'HexNAc' and 
                           structure.nodes[n]['position'] == 'branch']
        #print("Branch HexNAc:")
        for node in branch_hexnac:
            successors = list(structure.successors(node))
            parent = list(structure.predecessors(node))[0]  # Get parent node
            succ_info = [f"{s} ({structure.nodes[s]['type']})" for s in successors]
            #print(f"  Node {node} (HexNAc) attached to {parent} → {succ_info}")
        
        # Branch Hex and their attachments
        branch_hex = [n for n in structure.nodes() 
                     if structure.nodes[n]['type'] == 'Hex' and 
                        structure.nodes[n]['position'] == 'branch']
        #print("Branch Hex:")
        for node in branch_hex:
            successors = list(structure.successors(node))
            parent = list(structure.predecessors(node))[0]  # Get parent node
            succ_info = [f"{s} ({structure.nodes[s]['type']})" for s in successors]
            #print(f"  Node {node} (Hex) attached to {parent} → {succ_info}")
        
        # Fucose placements
        fuc_nodes = [n for n in structure.nodes() if structure.nodes[n]['type'] == 'Fuc']
        #print("Fucose placements:")
        for node in fuc_nodes:
            parent = list(structure.predecessors(node))[0]  # Get parent node
            parent_type = structure.nodes[parent]['position']
            #print(f"  Node {node} (Fuc) attached to {parent} (HexNAc - {parent_type})")
        
        # NeuAc placements
        neuac_nodes = [n for n in structure.nodes() if structure.nodes[n]['type'] == 'NeuAc']
        #print("NeuAc placements:")
        for node in neuac_nodes:
            parent = list(structure.predecessors(node))[0]  # Get parent node
            print(f"  Node {node} (NeuAc) attached to {parent} ({structure.nodes[parent]['type']})")
        
        #print("\nSummary of monosaccharide distribution:")
        monosac_counts = glycan._count_residues(structure)  # Use the glycan object
        #print(f"  HexNAc: {monosac_counts['HexNAc']}")
        #print(f"  Hex: {monosac_counts['Hex']}")
        #print(f"  Fuc: {monosac_counts['Fuc']}")
        #print(f"  NeuAc: {monosac_counts['NeuAc']}")
        #print("=" * 50)

def debug_print_oglycan_structure(graph):
    """Print a cleaner visualization of O-glycan structure"""
    print("\n=== O-GLYCAN STRUCTURE ===")
    
    # Get composition summary
    node_types = {}
    for node in graph.nodes:
        node_type = graph.nodes[node]['type']
        node_types[node_type] = node_types.get(node_type, 0) + 1
    
    #print(f"Composition: {', '.join([f'{count} {sugar}' for sugar, count in node_types.items()])}")
    
    # Create adjacency representation
    adjacency = {}
    for node in graph.nodes:
        adjacency[node] = {
            'type': graph.nodes[node]['type'],
            'successors': list(graph.successors(node)),
            'predecessors': list(graph.predecessors(node))
        }
    
    # Print the graph structure
    #print("\nGraph structure:")
    
    def print_subtree(node, level=0):
        indent = "  " * level
        node_info = adjacency[node]
        
        # Print connections with arrow only (no "parent" or "children" words)
        successors = node_info['successors']
        if successors:
            succ_str = ', '.join([f"{s}({adjacency[s]['type']})" for s in successors])
            print(f"{indent}{node}({node_info['type']}) → {succ_str}")
        else:
            print(f"{indent}{node}({node_info['type']})")
        
        # Print subtrees
        for child in successors:
            print_subtree(child, level + 1)


#Theoretical Fragmentation of Glycans
def add_custom_fragments(unique_fragments, glycan_code, modification_type=6, peptide=None, 
                        include_byy=False, generate_cz_glycan_fragment=False, generate_glycan_by_ions=True,
                        use_cam=None, fixed_mods=None, variable_mods=None, mod_string=None):
    """Add custom fragments with modified masses"""
    
    # print(f"🔧 BYY CUSTOM DEBUG: add_custom_fragments called")
    # print(f"🔧 BYY CUSTOM DEBUG:   include_byy: {include_byy}")
    # print(f"🔧 BYY CUSTOM DEBUG:   generate_cz_glycan_fragment: {generate_cz_glycan_fragment}")
    # print(f"🔧 BYY CUSTOM DEBUG:   generate_glycan_by_ions: {generate_glycan_by_ions}")
    
    # Create a copy of the unique fragments to avoid modifying the original
    extended_fragments = {
        'b_ions': unique_fragments['b_ions'].copy() if generate_glycan_by_ions else [],
        'y_ions': unique_fragments['y_ions'].copy() if generate_glycan_by_ions else [],
        'by_ions': unique_fragments['by_ions'].copy() if generate_glycan_by_ions else [],
        'yy_ions': unique_fragments['yy_ions'].copy() if generate_glycan_by_ions else [],
        'byy_ions': []
    }
    
    print(f"🔧 BYY CUSTOM DEBUG: Extended fragments initialized with:")
    for frag_type, frags in extended_fragments.items():
        print(f"🔧 BYY CUSTOM DEBUG:   {frag_type}: {len(frags)} fragments")
    
    # ALWAYS generate BYY ions if requested OR if C/Z conversion needs them
    if include_byy or generate_cz_glycan_fragment:
        print(f"🔧 BYY CUSTOM DEBUG: Generating BYY ions (include_byy={include_byy}, for_cz={generate_cz_glycan_fragment})")
        
        # First, ensure we have YY ions to work with
        working_fragments = extended_fragments.copy()
        
        # If we need YY ions but don't have them, get them from the original unique_fragments
        if len(working_fragments['yy_ions']) == 0 and 'yy_ions' in unique_fragments:
            working_fragments['yy_ions'] = unique_fragments['yy_ions'].copy()
            print(f"🔧 BYY CUSTOM DEBUG: Added {len(working_fragments['yy_ions'])} YY ions for BYY generation")
        
        # Generate BYY ions
        extended_with_byy = generate_byy_ions(working_fragments, glycan_code, modification_type, peptide)
        
        # Update extended_fragments with BYY ions
        extended_fragments['byy_ions'] = extended_with_byy.get('byy_ions', [])
        print(f"🔧 BYY CUSTOM DEBUG: Generated {len(extended_fragments['byy_ions'])} BYY ions")
        
        # Debug: Show first few BYY ions
        for i, byy_ion in enumerate(extended_fragments['byy_ions'][:3]):
            print(f"🔧 BYY CUSTOM DEBUG: BYY ion #{i}: {byy_ion.get('_custom_label', 'No label')} - {byy_ion.get('_ion_charge', 'No charge')}")
    
    # Create calculator
    calculator = GlycanMassCalculator()
    calculator.calculate_MONO_MASSES(modification_type)
    
    # Define masses
    water_mass = 18.0153
    methanol_mass = 32.042
    methyl_mass = 15.0235
    acetyl_plus_c2h4o2 = 78.07
    two_water_mass = 36.02
    
    # Adjust masses for permethylated glycans if needed
    if modification_type in [2, 3, 5]:
        water_mass = 18.0153 - (1 * 14.0157)
        methanol_mass = 32.042 - (1 * 14.0157)
        acetyl_plus_c2h4o2 = 78.07 - (3 * 14.0157)
        two_water_mass = 36.02 - (2 * 14.0157)
    
    # Parse glycan code
    hexnac, hex, fuc, neuac, neugc = calculator.parse_glycan_code(glycan_code)

    # ALWAYS generate custom BY fragments for C/Z conversion if C/Z is requested
    working_fragments = extended_fragments.copy()
    
    if generate_cz_glycan_fragment and not generate_glycan_by_ions:
        #print(f"🔧 CUSTOM DEBUG: Generating BY custom fragments internally for C/Z conversion")
        # Add original BY fragments for internal processing
        working_fragments['b_ions'] = unique_fragments.get('b_ions', []).copy()
        working_fragments['y_ions'] = unique_fragments.get('y_ions', []).copy()
        working_fragments['by_ions'] = unique_fragments.get('by_ions', []).copy()
        working_fragments['yy_ions'] = unique_fragments.get('yy_ions', []).copy()

    # Generate custom BY fragments (either for output or internal C/Z conversion)
    if generate_glycan_by_ions or generate_cz_glycan_fragment:
        #print(f"🔧 CUSTOM DEBUG: Starting custom BY fragment generation")
        custom_fragments_created = 0
        
        # 1. Y-HexNAc1-B custom fragments
        #print(f"🔧 CUSTOM DEBUG: Looking for Y-HexNAc1-B fragments to customize...")
        by_ions_to_process = unique_fragments.get('by_ions', [])
        #print(f"🔧 CUSTOM DEBUG: Found {len(by_ions_to_process)} BY ions to check")
        
        for i, fragment in enumerate(by_ions_to_process):
            if isinstance(fragment, dict) and fragment.get('HexNAc', 0) == 1 and len(fragment) == 1:
          #      print(f"🔧 CUSTOM DEBUG: Found HexNAc1 fragment #{i}: {fragment}")
                
                # Version without methanol - FIXED: Remove _ion_charge to allow multiple charge states
                demethanol_fragment = fragment.copy()
                demethanol_fragment['_custom_label'] = 'Y-HexNAc1(-CH3OH)-B'
                demethanol_fragment['_mass_adjustment'] = -methanol_mass
                # REMOVED: demethanol_fragment['_ion_charge'] = '1H+'  # This was forcing only 1H+
                demethanol_fragment['_is_custom'] = True
                demethanol_fragment['_custom_type'] = 'dehydration'
                working_fragments['by_ions'].append(demethanol_fragment)
                custom_fragments_created += 1
           #     print(f"🔧 CUSTOM DEBUG: ✅ Created custom fragment: Y-HexNAc1(-CH3OH)-B")
                
                # Version without water - FIXED: Remove _ion_charge to allow multiple charge states
                dehydrated_fragment = fragment.copy()
                dehydrated_fragment['_custom_label'] = 'Y-HexNAc1(-H2O)-B'
                dehydrated_fragment['_mass_adjustment'] = -water_mass
                # REMOVED: dehydrated_fragment['_ion_charge'] = '1H+'  # This was forcing only 1H+
                dehydrated_fragment['_is_custom'] = True
                dehydrated_fragment['_custom_type'] = 'dehydration'
                working_fragments['by_ions'].append(dehydrated_fragment)
                custom_fragments_created += 1
            #    print(f"🔧 CUSTOM DEBUG: ✅ Created custom fragment: Y-HexNAc1(-H2O)-B")
                
                # 126 Da fragment - FIXED: Remove _ion_charge to allow multiple charge states
                hexnac_126_fragment = fragment.copy()
                hexnac_126_fragment['_custom_label'] = 'Y-HexNAc1(-78Da)-B'
                hexnac_126_fragment['_mass_adjustment'] = -acetyl_plus_c2h4o2
                # REMOVED: hexnac_126_fragment['_ion_charge'] = '1H+'  # This was forcing only 1H+
                hexnac_126_fragment['_is_custom'] = True
                hexnac_126_fragment['_custom_type'] = 'neutral_loss'
                working_fragments['by_ions'].append(hexnac_126_fragment)
                custom_fragments_created += 1
             #   print(f"🔧 CUSTOM DEBUG: ✅ Created custom fragment: Y-HexNAc1(-78Da)-B")
                
                # 168 Da fragment - FIXED: Remove _ion_charge to allow multiple charge states
                hexnac_168_fragment = fragment.copy()
                hexnac_168_fragment['_custom_label'] = 'Y-HexNAc1(-2H2O)-B'
                hexnac_168_fragment['_mass_adjustment'] = -two_water_mass
                # REMOVED: hexnac_168_fragment['_ion_charge'] = '1H+'  # This was forcing only 1H+
                hexnac_168_fragment['_is_custom'] = True
                hexnac_168_fragment['_custom_type'] = 'dehydration'
                working_fragments['by_ions'].append(hexnac_168_fragment)
                custom_fragments_created += 1
             #   print(f"🔧 CUSTOM DEBUG: ✅ Created custom fragment: Y-HexNAc1(-2H2O)-B")
        
        # 2. NeuAc-B custom fragments
        if neuac > 0:
            #print(f"🔧 CUSTOM DEBUG: Looking for NeuAc-B fragments to customize (NeuAc count: {neuac})...")
            b_ions_to_process = unique_fragments.get('b_ions', [])
            #print(f"🔧 CUSTOM DEBUG: Found {len(b_ions_to_process)} B ions to check")
            
            for i, fragment in enumerate(b_ions_to_process):
                if isinstance(fragment, dict) and fragment.get('NeuAc', 0) == 1 and len(fragment) == 1:
            #        print(f"🔧 CUSTOM DEBUG: Found NeuAc1 fragment #{i}: {fragment}")
                    dehydrated_fragment = fragment.copy()
                    dehydrated_fragment['_custom_label'] = 'NeuAc1(-H2O)-B'
                    dehydrated_fragment['_mass_adjustment'] = -water_mass
                    # REMOVED: dehydrated_fragment['_ion_charge'] = '1H+'  # This was forcing only 1H+
                    dehydrated_fragment['_is_custom'] = True
                    dehydrated_fragment['_custom_type'] = 'dehydration'
                    working_fragments['b_ions'].append(dehydrated_fragment)
                    custom_fragments_created += 1
             #       print(f"🔧 CUSTOM DEBUG: ✅ Created custom fragment: NeuAc1(-H2O)-B")
        
        # 3. Fuc1-B custom fragments
        if fuc > 0:
         #   print(f"🔧 CUSTOM DEBUG: Looking for Fuc-B fragments to customize (Fuc count: {fuc})...")
            b_ions_to_process = unique_fragments.get('b_ions', [])
            
            for i, fragment in enumerate(b_ions_to_process):
                if isinstance(fragment, dict) and fragment.get('Fuc', 0) == 1 and len(fragment) == 1:
          #          print(f"🔧 CUSTOM DEBUG: Found Fuc1 fragment #{i}: {fragment}")
                    
                    # Dehydrated fucose - FIXED: Remove _ion_charge to allow multiple charge states
                    dehydrated_fuc = fragment.copy()
                    dehydrated_fuc['_custom_label'] = 'Fuc1(-H2O)-B'
                    dehydrated_fuc['_mass_adjustment'] = -water_mass
                    # REMOVED: dehydrated_fuc['_ion_charge'] = '1H+'  # This was forcing only 1H+
                    dehydrated_fuc['_is_custom'] = True
                    dehydrated_fuc['_custom_type'] = 'dehydration'
                    working_fragments['b_ions'].append(dehydrated_fuc)
                    custom_fragments_created += 1
           #         print(f"🔧 CUSTOM DEBUG: ✅ Created custom fragment: Fuc1(-H2O)-B")
                    
                    # Demethylated fucose - FIXED: Remove _ion_charge to allow multiple charge states
                    demethylated_fuc = fragment.copy()
                    demethylated_fuc['_custom_label'] = 'Fuc1(-CH3)-B'
                    demethylated_fuc['_mass_adjustment'] = -methyl_mass
                    # REMOVED: demethylated_fuc['_ion_charge'] = '1H+'  # This was forcing only 1H+
                    demethylated_fuc['_is_custom'] = True
                    demethylated_fuc['_custom_type'] = 'demethylation'
                    working_fragments['b_ions'].append(demethylated_fuc)
                    custom_fragments_created += 1
            #        print(f"🔧 CUSTOM DEBUG: ✅ Created custom fragment: Fuc1(-CH3)-B")

        print(f"🔧 CUSTOM DEBUG: Total custom BY fragments created: {custom_fragments_created}")

        # Update extended_fragments with custom BY fragments if BY output is enabled
        if generate_glycan_by_ions:
            extended_fragments = working_fragments.copy()
            print(f"🔧 CUSTOM DEBUG: Added custom BY fragments to output (generate_glycan_by_ions=True)")
        else:
            print(f"🔧 CUSTOM DEBUG: Custom BY fragments kept internal only (generate_glycan_by_ions=False)")
    
        # Generate C/Z fragments from custom fragments if requested
    if generate_cz_glycan_fragment:
        #print(f"🔧 CUSTOM DEBUG: Starting C/Z conversion of custom fragments")
        
        # Count custom fragments before C/Z conversion
        custom_by_count = 0
        for fragment_type, fragments_list in working_fragments.items():
            for frag in fragments_list:
                if frag.get('_is_custom'):
                    custom_by_count += 1
        
       # print(f"🔧 CUSTOM DEBUG: Found {custom_by_count} custom BY fragments for C/Z conversion")
        
        # First, generate regular C/Z fragments
        regular_cz_fragments = generate_glycan_cz_fragments(
            working_fragments, glycan_code, modification_type, peptide, 
            use_cam=use_cam, fixed_mods=fixed_mods, variable_mods=variable_mods, mod_string=mod_string,
            generate_by_ions=generate_glycan_by_ions,
            generate_cz_glycan_fragment=generate_cz_glycan_fragment
        )
        
        # Then, generate CUSTOM C/Z fragments using the helper function
        custom_cz_fragments = generate_custom_glycan_cz_fragments(
            working_fragments, glycan_code, modification_type, peptide,
            use_cam=use_cam, fixed_mods=fixed_mods, variable_mods=variable_mods,
            mod_string=mod_string
        )
        
        # Merge the custom C/Z fragments with the regular C/Z fragments
        for fragment_type, custom_fragments_list in custom_cz_fragments.items():
            if custom_fragments_list:
                if fragment_type not in regular_cz_fragments:
                    regular_cz_fragments[fragment_type] = []
                regular_cz_fragments[fragment_type].extend(custom_fragments_list)
        #        print(f"🔧 CUSTOM CZ: Added {len(custom_fragments_list)} custom {fragment_type}")
        
        # Count and add all fragments to extended_fragments
        total_custom_cz_count = 0
        for fragment_type, fragments_list in regular_cz_fragments.items():
            # Skip BY types if BY output is disabled
            if fragment_type in ['b_ions', 'y_ions', 'by_ions', 'yy_ions'] and not generate_glycan_by_ions:
         #       print(f"🔧 CUSTOM DEBUG: Skipping {fragment_type} in output (generate_glycan_by_ions=False)")
                continue
            
            # Count custom fragments in this type
            custom_count_in_type = sum(1 for frag in fragments_list if frag.get('_is_custom'))
            if custom_count_in_type > 0:
                total_custom_cz_count += custom_count_in_type
          #      print(f"🔧 CUSTOM DEBUG: Found {custom_count_in_type} custom fragments in {fragment_type}")
            
            # Add to extended fragments
            if fragment_type not in extended_fragments:
                extended_fragments[fragment_type] = []
            extended_fragments[fragment_type].extend(fragments_list)
        
      #  print(f"🔧 CUSTOM DEBUG: Total custom C/Z fragments created: {total_custom_cz_count}")
        # Final count of all custom fragments
        total_custom_count = 0
        for fragment_type, fragments_list in extended_fragments.items():
            type_custom_count = sum(1 for frag in fragments_list if frag.get('_is_custom'))
            #if type_custom_count > 0:
                #print(f"🔧 CUSTOM DEBUG: {fragment_type}: {type_custom_count} custom fragments")
            total_custom_count += type_custom_count
        
        print(f"🔧 CUSTOM DEBUG: TOTAL custom fragments in extended_fragments: {total_custom_count}")
    
    else:
        print(f"🔧 CUSTOM DEBUG: C/Z conversion disabled (generate_cz_glycan_fragment=False)")
    
        print(f"🔧 BYY CUSTOM DEBUG: Final extended_fragments:")
    for frag_type, frags in extended_fragments.items():
        print(f"🔧 BYY CUSTOM DEBUG:   {frag_type}: {len(frags)} fragments")
    
    return extended_fragments

def add_custom_peptide_fragments(peptide_fragments, peptide_sequence, modification_type=6, 
                                include_peptide_byy=False, generate_cz_peptide_fragment=False):
    """Add custom peptide fragments with neutral losses:
       - b/y ions - H2O (water loss from Ser, Thr, Glu, Asp)
       - b/y ions - NH3 (ammonia loss from Lys, Arg, Asn, Gln)
       - b/y ions - CO2 (carbon dioxide loss from Glu, Asp)
       - b/y ions - CH4OS (methylsulfenic acid loss from oxidized Met)
       - b/y ions - CO (carbon monoxide loss, rare)
    """
    # Create a copy of the peptide fragments to avoid modifying the original
    extended_fragments = {
        'b_ions': peptide_fragments['b_ions'].copy(),
        'y_ions': peptide_fragments['y_ions'].copy()
    }
    
    # Define neutral loss masses
    water_mass = 18.0106      # H2O
    ammonia_mass = 17.0265    # NH3
    co2_mass = 43.9898        # CO2
    co_mass = 27.9949         # CO
    met_ox_loss = 64.0034     # CH4OS (methylsulfenic acid from Met-O)
    
    # Check peptide composition for specific residues
    peptide_upper = peptide_sequence.upper()
    has_water_loss_residues = any(aa in peptide_upper for aa in ['S', 'T', 'E', 'D'])
    has_ammonia_loss_residues = any(aa in peptide_upper for aa in ['K', 'R', 'N', 'Q'])
    has_co2_loss_residues = any(aa in peptide_upper for aa in ['E', 'D'])
    has_met = 'M' in peptide_upper
    
    # print(f"Peptide composition analysis for {peptide_sequence}:")
    # print(f"  Water loss residues (S,T,E,D): {has_water_loss_residues}")
    # print(f"  Ammonia loss residues (K,R,N,Q): {has_ammonia_loss_residues}")
    # print(f"  CO2 loss residues (E,D): {has_co2_loss_residues}")
    # print(f"  Methionine present: {has_met}")
    
    # 1. Add water loss fragments (-H2O) for peptides with Ser, Thr, Glu, Asp
    if has_water_loss_residues:
        #print(f"Adding water loss fragments for {peptide_sequence}")
        
        # Process b-ions for water loss
        for fragment in peptide_fragments['b_ions']:
            if isinstance(fragment, dict) and 'fragment_mass' in fragment:
                # Check if this fragment contains water-loss residues
                frag_sequence = fragment.get('fragment_sequence', '')
                if any(aa in frag_sequence.upper() for aa in ['S', 'T', 'E', 'D']):
                    water_loss_fragment = fragment.copy()
                    water_loss_fragment['fragment_mass'] = fragment['fragment_mass'] - water_mass
                    water_loss_fragment['fragment_name'] = f"{fragment['fragment_name']}(-H2O)"
                    # Add the loss to the fragment sequence for display in Fragment column
                    water_loss_fragment['fragment_sequence'] = f"{frag_sequence}(-H2O)"
                    water_loss_fragment['_is_custom'] = True
                    water_loss_fragment['_custom_source'] = 'water_loss'
                    extended_fragments['b_ions'].append(water_loss_fragment)
        
        # Process y-ions for water loss
        for fragment in peptide_fragments['y_ions']:
            if isinstance(fragment, dict) and 'fragment_mass' in fragment:
                # Check if this fragment contains water-loss residues
                frag_sequence = fragment.get('fragment_sequence', '')
                if any(aa in frag_sequence.upper() for aa in ['S', 'T', 'E', 'D']):
                    water_loss_fragment = fragment.copy()
                    water_loss_fragment['fragment_mass'] = fragment['fragment_mass'] - water_mass
                    water_loss_fragment['fragment_name'] = f"{fragment['fragment_name']}(-H2O)"
                    # Add the loss to the fragment sequence for display in Fragment column
                    water_loss_fragment['fragment_sequence'] = f"{frag_sequence}(-H2O)"
                    water_loss_fragment['_is_custom'] = True
                    water_loss_fragment['_custom_source'] = 'water_loss'
                    extended_fragments['y_ions'].append(water_loss_fragment)
    
     # 2. Add ammonia loss fragments (-NH3) for peptides with Lys, Arg, Asn, Gln
    if has_ammonia_loss_residues:
         #print(f"Adding ammonia loss fragments for {peptide_sequence}")
        
        # Process b-ions for ammonia loss
        for fragment in peptide_fragments['b_ions']:
            if isinstance(fragment, dict) and 'fragment_mass' in fragment:
                # Check if this fragment contains ammonia-loss residues
                frag_sequence = fragment.get('fragment_sequence', '')
                if any(aa in frag_sequence.upper() for aa in ['K', 'R', 'N', 'Q']):
                    ammonia_loss_fragment = fragment.copy()
                    ammonia_loss_fragment['fragment_mass'] = fragment['fragment_mass'] - ammonia_mass
                    ammonia_loss_fragment['fragment_name'] = f"{fragment['fragment_name']}(-NH3)"
                    # Add the loss to the fragment sequence for display in Fragment column
                    ammonia_loss_fragment['fragment_sequence'] = f"{frag_sequence}(-NH3)"
                    ammonia_loss_fragment['_is_custom'] = True
                    ammonia_loss_fragment['_custom_source'] = 'ammonia_loss'
                    extended_fragments['b_ions'].append(ammonia_loss_fragment)
        
        # # Process y-ions for ammonia loss
        # for fragment in peptide_fragments['y_ions']:
        #     if isinstance(fragment, dict) and 'fragment_mass' in fragment:
        #         # Check if this fragment contains ammonia-loss residues
        #         frag_sequence = fragment.get('fragment_sequence', '')
        #         if any(aa in frag_sequence.upper() for aa in ['K', 'R', 'N', 'Q']):
        #             ammonia_loss_fragment = fragment.copy()
        #             ammonia_loss_fragment['fragment_mass'] = fragment['fragment_mass'] - ammonia_mass
        #             ammonia_loss_fragment['fragment_name'] = f"{fragment['fragment_name']}(-NH3)"
        #             # Add the loss to the fragment sequence for display in Fragment column
        #             ammonia_loss_fragment['fragment_sequence'] = f"{frag_sequence}(-NH3)"
        #             ammonia_loss_fragment['_is_custom'] = True
        #             ammonia_loss_fragment['_custom_source'] = 'ammonia_loss'
        #             extended_fragments['y_ions'].append(ammonia_loss_fragment)
    
    # 3. Add CO2 loss fragments for peptides with Glu, Asp
    if has_co2_loss_residues:
        #print(f"Adding CO2 loss fragments for {peptide_sequence}")
        
        # Process b-ions for CO2 loss
        for fragment in peptide_fragments['b_ions']:
            if isinstance(fragment, dict) and 'fragment_mass' in fragment:
                # Check if this fragment contains CO2-loss residues
                frag_sequence = fragment.get('fragment_sequence', '')
                if any(aa in frag_sequence.upper() for aa in ['E', 'D']):
                    co2_loss_fragment = fragment.copy()
                    co2_loss_fragment['fragment_mass'] = fragment['fragment_mass'] - co2_mass
                    co2_loss_fragment['fragment_name'] = f"{fragment['fragment_name']}(-CO2)"
                    # Add the loss to the fragment sequence for display in Fragment column
                    co2_loss_fragment['fragment_sequence'] = f"{frag_sequence}(-CO2)"
                    co2_loss_fragment['_is_custom'] = True
                    co2_loss_fragment['_custom_source'] = 'co2_loss'
                    extended_fragments['b_ions'].append(co2_loss_fragment)
        
        # Process y-ions for CO2 loss
        for fragment in peptide_fragments['y_ions']:
            if isinstance(fragment, dict) and 'fragment_mass' in fragment:
                # Check if this fragment contains CO2-loss residues
                frag_sequence = fragment.get('fragment_sequence', '')
                if any(aa in frag_sequence.upper() for aa in ['E', 'D']):
                    co2_loss_fragment = fragment.copy()
                    co2_loss_fragment['fragment_mass'] = fragment['fragment_mass'] - co2_mass
                    co2_loss_fragment['fragment_name'] = f"{fragment['fragment_name']}(-CO2)"
                    # Add the loss to the fragment sequence for display in Fragment column
                    co2_loss_fragment['fragment_sequence'] = f"{frag_sequence}(-CO2)"
                    co2_loss_fragment['_is_custom'] = True
                    co2_loss_fragment['_custom_source'] = 'co2_loss'
                    extended_fragments['y_ions'].append(co2_loss_fragment)
    
    # 4. Add methylsulfenic acid loss fragments (-CH4OS) for oxidized methionine
    if has_met:
        #print(f"Adding methylsulfenic acid loss fragments for {peptide_sequence} (potential Met oxidation)")
        
        # Process b-ions for Met-O loss
        for fragment in peptide_fragments['b_ions']:
            if isinstance(fragment, dict) and 'fragment_mass' in fragment:
                # Check if this fragment contains methionine
                frag_sequence = fragment.get('fragment_sequence', '')
                if 'M' in frag_sequence.upper():
                    met_ox_loss_fragment = fragment.copy()
                    met_ox_loss_fragment['fragment_mass'] = fragment['fragment_mass'] - met_ox_loss
                    met_ox_loss_fragment['fragment_name'] = f"{fragment['fragment_name']}(-CH4OS)"
                    # Add the loss to the fragment sequence for display in Fragment column
                    met_ox_loss_fragment['fragment_sequence'] = f"{frag_sequence}(-CH4OS)"
                    met_ox_loss_fragment['_is_custom'] = True
                    met_ox_loss_fragment['_custom_source'] = 'met_ox_loss'
                    extended_fragments['b_ions'].append(met_ox_loss_fragment)
        
        # Process y-ions for Met-O loss
        for fragment in peptide_fragments['y_ions']:
            if isinstance(fragment, dict) and 'fragment_mass' in fragment:
                # Check if this fragment contains methionine
                frag_sequence = fragment.get('fragment_sequence', '')
                if 'M' in frag_sequence.upper():
                    met_ox_loss_fragment = fragment.copy()
                    met_ox_loss_fragment['fragment_mass'] = fragment['fragment_mass'] - met_ox_loss
                    met_ox_loss_fragment['fragment_name'] = f"{fragment['fragment_name']}(-CH4OS)"
                    # Add the loss to the fragment sequence for display in Fragment column
                    met_ox_loss_fragment['fragment_sequence'] = f"{frag_sequence}(-CH4OS)"
                    met_ox_loss_fragment['_is_custom'] = True
                    met_ox_loss_fragment['_custom_source'] = 'met_ox_loss'
                    extended_fragments['y_ions'].append(met_ox_loss_fragment)
    
    # 5. Add CO loss fragments (rare, but possible)
    #print(f"Adding CO loss fragments for {peptide_sequence} (rare neutral loss)")
    
    # Process b-ions for CO loss (can occur from any fragment)
    for fragment in peptide_fragments['b_ions']:
        if isinstance(fragment, dict) and 'fragment_mass' in fragment:
            frag_sequence = fragment.get('fragment_sequence', '')
            co_loss_fragment = fragment.copy()
            co_loss_fragment['fragment_mass'] = fragment['fragment_mass'] - co_mass
            co_loss_fragment['fragment_name'] = f"{fragment['fragment_name']}(-CO)"
            # Add the loss to the fragment sequence for display in Fragment column
            co_loss_fragment['fragment_sequence'] = f"{frag_sequence}(-CO)"
            co_loss_fragment['_is_custom'] = True
            co_loss_fragment['_custom_source'] = 'co_loss'
            extended_fragments['b_ions'].append(co_loss_fragment)
    
    # Process y-ions for CO loss (can occur from any fragment)
    for fragment in peptide_fragments['y_ions']:
        if isinstance(fragment, dict) and 'fragment_mass' in fragment:
            frag_sequence = fragment.get('fragment_sequence', '')
            co_loss_fragment = fragment.copy()
            co_loss_fragment['fragment_mass'] = fragment['fragment_mass'] - co_mass
            co_loss_fragment['fragment_name'] = f"{fragment['fragment_name']}(-CO)"
            # Add the loss to the fragment sequence for display in Fragment column
            co_loss_fragment['fragment_sequence'] = f"{frag_sequence}(-CO)"
            co_loss_fragment['_is_custom'] = True
            co_loss_fragment['_custom_source'] = 'co_loss'
            extended_fragments['y_ions'].append(co_loss_fragment)
    
    # Generate C/Z fragments from custom peptide fragments if requested
    if generate_cz_peptide_fragment:
       # print(f"DEBUG: add_custom_peptide_fragments generating C/Z custom peptide fragments")
        # Generate C/Z fragments from custom peptide fragments
        cz_custom_fragments = generate_peptide_cz_fragments(
            extended_fragments, '', peptide_sequence, generate_bzz=False
        )
        
        # These should be added as individual c_ions and z_ions, not as a combined type
        for cz_frag in cz_custom_fragments:
            # Tag as custom fragment
            cz_frag['_is_custom'] = True
            cz_frag['_custom_source'] = 'cz_conversion'
            
            # Add to appropriate fragment type based on FragmentType
            if cz_frag['FragmentType'] == 'c':
                if 'c_ions' not in extended_fragments:
                    extended_fragments['c_ions'] = []
                extended_fragments['c_ions'].append(cz_frag)
            elif cz_frag['FragmentType'] == 'z':
                if 'z_ions' not in extended_fragments:
                    extended_fragments['z_ions'] = []
                extended_fragments['z_ions'].append(cz_frag)
        
        # Tag C/Z custom fragments and merge
        for cz_frag in cz_custom_fragments:
            # Tag as custom fragment
            cz_frag['_is_custom'] = True
            cz_frag['_custom_source'] = 'cz_conversion'
        
        # Add to extended fragments as formatted fragments (they're already formatted)
        if not hasattr(extended_fragments, 'cz_peptide_fragments'):
            extended_fragments['cz_peptide_fragments'] = []
        extended_fragments['cz_peptide_fragments'].extend(cz_custom_fragments)
    else:
        print(f"DEBUG: add_custom_peptide_fragments NOT generating C/Z custom peptide fragments (generate_cz_peptide_fragment=False)")
    
    return extended_fragments

def _add_byy_fragment(fragment, unique_keys, extended_fragments, prefix, suffix, charges):
    """Helper function to add a BYY fragment with proper labeling and deduplication"""
    #print(f"🔧 BYY DEBUG: _add_byy_fragment called with fragment: {fragment}")
    
    comp_tuple = tuple(sorted(
        (k, v) for k, v in fragment.items()
        if k in ['HexNAc', 'Hex', 'Fuc', 'NeuAc', 'NeuGc'] and v > 0
    ))
    
    #print(f"🔧 BYY DEBUG: Composition tuple: {comp_tuple}")
    
    added_count = 0
    for charge in charges:
        key = (comp_tuple, charge)
        #print(f"🔧 BYY DEBUG: Checking key {key} for charge {charge}")
        
        if key in unique_keys:
            #print(f"🔧 BYY DEBUG: Key {key} already exists, skipping")
            continue
        
        unique_keys.add(key)
        comp_parts = []
        for mono in ['HexNAc', 'Hex', 'Fuc', 'NeuAc', 'NeuGc']:
            if fragment.get(mono, 0) > 0:
                comp_parts.append(f"{mono}{fragment[mono]}")
        
        fragment_name = f"{prefix}-{'-'.join(comp_parts)}-{suffix}"
        charged_fragment = fragment.copy()
        charged_fragment['_custom_label'] = fragment_name
        charged_fragment['_triple_cleavage'] = True
        charged_fragment['_ion_charge'] = f"{charge}H+"
        
        # FIXED: Ensure extended_fragments['byy_ions'] exists and is a list
        if 'byy_ions' not in extended_fragments:
            extended_fragments['byy_ions'] = []
        
        extended_fragments['byy_ions'].append(charged_fragment)
        added_count += 1
        
        #print(f"🔧 BYY DEBUG: Added BYY fragment: {fragment_name} with charge {charge}H+")
    
    #print(f"🔧 BYY DEBUG: Total fragments added for this composition: {added_count}")
    return added_count

def generate_byy_ions(unique_fragments, glycan_code, modification_type=6, peptide=None):
    """
    Generate BYY ions - triple cleavage fragments derived from YY ions with additional
    cleavage of the peptide attachment point (core HexNAc), avoiding duplicates.
    Includes both single and double HexNAc cleavage scenarios.
    """
    #print(f"\n🔧 BYY DEBUG: Starting BYY ion generation for glycan {glycan_code}")
    #print(f"🔧 BYY DEBUG: Input unique_fragments keys: {list(unique_fragments.keys())}")
    
    # FIXED: Ensure all fragment types are properly initialized
    extended_fragments = {
        'b_ions': unique_fragments.get('b_ions', []).copy(),
        'y_ions': unique_fragments.get('y_ions', []).copy(),
        'by_ions': unique_fragments.get('by_ions', []).copy(),
        'yy_ions': unique_fragments.get('yy_ions', []).copy(),
        'byy_ions': []  # Always initialize as empty list
    }

    calculator = GlycanMassCalculator()
    calculator.calculate_MONO_MASSES(modification_type)
    hexnac, hex, fuc, neuac, neugc = calculator.parse_glycan_code(glycan_code)
    
    #print(f"🔧 BYY DEBUG: Glycan composition - HexNAc:{hexnac}, Hex:{hex}, Fuc:{fuc}, NeuAc:{neuac}")

    is_oglycan = False
    if hexnac == 1 and hexnac + hex + fuc + neuac + neugc <= 4:
        is_oglycan = True
        #print(f"🔧 BYY DEBUG: Detected O-glycan, total monosaccharides: {hexnac + hex + fuc + neuac + neugc}")
        if hexnac + hex + fuc + neuac + neugc <= 4:
            #print(f"🔧 BYY DEBUG: O-glycan too small for BYY generation, skipping")
            return extended_fragments

    # Use a set to track unique (composition, charge) tuples to avoid duplicates
    unique_byy_keys = set()
    yy_ions = unique_fragments.get('yy_ions', [])
    #print(f"🔧 BYY DEBUG: Input YY ions count: {len(yy_ions)}")

    # 1. Generate BYY ions from YY ions with single HexNAc cleavage
    byy_generated_count = 0
    for i, fragment in enumerate(yy_ions):
        #print(f"🔧 BYY DEBUG: Processing YY fragment #{i}: {fragment}")
        
        if isinstance(fragment, dict) and fragment.get('HexNAc', 0) >= 1:
            #print(f"🔧 BYY DEBUG: YY fragment has {fragment.get('HexNAc', 0)} HexNAc units")
            
            # Create fragments with one HexNAc removed
            byy_fragment = fragment.copy()
            original_hexnac = byy_fragment.get('HexNAc', 0)
            byy_fragment['HexNAc'] = max(0, original_hexnac - 1)
            
            #print(f"🔧 BYY DEBUG: Created BYY fragment with HexNAc reduced from {original_hexnac} to {byy_fragment['HexNAc']}")
            
            total_monosaccharides = sum(byy_fragment.get(mono, 0) for mono in ['HexNAc', 'Hex', 'Fuc', 'NeuAc', 'NeuGc'])
            #print(f"🔧 BYY DEBUG: Total monosaccharides in BYY fragment: {total_monosaccharides}")
            
            if total_monosaccharides > 0:
                # FIXED: Pass the correct parameters and handle the return value properly
                try:
                    added_count = _add_byy_fragment(byy_fragment, unique_byy_keys, extended_fragments, "YY", "B", [1, 2, 3])
                    if added_count is not None:  # Check if function returned a valid count
                        byy_generated_count += added_count
                        #print(f"🔧 BYY DEBUG: Added {added_count} BYY fragments (single HexNAc cleavage)")
                    #else:
                        #print(f"🔧 BYY DEBUG: _add_byy_fragment returned None, skipping count update")
                except Exception as e:
                    #print(f"🔧 BYY DEBUG: Error in _add_byy_fragment: {e}")
                    continue
            #else:
                #print(f"🔧 BYY DEBUG: Skipping empty BYY fragment")
            
            # 2. Create fragments with TWO HexNAc removed (for N-glycans with 2+ HexNAc)
            if fragment.get('HexNAc', 0) >= 2 and not is_oglycan:
                #print(f"🔧 BYY DEBUG: Attempting double HexNAc cleavage (original has {fragment.get('HexNAc', 0)} HexNAc)")
                
                byy_fragment2 = fragment.copy()
                original_hexnac2 = byy_fragment2.get('HexNAc', 0)
                byy_fragment2['HexNAc'] = max(0, original_hexnac2 - 2)
                
                #print(f"🔧 BYY DEBUG: Created double-cleavage BYY fragment with HexNAc reduced from {original_hexnac2} to {byy_fragment2['HexNAc']}")
                
                total_monosaccharides2 = sum(byy_fragment2.get(mono, 0) for mono in ['HexNAc', 'Hex', 'Fuc', 'NeuAc', 'NeuGc'])
                #print(f"🔧 BYY DEBUG: Total monosaccharides in double-cleavage BYY fragment: {total_monosaccharides2}")
                
                if total_monosaccharides2 > 0:
                    # FIXED: Same fix for double cleavage
                    try:
                        added_count2 = _add_byy_fragment(byy_fragment2, unique_byy_keys, extended_fragments, "YY", "B", [1, 2, 3])
                        if added_count2 is not None:
                            byy_generated_count += added_count2
                            #print(f"🔧 BYY DEBUG: Added {added_count2} BYY fragments (double HexNAc cleavage)")
                        #else:
                         #   print(f"🔧 BYY DEBUG: _add_byy_fragment returned None for double cleavage, skipping count update")
                    except Exception as e:
                        #print(f"🔧 BYY DEBUG: Error in _add_byy_fragment (double cleavage): {e}")
                        continue
                #else:
                    #print(f"🔧 BYY DEBUG: Skipping empty double-cleavage BYY fragment")
        #else:
           # print(f"🔧 BYY DEBUG: YY fragment #{i} does not have sufficient HexNAc for BYY generation")

    # print(f"🔧 BYY DEBUG: Total BYY fragments generated: {byy_generated_count}")
    # print(f"🔧 BYY DEBUG: Final BYY ions list length: {len(extended_fragments['byy_ions'])}")
    
    # Debug: Print first few BYY fragments
    #for i, byy_frag in enumerate(extended_fragments['byy_ions'][:3]):
        #print(f"🔧 BYY DEBUG: BYY fragment #{i}: {byy_frag}")

    return extended_fragments
 
def generate_extended_fragment_table(unique_fragments, glycan_code, modification_type=6, peptide=None, 
                                   use_cam=False, fixed_mods=None, variable_mods=None, mod_string=None,
                                   include_byy=False, generate_cz_glycan_fragment=False,
                                   generate_glycan_by_ions=True, generate_peptide_by_ions=True,
                                   generate_cz_peptide_fragment=False):
    """Generate fragment table with filtering BEFORE deduplication"""
    #print(f"🔧 BYY EXTENDED DEBUG: generate_extended_fragment_table called")
    #print(f"🔧 BYY EXTENDED DEBUG:   include_byy: {include_byy}")
    #print(f"🔧 BYY EXTENDED DEBUG:   generate_cz_glycan_fragment: {generate_cz_glycan_fragment}")
    #print(f"🔧 BYY EXTENDED DEBUG:   generate_glycan_by_ions: {generate_glycan_by_ions}")
    
    # First add custom fragments (this includes BYY and C/Z generation)
    extended_fragments = add_custom_fragments(
        unique_fragments, glycan_code, modification_type, peptide, 
        include_byy=include_byy, generate_cz_glycan_fragment=generate_cz_glycan_fragment,
        generate_glycan_by_ions=generate_glycan_by_ions  # Pass the setting
    )
    
    #print(f"🔧 BYY EXTENDED DEBUG: After add_custom_fragments:")
    # for frag_type, frags in extended_fragments.items():
    #     print(f"🔧 BYY EXTENDED DEBUG:   {frag_type}: {len(frags)} fragments")
    
    # Generate standard fragment table from ALL fragments
    all_fragments_df = generate_fragment_table(
        extended_fragments, glycan_code, modification_type, peptide,
        use_cam=use_cam, fixed_mods=fixed_mods, 
        variable_mods=variable_mods, mod_string=mod_string
    )
    
    #print(f"🔧 BYY EXTENDED DEBUG: Generated fragment table with {len(all_fragments_df)} fragments")
    
    # Check BYY fragments in the table
    if 'FragmentType' in all_fragments_df.columns:
        byy_in_table = len(all_fragments_df[all_fragments_df['FragmentType'] == 'byy'])
        #print(f"🔧 BYY EXTENDED DEBUG: Fragment table contains {byy_in_table} BYY fragments")
    
    # CRITICAL: Apply fragment type filtering BEFORE deduplication
    filtered_df = filter_fragments_by_generation_settings(
        all_fragments_df,
        generate_glycan_by_ions=generate_glycan_by_ions,
        generate_peptide_by_ions=generate_peptide_by_ions,
        generate_cz_glycan_fragment=generate_cz_glycan_fragment,
        generate_cz_peptide_fragment=generate_cz_peptide_fragment
    )
    
    print(f"🔧 BYY EXTENDED DEBUG: After filtering: {len(filtered_df)} fragments")
    
    # Check BYY fragments after filtering
    if 'FragmentType' in filtered_df.columns:
        byy_after_filter = len(filtered_df[filtered_df['FragmentType'] == 'byy'])
        #print(f"🔧 BYY EXTENDED DEBUG: After filtering contains {byy_after_filter} BYY fragments")
    
    # THEN apply deduplication to the filtered fragments
    final_df = deduplicate_fragments_by_mass(filtered_df)
    
    #print(f"🔧 BYY EXTENDED DEBUG: After deduplication: {len(final_df)} fragments")
    
    # Final BYY count check
    if 'FragmentType' in final_df.columns:
        byy_final = len(final_df[final_df['FragmentType'] == 'byy'])
        #print(f"🔧 BYY EXTENDED DEBUG: Final result contains {byy_final} BYY fragments")
    
    print(f"🔧 BYY EXTENDED DEBUG: generate_extended_fragment_table returning {len(final_df)} fragments")
    return final_df

def generate_peptide_fragments(peptide_sequence, glycan_code, calculator=None, modification_type=6, 
                        use_cam=False, fixed_mods=None, variable_mods=None, mod_string=None,
                        enable_custom_peptide_fragments=False, generate_cz_peptide_fragment=False):
    """
    Generate peptide b and y ion fragments using an existing calculator that already
    has the modification information.
    """
    print(f"Generating peptide fragments for: {peptide_sequence}")
    print(f"Custom peptide fragments enabled: {enable_custom_peptide_fragments}")
    
    # If no calculator is provided, create one
    if calculator is None:
        print("Creating new calculator for peptide fragmentation")
        calculator = GlycanMassCalculator(
            modification_type=modification_type,
            use_cam=use_cam,
            fixed_mods=fixed_mods or [],
            variable_mods=variable_mods or [],
            mod_string=mod_string,
            peptide=peptide_sequence
        )
        # Calculate peptide mass to ensure modifications are applied and stored
        calculator.calculate_peptide_mass(
            peptide_sequence, 
            use_cam=use_cam, 
            fixed_mods=fixed_mods, 
            variable_mods=variable_mods, 
            mod_string=mod_string
        )
    
    # Create fragment results storage
    fragments = {
        'b_ions': [],
        'y_ions': []
    }
    
    # Calculate b-ion masses (N-terminus to each position)
    cumulative_mass = 0.0  # Initialize (b-ions don't include water)
    
    for i, aa in enumerate(peptide_sequence):
        # Get the amino acid mass with any modifications already applied
        aa_mass = calculator.get_amino_acid_mass(aa, i, peptide_sequence)
        cumulative_mass += aa_mass
        
        # Store current b-ion (except for position 0 - that would be empty)
        if i >= 0:
            b_ion = {
                'fragment_name': f"b{i+1}",
                'fragment_mass': cumulative_mass + calculator.PROTON_MASS,  # Add proton for +1 charge
                'fragment_sequence': peptide_sequence[:i+1],  # FIXED: This is the actual amino acid sequence
                'fragment_position': i+1,
                'fragment_type': 'b',
                # FIXED: Add missing fields that generate_peptide_cz_fragments expects
                'position': i+1,
                'mass': cumulative_mass + calculator.PROTON_MASS,
                'sequence': peptide_sequence[:i+1]
            }
            fragments['b_ions'].append(b_ion)
    
    # Calculate y-ion masses (C-terminus to each position, reversed direction)
    cumulative_mass = 18.0153  # Start with water mass for y ions
    
    # Loop through all positions to generate ALL y-ions (including the full peptide as y<n>)
    for i in range(len(peptide_sequence)-1, -1, -1):  # Changed loop range to include first position
        aa = peptide_sequence[i]
        # Get the amino acid mass with any modifications already applied
        aa_mass = calculator.get_amino_acid_mass(aa, i, peptide_sequence)
        cumulative_mass += aa_mass
        
        # Store current y-ion - including the full peptide (y<n>)
        y_position = len(peptide_sequence) - i
        y_ion = {
            'fragment_name': f"y{y_position}",
            'fragment_mass': cumulative_mass + calculator.PROTON_MASS,  # Add proton for +1 charge
            'fragment_sequence': peptide_sequence[i:],  # FIXED: This is the actual amino acid sequence
            'fragment_position': y_position,
            'fragment_type': 'y',
            # FIXED: Add missing fields that generate_peptide_cz_fragments expects
            'position': y_position,
            'mass': cumulative_mass + calculator.PROTON_MASS,
            'sequence': peptide_sequence[i:]
        }
        fragments['y_ions'].append(y_ion)
    
    # Add custom peptide fragments if requested
    if enable_custom_peptide_fragments:
        print(f"Adding custom peptide fragments with neutral losses")
        fragments = add_custom_peptide_fragments(
            fragments, 
            peptide_sequence, 
            modification_type=modification_type,
            generate_cz_peptide_fragment=generate_cz_peptide_fragment
        )
    
    return fragments

def generate_glycan_cz_fragments(unique_fragments, glycan_code, modification_type=6, peptide=None, 
                               use_cam=False, fixed_mods=None, variable_mods=None, mod_string=None,
                               generate_by_ions=True, generate_cz_glycan_fragment=True):
    """
    Generate C/Z fragments from existing B/Y fragments for glycans.
    
    Args:
        unique_fragments: Dictionary with glycan fragment types
        glycan_code: Glycan composition code
        modification_type: Type of modification
        peptide: Peptide sequence if applicable
        use_cam: Whether to use carbamidomethylation
        fixed_mods: Fixed modifications
        variable_mods: Variable modifications
        mod_string: Modification string
        generate_by_ions: Whether to include by_ions in the output (for glycan BY generation)
        generate_cz_glycan_fragment: Whether to generate BZZ ions from CZZ ions
        
    Returns:
        Dictionary with additional C/Z fragment types
    """
    # Initialize calculator
    calculator = GlycanMassCalculator(
        modification_type=modification_type,
        use_cam=use_cam,
        fixed_mods=fixed_mods,
        variable_mods=variable_mods,
        mod_string=mod_string,
        peptide=peptide
    )
    
    # Mass differences for glycan C/Z fragments
    GLYCAN_C_MASS_DIFF = 18.026   # For C ions from B ions
    GLYCAN_Z_MASS_DIFF = -18.026  # For Z ions from Y ions
    ZZ_MASS_DIFF = -36.0211       # For ZZ ions from YY ions
    CZZ_MASS_DIFF = -18.026       # For CZZ ions from BYY ions
    BZZ_FROM_CZZ_DIFF = -18.0105  # For BZZ ions from CZZ ions (subtracting 18.0105)
        
    # Handle the case where BY ions are needed for CZ conversion but not for output
    working_fragments = unique_fragments.copy()
    
    # Check if we need to generate BY ions internally for CZ conversion
    if generate_cz_glycan_fragment and not generate_by_ions:
        # Check if BY ions are missing or insufficient
        missing_by_types = []
        for by_type in ['by_ions', 'yy_ions']:
            if by_type not in working_fragments or len(working_fragments[by_type]) == 0:
                missing_by_types.append(by_type)
        
        if missing_by_types:
            print("BZZ DEBUG: Generating BY ions internally using glycan structure prediction...")
            
            # Generate BY ions using existing functions
            try:
                # Parse glycan code to get structure info
                hexnac, hex, fuc, neuac, neugc = calculator.parse_glycan_code(glycan_code)
                
                # Determine glycan type (simplified logic)
                glycan_type = "O" if (hexnac <= 2 and hex <= 1) else "N"
                
                # Generate structures and fragments
                results, glycan_obj = predict_glycan_structure(glycan_code, glycan_type, peptide)
                
                if results:
                    # Collect fragments from all structures
                    temp_by_fragments = collect_unique_fragments(
                        results, 
                        modification_type=modification_type, 
                        peptide=peptide, 
                        use_cam=use_cam, 
                        fixed_mods=fixed_mods, 
                        variable_mods=variable_mods, 
                        mod_string=mod_string
                    )
                    
                    # Add the missing BY ion types to working_fragments
                    for by_type in missing_by_types:
                        if by_type in temp_by_fragments:
                            working_fragments[by_type] = temp_by_fragments[by_type]
                
                # Also generate BYY ions if needed for CZZ conversion
                if 'byy_ions' not in working_fragments or len(working_fragments['byy_ions']) == 0:
                    extended_with_byy = generate_byy_ions(working_fragments, glycan_code, modification_type, peptide)
                    working_fragments['byy_ions'] = extended_with_byy.get('byy_ions', [])
                    
            except Exception as e:
                print(f"BZZ DEBUG: Error generating BY ions internally: {e}")
                # Continue with whatever fragments we have
        else:
            print("BZZ DEBUG: BY ions already present in working_fragments")
    
    # Create extended fragments dictionary
    extended_fragments = {
        'c_ions': [],    # New
        'z_ions': [],    # New
        'cz_ions': [],   # New
        'zz_ions': [],   # New
        'czz_ions': [],  # New
        'bzz_ions': []   # New (when both cz and by are enabled for GLYCANS only)
    }
    
    # Only include BY ions in output if generate_by_ions is True
    if generate_by_ions:
        extended_fragments.update({
            'b_ions': unique_fragments.get('b_ions', []).copy(),
            'y_ions': unique_fragments.get('y_ions', []).copy(),
            'by_ions': unique_fragments.get('by_ions', []).copy(),
            'yy_ions': unique_fragments.get('yy_ions', []).copy(),
        })
        print(f"BZZ DEBUG: Included BY ions in output")
    else:
        print(f"BZZ DEBUG: generate_by_ions=False, not including BY ions in output")
        
    # Use sets to track unique fragments and prevent duplicates
    unique_c_fragments = set()
    unique_z_fragments = set()
    unique_cz_fragments = set()
    unique_zz_fragments = set()
    unique_czz_fragments = set()
    unique_bzz_fragments = set()
    
    # Helper function to create fragment label based on source fragment
    def create_fragment_label(source_fragment, source_type, target_type):
        """Create proper fragment label by copying from source and replacing type"""
        # Get the composition parts (excluding metadata)
        comp_parts = []
        for key in ['HexNAc', 'Hex', 'Fuc', 'NeuAc', 'NeuGc']:
            if key in source_fragment and source_fragment[key] > 0:
                comp_parts.append(f"{key}{source_fragment[key]}")
        
        composition = "-".join(comp_parts)
        
        # Handle different fragment type conversions
        if target_type == 'c' and source_type == 'b':
            # C ions from B ions: B-composition becomes composition-C
            return f"{composition}-C"
        elif target_type == 'z' and source_type == 'y':
            # Z ions from Y ions: handle -PEP correctly
            if modification_type == 6 and peptide:
                return f"Z-{composition}-PEP"  # Keep -PEP for glycopeptides
            else:
                return f"Z-{composition}"
        elif target_type == 'cz' and source_type == 'by':
            # CZ ions from BY ions: keep the same format as BY but change to CZ
            return f"Z-{composition}-C"
        elif target_type == 'zz' and source_type == 'yy':
            # ZZ ions from YY ions: handle -PEP correctly
            if modification_type == 6 and peptide:
                return f"ZZ-{composition}-PEP"  # Keep -PEP for glycopeptides
            else:
                return f"ZZ-{composition}"
        elif target_type == 'czz' and source_type == 'byy':
            # CZZ ions from BYY ions: change BYY to CZZ
            return f"ZZ-{composition}-C"
        elif target_type == 'bzz' and source_type == 'czz':
            # BZZ ions from CZZ ions: change CZZ to BZZ
            return f"ZZ-{composition}-B"
        else:
            return f"{target_type.upper()}-{composition}"
    
    # Generate C ions from B ions (use working_fragments for internal generation compatibility)
    for fragment in working_fragments.get('b_ions', []):
        if isinstance(fragment, dict) and sum(fragment.get(key, 0) for key in ['HexNAc', 'Hex', 'Fuc', 'NeuAc', 'NeuGc']) > 0:
            base_mass = calculator.calculate_fragment_mass(fragment, 'b_ions', peptide=peptide)
            
            for charge in [1, 2, 3]:
                c_mass = base_mass + GLYCAN_C_MASS_DIFF
                mz = calculator.calculate_mz(c_mass, charge)
                
                # Create unique key for deduplication
                fragment_key = (tuple(sorted((k, v) for k, v in fragment.items() 
                                           if k in ['HexNAc', 'Hex', 'Fuc', 'NeuAc', 'NeuGc'] and v > 0)), charge)
                
                if fragment_key not in unique_c_fragments:
                    unique_c_fragments.add(fragment_key)
                    
                    c_fragment = fragment.copy()
                    c_fragment['_fragment_type'] = 'c'  
                    c_fragment['_mass'] = c_mass
                    c_fragment['_mz'] = mz
                    c_fragment['_charge'] = charge
                    c_fragment['_custom_label'] = create_fragment_label(fragment, 'b', 'c')
                    extended_fragments['c_ions'].append(c_fragment)
    
    print(f"BZZ DEBUG: Generated {len(extended_fragments['c_ions'])} C ions")
    
    # Generate Z ions from Y ions (use working_fragments for internal generation compatibility)
    for fragment in working_fragments.get('y_ions', []):
        if isinstance(fragment, dict) and sum(fragment.get(key, 0) for key in ['HexNAc', 'Hex', 'Fuc', 'NeuAc', 'NeuGc']) > 0:
            base_mass = calculator.calculate_fragment_mass(fragment, 'y_ions', peptide=peptide)
            
            for charge in [1, 2, 3]:
                z_mass = base_mass + GLYCAN_Z_MASS_DIFF
                mz = calculator.calculate_mz(z_mass, charge)
                
                # Create unique key for deduplication
                fragment_key = (tuple(sorted((k, v) for k, v in fragment.items() 
                                           if k in ['HexNAc', 'Hex', 'Fuc', 'NeuAc', 'NeuGc'] and v > 0)), charge)
                
                if fragment_key not in unique_z_fragments:
                    unique_z_fragments.add(fragment_key)
                    
                    z_fragment = fragment.copy()
                    z_fragment['_fragment_type'] = 'z' 
                    z_fragment['_mass'] = z_mass
                    z_fragment['_mz'] = mz
                    z_fragment['_charge'] = charge
                    z_fragment['_custom_label'] = create_fragment_label(fragment, 'y', 'z')
                    extended_fragments['z_ions'].append(z_fragment)
    
    print(f"BZZ DEBUG: Generated {len(extended_fragments['z_ions'])} Z ions")
    
    # Generate CZ ions (same mass as BY ions) (use working_fragments)
    for fragment in working_fragments.get('by_ions', []):
        if isinstance(fragment, dict) and sum(fragment.get(key, 0) for key in ['HexNAc', 'Hex', 'Fuc', 'NeuAc', 'NeuGc']) > 0:
            base_mass = calculator.calculate_fragment_mass(fragment, 'by_ions', peptide=peptide)
            
            for charge in [1, 2, 3]:
                mz = calculator.calculate_mz(base_mass, charge)
                
                # Create unique key for deduplication
                fragment_key = (tuple(sorted((k, v) for k, v in fragment.items() 
                                           if k in ['HexNAc', 'Hex', 'Fuc', 'NeuAc', 'NeuGc'] and v > 0)), charge)
                
                if fragment_key not in unique_cz_fragments:
                    unique_cz_fragments.add(fragment_key)
                    
                    cz_fragment = fragment.copy()
                    cz_fragment['_fragment_type'] = 'cz'  
                    cz_fragment['_mass'] = base_mass
                    cz_fragment['_mz'] = mz
                    cz_fragment['_charge'] = charge
                    cz_fragment['_custom_label'] = create_fragment_label(fragment, 'by', 'cz')
                    extended_fragments['cz_ions'].append(cz_fragment)
    
    print(f"BZZ DEBUG: Generated {len(extended_fragments['cz_ions'])} CZ ions")
    
    # Generate ZZ ions from YY ions (use working_fragments)
    for fragment in working_fragments.get('yy_ions', []):
        if isinstance(fragment, dict) and sum(fragment.get(key, 0) for key in ['HexNAc', 'Hex', 'Fuc', 'NeuAc', 'NeuGc']) > 0:
            base_mass = calculator.calculate_fragment_mass(fragment, 'yy_ions', peptide=peptide)
            
            for charge in [1, 2, 3]:
                zz_mass = base_mass + ZZ_MASS_DIFF
                mz = calculator.calculate_mz(zz_mass, charge)
                
                # Create unique key for deduplication
                fragment_key = (tuple(sorted((k, v) for k, v in fragment.items() 
                                           if k in ['HexNAc', 'Hex', 'Fuc', 'NeuAc', 'NeuGc'] and v > 0)), charge)
                
                if fragment_key not in unique_zz_fragments:
                    unique_zz_fragments.add(fragment_key)
                    
                    zz_fragment = fragment.copy()
                    zz_fragment['_fragment_type'] = 'zz'  
                    zz_fragment['_mass'] = zz_mass
                    zz_fragment['_mz'] = mz
                    zz_fragment['_charge'] = charge
                    zz_fragment['_custom_label'] = create_fragment_label(fragment, 'yy', 'zz')
                    extended_fragments['zz_ions'].append(zz_fragment)
    
    print(f"BZZ DEBUG: Generated {len(extended_fragments['zz_ions'])} ZZ ions")
    
    # Generate CZZ ions from BYY ions (use working_fragments)
    byy_ions_source = working_fragments.get('byy_ions', [])
    print(f"BZZ DEBUG: Found {len(byy_ions_source)} BYY ions in working_fragments")
    
    # If not found in working_fragments, try to generate them
    if not byy_ions_source and generate_cz_glycan_fragment:
        print("BZZ DEBUG: No BYY ions found in working_fragments, generating them for C/Z conversion...")
        # Generate BYY ions using the helper function
        extended_with_byy = generate_byy_ions(working_fragments, glycan_code, modification_type, peptide)
        byy_ions_source = extended_with_byy.get('byy_ions', [])
        print(f"BZZ DEBUG: Generated {len(byy_ions_source)} BYY ions")
    
    # Generate CZZ ions from BYY ions
    czz_generated_count = 0
    if byy_ions_source:
        print(f"BZZ DEBUG: Processing {len(byy_ions_source)} BYY ions for CZZ conversion...")
        for fragment in byy_ions_source:
            if isinstance(fragment, dict) and sum(fragment.get(key, 0) for key in ['HexNAc', 'Hex', 'Fuc', 'NeuAc', 'NeuGc']) > 0:
                base_mass = calculator.calculate_fragment_mass(fragment, 'byy_ions', peptide=peptide)
                
                for charge in [1, 2, 3]:
                    czz_mass = base_mass + CZZ_MASS_DIFF
                    mz = calculator.calculate_mz(czz_mass, charge)
                    
                    # Create unique key for deduplication
                    fragment_key = (tuple(sorted((k, v) for k, v in fragment.items() 
                                               if k in ['HexNAc', 'Hex', 'Fuc', 'NeuAc', 'NeuGc'] and v > 0)), charge)
                    
                    if fragment_key not in unique_czz_fragments:
                        unique_czz_fragments.add(fragment_key)
                        
                        czz_fragment = fragment.copy()
                        czz_fragment['_fragment_type'] = 'czz'  
                        czz_fragment['_mass'] = czz_mass
                        czz_fragment['_mz'] = mz
                        czz_fragment['_charge'] = charge
                        czz_fragment['_custom_label'] = create_fragment_label(fragment, 'byy', 'czz')
                        extended_fragments['czz_ions'].append(czz_fragment)
                        czz_generated_count += 1
    
    # Generate BZZ ions from CZZ ions by subtracting 18.0105
    bzz_generated_count = 0
    # BZZ generation when CZ is enabled (regardless of BY output setting)
    if generate_cz_glycan_fragment and generate_by_ions:  
        # Use the CZZ ions we just generated
        if extended_fragments['czz_ions']:
            for i, czz_fragment in enumerate(extended_fragments['czz_ions']):
                if isinstance(czz_fragment, dict) and sum(czz_fragment.get(key, 0) for key in ['HexNAc', 'Hex', 'Fuc', 'NeuAc', 'NeuGc']) > 0:
                    # Get the CZZ mass and subtract 18.0105 to get BZZ mass
                    czz_mass = czz_fragment['_mass']
                    charge = czz_fragment['_charge']
                    
                    bzz_mass = czz_mass + BZZ_FROM_CZZ_DIFF  # Subtracting 18.0105
                    mz = calculator.calculate_mz(bzz_mass, charge)
                    
                    # Create unique key for deduplication
                    fragment_key = (tuple(sorted((k, v) for k, v in czz_fragment.items() 
                                               if k in ['HexNAc', 'Hex', 'Fuc', 'NeuAc', 'NeuGc'] and v > 0)), charge)
                    
                    if fragment_key not in unique_bzz_fragments:
                        unique_bzz_fragments.add(fragment_key)
                    
                        bzz_fragment = czz_fragment.copy()
                        bzz_fragment['_fragment_type'] = 'bzz'  
                        bzz_fragment['_mass'] = bzz_mass
                        bzz_fragment['_mz'] = mz
                        bzz_fragment['_charge'] = charge
                        bzz_fragment['_custom_label'] = create_fragment_label(czz_fragment, 'czz', 'bzz')
                        extended_fragments['bzz_ions'].append(bzz_fragment)
                        bzz_generated_count += 1
    
    print(f"\nBZZ DEBUG: Final fragment counts:")
    print(f"  C ions: {len(extended_fragments['c_ions'])}")
    print(f"  Z ions: {len(extended_fragments['z_ions'])}")
    print(f"  CZ ions: {len(extended_fragments['cz_ions'])}")
    print(f"  ZZ ions: {len(extended_fragments['zz_ions'])}")
    print(f"  CZZ ions: {len(extended_fragments['czz_ions'])}")
    print(f"  BZZ ions: {len(extended_fragments['bzz_ions'])}")
    
    # Only include BY ions in output if requested
    if generate_by_ions:
        print(f"  B ions: {len(extended_fragments.get('b_ions', []))}")
        print(f"  Y ions: {len(extended_fragments.get('y_ions', []))}")
        print(f"  BY ions: {len(extended_fragments.get('by_ions', []))}")
        print(f"  YY ions: {len(extended_fragments.get('yy_ions', []))}")
    else:
        print("  BY ions: Not included in output (generate_by_ions=False)")
    
    return extended_fragments

def generate_custom_glycan_cz_fragments(working_fragments, glycan_code, modification_type=6, 
                                       peptide=None, use_cam=True, fixed_mods=None, 
                                       variable_mods=None, mod_string=None):
    """
    Helper function to generate custom C/Z fragments from custom BY fragments
    Ensures custom fragments with neutral losses are converted to C/Z format
    C/Z fragments have the SAME mass as their corresponding BY fragments
    """
    #print(f"🔧 CUSTOM CZ: Starting custom C/Z fragment generation")
    
    # Initialize custom C/Z fragments storage
    custom_cz_fragments = {
        'c_ions': [],
        'z_ions': [],
        'cz_ions': [],
        'zz_ions': [],
        'czz_ions': [],
        'bzz_ions': []
    }
    
    # Count custom fragments found
    custom_fragments_processed = 0
    
    # 1. Convert custom B ions to custom C ions - COPY MASS DIRECTLY
    for fragment in working_fragments.get('b_ions', []):
        if fragment.get('_is_custom', False):
            #print(f"🔧 CUSTOM CZ: Processing custom B ion: {fragment.get('_custom_label', 'unlabeled')}")
            
            # Get the already calculated mass from the custom B fragment
            if '_mass_adjustment' in fragment:
                # The base mass already includes the custom adjustment
                base_mass = sum(fragment.get(mono, 0) * 203.0794 if mono == 'HexNAc' 
                               else fragment.get(mono, 0) * 162.0528 if mono == 'Hex'
                               else fragment.get(mono, 0) * 146.0579 if mono == 'Fuc'
                               else fragment.get(mono, 0) * 291.0954 if mono == 'NeuAc'
                               else 0 for mono in ['HexNAc', 'Hex', 'Fuc', 'NeuAc', 'NeuGc'])
                
                # Add the custom mass adjustment
                final_mass = base_mass + fragment['_mass_adjustment']
            else:
                # Standard Fragment_mz calculation if no custom adjustment
                final_mass = sum(fragment.get(mono, 0) * 203.0794 if mono == 'HexNAc' 
                               else fragment.get(mono, 0) * 162.0528 if mono == 'Hex'
                               else fragment.get(mono, 0) * 146.0579 if mono == 'Fuc'
                               else fragment.get(mono, 0) * 291.0954 if mono == 'NeuAc'
                               else 0 for mono in ['HexNAc', 'Hex', 'Fuc', 'NeuAc', 'NeuGc'])
            
            for charge in [1, 2, 3]:
                # FIXED: Proper m/z calculation for all charge states
                c_mass = final_mass  # C ions have the SAME mass as B ions
                mz = (c_mass + (charge * 1.0073)) / charge  # Correct m/z calculation
                
                # Create custom C ion with SAME mass as B ion
                c_fragment = fragment.copy()
                c_fragment['_mz'] = mz
                c_fragment['_mass'] = c_mass
                c_fragment['_charge'] = charge
                c_fragment['_fragment_type'] = 'c'
                
                # Update custom label for C ion
                if '_custom_label' in c_fragment:
                    original_label = c_fragment['_custom_label']
                    if '-B' in original_label:
                        c_fragment['_custom_label'] = original_label.replace('-B', '-C')
                    else:
                        c_fragment['_custom_label'] = f"{original_label}-C"
                
                custom_cz_fragments['c_ions'].append(c_fragment)
                custom_fragments_processed += 1
             #   print(f"🔧 CUSTOM CZ: ✅ Created custom C ion: {c_fragment['_custom_label']} with mass {c_mass:.4f} and m/z {mz:.4f} ({charge}H+)")
    
    # 2. Convert custom Y ions to custom Z ions - COPY MASS DIRECTLY
    for fragment in working_fragments.get('y_ions', []):
        if fragment.get('_is_custom', False):
            #print(f"🔧 CUSTOM CZ: Processing custom Y ion: {fragment.get('_custom_label', 'unlabeled')}")
            
            # Get the already calculated mass from the custom Y fragment (same logic as B)
            if '_mass_adjustment' in fragment:
                base_mass = sum(fragment.get(mono, 0) * 203.0794 if mono == 'HexNAc' 
                               else fragment.get(mono, 0) * 162.0528 if mono == 'Hex'
                               else fragment.get(mono, 0) * 146.0579 if mono == 'Fuc'
                               else fragment.get(mono, 0) * 291.0954 if mono == 'NeuAc'
                               else 0 for mono in ['HexNAc', 'Hex', 'Fuc', 'NeuAc', 'NeuGc'])
                final_mass = base_mass + fragment['_mass_adjustment']
            else:
                final_mass = sum(fragment.get(mono, 0) * 203.0794 if mono == 'HexNAc' 
                               else fragment.get(mono, 0) * 162.0528 if mono == 'Hex'
                               else fragment.get(mono, 0) * 146.0579 if mono == 'Fuc'
                               else fragment.get(mono, 0) * 291.0954 if mono == 'NeuAc'
                               else 0 for mono in ['HexNAc', 'Hex', 'Fuc', 'NeuAc', 'NeuGc'])
            
            for charge in [1, 2, 3]:
                # FIXED: Proper m/z calculation for all charge states
                z_mass = final_mass  # Z ions have the SAME mass as Y ions
                mz = (z_mass + (charge * 1.0073)) / charge  # Correct m/z calculation
                
                # Create custom Z ion with SAME mass as Y ion
                z_fragment = fragment.copy()
                z_fragment['_mz'] = mz
                z_fragment['_mass'] = z_mass
                z_fragment['_charge'] = charge
                z_fragment['_fragment_type'] = 'z'
                
                # Update custom label for Z ion
                if '_custom_label' in z_fragment:
                    original_label = z_fragment['_custom_label']
                    if 'Y-' in original_label:
                        z_fragment['_custom_label'] = original_label.replace('Y-', 'Z-')
                        if modification_type == 6 and peptide and not z_fragment['_custom_label'].endswith('-PEP'):
                            z_fragment['_custom_label'] += '-PEP'
                    else:
                        z_fragment['_custom_label'] = f"Z-{original_label}"
                        if modification_type == 6 and peptide:
                            z_fragment['_custom_label'] += '-PEP'
                
                custom_cz_fragments['z_ions'].append(z_fragment)
                custom_fragments_processed += 1
             #   print(f"🔧 CUSTOM CZ: ✅ Created custom Z ion: {z_fragment['_custom_label']} with mass {z_mass:.4f} and m/z {mz:.4f} ({charge}H+)")
    
    # 3. Convert custom BY ions to custom CZ ions - COPY MASS DIRECTLY
    for fragment in working_fragments.get('by_ions', []):
        if fragment.get('_is_custom', False):
           # print(f"🔧 CUSTOM CZ: Processing custom BY ion: {fragment.get('_custom_label', 'unlabeled')}")
            
            # Get the already calculated mass from the custom BY fragment (same logic)
            if '_mass_adjustment' in fragment:
                base_mass = sum(fragment.get(mono, 0) * 203.0794 if mono == 'HexNAc' 
                               else fragment.get(mono, 0) * 162.0528 if mono == 'Hex'
                               else fragment.get(mono, 0) * 146.0579 if mono == 'Fuc'
                               else fragment.get(mono, 0) * 291.0954 if mono == 'NeuAc'
                               else 0 for mono in ['HexNAc', 'Hex', 'Fuc', 'NeuAc', 'NeuGc'])
                final_mass = base_mass + fragment['_mass_adjustment']
            else:
                final_mass = sum(fragment.get(mono, 0) * 203.0794 if mono == 'HexNAc' 
                               else fragment.get(mono, 0) * 162.0528 if mono == 'Hex'
                               else fragment.get(mono, 0) * 146.0579 if mono == 'Fuc'
                               else fragment.get(mono, 0) * 291.0954 if mono == 'NeuAc'
                               else 0 for mono in ['HexNAc', 'Hex', 'Fuc', 'NeuAc', 'NeuGc'])
            
            for charge in [1, 2, 3]:
                # FIXED: Proper m/z calculation for all charge states
                cz_mass = final_mass  # CZ ions have the SAME mass as BY ions
                mz = (cz_mass + (charge * 1.0073)) / charge  # Correct m/z calculation
                
                # Create custom CZ ion with SAME mass as BY ion
                cz_fragment = fragment.copy()
                cz_fragment['_mz'] = mz
                cz_fragment['_mass'] = cz_mass
                cz_fragment['_charge'] = charge
                cz_fragment['_fragment_type'] = 'cz'
                
                # Update custom label for CZ ion
                if '_custom_label' in cz_fragment:
                    original_label = cz_fragment['_custom_label']
                    if 'Y-' in original_label and '-B' in original_label:
                        # Convert Y-composition-B to Z-composition-C
                        composition_part = original_label.replace('Y-', '').replace('-B', '')
                        cz_fragment['_custom_label'] = f"Z-{composition_part}-C"
                    else:
                        cz_fragment['_custom_label'] = f"CZ-{original_label}"
                
                custom_cz_fragments['cz_ions'].append(cz_fragment)
                custom_fragments_processed += 1
            #    print(f"🔧 CUSTOM CZ: ✅ Created custom CZ ion: {cz_fragment['_custom_label']} with mass {cz_mass:.4f} and m/z {mz:.4f} ({charge}H+)")
    
    print(f"🔧 CUSTOM CZ: Total custom C/Z fragments generated: {custom_fragments_processed}")
    
    # Print summary by type
    for frag_type, fragments in custom_cz_fragments.items():
        if fragments:
            print(f"🔧 CUSTOM CZ: {frag_type}: {len(fragments)} custom fragments")
    
    return custom_cz_fragments

def generate_peptide_cz_fragments(peptide_fragments, glycan_code, peptide_sequence, generate_bzz=False):
    """Generate c and z ions from peptide b and y ions with proper Type naming"""
    
    cz_fragments = []
    
    # Process b and y ions to create c and z ions
    for fragment_type, ions in peptide_fragments.items():
        if fragment_type in ['b_ions', 'y_ions']:
            for ion in ions:
                # FIXED: Handle both old and new fragment structure
                if 'position' in ion:
                    position = ion['position']
                    mass = ion['mass']
                    sequence = ion['sequence']
                elif 'fragment_position' in ion:
                    position = ion['fragment_position']
                    mass = ion['fragment_mass']
                    sequence = ion['fragment_sequence']
                else:
                    print(f"Warning: Invalid ion structure: {ion}")
                    continue
                
                if fragment_type == 'b_ions':
                    # Convert b to c: add NH3 (+17.0265)
                    c_mass = mass + 17.0265
                    
                    # Standard c ion
                    c_fragment = {
                        'Type': f"c{position}",
                        'FragmentType': 'c',
                        'Fragment': sequence,
                        'Ions': '1H+',
                        'Fragment_mz': c_mass,
                        'Glycan': glycan_code,
                        'Glycopeptide': f"{peptide_sequence}-{glycan_code}",
                        'Is_Peptide_Fragment': True
                    }
                    cz_fragments.append(c_fragment)
                    
                    # c ion with CO loss (-27.9949)
                    c_co_loss_mass = c_mass - 27.9949
                    c_co_fragment = {
                        'Type': f"c{position}(-CO)",  # FIXED: Include (-CO) in Type
                        'FragmentType': 'c',
                        'Fragment': f"{sequence}(-CO)",
                        'Ions': '1H+',
                        'Fragment_mz': c_co_loss_mass,
                        'Glycan': glycan_code,
                        'Glycopeptide': f"{peptide_sequence}-{glycan_code}",
                        'Is_Peptide_Fragment': True
                    }
                    cz_fragments.append(c_co_fragment)
                    
                    # Add multiple charge states for both
                    for charge in [2, 3]:
                        # Standard c ion
                        c_charged = c_fragment.copy()
                        c_charged['Ions'] = f"{charge}H+"
                        c_charged['Fragment_mz'] = (c_mass + (charge - 1) * 1.007276) / charge
                        cz_fragments.append(c_charged)
                        
                        # c ion with CO loss
                        c_co_charged = c_co_fragment.copy()
                        c_co_charged['Ions'] = f"{charge}H+"
                        c_co_charged['Fragment_mz'] = (c_co_loss_mass + (charge - 1) * 1.007276) / charge
                        cz_fragments.append(c_co_charged)
                
                elif fragment_type == 'y_ions':
                    # Convert y to z: subtract NH3 (-17.0265)
                    z_mass = mass - 17.0265
                    
                    # Standard z ion
                    z_fragment = {
                        'Type': f"z{position}",
                        'FragmentType': 'z',
                        'Fragment': sequence,
                        'Ions': '1H+',
                        'Fragment_mz': z_mass,
                        'Glycan': glycan_code,
                        'Glycopeptide': f"{peptide_sequence}-{glycan_code}",
                        'Is_Peptide_Fragment': True
                    }
                    cz_fragments.append(z_fragment)
                    
                    # z ion with H2O loss (-18.0153)
                    z_h2o_loss_mass = z_mass - 18.0153
                    z_h2o_fragment = {
                        'Type': f"z{position}(-H2O)",  # FIXED: Include (-H2O) in Type
                        'FragmentType': 'z',
                        'Fragment': f"{sequence}(-H2O)",
                        'Ions': '1H+',
                        'Fragment_mz': z_h2o_loss_mass,
                        'Glycan': glycan_code,
                        'Glycopeptide': f"{peptide_sequence}-{glycan_code}",
                        'Is_Peptide_Fragment': True
                    }
                    cz_fragments.append(z_h2o_fragment)
                    
                    # Add multiple charge states for both
                    for charge in [2, 3]:
                        # Standard z ion
                        z_charged = z_fragment.copy()
                        z_charged['Ions'] = f"{charge}H+"
                        z_charged['Fragment_mz'] = (z_mass + (charge - 1) * 1.007276) / charge
                        cz_fragments.append(z_charged)
                        
                        # z ion with H2O loss
                        z_h2o_charged = z_h2o_fragment.copy()
                        z_h2o_charged['Ions'] = f"{charge}H+"
                        z_h2o_charged['Fragment_mz'] = (z_h2o_loss_mass + (charge - 1) * 1.007276) / charge
                        cz_fragments.append(z_h2o_charged)
    
    return cz_fragments

def format_peptide_fragments_for_table(peptide_fragments, glycan_code, peptide_sequence, 
                                     generate_glycan_by_ions=True, generate_peptide_by_ions=True,
                                     generate_cz_glycan_fragment=True, generate_cz_peptide_fragment=True):
    formatted_fragments = []
    
    # Define which fragment types to exclude based on settings
    excluded_types = set()
    
    if not generate_glycan_by_ions:
        excluded_types.update(['by_ions', 'b_ions', 'y_ions', 'yy_ions'])
    
    if not generate_peptide_by_ions:
        excluded_types.update(['peptide_b_ions', 'peptide_y_ions'])
    
    if not generate_cz_glycan_fragment:
        excluded_types.update(['cz_ions', 'czz_ions'])
        
    if not generate_cz_peptide_fragment:
        excluded_types.update(['c_ions', 'z_ions'])
    
    for ion_type, fragments in peptide_fragments.items():
        # Skip excluded fragment types
        if ion_type in excluded_types:
            continue

        for fragment in fragments:
            # Initialize fragment_composition to avoid UnboundLocalError
            fragment_composition = ""
            
            # Determine the fragment name based on the fragment structure
            if '_custom_label' in fragment:
                fragment_name = fragment['_custom_label']
                # Skip any remaining BY fragments that weren't caught by ion_type filtering
                if any(by_indicator in fragment_name.upper() for by_indicator in ['-B', 'BY-', 'YY-']):
                    continue
            elif 'fragment_name' in fragment:
                fragment_name = fragment['fragment_name']
                # Skip peptide BY fragments if not enabled
                if fragment_name.startswith(('b', 'y')) and not generate_peptide_by_ions:
                    continue
            else:
                # Generate fragment name from composition for glycan fragments
                comp_parts = []
                for key in ['HexNAc', 'Hex', 'Fuc', 'NeuAc', 'NeuGc']:
                    if key in fragment and fragment[key] > 0:
                        comp_parts.append(f"{key}{fragment[key]}")
                
                if comp_parts:
                    fragment_name = "-".join(comp_parts)
                else:
                    fragment_name = "Unknown"
            
            # Get Fragment_mz and charge
            if '_mass' in fragment and '_charge' in fragment:
                fragment_mass = fragment['_mz']
                charge = fragment['_charge']
            elif 'fragment_mass' in fragment:
                fragment_mass = fragment['fragment_mass']
                charge = 1
            else:
                fragment_mass = 0.0
                charge = 1
            
            # Skip fragments with zero or invalid mass
            if fragment_mass <= 0:
                continue
            
            # FIXED: For peptide fragments, use the actual amino acid sequence from fragment_sequence
            # For other fragments, extract composition from fragment name
            if 'fragment_sequence' in fragment and fragment['fragment_sequence']:
                # This is a peptide fragment - use the actual amino acid sequence
                fragment_composition = fragment['fragment_sequence']
            elif 'sequence' in fragment and fragment['sequence']:
                # Alternative sequence field
                fragment_composition = fragment['sequence']
            elif 'Fragment' in fragment and fragment['Fragment']:
                # This fragment already has a Fragment field - use it
                fragment_composition = fragment['Fragment']
            else:
                # Extract fragment composition for other fragments
                fragment_composition = extract_fragment_composition(fragment_name)
            
            # FIXED: Comprehensive peptide fragment detection
            is_peptide_fragment = False
            
            # Method 1: Check if it's a custom peptide fragment
            if (fragment.get('_is_custom', False) and 
                fragment.get('_custom_source') in ['cz_conversion', 'water_loss', 'ammonia_loss', 'co_loss']):
                is_peptide_fragment = True
            
            # Method 2: Check if it's a standard peptide fragment by fragment_type
            elif 'fragment_type' in fragment and fragment['fragment_type'] in ['b', 'y', 'c', 'z']:
                is_peptide_fragment = True
            
            # Method 3: Check by fragment name pattern (b1, y2, c3, z4, etc.)
            elif re.match(r'^[bycz]\d+', fragment_name):
                is_peptide_fragment = True
            
            # Method 4: Check if it has peptide-specific fields
            elif 'fragment_sequence' in fragment or 'sequence' in fragment:
                # Only consider it a peptide fragment if the sequence contains amino acids
                seq = fragment.get('fragment_sequence') or fragment.get('sequence', '')
                if seq and isinstance(seq, str) and re.match(r'^[ACDEFGHIKLMNPQRSTVWY]+', seq.upper()):
                    is_peptide_fragment = True
            
            # Method 5: For glycan fragments, explicitly set to False
            else:
                # This is a glycan fragment - all glycan fragments should be False
                is_peptide_fragment = False
            
            fragment_entry = {
                'Glycopeptides': f"{glycan_code}_{peptide_sequence}",
                'Glycan': glycan_code,
                'Type': fragment_name,
                'FragmentType': ion_type.replace('_ions', ''),
                'Fragment_mz': fragment_mass,
                'Ions': f"{charge}H+",
                'Theoretical_mz': fragment_mass,
                'Fragment': fragment_composition,
                'Is_Peptide_Fragment': is_peptide_fragment  # Now properly set for all fragments
            }
            formatted_fragments.append(fragment_entry)
    
    return formatted_fragments

def extract_fragment_composition(fragment_name):
    """
    Extract the composition part from a fragment name, removing prefixes and suffixes.
    For peptide fragments, return the actual amino acid sequence.
    """
    if not fragment_name:
        return fragment_name
    
    # Check if this is a peptide b/y fragment (pattern: b/y followed by number)
    peptide_by_match = re.match(r'^([by])(\d+)$', fragment_name)
    if peptide_by_match:
        # For peptide fragments, return the fragment name as-is since we don't have sequence context here
        return fragment_name
    
    # Check if this is a c/z peptide fragment (keep as is)
    if re.match(r'^[cz]\d+$', fragment_name):
        return fragment_name
    
    # Check for peptide fragments with neutral losses (e.g., "b1(-CO)", "y2(-NH3)")
    peptide_loss_match = re.match(r'^([bycz]\d+)\(([^)]+)\)$', fragment_name)
    if peptide_loss_match:
        return fragment_name  # Return the full name including the loss
    
    # This is a glycan fragment - apply prefix/suffix removal
    composition = fragment_name
    
    # Remove common prefixes for glycan fragments
    prefixes_to_remove = ['YY-', 'Y-', 'B-', 'BY-', 'BYY-', 'C-', 'Z-', 'CZ-', 'ZZ-', 'CZZ-', 'BZZ-']
    
    for prefix in prefixes_to_remove:
        if composition.startswith(prefix):
            composition = composition[len(prefix):]
            break
    
    # Remove common suffixes (but keep -PEP for glycopeptides)
    suffixes_to_remove = ['-B', '-C']
    
    for suffix in suffixes_to_remove:
        if composition.endswith(suffix):
            composition = composition[:-len(suffix)]
            break
    
    return composition

def ensure_peptide_masses_initialized(calculator):
    if not hasattr(calculator, 'PEPTIDE_MASSES'):
        calculator.PEPTIDE_MASSES = {}

def parse_glycopeptide(glycopeptide_string):
    """
    Parse a glycopeptide string to extract peptide, glycan, and modification components.
    
    Args:
        glycopeptide_string (str): String in various formats with modifications
    
    Returns:
        dict: Dictionary with 'peptide', 'glycan', 'glycan_type', 'glycan_base_mass', and 'pep_modification' keys
    """
    original_string = glycopeptide_string
    modifications = []
    glycan_base_mass = None
    glycan_type = None
    
    # First, remove prefix amino acid (e.g., "S.", "R.")
    if re.match(r'^[A-Z]\.', glycopeptide_string):
        glycopeptide_string = glycopeptide_string[2:]
    
    # Check for N-terminal modification at the beginning
    nterm_match = re.match(r'^\[\+?(\d+\.?\d*)\]\.(.+)', glycopeptide_string)
    if nterm_match:
        nterm_mod = nterm_match.group(1)
        modifications.append(f"(+{nterm_mod}):Nterm")
        glycopeptide_string = nterm_match.group(2)
    
    # Split peptide and glycan parts
    # Look for pattern: peptide.suffix_amino_acid + glycan
    match = re.match(r'(.+)\.([A-Z])([A-Za-z\d\(\)]+)$', glycopeptide_string)
    
    if match:
        peptide_part = match.group(1)
        suffix_aa = match.group(2)
        glycan_part = match.group(3)
    else:
        # Handle cases without suffix amino acid
        match = re.match(r'(.+?)([A-Za-z\d\(\)]+)$', glycopeptide_string)
        if match:
            peptide_part = match.group(1)
            glycan_part = match.group(2)
        else:
            return {"peptide": None, "glycan": None, "glycan_type": None, "glycan_base_mass": None, "pep_modification": None}
    
    # Extract position-specific modifications from peptide
    clean_peptide = ""
    position = 1
    i = 0
    
    while i < len(peptide_part):
        if peptide_part[i].isalpha():
            clean_peptide += peptide_part[i]
            # Check if next character starts a modification
            if i + 1 < len(peptide_part) and peptide_part[i + 1] == '[':
                # Find the end of the modification
                mod_end = peptide_part.find(']', i + 1)
                if mod_end != -1:
                    mod_value = peptide_part[i + 2:mod_end]  # Skip '[+'
                    if mod_value.startswith('+'):
                        mod_value = mod_value[1:]
                    
                    # Check if this is a glycan attachment site
                    amino_acid = peptide_part[i]
                    if amino_acid in ['S', 'T']:
                        glycan_type = "O"  # Return "O" instead of "O-glycopeptide"
                        glycan_base_mass = mod_value
                    elif amino_acid == 'N':
                        glycan_type = "N"  # Return "N" instead of "N-glycopeptide"
                        glycan_base_mass = mod_value
                    else:
                        # Regular peptide modification
                        modifications.append(f"(+{mod_value}):{amino_acid}{position}")
                    
                    i = mod_end + 1
                else:
                    i += 1
            else:
                i += 1
            position += 1
        else:
            i += 1
    
    # Format modifications
    pep_modification = "; ".join(modifications) if modifications else None
    
    return {
        "peptide": clean_peptide,
        "glycan": glycan_part,
        "glycan_type": glycan_type,
        "glycan_base_mass": glycan_base_mass,
        "pep_modification": pep_modification
    }

def combine_glycan_and_peptide_fragments(glycan_fragments_df, peptide_fragments, glycan_code, peptide_sequence, 
                                       generate_cz_peptide=False, generate_cz_glycan=False, 
                                       generate_peptide_by_ions=False, generate_glycan_by_ions=False,
                                       enable_custom_peptide_fragments=False):
    """
    Combine glycan fragments with peptide fragments into a single DataFrame.
    """
    print(f"DEBUG: combine_glycan_and_peptide_fragments called with:")
    print(f"  generate_cz_peptide: {generate_cz_peptide}")
    print(f"  generate_peptide_by_ions: {generate_peptide_by_ions}")
    print(f"  add_custom_peptide_fragments: {enable_custom_peptide_fragments}")
    
    peptide_rows = []
    
    # FIXED: Only include b/y peptide fragments if explicitly requested
    if generate_peptide_by_ions:
        print(f"DEBUG: generate_peptide_by_ions=True, including peptide b/y fragments")
        peptide_rows = format_peptide_fragments_for_table(
            peptide_fragments, glycan_code, peptide_sequence,
            generate_glycan_by_ions=generate_glycan_by_ions,
            generate_peptide_by_ions=generate_peptide_by_ions,
            generate_cz_glycan_fragment=generate_cz_glycan,
            generate_cz_peptide_fragment=generate_cz_peptide
        )
        print(f"DEBUG: Added {len(peptide_rows)} peptide b/y fragments")
    else:
        print(f"DEBUG: generate_peptide_by_ions=False, skipping peptide b/y fragments")
    
    # Generate c/z peptide fragments if requested (independent of b/y setting)
    if generate_cz_peptide:
        print(f"DEBUG: generate_cz_peptide=True, generating peptide C/Z fragments")
        cz_peptide_fragments = generate_peptide_cz_fragments(
            peptide_fragments, glycan_code, peptide_sequence
        )
        peptide_rows.extend(cz_peptide_fragments)
        print(f"DEBUG: Added {len(cz_peptide_fragments)} peptide C/Z fragments")
    else:
        print(f"DEBUG: generate_cz_peptide=False, skipping peptide C/Z fragment generation")
    
    # FIXED: Handle empty glycan_fragments_df case
    if glycan_fragments_df.empty:
        print(f"DEBUG: No glycan fragments to combine - creating DataFrame from peptide fragments only")
        # Create a minimal glycan DataFrame structure
        glycan_fragments_df = pd.DataFrame(columns=[
            'Type', 'FragmentType', 'Fragment_mz', 'Ions', 'Theoretical_mz', 
            'Fragment', 'Glycan', 'Glycopeptide', 'Is_Peptide_Fragment'
        ])
    
    # Add flag to glycan fragments for filtering
    glycan_fragments_df['Is_Peptide_Fragment'] = False
    
    # Create DataFrame from peptide rows and combine with glycan fragments
    if peptide_rows:
        print(f"DEBUG: Creating combined DataFrame with {len(peptide_rows)} peptide fragments")
        peptide_df = pd.DataFrame(peptide_rows)
        combined_df = pd.concat([glycan_fragments_df, peptide_df], ignore_index=True)
    else:
        print(f"DEBUG: No peptide fragments to add, using only glycan fragments")
        combined_df = glycan_fragments_df.copy()
    
    # FIXED: Add missing column validation before deduplication
    required_columns = ['Fragment_mz', 'Glycopeptide']  # Changed from 'Glycopeptide' to what we actually need
    missing_columns = [col for col in required_columns if col not in combined_df.columns]
    
    if missing_columns:
        print(f"DEBUG: Adding missing columns: {missing_columns}")
        for col in missing_columns:
            if col == 'Glycopeptide':
                # FIXED: Create the Glycopeptide column properly
                combined_df['Glycopeptide'] = f"{peptide_sequence}-{glycan_code}"
            else:
                combined_df[col] = 0  # Default value for missing columns
    
    # Apply priority-based deduplication to the combined DataFrame
    combined_df = deduplicate_fragments_by_mass(combined_df)
    
    print(f"DEBUG: Combined DataFrame has {len(combined_df)} fragments after filtering")
    
    return combined_df

def format_fragment_string(fragment, frag_type):
    """Create a consistent string representation of a fragment"""
    # Generate fragment composition string
    comp_parts = []
    if fragment.get('HexNAc', 0) > 0:
        comp_parts.append(f"HexNAc{fragment['HexNAc']}")
    if fragment.get('Hex', 0) > 0:
        comp_parts.append(f"Hex{fragment['Hex']}")
    if fragment.get('Fuc', 0) > 0:
        comp_parts.append(f"Fuc{fragment['Fuc']}")
    if fragment.get('NeuAc', 0) > 0:
        comp_parts.append(f"NeuAc{fragment['NeuAc']}")
    
    # Add -redend for y/yy ions
    composition = "-".join(comp_parts)
    has_reducing_end = frag_type in ['y_ions', 'yy_ions']
    if has_reducing_end:
        composition += "-redend"
    
    # Format according to ion type - ENSURE CONSISTENT PREFIX HANDLING
    if frag_type == 'by_ions':
        return f"Y-{composition.replace('-redend', '')}-B"
    elif frag_type == 'y_ions':
        return f"Y-{composition}"  # Must have Y- prefix for Y ions
    elif frag_type == 'yy_ions':
        return f"YY-{composition}"
    elif frag_type == 'b_ions':
        return f"{composition}-B"
    else:
        return composition

def collect_unique_fragments(results, modification_type=6, peptide=None, use_cam=False, fixed_mods=None, variable_mods=None, mod_string=None):
    """Collect and deduplicate fragments from all structures using composition and mass"""
    
    # Ensure we have lists for modifications to avoid type errors
    fixed_mods = fixed_mods or []
    variable_mods = variable_mods or []
    
    # Convert all elements to strings to avoid type errors
    fixed_mods = [str(mod) for mod in fixed_mods]
    variable_mods = [str(mod) for mod in variable_mods]
    
    calculator = GlycanMassCalculator(
    modification_type=modification_type,
    use_cam=use_cam,
    fixed_mods=fixed_mods,
    variable_mods=variable_mods,
    mod_string=mod_string
        )
    
    # Dictionary to store unique fragments by composition and mass
    unique_fragments = {
        'b_ions': {},
        'y_ions': {},
        'by_ions': {},
        'yy_ions': {}
    }
    
    # Track fragment IDs to aid debugging
    fragment_ids = {
        'b_ions': set(),
        'y_ions': set(),
        'by_ions': set(),
        'yy_ions': set()
    }
    
    for result in results:
        # Extract fragments from the tuple (fragments, cleavage_info)
        if isinstance(result['fragments'], tuple):
            fragments, cleavage_info = result['fragments']
        else:
            fragments = result['fragments']
        
        # Process each fragment type
        for frag_type, frags in fragments.items():
            for fragment in frags:
                # Ensure fragment is a dictionary with numeric counts
                if not isinstance(fragment, dict):
                    continue
                
                # Generate a consistent fragment string (the same way it's formatted in output)
                frag_str = format_fragment_string(fragment, frag_type)
                fragment_ids[frag_type].add(frag_str)
                
                # Create a comprehensive deduplication key that captures all attributes
                # The key format is: (composition tuple, fragment type, reducing_end flag)
                has_reducing_end = frag_type in ['y_ions', 'yy_ions']
                comp_tuple = tuple(sorted((k, v) for k, v in fragment.items() if v > 0))
                dedup_key = (comp_tuple, frag_type, has_reducing_end)
                
                # Calculate mass for the fragment
                fragment_mass = calculator.calculate_fragment_mass(fragment, frag_type, peptide=peptide)
                
                # Store using the combined key
                unique_fragments[frag_type][dedup_key] = fragment
    
    # For debugging - check what Y ions we actually collected
    #print(f"Y-ion fragments collected: {fragment_ids['y_ions']}")
    
    # Convert back to lists for easier usage
    deduplicated_fragments = {
        'b_ions': list(unique_fragments['b_ions'].values()),
        'y_ions': list(unique_fragments['y_ions'].values()),
        'by_ions': list(unique_fragments['by_ions'].values()),
        'yy_ions': list(unique_fragments['yy_ions'].values())
    }
    
    return deduplicated_fragments

def deduplicate_fragments_by_mass(df):
    """
    Deduplicate fragments by Fragment_mz per Glycopeptide, prioritizing fragment types
    in this order: Glycan fragments (b > y > by > yy > byy > c > z > cz > zz > czz > bzz) 
    then Peptide fragments (b > y > c > z), with charge state priority (1+ > 2+ > 3+)
    """
    if df.empty:
        return df
    
    # Create a copy to avoid modifying the original
    df = df.copy()
    
    # Round Fragment_mz to ensure consistent comparisons (4 decimal places)
    df['Fragment_mz'] = df['Fragment_mz'].round(4)
    
    # Define priority mapping with glycan fragments first, then peptide fragments
    priority_map = {
        # Glycan fragments (lower number = higher priority)
        'b': 1,     # Glycan B ions
        'y': 2,     # Glycan Y ions  
        'by': 3,    # Glycan BY ions
        'yy': 4,    # Glycan YY ions
        'byy': 5,   # Glycan BYY ions
        'c': 6,     # Glycan C ions
        'z': 7,     # Glycan Z ions
        'cz': 8,    # Glycan CZ ions
        'zz': 9,    # Glycan ZZ ions
        'czz': 10,  # Glycan CZZ ions
        'bzz': 11,  # Glycan BZZ ions
    }
    
    # Add peptide fragment priorities (higher numbers than glycan fragments)
    peptide_priority_offset = 50  # Ensure peptide fragments have lower priority than glycan
    peptide_priority_map = {
        'b': peptide_priority_offset + 1,  # Peptide b ions
        'y': peptide_priority_offset + 2,  # Peptide y ions
        'c': peptide_priority_offset + 3,  # Peptide c ions
        'z': peptide_priority_offset + 4,  # Peptide z ions
    }
    
    # Function to determine priority based on fragment type and whether it's a peptide fragment
    def get_fragment_priority(row):
        fragment_type = row['FragmentType']
        
        # Determine if this is a peptide fragment based on the Type column
        fragment_name = row.get('Type', '')
        
        # Peptide fragments have specific patterns: b1, b2, y1, y2, etc.
        is_peptide = bool(re.match(r'^[bycz]\d+$', fragment_name))
        
        if is_peptide:
            # For peptide fragments, use peptide priority map (lower priority numbers)
            return peptide_priority_map.get(fragment_type, 99)
        else:
            # For glycan fragments, use glycan priority map (higher priority numbers) 
            return priority_map.get(fragment_type, 99)
    
    # Function to extract charge state from Ions column (e.g., "2H+" -> 2)
    def get_charge_priority(ions_str):
        try:
            if 'H+' in str(ions_str):
                charge = int(str(ions_str).replace('H+', ''))
                return charge  # Lower charge = higher priority (1+ > 2+ > 3+)
            else:
                return 99  # Unknown charge gets lowest priority
        except:
            return 99
    
    # Apply priority calculations
    df['fragment_priority'] = df.apply(get_fragment_priority, axis=1)
    df['charge_priority'] = df['Ions'].apply(get_charge_priority)
    
    # Sort by Glycopeptide, Fragment_mz, fragment priority, and charge priority
    # Lower numbers = higher priority for all columns
    df = df.sort_values(['Glycopeptide', 'Fragment_mz', 'fragment_priority', 'charge_priority'])
    
    # Log deduplication information
    print(f"Before deduplication: {len(df)} fragments")
    
    # Identify duplicates for debugging
    dupes_mask = df.duplicated(subset=['Glycopeptide', 'Fragment_mz'], keep=False)
    if dupes_mask.sum() > 0:
        #print(f"Found {dupes_mask.sum()} fragments with duplicate masses")
        
        # Show some examples of what will be deduplicated
        dupe_df = df[dupes_mask].sort_values(['Glycopeptide', 'Fragment_mz', 'fragment_priority', 'charge_priority'])
        
        # Group by glycopeptide and mass to show which fragments are competing
        duplicate_groups = dupe_df.groupby(['Glycopeptide', 'Fragment_mz'])
        
        examples_shown = 0
        for (glycopeptide, mass), group in duplicate_groups:
            if examples_shown < 5:  # Show first 5 examples
                #print(f"\nDuplicate mass {mass:.4f} in {glycopeptide}:")
                for _, row in group.iterrows():
                    fragment_type = row['FragmentType']
                    is_peptide = row.get('Is_Peptide_Fragment', False)
                    fragment_priority = row['fragment_priority']
                    charge_priority = row['charge_priority']
                    ions = row['Ions']
                    keep_status = "KEEP" if (fragment_priority == group['fragment_priority'].min() and 
                                           charge_priority == group[group['fragment_priority'] == group['fragment_priority'].min()]['charge_priority'].min()) else "REMOVE"
                    fragment_source = "Peptide" if is_peptide else "Glycan"
                    #print(f"  {keep_status}: {fragment_source} {fragment_type} ion {ions} (frag_priority {fragment_priority}, charge_priority {charge_priority}) - {row.get('Type', 'N/A')}")
                examples_shown += 1
            else:
                break
    
    # Drop duplicates, keeping the first occurrence (highest priority after sorting)
    df_deduplicated = df.drop_duplicates(subset=['Glycopeptide', 'Fragment_mz'], keep='first')
    
    # Remove the temporary priority columns
    df_deduplicated = df_deduplicated.drop(['fragment_priority', 'charge_priority'], axis=1)
    
    print(f"After deduplication: {len(df_deduplicated)} fragments")
    print(f"Removed {len(df) - len(df_deduplicated)} duplicate fragments")
    
    # Show summary of what was kept
    if 'Is_Peptide_Fragment' in df_deduplicated.columns:
        glycan_fragments = len(df_deduplicated[df_deduplicated.get('Is_Peptide_Fragment', True) == False])
        peptide_fragments = len(df_deduplicated[df_deduplicated.get('Is_Peptide_Fragment', False) == True])
        print(f"Final composition: {glycan_fragments} glycan fragments, {peptide_fragments} peptide fragments")
    
    # Show charge state distribution in final results
    if 'Ions' in df_deduplicated.columns:
        charge_counts = df_deduplicated['Ions'].value_counts()
        print(f"Charge state distribution: {dict(charge_counts)}")
    
    return df_deduplicated

def generate_all_fragments_table(results, glycan_code, modification_type=6, peptide=None, use_cam=False, fixed_mods=None, variable_mods=None, mod_string=None):
    """Generate a DataFrame with ALL fragments from each structure with cleavage info"""
    all_data = []
    calculator = GlycanMassCalculator(
    modification_type=modification_type,
    use_cam=use_cam,
    fixed_mods=fixed_mods,
    variable_mods=variable_mods,
    mod_string=mod_string
        )
    
    proton_mass = 1.0073
    
    for result_idx, result in enumerate(results):
        # Extract fragments and cleavage info from the tuple
        if isinstance(result['fragments'], tuple):
            fragments, cleavage_info = result['fragments']
        else:
            fragments = result['fragments']
            cleavage_info = {frag_type: {} for frag_type in ['b_ions', 'y_ions', 'by_ions', 'yy_ions']}
        
        structure_id = result['structure_id']
        structure_type = result['type']
        
        for frag_type, frags in fragments.items():
            for fragment in frags:
                if not isinstance(fragment, dict) or sum(fragment.values()) == 0:
                    continue
                    
                has_reducing_end = frag_type in ['y_ions', 'yy_ions']
                neutral_mass = calculator.calculate_fragment_mass(fragment, frag_type, peptide=peptide)
                
                # Build composition string consistently
                comp_parts = []
                if fragment.get('HexNAc', 0) > 0:
                    comp_parts.append(f"HexNAc{fragment['HexNAc']}")
                if fragment.get('Hex', 0) > 0:
                    comp_parts.append(f"Hex{fragment['Hex']}")
                if fragment.get('Fuc', 0) > 0:
                    comp_parts.append(f"Fuc{fragment['Fuc']}")
                if fragment.get('NeuAc', 0) > 0:
                    comp_parts.append(f"NeuAc{fragment['NeuAc']}")
                
                composition = "-".join(comp_parts)
                
                # Format for display
                if has_reducing_end and frag_type in ['y_ions', 'yy_ions']:
                    composition += "-redend"
                    
                # Very important: Get the EXACT same fragment ID that was stored in cleavage_info
                # Use the same method that was used to store it
                fragment_str = composition
                if frag_type == 'by_ions':
                    fragment_id = f"Y-{composition.replace('-redend', '')}-B"
                    fragment_display = composition.replace('-redend', '')
                # In generate_all_fragments_table()
                elif frag_type == 'y_ions':
                    fragment_id = f"Y-{composition}"  # Add the "Y-" prefix consistently
                    fragment_display = composition
                elif frag_type == 'yy_ions':
                    fragment_id = composition
                    fragment_display = composition
                elif frag_type == 'b_ions':
                    fragment_id = f"{composition}-B"
                    fragment_display = composition.replace('-redend', '')
                else:
                    fragment_id = composition
                    fragment_display = composition
                
                for charge in [1, 2, 3]:
                    mz = (neutral_mass + (charge * proton_mass)) / charge
                    
                    all_data.append({
                        'Structure ID': structure_id,
                        'Structure Type': structure_type,
                        'Type': fragment_id,
                        'FragmentType': frag_type.split('_')[0],
                        'Fragment': fragment_display,
                        'Cleavage': cleavage_info.get(frag_type, {}).get(fragment_id, "Not available"),
                        'Ions': f"{charge}H+",
                        'Fragment_mz': round(mz, 4),
                        'Glycan': glycan_code
                    })
    
    df_all = pd.DataFrame(all_data)
    return df_all

def generate_fragment_table(unique_fragments, glycan_code, modification_type=6, peptide=None, use_cam=False, fixed_mods=None, variable_mods=None, mod_string=None):
    """Generate a DataFrame with Fragment_mzes and charge states"""
    # Debug message at beginning
    print(f"DEBUG: generate_fragment_table called with: use_cam={use_cam}, fixed_mods={fixed_mods}")
    print(f"\n=== DEBUG: generate_fragment_table ===")
    print(f"Glycan code: {glycan_code}")
    print(f"Peptide: {peptide}")
    print(f"use_cam: {use_cam}")
    print(f"fixed_mods: {fixed_mods}")
    print(f"variable_mods: {variable_mods}")
    
    # Ensure we have lists for modifications to avoid type errors
    fixed_mods = fixed_mods if fixed_mods is not None else []
    variable_mods = variable_mods if variable_mods is not None else []
    
    # Convert all elements to strings to avoid type errors
    fixed_mods = [str(mod) for mod in fixed_mods]
    variable_mods = [str(mod) for mod in variable_mods]
    
    # Create a calculator with the EXACT SAME parameters that were used for peptide mass calculation
    calculator = GlycanMassCalculator(
        modification_type=modification_type,
        use_cam=use_cam,
        fixed_mods=fixed_mods.copy(),  # Use .copy() to avoid reference issues
        variable_mods=variable_mods.copy(),
        mod_string=mod_string,
        peptide=peptide  # Explicitly pass peptide to calculator
    )
    calculator.calculate_MONO_MASSES(modification_type)
    
    # Debug the calculator state after initialization to verify parameters
    print(f"Initialized calculator with use_cam: {calculator.use_cam}")
    print(f"Initialized calculator with fixed_mods: {calculator.fixed_mods}")
    
    # Create comprehensive cache key for peptide mass lookup
    if peptide:
        peptide_cache_key = create_comprehensive_peptide_cache_key(
            peptide,
            use_cam=use_cam,
            fixed_mods=fixed_mods,
            variable_mods=variable_mods,
            mod_string=mod_string
        )
        print(f"Using peptide cache key: {peptide_cache_key}")
        
        # Ensure PEPTIDE_MASSES exists
        if not hasattr(calculator, 'PEPTIDE_MASSES'):
            calculator.PEPTIDE_MASSES = {}
            
        # Check if we need to calculate peptide mass
        if peptide_cache_key not in calculator.PEPTIDE_MASSES:
            print(f"Calculating peptide mass for {peptide} with use_cam={use_cam}")
            calculator.PEPTIDE_MASSES[peptide_cache_key] = calculator.calculate_peptide_mass(
                peptide,
                use_cam=use_cam,
                fixed_mods=fixed_mods,
                variable_mods=variable_mods,
                mod_string=mod_string
            )
        print(f"Peptide mass in cache: {calculator.PEPTIDE_MASSES[peptide_cache_key]:.4f} Da")

    
    data = []
    charges = [1, 2, 3]  # Generate fragments with these charge states
    
    for frag_type, fragments in unique_fragments.items():
        for fragment in fragments:
            # FIX: Check if fragment is valid and filter out metadata fields
            if not isinstance(fragment, dict):
                continue
                
            # Filter out metadata fields and only sum numeric monosaccharide values
            monosaccharide_keys = ['HexNAc', 'Hex', 'Fuc', 'NeuAc', 'NeuGc']
            monosaccharide_sum = sum(fragment.get(key, 0) for key in monosaccharide_keys if isinstance(fragment.get(key, 0), (int, float)))
            
            if monosaccharide_sum == 0:
                continue

            # Check if this is a C/Z fragment with pre-calculated values
            if '_fragment_type' in fragment and '_mz' in fragment and '_charge' in fragment:
                # This is a pre-calculated C/Z fragment
                fragment_name = fragment.get('_custom_label', 'Unknown')
                theoretical_mz = fragment['_mz']
                charge = fragment['_charge']
                fragment_mass = (theoretical_mz * charge) - (charge * calculator.PROTON_MASS)
                fragment_type_clean = fragment['_fragment_type']  # Already clean (no "_ions")
                
                # Apply extract_fragment_composition to clean the fragment name for Fragment column
                fragment_composition = extract_fragment_composition(fragment_name)
                
                data.append({
                    'Type': fragment_name,
                    'FragmentType': fragment_type_clean,
                    'Fragment': fragment_composition,  # <-- FIXED: Now uses cleaned composition
                    'Ions': f"{charge}H+",
                    'Fragment_mz': theoretical_mz,
                    'Glycan': glycan_code,
                    'Glycopeptide': f"{peptide}-{glycan_code}" if peptide else glycan_code
                })
            else:
                # Regular fragment processing
                fragment_mass = calculator.calculate_fragment_mass(fragment, frag_type, peptide=peptide)
                
                # Generate fragment string
                fragment_string = format_fragment_string(fragment, frag_type)
                
                # Check for custom label
                if '_custom_label' in fragment:
                    fragment_string = fragment['_custom_label']
                
                # Clean fragment type (remove "_ions" suffix)
                fragment_type_clean = frag_type.replace('_ions', '')
                
                # Apply extract_fragment_composition to clean the fragment name for Fragment column
                fragment_composition = extract_fragment_composition(fragment_string)
                
                # Check for custom charge
                if '_ion_charge' in fragment:
                    charge_info = fragment['_ion_charge']
                    if charge_info.endswith('H+'):
                        charge = int(charge_info[:-2])
                        mz = calculator.calculate_mz(fragment_mass, charge)
                        
                        data.append({
                            'Type': fragment_string,
                            'FragmentType': fragment_type_clean,
                            'Fragment': fragment_composition,  # <-- FIXED: Now uses cleaned composition
                            'Ions': charge_info,
                            'Fragment_mz': mz,
                            'Glycan': glycan_code,
                            'Glycopeptide': f"{peptide}-{glycan_code}" if peptide else glycan_code
                        })
                else:
                    # Generate for multiple charge states
                    for charge in charges:
                        mz = calculator.calculate_mz(fragment_mass, charge)
                        
                        data.append({
                            'Type': fragment_string,
                            'FragmentType': fragment_type_clean,
                            'Fragment': fragment_composition,  # <-- FIXED: Now uses cleaned composition
                            'Ions': f"{charge}H+",
                            'Fragment_mz': mz,
                            'Glycan': glycan_code,
                            'Glycopeptide': f"{peptide}-{glycan_code}" if peptide else glycan_code,
                            'Is_Peptide_Fragment': False
                        })
    
    df = pd.DataFrame(data)
    return df

def export_fragment_table_to_excel(df, df_all=None, filename='glycan_fragments.xlsx'):
    """Export the fragment tables to Excel with multiple sheets"""
    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        # Write deduplicated fragments to Sheet1
        df.to_excel(writer, sheet_name='Unique Fragments', index=False)
        
        # Write all fragments (if available) to Sheet2
        if df_all is not None:
            df_all.to_excel(writer, sheet_name='All Fragments', index=False)
    
    return f"Fragment tables exported to {filename}"


#Extracting PRM Fragments from mzML Files
def read_target_mzs_from_excel(excel_file):
    """Read target m/z values and retention times from Excel file with row uniqueness"""
    df = pd.read_excel(excel_file)
    print(f"Reading Excel file: {excel_file}")
    
    # Add row index as unique identifier
    df['row_id'] = df.index
    
    # Initialize metadata dictionary 
    mz_metadata = {}
    target_mzs = []
    
    # Find RT column
    rt_column = next((col for col in df.columns if col.strip().upper() == 'RT'), None)
    if not rt_column:
        rt_column = next((col for col in df.columns if 'rt' in col.lower() or 'time' in col.lower()), None)
    
    # Process each row individually
    for idx, row in df.iterrows():
        glycan = str(row['Glycan']).strip() if pd.notna(row['Glycan']) else ''
        peptide = str(row['Peptide']).strip() if pd.notna(row['Peptide']) else ''
        
        # Create unique glycopeptide ID using row position
        unique_id = f"{glycan}{'_' + peptide if peptide else ''}_row{idx}"
        
        # Get RT value
        rt = None
        if rt_column and pd.notna(row[rt_column]):
            rt = float(row[rt_column])
        
        # Process m/z columns
        excluded_cols = ['Glycan', 'Peptide', 'row_id', rt_column] if rt_column else ['Glycan', 'Peptide', 'row_id']
        mz_columns = [col for col in df.columns if col not in excluded_cols]
        
        for col in mz_columns:
            mz_value = row[col]
            if pd.notna(mz_value) and mz_value > 0:
                mz_value = float(mz_value)
                target_mzs.append(mz_value)
                mz_metadata[mz_value] = {
                    'Glycan': glycan,
                    'Peptide': peptide,
                    'RT': rt,
                    'Column': col,
                    'row_id': idx,
                    'unique_id': unique_id  # Store the unique ID
                }
    
    return target_mzs, mz_metadata, df

def calculate_ppm_tolerance(mz, ppm):
    return mz * (ppm / 1e6)

def is_within_ppm_tolerance(measured_mz, theoretical_mz, ppm_tolerance):
    # Add type conversion but preserve full precision
    try:
        measured_mz = float(measured_mz)
        theoretical_mz = float(theoretical_mz)
    except (ValueError, TypeError):
        print(f"Warning: Invalid m/z values for comparison: {measured_mz}, {theoretical_mz}")
        return False
        
    abs_tolerance = calculate_ppm_tolerance(theoretical_mz, ppm_tolerance)
    return abs(measured_mz - theoretical_mz) <= abs_tolerance

def extract_prm_fragments_with_unique_keys(mzml_file, target_mzs=None, target_keys=None, 
                                         mz_metadata=None, ms1_ppm_tolerance=10, intensity_threshold=1000,
                                         rt_window=5.0, back_window_ratio=0.1):
    """
    Extract PRM fragments from mzML file with row-unique identifiers
    
    Args:
        mzml_file: Path to mzML file
        target_mzs: List of target m/z values
        target_keys: List of tuples (mz, unique_key) where unique_key is "{mz}_{row_id}"
        mz_metadata: Dictionary with metadata for each unique_key
        ms1_ppm_tolerance: PPM tolerance for matching precursors
        rt_window: Total RT window width in minutes
        back_window_ratio: Ratio of RT window to use for backward search
    
    Returns:
        Dictionary mapping composite keys to MS2 data
    """
    # Ensure rt_window is a numeric value
    rt_window = float(rt_window)
    
    # Calculate the backward and forward window sizes
    back_window = rt_window * back_window_ratio
    forward_window = rt_window - back_window
    
    # Initialize data structure to store PRM data with composite keys
    prm_data = {}
    
    # Create a mapping from search m/z to unique key
    mz_to_unique_key = {}
    for mz, unique_key in target_keys:
        mz_to_unique_key[mz] = unique_key
    
    # Track precursor detection status
    precursor_tracking = {}
    for mz, unique_key in target_keys:
        if unique_key in mz_metadata:
            rt_value = mz_metadata[unique_key].get('RT')
            row_id = mz_metadata[unique_key].get('row_id')
            
            # Store tracking info with composite key (mz_row_id)
            precursor_tracking[unique_key] = {
                'mz': mz,
                'rt': rt_value,
                'row_id': row_id,
                'found_in_mzml': False,
                'found_in_rt_window': False,
                'spectra_count': 0
            }
    
    # Track RT region MS2 counts
    rt_region_counts = {}
    
    print(f"\nStarting mzML extraction from {mzml_file}")
    print(f"Processing {len(target_keys)} precursor targets")
    
    # Add after collecting fragment data for each scan
    scan_debug_count = 0
    total_zero_intensity = 0
    total_nonzero_intensity = 0
    
    with mzml.MzML(mzml_file) as reader:
        for spectrum in reader:
            if spectrum.get('ms level', 0) != 2:
                continue
            
            # Get m/z arrays from the spectrum
            mz_array = spectrum.get('m/z array', [])
            intensity_array = spectrum.get('intensity array', [])
            
            # APPLY INTENSITY FILTERING TO MATCH RAW PROCESSING
            # Filter out zero and low intensity fragments
            intensity_mask = intensity_array > intensity_threshold
            
            # Count fragments before and after filtering for debugging
            fragments_before = len(mz_array)
            
            # Apply the filter
            mz_array = mz_array[intensity_mask]
            intensity_array = intensity_array[intensity_mask]
            
            fragments_after = len(mz_array)
            
            # DEBUG: Enhanced logging for first few scans
            if scan_debug_count < 5:
                print(f"    DEBUG mzML Scan {scan_debug_count}: {fragments_before} → {fragments_after} fragments after intensity filtering (threshold: {intensity_threshold})")
                print(f"    DEBUG mzML: Intensity range after filtering: {min(intensity_array) if len(intensity_array) > 0 else 0:.0f}-{max(intensity_array) if len(intensity_array) > 0 else 0:.0f}")
                
                if len(mz_array) > 0:
                    print(f"    DEBUG mzML: First 5 m/z after filtering: {mz_array[:5]}")
                    print(f"    DEBUG mzML: First 5 intensities after filtering: {intensity_array[:5]}")
                else:
                    print(f"    DEBUG mzML: NO FRAGMENTS REMAIN AFTER INTENSITY FILTERING")
                
                scan_debug_count += 1

            # Get precursor information
            precursor_list = spectrum.get('precursorList', {}).get('precursor', [])
            if not precursor_list:
                continue
                
            # Get retention time in minutes
            rt_seconds = spectrum.get('scanList', {}).get('scan', [{}])[0].get('scan start time', 0)
            rt_minutes = rt_seconds / 60.0 if rt_seconds > 100 else rt_seconds
            
            # Track MS2 spectra by RT region (1-minute bins)
            rt_region = int(rt_minutes)
            rt_region_counts[rt_region] = rt_region_counts.get(rt_region, 0) + 1
            
            # Get m/z arrays from the spectrum
            mz_array = spectrum.get('m/z array', [])
            intensity_array = spectrum.get('intensity array', [])
            
            # Get precursor m/z
            selected_ion_list = precursor_list[0].get('selectedIonList', {}).get('selectedIon', [{}])
            if not selected_ion_list:
                continue
                
            precursor_mz = selected_ion_list[0].get('selected ion m/z')
            if not precursor_mz:
                continue
            
            # Find matching target within tolerance
            for target_mz, unique_key in target_keys:
                if is_within_ppm_tolerance(precursor_mz, target_mz, ms1_ppm_tolerance):
                    # Get row ID and RT from the metadata
                    metadata = mz_metadata.get(unique_key, {})
                    row_id = metadata.get('row_id')
                    target_rt = metadata.get('RT')
                    
                    # Update tracking - found in mzML
                    if unique_key in precursor_tracking:
                        precursor_tracking[unique_key]['found_in_mzml'] = True
                    
                    # Skip if no target RT is provided (or optional RT filtering)
                    if target_rt is None:
                        continue
                        
                    # Check if current scan is within RT window of target
                    if (rt_minutes >= target_rt - back_window and 
                        rt_minutes <= target_rt + forward_window):
                        
                        # Update tracking - found in RT window
                        if unique_key in precursor_tracking:
                            precursor_tracking[unique_key]['found_in_rt_window'] = True
                            precursor_tracking[unique_key]['spectra_count'] += 1
                        
                        # Create composite key with the ORIGINAL mz and row_id values
                        composite_key = unique_key  # Already in "mz_row_id" format
                        
                        # Initialize entry if not exists
                        if composite_key not in prm_data:
                            prm_data[composite_key] = {
                                'fragments': [],
                                'intensities': [],
                                'retention_times': [],
                                'scan_times': [],
                                'original_rt': target_rt,
                                'mz': target_mz,
                                'row_id': row_id
                            }
                        
                        # Add data
                        prm_data[composite_key]['fragments'].append(mz_array)
                        prm_data[composite_key]['intensities'].append(intensity_array)
                        prm_data[composite_key]['retention_times'].append(rt_minutes)
                        prm_data[composite_key]['scan_times'].append(rt_minutes)
                        # Add this debug print:
                        #print(f"DEBUG: \nPrecursor {composite_key} \nFragments: {mz_array} \nIntensities: {intensity_array} \nSaved scan time {rt_minutes}")
    
    # Print intensity filtering summary
    print(f"\n=== INTENSITY FILTERING SUMMARY ===")
    print(f"Applied intensity threshold: {intensity_threshold}")
    print(f"Fragments with intensity > {intensity_threshold}: {total_nonzero_intensity}")
    print(f"Fragments filtered out: {total_zero_intensity}")
    print(f"Filtering effectiveness: {(total_zero_intensity/(total_zero_intensity+total_nonzero_intensity)*100) if (total_zero_intensity+total_nonzero_intensity) > 0 else 0:.1f}% removed")
    print(f"===================================\n")

    # Print precursor tracking report
    print("\n===== PRECURSOR DETECTION REPORT =====")
    print(f"{'m/z':<10} {'RT':<8} {'Row ID':<8} {'Found in mzML':<15} {'Within RT Window':<18} {'Spectra Count':<15}")
    print("-" * 80)
    
    for key, info in sorted(precursor_tracking.items(), key=lambda x: (x[1]['mz'], x[1]['rt'] or 0)):
        mz = info['mz']
        rt = info['rt']
        row_id = info['row_id']
        rt_window_str = f"{rt-back_window:.2f}-{rt+forward_window:.2f}" if rt is not None else "N/A"
        
        print(f"{mz:<10.4f} {rt if rt is not None else 'None':<8.2f} {row_id:<8} "
              f"{'Yes' if info['found_in_mzml'] else 'No':<15} "
              f"{'Yes' if info['found_in_rt_window'] else 'No':<18} "
              f"{info['spectra_count']:<15}")
    
    # Print final data summary
    print("\nFinal data collection:")
    
    # CHECK IF ANY PRECURSORS WERE FOUND - Add this new check
    if not prm_data:
        print(f"ERROR: No matching precursors found in mzML file. Analysis cannot proceed.")
        print(f"ERROR: Processed mzML file with 0 matching precursors")
        print(f"ERROR: Processed file with 0 matching precursors")
        
        # Return empty dict to indicate failure
        return {}
    
    # Only print success messages if we actually found precursors
    for composite_key, data in prm_data.items():
        mz = data['mz']
        rt = data['original_rt']
        row_id = data['row_id']
        total_fragments = sum(len(f) for f in data['fragments'])
        
        print(f"Precursor: {composite_key}, m/z {mz:.4f}, RT {rt:.2f}, Row {row_id}: "
              f"{len(data['fragments'])} spectra with {total_fragments} total fragments")
    
    print(f"INFO: Successfully processed mzML file with {len(prm_data)} matching precursors")
    
    return prm_data

def extract_prm_fragments(mzml_file, target_mzs=None, mz_metadata=None, ms1_ppm_tolerance=10, 
                          rt_window=5.0, back_window_ratio=0.1):
    """
    Extract PRM fragments from mzML file (WRAPPER FUNCTION)
    This function is maintained for backward compatibility but now uses the row-unique implementation.
    
    Args:
        mzml_file: Path to mzML file
        target_mzs: List of target m/z values
        mz_metadata: Dictionary with metadata for each target m/z
        ms1_ppm_tolerance: PPM tolerance for matching precursors (MS1)
        rt_window: Total RT window width in minutes
        back_window_ratio: Ratio of RT window to use for backward search
    """
    # Convert old-style inputs to the new format with unique keys
    target_keys = []
    for mz in target_mzs:
        # Create a unique key based on the mz value itself (non-row-based, but works for backward compatibility)
        unique_key = f"mz_{mz}"
        target_keys.append((mz, unique_key))
    
    # Call the new implementation with converted parameters
    prm_data = extract_prm_fragments_with_unique_keys(
        mzml_file=mzml_file,
        target_mzs=target_mzs,
        target_keys=target_keys,
        mz_metadata=mz_metadata,
        ms1_ppm_tolerance=ms1_ppm_tolerance,  # <-- Changed here
        rt_window=rt_window,
        back_window_ratio=back_window_ratio
    )
    
    return prm_data

def process_fragment_batch(fragments_batch, intensity_threshold=100):
    """Process a batch of fragments to reduce memory usage"""
    fragment_intensity_map = {}
    
    for i, (fragment_array, intensity_array, scan_time) in enumerate(fragments_batch):
        for fragment, intensity in zip(fragment_array, intensity_array):
            if intensity > intensity_threshold:
                fragment_rounded = round(fragment, 4)
                scan_time_rounded = round(scan_time, 2)
                intensity_rounded = round(intensity, 2)
                
                if fragment_rounded not in fragment_intensity_map:
                    fragment_intensity_map[fragment_rounded] = {
                        'intensities': [], 'scan_times': []
                    }
                
                fragment_intensity_map[fragment_rounded]['intensities'].append(intensity_rounded)
                fragment_intensity_map[fragment_rounded]['scan_times'].append(scan_time_rounded)
    
    return fragment_intensity_map

def analyze_fragments(prm_data, intensity_threshold=1000, max_rt_difference=None, precursor_rt=None):
    """Improved fragment analysis with better intensity handling"""
    all_results = []
    
    for precursor_mz, data in prm_data.items():
        target_rt = precursor_rt or data.get('original_rt')
        
        # Create comprehensive fragment data structure
        fragment_intensity_map = {}
        
        # Process each scan individually
        for scan_idx, (fragments, intensities, scan_time) in enumerate(
            zip(data['fragments'], data['intensities'], data['scan_times'])
        ):
            # Apply RT filter if specified
            if target_rt is not None and max_rt_difference is not None:
                rt_diff = abs(scan_time - target_rt)
                if rt_diff > max_rt_difference:
                    continue
            
            # Process each fragment in the scan
            for fragment, intensity in zip(fragments, intensities):
                if intensity > intensity_threshold:
                    fragment_rounded = round(fragment, 4)
                    
                    if fragment_rounded not in fragment_intensity_map:
                        fragment_intensity_map[fragment_rounded] = {
                            'all_intensities': [],
                            'scan_times': [],
                            'max_intensity': 0,
                            'scan_count': 0
                        }
                    
                    fragment_intensity_map[fragment_rounded]['all_intensities'].append(intensity)
                    fragment_intensity_map[fragment_rounded]['scan_times'].append(scan_time)
                    fragment_intensity_map[fragment_rounded]['max_intensity'] = max(
                        fragment_intensity_map[fragment_rounded]['max_intensity'], intensity
                    )
                    fragment_intensity_map[fragment_rounded]['scan_count'] += 1
        
        # Build results using MAXIMUM intensity instead of sum
        fragments_list = []
        max_intensities_list = []  # Use max instead of sum
        scan_times_list = []
        observation_counts = []
        
        for fragment, frag_data in fragment_intensity_map.items():
            fragments_list.append(fragment)
            # Use maximum intensity instead of sum
            max_intensities_list.append(frag_data['max_intensity'])
            # Use scan time of maximum intensity
            max_idx = np.argmax(frag_data['all_intensities'])
            scan_times_list.append(frag_data['scan_times'][max_idx])
            observation_counts.append(frag_data['scan_count'])
        
        # Sort by maximum intensity
        sort_idx = np.argsort(max_intensities_list)[::-1]
        fragments_array = np.array(fragments_list)[sort_idx]
        intensities_array = np.array(max_intensities_list)[sort_idx]  # Now max intensities
        scan_times_array = np.array(scan_times_list)[sort_idx]
        observation_counts_array = np.array(observation_counts)[sort_idx]
        
        all_results.append({
            'precursor_mz': precursor_mz,
            'total_raw_fragments': sum(len(f) for f in data['fragments']),
            'num_unique_fragments': len(fragments_list),
            'fragment_mzs': fragments_array.tolist(),
            'max_intensities': intensities_array.tolist(),  # Changed from sum_intensities
            'scan_times': scan_times_array.tolist(),
            'observation_counts': observation_counts_array.tolist()
        })
    
    return pd.DataFrame(all_results)

def process_fragment_batch_with_rt_filter(fragments_batch, intensity_threshold=100, 
                                         target_rt=None, max_rt_difference=None):
    """Process a batch of fragments with optional RT filtering"""
    fragment_intensity_map = {}
    
    for i, (fragment_array, intensity_array, scan_time) in enumerate(fragments_batch):
        # Apply RT filter if specified
        if target_rt is not None and max_rt_difference is not None:
            rt_diff = abs(scan_time - target_rt)
            if rt_diff > max_rt_difference:
                continue  # Skip this scan if outside RT window
        
        for fragment, intensity in zip(fragment_array, intensity_array):
            if intensity > intensity_threshold:
                fragment_rounded = round(fragment, 4)
                scan_time_rounded = round(scan_time, 2)
                intensity_rounded = round(intensity, 2)
                
                if fragment_rounded not in fragment_intensity_map:
                    fragment_intensity_map[fragment_rounded] = {
                        'intensities': [], 'scan_times': [], 'observations': []
                    }
                
                fragment_intensity_map[fragment_rounded]['intensities'].append(intensity_rounded)
                fragment_intensity_map[fragment_rounded]['scan_times'].append(scan_time_rounded)
                fragment_intensity_map[fragment_rounded]['observations'].append({
                    'intensity': intensity_rounded,
                    'scan_time': scan_time_rounded
                })
    
    return fragment_intensity_map

def debug_raw_file_info(raw_reader):
    """Debug RAW file properties with correct fisher_py API methods"""
    try:
        print("\n=== RAW FILE DEBUG INFO ===")
        
        # Try to get basic file information using correct API
        try:
            # Test basic scan access with correct property access (NO parentheses)
            print("Testing basic scan access...")
            
            # Get scan range using PROPERTIES, not methods
            first_scan = raw_reader.first_scan  # Property, not method
            last_scan = raw_reader.last_scan    # Property, not method
            total_scans = raw_reader.number_of_scans  # Property, not method
            total_time = raw_reader.total_time_min    # Property, not method
            
            print(f"  Scan range: {first_scan} to {last_scan}")
            print(f"  Total scans: {total_scans}")
            print(f"  Total time: {total_time:.2f} minutes")
            
            # Test RT access with the correct method name
            test_scan = first_scan
            try:
                test_rt = raw_reader.get_retention_time_from_scan_number(test_scan)
                print(f"  Test scan {test_scan} RT: {test_rt:.3f} (using get_retention_time_from_scan_number)")
            except Exception as e:
                print(f"  Method get_retention_time_from_scan_number failed: {e}")
                raise
                
        except Exception as e:
            print(f"CRITICAL: Basic scan access failed: {e}")
            raise
            
        print("=== END DEBUG INFO ===\n")
        
    except Exception as e:
        print(f"Debug failed with critical error: {e}")
        raise

def get_rt_range_from_raw(raw_reader):
    """Get the actual RT range from RAW file using correct fisher_py API"""
    try:
        # Method 1: Get scan range using PROPERTIES (not methods)
        try:
            first_scan = raw_reader.first_scan      # Property access
            last_scan = raw_reader.last_scan        # Property access
            total_scans = raw_reader.number_of_scans # Property access
            total_time = raw_reader.total_time_min   # Property access
            
            print(f"Got scan range: {first_scan} to {last_scan} ({total_scans} total scans)")
            print(f"File duration: {total_time:.2f} minutes")
            
        except Exception as e:
            raise Exception(f"Failed to get scan range from properties: {e}")

        # Method 2: Get RT values using correct API
        try:
            first_rt = raw_reader.get_retention_time_from_scan_number(first_scan)
            last_rt = raw_reader.get_retention_time_from_scan_number(last_scan)
            print(f"Got RT values: {first_rt:.3f} - {last_rt:.3f}")
        except Exception as e:
            raise Exception(f"Failed to get retention times: {e}")
        
        # Validate the RT range makes sense
        if first_rt <= 0 or last_rt <= 0:
            raise Exception(f"Invalid RT values: first_rt={first_rt}, last_rt={last_rt}")
            
        if last_rt <= first_rt:
            raise Exception(f"Invalid RT range: last_rt ({last_rt}) <= first_rt ({first_rt})")
            
        # Check if RT range is suspiciously small (less than 5 minutes for LC-MS)
        rt_span = last_rt - first_rt
        if rt_span < 5:
            raise Exception(f"RT range too small ({rt_span:.1f} min) - possible API error or incomplete file")
        
        # Check if RTs are in seconds instead of minutes
        if first_rt > 500:  # Likely in seconds if > 500
            print("RTs appear to be in seconds, converting to minutes...")
            first_rt = first_rt / 60.0
            last_rt = last_rt / 60.0
            print(f"Converted RT range: {first_rt:.3f} - {last_rt:.3f} minutes")
            
        return first_rt, last_rt, first_scan, last_scan
        
    except Exception as e:
        print(f"CRITICAL ERROR: Could not read retention time range from RAW file: {e}")
        raise Exception(f"RT detection failed: {e}")

def extract_prm_fragments_from_raw_fisher(raw_file, target_mzs=None, target_keys=None, 
                                         mz_metadata=None, ms1_ppm_tolerance=10, intensity_threshold=1000, 
                                         rt_window=5.0, back_window_ratio=0.1):
    """
    Extract PRM fragments directly from RAW file using fisher_py with correct API
    """
    try:
        import fisher_py
        
        # Create RawFile object with the file path
        raw_reader = fisher_py.RawFile(raw_file)
        print(f"Successfully created RawFile object for {raw_file}")
        
    except ImportError:
        raise Exception("fisher_py not available. Please install with: pip install fisher_py")
    except Exception as e:
        raise Exception(f"fisher_py API error: {e}")
    
    # Add debug information FIRST
    #debug_raw_file_info(raw_reader)
    
    # Get the actual RT range from the RAW file with strict validation
    try:
        first_rt, last_rt, first_scan, last_scan = get_rt_range_from_raw(raw_reader)
        print(f"Successfully detected RAW file RT range: {first_rt:.3f} - {last_rt:.3f} minutes")
        print(f"Scan range: {first_scan} - {last_scan}")
        
    except Exception as e:
        print(f"FAILED TO READ RT RANGE FROM RAW FILE")
        print(f"Error: {e}")
        print(f"Cannot proceed with fragment extraction without valid RT information")
        return {}
    
    # Initialize data structures for tracking
    prm_data = {}
    precursor_tracking = {}
    
    # Calculate the backward and forward window sizes
    back_window = rt_window * back_window_ratio
    forward_window = rt_window - back_window
    
    # Initialize precursor tracking
    for target_mz, unique_key in target_keys:
        if unique_key in mz_metadata:
            precursor_tracking[unique_key] = {
                'mz': target_mz,
                'rt': mz_metadata[unique_key].get('RT'),
                'row_id': mz_metadata[unique_key].get('row_id'),
                'found_in_raw': False,
                'found_in_rt_window': False,
                'spectra_count': 0
            }
    
    print(f"\nStarting RAW file extraction from {raw_file}")
    print(f"Processing {len(target_keys)} precursor targets")
    
    # OPTIMIZED APPROACH: Collect ALL MS2 scans across RT window
    try:
        processed_targets = 0
        
        # Process each target precursor directly
        for target_mz, unique_key in target_keys:
            if unique_key not in mz_metadata:
                continue
                
            # Get target RT
            target_rt = mz_metadata[unique_key].get('RT')
            row_id = mz_metadata[unique_key].get('row_id')
            
            if target_rt is None:
                print(f"No target RT for {unique_key}, skipping")
                continue
                
            print(f"Processing target: m/z {target_mz:.4f} at RT {target_rt:.2f} min")
            
            # Calculate RT window
            rt_start = max(first_rt, target_rt - back_window)
            rt_end = min(last_rt, target_rt + forward_window)
            print(f"  Searching RT window {rt_start:.2f}-{rt_end:.2f} min")
            
            # Convert RT range to scan numbers
            try:
                start_scan = raw_reader.get_scan_number_from_retention_time(rt_start)
                end_scan = raw_reader.get_scan_number_from_retention_time(rt_end)
                
                # Collect fragment data for this precursor ACROSS ALL SCANS
                fragments_list = []
                intensities_list = []
                retention_times_list = []
                scan_count = 0
                
                # Search through EVERY scan in the RT range
                scan_debug_count = 0
                total_fragments_before_filter = 0
                total_fragments_after_filter = 0
                
                for scan_num in range(start_scan, end_scan + 1):
                    try:
                        # Get scan event to check if it's MS2 and matches our precursor
                        scan_event = raw_reader.get_scan_event_str_from_scan_number(scan_num)
                        scan_rt = raw_reader.get_retention_time_from_scan_number(scan_num)
                        
                        if 'ms2' in scan_event.lower():
                            # Extract precursor m/z from scan event
                            if '@' in scan_event:
                                try:
                                    parts = scan_event.split('@')[0].split()
                                    precursor_mz = float(parts[-1])
                                    
                                    # Check if within tolerance
                                    ppm_error = abs(precursor_mz - target_mz) / target_mz * 1e6
                                    if ppm_error <= ms1_ppm_tolerance: 
                                        # Get fragment data from THIS scan
                                        mz_array, intensity_array, charge_array, _ = raw_reader.get_scan_from_scan_number(scan_num)
                                        
                                        # DEBUG: Check what intensity filtering is happening
                                        total_fragments_before_filter += len(mz_array)
                                        
                                        # Check if there's implicit intensity filtering in fisher_py
                                        zero_count = np.sum(intensity_array == 0)
                                        nonzero_count = np.sum(intensity_array > 0)
                                        min_intensity = np.min(intensity_array) if len(intensity_array) > 0 else 0

                                        # DEBUG: Add fragment count logging
                                        # if scan_count < 5:  # Only log first 5 scans to avoid spam
                                        #     print(f"    DEBUG RAW Scan {scan_num}: {len(mz_array)} fragments, "
                                        #         f"intensity range: {min(intensity_array):.0f}-{max(intensity_array):.0f}")
                                        #     print(f"    DEBUG RAW: First 5 m/z values: {mz_array[:5]}")
                                        #     print(f"    DEBUG RAW: First 5 intensities: {intensity_array[:5]}")
                                        #     if len(mz_array) > 0:
                                        #         print(f"    DEBUG RAW: First 5 m/z values: {mz_array[:5]}")
                                        #         print(f"    DEBUG RAW: First 5 intensities: {intensity_array[:5]}")
                                            
                                        #     scan_debug_count += 1
                                        
                                        total_fragments_after_filter += len(mz_array)

                                        # Store data from THIS scan
                                        fragments_list.append(mz_array)
                                        intensities_list.append(intensity_array)
                                        retention_times_list.append(scan_rt)
                                        scan_count += 1
                                        
                                        # Update tracking
                                        precursor_tracking[unique_key]['found_in_raw'] = True
                                        precursor_tracking[unique_key]['found_in_rt_window'] = True
                                        precursor_tracking[unique_key]['spectra_count'] += 1
                                        
                                except:
                                    continue
                                    
                    except Exception as e:
                        continue
                
                # Store data if we found any scans
                if fragments_list:
                    composite_key = f"{target_mz}_{row_id}"
                    prm_data[composite_key] = {
                        'mz': target_mz,
                        'original_rt': target_rt,
                        'row_id': row_id,
                        'fragments': fragments_list,        # List of arrays, one per scan
                        'intensities': intensities_list,    # List of arrays, one per scan  
                        'scan_times': retention_times_list,  # FIXED: Use 'scan_times' key instead of 'retention_times'
                        'retention_times': retention_times_list  # Keep both for compatibility
                    }
                    
                    total_fragments = sum(len(f) for f in fragments_list)
                    print(f"  ✓ Found MS2 data: {total_fragments} fragments across {scan_count} scans")
                    print(f"  ✓ Stored data for {composite_key}")
                #else:
                    #print(f"  ✗ No matching MS2 scans found")
                    
            except Exception as e:
                print(f"  Error processing target {target_mz}: {e}")
                continue
                
            processed_targets += 1
        
        print(f"Finished processing RAW file: {processed_targets} targets processed")
        
    except Exception as e:
        print(f"Error during RAW file processing: {e}")
        return {}

    # Print precursor tracking report
    print("\n===== RAW FILE PRECURSOR DETECTION REPORT =====")
    print(f"{'m/z':<10} {'RT':<8} {'Row ID':<8} {'Found in RAW':<15} {'Within RT Window':<18} {'Spectra Count':<15}")
    print("-" * 80)
    
    for key, info in sorted(precursor_tracking.items(), key=lambda x: (x[1]['mz'], x[1]['rt'] or 0)):
        mz = info['mz']
        rt = info['rt']
        row_id = info['row_id']
        
        print(f"{mz:<10.4f} {rt if rt is not None else 'None':<8} {row_id:<8} "
              f"{'Yes' if info['found_in_raw'] else 'No':<15} "
              f"{'Yes' if info['found_in_rt_window'] else 'No':<18} "
              f"{info['spectra_count']:<15}")
    
    # CHECK IF ANY PRECURSORS WERE FOUND - Add this new check
    if len(prm_data) == 0:
        print(f"\nFinal EIC data collection from RAW file:")
        print(f"ERROR: No matching precursors found in RAW file. Analysis cannot proceed.")
        print(f"ERROR: Processed RAW file with 0 matching precursors")
        print(f"ERROR: Processed file with 0 matching precursors")
        
        # Return None or empty dict to indicate failure
        return {}
    
    # Only print success messages if we actually found precursors
    print(f"\nFinal EIC data collection from RAW file:")
    for composite_key, data in prm_data.items():
        mz = data['mz']
        rt = data['original_rt']
        row_id = data['row_id']
        total_fragments = sum(len(f) for f in data['fragments'])
        
        print(f"Precursor: {composite_key}, m/z {mz:.4f}, RT {rt:.2f}, Row {row_id}: "
              f"{len(data['fragments'])} scans with {total_fragments} total fragments for EIC")
    
    print(f"INFO: Successfully processed RAW file with {len(prm_data)} matching precursors for EIC integration")
    print(f"INFO: Processed RAW file with {len(prm_data)} matching precursors")
    
    return prm_data

def match_fragments_with_database(results_df, generated_fragments, max_rt_window=None,
                                  ms2_ppm_tolerance=20, modification_type=6, fragment_types="all", 
                                  fdr_grade_cutoff=None, **kwargs):
    
    try:
        matched_results = []
        all_raw_matches = []
        
        # Get RT filtering parameters
        max_rt_diff = kwargs.get('max_rt_difference', 1.0)  # Default 1.0 minute if not specified
        
        # Print debug info about the generated fragments DataFrame
        print("\nGenerated fragments information:")
        print(f"Total generated fragments: {len(generated_fragments)}")
        print(f"Unique glycans in generated fragments: {generated_fragments['Glycan'].unique().tolist()}")
        print(f"Columns in generated_fragments: {list(generated_fragments.columns)}")
        
        # Filter fragments by type if requested
        if fragment_types.lower() != "all":
            # Handle comma-separated list of fragment types
            fragment_type_list = [ft.strip().lower() for ft in fragment_types.lower().split(',')]
            
            print(f"Filtering theoretical fragments by types: {fragment_type_list}")
            original_count = len(generated_fragments)
            
            # Filter to include any of the specified fragment types
            generated_fragments = generated_fragments[
                generated_fragments['FragmentType'].str.lower().isin(fragment_type_list)
            ]
            
            print(f"Filtered theoretical fragments by types {fragment_type_list}: {len(generated_fragments)} of {original_count} fragments kept")
            
            if generated_fragments.empty:
                print(f"No theoretical fragments of types {fragment_type_list} found. No matching possible.")
                return pd.DataFrame(), pd.DataFrame()
        
        # Process each result row (precursor)
        for index, row in results_df.iterrows():
            # Extract the actual m/z value from the composite key
            precursor_key = row['precursor_mz']
            row_id = None
            # Handle composite keys like "1219.0123600000002_2"
            if isinstance(precursor_key, str) and '_' in precursor_key:
                precursor_mz = float(precursor_key.split('_')[0])
                row_id = float(precursor_key.split('_')[1])
            else:
                precursor_mz = float(precursor_key)
                # Ensure row_id is set even if not in the composite key
                row_id = row.get('row_id', index)
                    
            precursor_rt = row['precursor_rt'] if 'precursor_rt' in row else None
            
            # Now use the corrected precursor_mz value for the message
            if precursor_rt is not None:
                print(f"Processing precursor m/z: {precursor_mz:.4f} with RT: {precursor_rt:.2f}")
            else:
                print(f"Processing precursor m/z: {precursor_mz:.4f}")
            glycan = str(row['Glycan']).strip() if 'Glycan' in row else ''
            peptide = str(row['Peptide']).strip() if 'Peptide' in row else ''
            
            fragments = np.array(row['fragment_mzs'])
            intensities = np.array(row['max_intensities'])

            # DEBUG: Add data source identification - FIXED
            # Determine data source based on the input file type or method used
            data_source = "RAW" if "fisher" in kwargs.get('input_method', '').lower() else "mzML"
            
            print(f"DEBUG {data_source}: Processing {len(fragments)} fragments")
            print(f"DEBUG {data_source}: Intensity range: {min(intensities):.0f} - {max(intensities):.0f}")
            print(f"DEBUG {data_source}: Fragment m/z range: {min(fragments):.4f} - {max(fragments):.4f}")
            
            # DEBUG: Check for intensity differences
            high_intensity_count = np.sum(intensities > 1000)
            medium_intensity_count = np.sum((intensities > 100) & (intensities <= 1000))
            low_intensity_count = np.sum(intensities <= 100)
            
            print(f"DEBUG {data_source}: High intensity (>1000): {high_intensity_count}")
            print(f"DEBUG {data_source}: Medium intensity (100-1000): {medium_intensity_count}")
            print(f"DEBUG {data_source}: Low intensity (≤100): {low_intensity_count}")
    
            matched_fragment_indices = set()
            
            # Initialize fragment_counter here before using it
            fragment_counter = 0

            # Extract and prepare scan times
            try:
                scan_times = row['scan_times'] if 'scan_times' in row else []
                retention_times = row['retention_times'] if 'retention_times' in row else []
                
                # If scan_times is empty but retention_times is available, use retention_times
                if not scan_times and len(retention_times) > 0:
                    scan_times = retention_times
                    
                # Ensure scan times match fragment data in length and structure
                if not isinstance(scan_times, list) and hasattr(scan_times, 'tolist'):
                    scan_times = scan_times.tolist()
                    
                # Make sure we have a scan time for each fragment
                if len(scan_times) < len(fragments):
                    scan_times.extend([0] * (len(fragments) - len(scan_times)))

            except Exception as e:
                print(f"Warning: Error processing scan times: {e}")
                scan_times = [0] * len(fragments)  # Initialize with zeros
            
            # CRITICAL: Apply RT filter BEFORE database matching if precursor_rt is available
            if precursor_rt is not None and max_rt_diff is not None and max_rt_diff > 0:
                print(f"Applying RT filter BEFORE database matching: max RT difference = {max_rt_diff} min")
                
                # Calculate RT differences for all fragments
                rt_differences = np.abs(np.array(scan_times) - precursor_rt)
                
                # Create mask for fragments within RT window
                rt_filter_mask = rt_differences <= max_rt_diff
                
                # Count fragments before and after filtering
                fragments_before = len(fragments)
                
                # Apply RT filter to all arrays
                fragments = fragments[rt_filter_mask]
                intensities = intensities[rt_filter_mask]
                scan_times = np.array(scan_times)[rt_filter_mask].tolist()
                
                fragments_after = len(fragments)
                filtered_fragments = fragments_before - fragments_after
                
                print(f"RT filtering results:")
                print(f"  Fragments before RT filter: {fragments_before}")
                print(f"  Fragments after RT filter: {fragments_after}")
                print(f"  Fragments filtered out: {filtered_fragments}")
                print(f"  Retention rate: {(fragments_after/fragments_before)*100:.1f}%")
                
                if len(fragments) == 0:
                    print(f"No fragments remain after RT filtering for precursor {precursor_mz:.4f}")
                    continue  # Skip to next precursor
            else:
                print("RT filtering skipped: precursor_rt or max_rt_diff not available")
                
            # Determine matching column
            if modification_type == 6 and peptide:
                search_key = f"{peptide}-{glycan}"
                search_column = 'Glycopeptide'
                print(f"Matching using Glycopeptide: '{search_key}'")
                matches = generated_fragments[generated_fragments['Glycopeptide'] == search_key]
            else:
                search_key = glycan
                search_column = 'Glycan'
                print(f"Matching using Glycan: '{search_key}'")
                matches = generated_fragments[generated_fragments['Glycan'] == search_key]
            
            if not matches.empty:
                print(f"Found {len(matches)} theoretical fragments for {search_column} '{search_key}'")
                
                for _, db_row in matches.iterrows():
                    theoretical_mz = db_row['Fragment_mz']
                    tolerance = calculate_ppm_tolerance(theoretical_mz, ms2_ppm_tolerance)
                    
                    # FIXED: Use Fragment column directly if available, otherwise extract from Type
                    if 'Fragment' in db_row and pd.notna(db_row['Fragment']) and db_row['Fragment'] != '':
                        fragment_composition = db_row['Fragment']
                    else:
                        # Fallback to extracting from Type column
                        fragment_composition = extract_fragment_composition(db_row['Type'])
                    
                    # Find matching experimental fragments (already RT-filtered)
                    matches_idx = np.where(np.abs(fragments - theoretical_mz) <= tolerance)[0]
                    
                    for match_idx in matches_idx:
                        if match_idx not in matched_fragment_indices:
                            matched_fragment_indices.add(match_idx)
                            
                            ppm_diff = ((fragments[match_idx] - theoretical_mz) / theoretical_mz) * 1e6
                            
                            match_data = {
                                'Glycan': glycan,
                                'Glycopeptides': search_key,
                                'Precursor_mz': precursor_mz,
                                'precursor_rt': precursor_rt,
                                'Type': db_row['Type'],
                                'FragmentType': db_row['FragmentType'],
                                'Theoretical_mz': theoretical_mz,
                                'Experimental_mz': fragments[match_idx],
                                'PPM_diff': ppm_diff,
                                'Intensity': intensities[match_idx],
                                'Ions': db_row['Ions'],
                                'Fragment_mz': db_row['Fragment_mz'],
                                'scan_time': scan_times[match_idx] if match_idx < len(scan_times) else 0,
                                'row_id': row_id,
                                'Fragment': fragment_composition,  # FIXED: Use proper fragment composition
                                'Match_type': 'Raw'
                            }
                            
                            # Calculate RT difference (should be <= max_rt_diff due to pre-filtering)
                            if precursor_rt is not None:
                                match_data['rt_difference'] = abs(match_data['scan_time'] - precursor_rt)
                            
                            all_raw_matches.append(match_data)

            else:
                print(f"No theoretical fragments found for {search_column} '{search_key}'")
            
            print(f"Total matches found: {len(matched_fragment_indices)} out of {len(fragments)} RT-filtered fragments")

        # Create DataFrames from BOTH lists
        all_raw_matched_df = pd.DataFrame(all_raw_matches) if all_raw_matches else pd.DataFrame()
        
        if not all_raw_matched_df.empty:
            print(f"Created raw matches DataFrame with {len(all_raw_matched_df)} entries")
            
            # STEP 1: Calculate scores for ALL raw matches BEFORE any processing
            print("Calculating fragment scores for all raw matches...")
            all_raw_matched_df['Fragments_Score'] = 0.0
            all_raw_matched_df['FDR_Grade'] = "F"
            all_raw_matched_df['Fragments_Rating'] = "Low"
            all_raw_matched_df['Score_Details'] = ""

            # Calculate duplicate counts first for scoring
            try:
                groupby_columns = ['Precursor_mz', 'Theoretical_mz']
                if 'FragmentType' in all_raw_matched_df.columns:
                    groupby_columns.append('FragmentType')
                
                duplicate_counts = all_raw_matched_df.groupby(groupby_columns).size().reset_index(name='Duplicate_Count')
                
                # Create mapping for duplicate counts
                if 'FragmentType' in groupby_columns:
                    count_mapping = dict(zip(
                        zip(duplicate_counts['Precursor_mz'], duplicate_counts['Theoretical_mz'], duplicate_counts['FragmentType']),
                        duplicate_counts['Duplicate_Count']
                    ))
                    all_raw_matched_df['Duplicate_Count'] = all_raw_matched_df.apply(
                        lambda row: count_mapping.get((row['Precursor_mz'], row['Theoretical_mz'], row['FragmentType']), 1), axis=1
                    )
                else:
                    count_mapping = dict(zip(
                        zip(duplicate_counts['Precursor_mz'], duplicate_counts['Theoretical_mz']),
                        duplicate_counts['Duplicate_Count']
                    ))
                    all_raw_matched_df['Duplicate_Count'] = all_raw_matched_df.apply(
                        lambda row: count_mapping.get((row['Precursor_mz'], row['Theoretical_mz']), 1), axis=1
                    )
                
                #print(f"Duplicate counts calculated. Range: {all_raw_matched_df['Duplicate_Count'].min()}-{all_raw_matched_df['Duplicate_Count'].max()}")
                
            except Exception as e:
                print(f"Warning: Error calculating duplicate counts: {e}")
                all_raw_matched_df['Duplicate_Count'] = 1

            # Calculate scores for all raw matches
            for idx, row in all_raw_matched_df.iterrows():
                try:
                    score_result = calculate_Fragments_Score(row, max_rt_window=max_rt_window)
                    all_raw_matched_df.at[idx, 'Fragments_Score'] = score_result['Score']
                    all_raw_matched_df.at[idx, 'FDR_Grade'] = score_result['Letter_Grade']
                    all_raw_matched_df.at[idx, 'Fragments_Rating'] = score_result['Rating']
                    all_raw_matched_df.at[idx, 'Score_Details'] = f"PPM:{score_result['PPM_Score']:.1f} Int:{score_result['Intensity_Score']:.1f} RT:{score_result['RT_Score']:.1f} SNR:{score_result['SNR_Score']:.1f} Dup:{score_result['Duplicate_Score']:.1f}"
                except Exception as e:
                    print(f"Warning: Error calculating score for fragment {idx}: {e}")
                    all_raw_matched_df.at[idx, 'Fragments_Score'] = 0.0
                    all_raw_matched_df.at[idx, 'FDR_Grade'] = "F"
                    all_raw_matched_df.at[idx, 'Fragments_Rating'] = "Low"
                    all_raw_matched_df.at[idx, 'Score_Details'] = "Error in calculation"

            # STEP 3: NOW perform deduplication with BEST QUALITY-BASED SORTING (with RT difference as #1 priority)
            try:
                #print("Deduplicating fragments while preserving BEST QUALITY values (RT difference priority)...")
                
                # CORRECTED: Multi-criteria sorting with RT difference as #1 priority
                sort_columns = []
                sort_ascending = []
                
                # 1. FIRST priority: RT difference (closer to precursor RT is better)
                if 'rt_difference' in all_raw_matched_df.columns:
                    sort_columns.append('rt_difference')
                    sort_ascending.append(True)  # Lower RT difference is better
                
                # 2. Second priority: FDR Grade (A > B > C > D > F)
                sort_columns.append('FDR_Grade')
                sort_ascending.append(True)  # A comes before F alphabetically
                
                # 3. Third priority: Fragment Score (higher is better)
                sort_columns.append('Fragments_Score')
                sort_ascending.append(False)  # Higher score is better
                
                # 4. Fourth priority: Intensity (higher is better)
                sort_columns.append('Intensity')
                sort_ascending.append(False)  # Higher intensity is better
                
                # Apply the multi-criteria sorting with RT difference as top priority
                all_raw_matched_df = all_raw_matched_df.sort_values(sort_columns, ascending=sort_ascending)
                #print(f"Applied QUALITY-FIRST sorting: RT difference → FDR Grade → Fragment Score → Intensity")
                
                # Group by unique fragment identifiers and keep the BEST QUALITY entry (first after sorting)
                cleaned_df = all_raw_matched_df.groupby(
                    ['Precursor_mz', 'precursor_rt', 'Theoretical_mz'], dropna=False
                ).agg({
                    'Experimental_mz': 'first',
                    'Glycan': 'first',
                    'Glycopeptides': 'first',         
                    'Intensity': 'max',  
                    'PPM_diff': 'first',  
                    'Match_type': 'first',
                    'Type': 'first',
                    'FragmentType': 'first',
                    'Ions': 'first',
                    'Fragment_mz': 'first',
                    'scan_time': 'first',
                    'row_id': 'first',
                    'rt_difference': 'first',
                    'Fragments_Score': 'first',  
                    'FDR_Grade': 'first',      
                    'Fragments_Rating': 'first', 
                    'Score_Details': 'first',  
                    'Duplicate_Count': 'first',
                    'Fragment': 'first'
                }).reset_index()
                
                print(f"Deduplication complete: {len(all_raw_matched_df)} raw matches → {len(cleaned_df)} unique fragments")
                print(f"Preserved HIGHEST QUALITY matches (including best FDR) for each unique fragment")
                
            except Exception as e:
                print(f"Warning: Error during dataframe grouping: {e}")
                cleaned_df = all_raw_matched_df.copy()

            # STEP 3.2: Apply intensity threshold filtering after deduplication but before FDR cutoff
            print("\nApplying intensity threshold filtering")
            # Count fragments before filtering
            intensity_before_count = len(cleaned_df)
            print(f"  Fragments before intensity filtering: {intensity_before_count}")

            # Show intensity distribution before filtering
            if not cleaned_df.empty:
                intensity_min = cleaned_df['Intensity'].min()
                intensity_max = cleaned_df['Intensity'].max() 
                intensity_mean = cleaned_df['Intensity'].mean()
                intensity_median = cleaned_df['Intensity'].median()
                print(f"  Intensity range before filtering: {intensity_min:.1f} - {intensity_max:.1f}")
                print(f"  Mean intensity: {intensity_mean:.1f}, Median: {intensity_median:.1f}")
                
                # Count low intensity fragments
                low_intensity_fragments = (cleaned_df['Intensity'] < 1000).sum()
                print(f"  Fragments with intensity < 1000: {low_intensity_fragments} ({low_intensity_fragments/intensity_before_count*100:.1f}%)")

            # Apply intensity threshold filter (1000)
            cleaned_df = cleaned_df[cleaned_df['Intensity'] >= 1000].copy()

            # Count after filtering
            intensity_after_count = len(cleaned_df)
            intensity_filtered_count = intensity_before_count - intensity_after_count
            intensity_retention_rate = (intensity_after_count / intensity_before_count * 100) if intensity_before_count > 0 else 0

            print(f"Intensity filtering results:")
            print(f"  Threshold: 1000")
            print(f"  Fragments before: {intensity_before_count}")
            print(f"  Fragments after: {intensity_after_count}")
            print(f"  Fragments filtered out: {intensity_filtered_count}")
            print(f"  Retention rate: {intensity_retention_rate:.1f}%")

            # Check if we have any fragments left after intensity filtering
            if cleaned_df.empty:
                print("No fragments remain after intensity filtering")
                return pd.DataFrame(), all_raw_matched_df

            # STEP 3.5: Apply FDR Grade Cutoff AFTER deduplication
            if fdr_grade_cutoff is not None and 'FDR_Grade' in cleaned_df.columns:
                print(f"\nApplying FDR Grade cutoff: {fdr_grade_cutoff}")
                
                # ADD THIS DEBUG SECTION HERE:
                print(f"DEBUG: FDR Grade column exists with {len(cleaned_df)} total fragments")
                print(f"DEBUG: Unique FDR grades BEFORE filtering: {sorted(cleaned_df['FDR_Grade'].unique())}")
                print(f"DEBUG: FDR grade value counts BEFORE filtering:")
                grade_counts_before = cleaned_df['FDR_Grade'].value_counts()
                for grade, count in grade_counts_before.items():
                    print(f"  {grade}: {count}")
                
                # Count fragments before filtering
                before_count = len(cleaned_df)
                
                # Define allowed grades based on cutoff - FIXED LOGIC
                if fdr_grade_cutoff.upper() == 'A':
                    allowed_grades = ['A']
                elif fdr_grade_cutoff.upper() == 'B':
                    allowed_grades = ['A', 'B']
                elif fdr_grade_cutoff.upper() == 'C':
                    allowed_grades = ['A', 'B', 'C']
                elif fdr_grade_cutoff.upper() == 'D':
                    allowed_grades = ['A', 'B', 'C', 'D']  # ← This should include D but exclude F
                elif fdr_grade_cutoff.upper() == 'F' or fdr_grade_cutoff is None:
                    allowed_grades = ['A', 'B', 'C', 'D', 'F']  # Allow all grades
                else:
                    # Handle unexpected values - default to allowing all grades
                    print(f"Warning: Unexpected FDR grade cutoff '{fdr_grade_cutoff}', allowing all grades")
                    allowed_grades = ['A', 'B', 'C', 'D', 'F']
                
                print(f"DEBUG: Cutoff grade: {fdr_grade_cutoff}")
                print(f"DEBUG: Allowed grades: {allowed_grades}")
                
                # Apply grade filter - keep fragments whose grade is in allowed list
                grade_filter_mask = cleaned_df['FDR_Grade'].isin(allowed_grades)
                
                # ADD MORE DEBUG HERE:
                print(f"DEBUG: Grade filter mask summary:")
                print(f"  Fragments matching allowed grades: {grade_filter_mask.sum()}")
                print(f"  Fragments NOT matching allowed grades: {(~grade_filter_mask).sum()}")
                
                # Show which specific grades are being filtered out
                filtered_out_grades = cleaned_df[~grade_filter_mask]['FDR_Grade'].value_counts()
                if not filtered_out_grades.empty:
                    print(f"DEBUG: Grades being filtered out:")
                    for grade, count in filtered_out_grades.items():
                        print(f"  {grade}: {count} fragments")
                
                cleaned_df = cleaned_df[grade_filter_mask].copy()
                
                # Count after filtering
                after_count = len(cleaned_df)
                filtered_count = before_count - after_count
                retention_rate = (after_count / before_count * 100) if before_count > 0 else 0
                
                # print(f"FDR Grade filtering results:")
                # print(f"  Cutoff grade: {fdr_grade_cutoff}")
                # print(f"  Allowed grades: {allowed_grades}")
                # print(f"  Total fragments before: {before_count}")
                # print(f"  Total fragments after: {after_count}")
                # print(f"  Fragments filtered out: {filtered_count}")
                # print(f"  Retention rate: {retention_rate:.1f}%")
                
                # Show final grade distribution
                # Show final grade distribution
                if not cleaned_df.empty:
                    final_grade_counts = cleaned_df['FDR_Grade'].value_counts()
                    grade_dict = {grade: int(count) for grade, count in final_grade_counts.items()}
                    print(f"  Remaining grade distribution: {grade_dict}")
                    
                    # ADD THIS CRITICAL DEBUG - MOVED INSIDE THE NOT EMPTY BLOCK:
                    remaining_unique_grades = sorted(cleaned_df['FDR_Grade'].unique())
                    print(f"DEBUG: Unique grades AFTER filtering: {remaining_unique_grades}")
                    
                    # Check if any F grades remain when they shouldn't
                    if fdr_grade_cutoff.upper() == 'D' and 'F' in remaining_unique_grades:
                        print(f"🚨 CRITICAL BUG: F grades found after D cutoff!")
                        f_fragments = cleaned_df[cleaned_df['FDR_Grade'] == 'F']
                        print(f"Number of F grade fragments remaining: {len(f_fragments)}")
                        print(f"Sample F grade fragments:")
                        for idx, row in f_fragments.head(3).iterrows():
                            print(f"  Row {idx}: {row.get('Type', 'N/A')} - Score: {row.get('Fragments_Score', 'N/A')}")
                else:
                    print(f"  No fragments remaining after filtering")
                    # Don't try to check grades in an empty DataFrame
                    return pd.DataFrame(), all_raw_matched_df
            
            # Sort final results
            cleaned_df = cleaned_df.sort_values(['Precursor_mz', 'Theoretical_mz'])

            print(f"Final results: {len(cleaned_df)} unique HIGH-QUALITY fragments with best FDR values")
            
            return cleaned_df, all_raw_matched_df
        else:
            print("No matches to process")
            return pd.DataFrame(), pd.DataFrame()
        
    except Exception as e:
        print(f"Error in match_fragments_with_database: {e}")
        traceback.print_exc()
        return pd.DataFrame(), pd.DataFrame()  # Return empty DataFrames on error


#Integrate Areas and Visualization
def apply_savgol_filter(data, window_length=51, polyorder=2, aggressive=False):
    """Apply Savitzky-Golay filter with adjustable smoothing intensity"""
    from scipy.signal import savgol_filter
    import numpy as np
    
    if len(data) < 5:
        return data
        
    # Ensure window length is odd and appropriate for dataset
    if len(data) < window_length:
        # Use a smaller fraction of data points (25-33%)
        window_length = max(5, min(len(data) // 4 * 2 + 1, 15))
        
    # Ensure window length is odd
    if window_length % 2 == 0:
        window_length -= 1
    
    # Very small datasets need special handling
    if window_length < 5:
        return data
    
    # Ensure polyorder is appropriate
    polyorder = min(polyorder, window_length - 1)
    
    try:
        # Single pass smoothing by default
        smoothed = savgol_filter(data, window_length=window_length, polyorder=polyorder)
        
        # Only apply second pass if aggressive smoothing is requested
        if aggressive:
            second_window = min(window_length, 11)  # Smaller second window
            smoothed = savgol_filter(smoothed, window_length=second_window, polyorder=polyorder)
        
        # Preserve peak height after smoothing
        if max(data) > 0 and max(smoothed) > 0:
            scale_factor = max(data) / max(smoothed)
            smoothed = smoothed * scale_factor
        return smoothed
    except Exception as e:
        print(f"Smoothing error: {e}")
        return data

def interpolate_chromatogram(rt_array, intensity_array, factor=5):
    """Interpolate chromatogram for smoother appearance"""
    from scipy.interpolate import interp1d
    
    if len(rt_array) < 3:
        return rt_array, intensity_array
    
    # Choose interpolation kind based on number of points
    if len(rt_array) < 5:  # Not enough points for cubic
        kind = 'linear'
    else:
        kind = 'cubic'  # Use cubic when we have enough points
    
    # Create interpolation function with appropriate kind
    try:
        f = interp1d(rt_array, intensity_array, kind=kind, bounds_error=False, fill_value=0)
        
        # Create denser time array
        num_points = len(rt_array) * factor
        rt_dense = np.linspace(min(rt_array), max(rt_array), num_points)
        
        # Apply interpolation
        intensity_dense = f(rt_dense)
        
        return rt_dense, intensity_dense
    
    except Exception as e:
        print(f"Interpolation failed with {kind} method: {str(e)}")
        # Fallback to original data if interpolation fails
        return rt_array, intensity_array

def extract_fragment_areas_from_matches(cached_data, cleaned_df, back_window_ratio=0.1, 
                                   max_rt_window=None, use_strict_rt_window=True, 
                                   use_provided_rt=True, ms1_ppm_tolerance=20):
    """Corrected area extraction that properly integrates ALL matching fragments"""
    
    all_results = []
    
    for group_key, group_df in cleaned_df.groupby(['Precursor_mz', 'precursor_rt', 'Glycopeptides']):
        precursor_mz, precursor_rt, glycopeptide = group_key
        
        # Get cached data
        row_id = str(int(group_df['row_id'].iloc[0]))
        composite_key = f"{precursor_mz}_{row_id}"
        
        if composite_key not in cached_data:
            continue
            
        data = cached_data[composite_key]
        
        # Process each fragment in the group
        for _, frag_row in group_df.iterrows():
            fragment_mz = frag_row['Theoretical_mz']
            
            #print(f"\nProcessing fragment m/z {fragment_mz:.4f} for precursor RT {precursor_rt:.2f}")
            
            # STEP 1: Collect ALL matching data points across ALL scans
            all_rt_values = []
            all_intensity_values = []
            scan_count = 0
            
            for scan_idx, (rt, fragments_array, intensities_array) in enumerate(
                zip(data['retention_times'], data['fragments'], data['intensities'])
            ):
                if len(fragments_array) == 0:
                    continue
                
                # STEP 2: Find ALL fragments within PPM tolerance in this scan
                tolerance_mz = fragment_mz * (ms1_ppm_tolerance / 1e6)
                matches = np.where(np.abs(fragments_array - fragment_mz) <= tolerance_mz)[0]
                
                # STEP 3: Add ALL matching fragments from this scan (not just one!)
                for match_idx in matches:
                    all_rt_values.append(rt)
                    all_intensity_values.append(intensities_array[match_idx])
                
                if len(matches) > 0:
                    scan_count += 1
            
            #print(f"  Found {len(all_rt_values)} data points across {scan_count} scans")
            
            if not all_rt_values:
                # No matches found
                result_row = create_empty_result(frag_row)
                all_results.append(result_row)
                continue
            
            # STEP 4: Convert to arrays and sort by RT
            rt_array = np.array(all_rt_values)
            intensity_array = np.array(all_intensity_values)
            
            # Sort by RT to ensure proper integration
            sort_indices = np.argsort(rt_array)
            rt_array = rt_array[sort_indices]
            intensity_array = intensity_array[sort_indices]
            
            #print(f"  RT range: {rt_array.min():.3f} - {rt_array.max():.3f} minutes")
            #print(f"  Intensity range: {intensity_array.min():.0f} - {intensity_array.max():.0f}")
            
            # STEP 5: Apply RT window filter if needed
            if max_rt_window and use_strict_rt_window:
                back_window = max_rt_window * back_window_ratio
                forward_window = max_rt_window - back_window
                
                rt_mask = (rt_array >= (precursor_rt - back_window)) & \
                         (rt_array <= (precursor_rt + forward_window))
                
                rt_array = rt_array[rt_mask]
                intensity_array = intensity_array[rt_mask]
                
                #print(f"  After RT filtering: {len(rt_array)} points in window")
            
            # STEP 6: Calculate area using ACTUAL RT values and ALL intensities
            if len(rt_array) < 2:
                # Single point - use point height × minimal width
                area = intensity_array[0] * 0.01 if len(intensity_array) > 0 else 0
                max_intensity = intensity_array[0] if len(intensity_array) > 0 else 0
                integration_start = rt_array[0] if len(rt_array) > 0 else 0
                integration_end = rt_array[0] if len(rt_array) > 0 else 0
                width = 0.01
            else:
                # Multiple points - integrate using actual RT spacing
                from numpy import trapz
                
                # Use trapzal rule with ACTUAL RT values
                area = trapz(y=intensity_array, x=rt_array)
                max_intensity = np.max(intensity_array)
                integration_start = rt_array[0]
                integration_end = rt_array[-1]
                width = integration_end - integration_start
            
            # print(f"  CORRECTED Area: {area:.2f}")
            # print(f"  Integration window: {integration_start:.3f} - {integration_end:.3f} min")
            # print(f"  Peak width: {width:.3f} min")
            # print(f"  Max intensity: {max_intensity:.0f}")
            
            # STEP 7: Create result with ALL the data
            result_row = frag_row.copy()
            result_row['Area'] = area
            result_row['Integration_Start'] = integration_start
            result_row['Integration_End'] = integration_end
            result_row['Peak_Width'] = width
            result_row['Max_Intensity'] = max_intensity
            result_row['Total_Data_Points'] = len(all_rt_values)
            result_row['Data_Points_Used'] = len(rt_array)
            
            all_results.append(result_row)
    
    # Create DataFrame from all results
    results_df = pd.DataFrame(all_results)
    
    if not results_df.empty:
        # Count before filtering
        before_count = len(results_df)
        
        # Filter out fragments with only 1 data point
        multi_point_mask = results_df['Data_Points_Used'] > 1
        results_df = results_df[multi_point_mask].copy()
        
        # Count after filtering
        after_count = len(results_df)
        removed_count = before_count - after_count
        
        print(f"Single data point filtering results:")
        print(f"  Fragments before: {before_count}")
        print(f"  Fragments after: {after_count}")
        print(f"  Fragments removed: {removed_count} ({(removed_count/before_count*100):.1f}%)")
    
    return results_df

def create_empty_result(frag_row):
    """Create an empty result row for fragments with no matches"""
    result_row = frag_row.copy()
    result_row['Area'] = 0.0
    result_row['Integration_Start'] = 0.0
    result_row['Integration_End'] = 0.0
    result_row['Peak_Width'] = 0.0
    result_row['Max_Intensity'] = 0.0
    result_row['Total_Data_Points'] = 0
    result_row['Data_Points_Used'] = 0
    return result_row

def format_intensity(value):
    """Format intensity value in scientific notation (e.g., 1.99E6)"""
    # Get the exponent (power of 10)
    if value == 0:
        return "0.00E0"
        
    exponent = int(np.floor(np.log10(abs(value))))
    
    # Calculate the mantissa (the part before E)
    mantissa = value / (10 ** exponent)
    
    # Format with 2 decimal places for mantissa
    return f"{mantissa:.2f}E{exponent}"

def plot_fragment_eics(cached_data, matched_fragments, glycan_code, peptide=None, 
                      rt_window=5.0, max_rt_window=None, use_strict_rt_window=True, 
                      use_provided_rt=True, back_window_ratio=0.1, output_dir=None,
                      display_time_extension=0.0, use_intensity_instead_of_area=False, 
                      fragment_types="all", max_fragments_displayed=30):
    """
    Plot EICs for the integrated fragments for each precursor.
    
    Args:
        cached_data: Dictionary of cached mzML data
        matched_fragments: DataFrame of matched fragments with integration info
        glycan_code: String glycan code
        peptide: Optional peptide sequence for glycopeptides
        rt_window: RT window for fragment matching (minutes)
        max_rt_window: Maximum RT window for integration (minutes)
        use_strict_rt_window: Whether to use a strict RT window
        use_provided_rt: Whether to use the RT from the matched fragments
        back_window_ratio: Ratio of RT window to use for backward search
        output_dir: Directory to save plots
        display_time_extension: Time to extend display window on each side
        use_intensity_instead_of_area: Whether to use intensity instead of area for metrics
        fragment_types: Which fragment types to plot ("all", "b", "by", "y", "yy")
        max_fragments_displayed: Maximum number of fragments to display in legend and plots
    
    Returns:
        Dictionary mapping precursor keys to generated figures
    """
    try:
        from matplotlib.gridspec import GridSpec
        
        # Create output directory if specified
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        if matched_fragments.empty:
            print("No matched fragments to plot")
            return {}
        
        # Filter fragments based on selected fragment type
        if fragment_types.lower() != "all":
            # Convert to lowercase for case-insensitive comparison
            frag_type = fragment_types.lower()
            # Filter matched_fragments to only include the specified fragment type
            original_count = len(matched_fragments)
            matched_fragments = matched_fragments[matched_fragments['FragmentType'].str.lower() == frag_type]
            print(f"Filtered fragments by type '{frag_type}': {len(matched_fragments)} of {original_count} fragments kept")
            
            if matched_fragments.empty:
                print(f"No fragments of type '{frag_type}' found. Nothing to plot.")
                return {}
        
        # Group by precursor m/z and RT to create separate plots for each precursor
        precursor_groups = matched_fragments.groupby(['Precursor_mz', 'precursor_rt'])
        print(f"Creating EIC plots for {len(precursor_groups)} precursors")
        
        # Dictionary to store generated figures
        generated_figures = {}
        
        # Process each precursor group
        for group_key, group_df in precursor_groups:
            precursor_mz, precursor_rt = group_key
            
            # Get row_id from the first fragment to create the correct cache key
            if 'row_id' in group_df.columns:
                row_id = group_df['row_id'].iloc[0]
                if isinstance(row_id, float):
                    row_id = str(int(row_id))  # Convert float to string without decimal
                else:
                    row_id = str(row_id)
            else:
                print(f"Warning: row_id not found for precursor {precursor_mz}, skipping")
                continue
                
            # Create composite key to access cached data
            composite_key = f"{precursor_mz}_{row_id}"
            
            if composite_key not in cached_data:
                print(f"Warning: No cached data found for key {composite_key}, skipping")
                continue
                
            precursor_data = cached_data[composite_key]
            
            # Extract data from cache
            rt_array = np.array(precursor_data.get('retention_times', []))
            fragments_list = precursor_data.get('fragments', [])
            intensities_list = precursor_data.get('intensities', [])
            
            if len(rt_array) == 0 or len(fragments_list) == 0:
                print(f"Warning: No data found for precursor {precursor_mz}, skipping")
                continue
                
            # Determine time units (seconds vs minutes)
            is_seconds = np.mean(rt_array) > 100  # Assume > 100 is seconds
            if is_seconds:
                rt_array = rt_array / 60.0  # Convert to minutes for plotting
                
            # Create figure
            fig, ax = plt.subplots(figsize=(10, 6))
            
            # Get fragment m/z values from this precursor group
            fragment_mzs = group_df['Theoretical_mz'].values
            
            # Track fragment traces and intensities
            fragment_traces = {}
            global_max_intensity = 0
            max_rt = 0
            
            # Determine metric name and initialize total metric value
            metric_name = "Intensity" if use_intensity_instead_of_area else "Area"
            total_metric_value = 0
            
            # Process each MS2 scan
            for scan_idx, (scan_fragments, scan_intensities) in enumerate(zip(fragments_list, intensities_list)):
                scan_fragments = np.array(scan_fragments)
                scan_intensities = np.array(scan_intensities)
                
                # Match target fragments within tolerance
                for frag_idx, target_mz in enumerate(fragment_mzs):
                    # Find matches within 20 ppm tolerance
                    tolerance = target_mz * (20 / 1e6)  # 20 ppm
                    matches = np.where(np.abs(scan_fragments - target_mz) <= tolerance)[0]
                    
                    if len(matches) > 0:
                        match_idx = matches[0]
                        intensity = scan_intensities[match_idx]
                        
                        if target_mz not in fragment_traces:
                            # Get type and ion info from the DataFrame
                            frag_row = group_df[group_df['Theoretical_mz'] == target_mz].iloc[0]
                            fragment_traces[target_mz] = {
                                'intensities': np.zeros_like(rt_array),
                                'type': frag_row['Type'] if 'Type' in frag_row else '',
                                'fragment_type': frag_row['FragmentType'] if 'FragmentType' in frag_row else '',
                                'ion': frag_row['Ions'] if 'Ions' in frag_row else '',
                                'area': frag_row['Area'] if 'Area' in frag_row else 0.0,
                                'max_intensity': 0.0,  # Track max intensity for each fragment
                                'integration_start': frag_row['Integration_Start'] if 'Integration_Start' in frag_row else None,
                                'integration_end': frag_row['Integration_End'] if 'Integration_End' in frag_row else None
                            }
                            
                        fragment_traces[target_mz]['intensities'][scan_idx] = intensity
                        
                        # Update max intensity for this fragment
                        if intensity > fragment_traces[target_mz]['max_intensity']:
                            fragment_traces[target_mz]['max_intensity'] = intensity
                        
                        # Update global max intensity and corresponding RT
                        if intensity > global_max_intensity:
                            global_max_intensity = intensity
                            max_rt = rt_array[scan_idx]
            
            # Integration boundaries for visualization
            integration_boundaries = {}
            
            # Sort fragments by intensity before plotting
            fragment_items = []
            for frag_mz, trace in fragment_traces.items():
                max_intensity = np.max(trace['intensities']) if len(trace['intensities']) > 0 else 0
                area = trace['area']
                
                # Calculate the metric value based on preference
                if use_intensity_instead_of_area:
                    metric_value = trace['max_intensity']
                else:
                    metric_value = area
                
                # Add to total metric value
                total_metric_value += metric_value
                
                # Store integration boundaries for visualization
                if trace['integration_start'] is not None and trace['integration_end'] is not None:
                    integration_boundaries[frag_mz] = {
                        'left_rt': trace['integration_start'],
                        'right_rt': trace['integration_end'],
                        'apex_rt': max_rt  # Use max RT as apex
                    }
                
                # Store fragment data for sorting
                fragment_items.append({
                    'frag_mz': frag_mz, 
                    'trace': trace, 
                    'max_intensity': max_intensity,
                    'area': area
                })
            
            # Sort by maximum intensity in descending order
            fragment_items.sort(key=lambda x: x['max_intensity'], reverse=True)
            
            # Limit to top 30 fragments for the legend and plot labels
            plot_items = fragment_items[:30] if len(fragment_items) > 30 else fragment_items
            
            # Plot fragment traces in order of intensity (most intense first)
            colors = plt.cm.tab10(np.linspace(0, 1, len(fragment_traces)))
            
            # Create legend entries list - now limited to top 30
            legend_handles = []
            max_intensity_at_rt = 0

            # Plot all fragments but only include top 30 in legend
            for i, item in enumerate(fragment_items):
                frag_mz = item['frag_mz']
                trace = item['trace']
                max_intensity = item['max_intensity']
                area = item['area']
                color = colors[i % len(colors)]
                
                intensities = trace['intensities']
                relative_intensity = (intensities / global_max_intensity) * 100 if global_max_intensity > 0 else intensities
                
                # Sort by retention time
                sort_idx = np.argsort(rt_array)
                sorted_rt = rt_array[sort_idx]
                sorted_intensity = relative_intensity[sort_idx]
                
                # Apply smoothing if enough points
                if len(sorted_rt) >= 5:
                    smoothed = apply_savgol_filter(sorted_intensity)
                    # Find intensity at or near precursor RT
                    closest_idx = np.abs(sorted_rt - precursor_rt).argmin()
                    if abs(sorted_rt[closest_idx] - precursor_rt) < 0.1:  # Only consider points close to target RT
                        if smoothed[closest_idx] > max_intensity_at_rt:
                            max_intensity_at_rt = smoothed[closest_idx]
                    line = ax.plot(sorted_rt, smoothed, color=color, linewidth=2)[0]
                else:
                    # For sparse data, find intensity at/near precursor RT
                    closest_idx = np.abs(sorted_rt - precursor_rt).argmin()
                    if abs(sorted_rt[closest_idx] - precursor_rt) < 0.1:
                        if sorted_intensity[closest_idx] > max_intensity_at_rt:
                            max_intensity_at_rt = sorted_intensity[closest_idx]
                    line = ax.plot(sorted_rt, sorted_intensity, color=color, linewidth=2)[0]

                # Add integration boundary markers and fill for this fragment
                if frag_mz in integration_boundaries:
                    bounds = integration_boundaries[frag_mz]
                    left_rt = bounds['left_rt']
                    right_rt = bounds['right_rt']
                    
                    # Only highlight the integration region with filled area
                    mask = (sorted_rt >= left_rt) & (sorted_rt <= right_rt)
                    if len(sorted_rt) >= 5:
                        ax.fill_between(sorted_rt[mask], smoothed[mask], color=color, alpha=0.3)
                    else:
                        ax.fill_between(sorted_rt[mask], sorted_intensity[mask], color=color, alpha=0.3)

                # Only add to legend if in top 30 fragments (preserves plotting of all fragments)
                if i < max_fragments_displayed:
                    legend_handles.append((line, f"{i+1}. {trace['type']} ({trace['ion']}): m/z {frag_mz:.4f}"))
            
            # Format glycopeptide ID
            glycopeptide_id = f"{glycan_code}"
            if peptide:
                glycopeptide_id = f"{peptide}-{glycan_code}"
            
            # Add fragment count to the title if we limited the labels
            if len(fragment_items) > max_fragments_displayed:
                title_suffix = f"\nShowing top {max_fragments_displayed} of {len(fragment_items)} fragments"
            else:
                title_suffix = ""
            
            # Customize main plot with INCREASED FONT SIZE AND WEIGHT
            ax.set_xlabel('Retention Time (min)', fontsize=14, fontweight='bold')
            ax.set_ylabel('Relative Abundance (%)', fontsize=14, fontweight='bold')
            ax.set_title(f'{glycopeptide_id}\nPrecursor m/z: {precursor_mz:.4f}, RT: {precursor_rt:.2f} min{title_suffix}', 
                        fontsize=14, fontweight='bold')
            ax.set_ylim(0, 105)
            
            # Make tick labels larger and bold
            ax.tick_params(axis='both', labelsize=14, width=2)
            for label in ax.get_xticklabels() + ax.get_yticklabels():
                label.set_fontweight('bold')
            
            # Set x-axis limits with the new display time extension parameter
            rt_min = max(0, precursor_rt - 2.5 - display_time_extension)
            rt_max = precursor_rt + 2.5 + display_time_extension
            ax.set_xlim(rt_min, rt_max)

            # Add annotations to main plot
            ax.text(0.02, 0.98, f"{format_intensity(global_max_intensity)}",
                    transform=ax.transAxes, fontsize=14, va='top', fontweight='bold')
            # Update the annotation text based on metric preference:
            ax.text(0.05, 0.6, f"Total {metric_name}: {format_intensity(total_metric_value)}",
                    transform=ax.transAxes, fontsize=16, va='top', fontweight='bold')
            
            # MODIFIED: Place RT annotation at top of peaks (105% of height)
            # Always place the RT annotation at the top of the plot instead of midway
            ax.text(precursor_rt, 102, f"{precursor_rt:.2f}",
                    fontsize=14, va='bottom', ha='center', fontweight='bold', color='black')
            
            # Remove top and right spines
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            # Make remaining spines thicker for better visibility
            ax.spines['bottom'].set_linewidth(1.5)
            ax.spines['left'].set_linewidth(1.5)
            
            # Create legend outside the plot with limited entries
            lines = [h[0] for h in legend_handles]
            labels = [h[1] for h in legend_handles]
            # In the plot_fragment_eics function, locate line 5846 and replace with this:
            legend = ax.legend(lines, labels, loc='center left', fontsize=10, bbox_to_anchor=(1.05, 0.5))
            # Apply bold font to legend text
            for text in legend.get_texts():
                text.set_fontweight('bold')
            
            plt.tight_layout()
            plt.subplots_adjust(right=0.75)
            
            # Store the figure in the dictionary
            generated_figures[composite_key] = fig
            
            # Save the figure if output directory specified
            if output_dir:
                if fragment_types.lower() != "all":
                    filename = f"{output_dir}/EIC_{glycan_code}_{precursor_mz:.4f}_{precursor_rt:.2f}_{fragment_types.lower()}.svg"
                else:
                    filename = f"{output_dir}/EIC_{glycan_code}_{precursor_mz:.4f}_{precursor_rt:.2f}_{fragment_types}.svg"
                try:
                    plt.savefig(filename, format='svg', bbox_inches='tight')
                    print(f"Saved SVG plot to {filename}")
                except Exception as e:
                    print(f"Error saving plot: {str(e)}")
            
        return generated_figures
        
    except Exception as e:
        print(f"Error plotting fragment EICs: {str(e)}")
        traceback.print_exc()
        return {}
    
def plot_ms2_spectra(cached_data, matched_fragments, glycan_code, peptide=None, max_fragments_displayed=30, output_dir=None):
    """
    Plot MS2 spectra showing ONLY the matched fragments with intensities relative to the
    most intense matched fragment, limited to the top most intense fragments.
    
    Args:
        cached_data: Dictionary of cached mzML data
        matched_fragments: DataFrame of matched fragments
        glycan_code: String glycan code
        peptide: Optional peptide sequence for glycopeptides
        output_dir: Directory to save plots
    
    Returns:
        Dictionary mapping precursor keys to generated MS2 spectrum figures
    """
    try:
        
        # Create output directory if specified
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        if matched_fragments.empty:
            print("No matched fragments to plot MS2 spectra")
            return {}
        
        # Group by precursor m/z and RT
        precursor_groups = matched_fragments.groupby(['Precursor_mz', 'precursor_rt'])
        print(f"Creating MS2 spectrum plots for {len(precursor_groups)} precursors")
        
        # Dictionary to store generated figures
        generated_figures = {}
        skipped_count = 0
        
        # Process each precursor group
        for group_key, group_df in precursor_groups:
            precursor_mz, precursor_rt = group_key
            
            # Get row_id from the first fragment to create the correct cache key
            if 'row_id' in group_df.columns:
                row_id = group_df['row_id'].iloc[0]
                if isinstance(row_id, float):
                    row_id = str(int(row_id))
                else:
                    row_id = str(row_id)
            else:
                print(f"Warning: row_id not found for precursor {precursor_mz}, skipping")
                continue
                
            # Create composite key to access cached data
            composite_key = f"{precursor_mz}_{row_id}"
            
            if composite_key not in cached_data:
                print(f"Warning: No cached data found for key {composite_key}, skipping")
                continue
                
            precursor_data = cached_data[composite_key]
            
            # Find scan closest to the target retention time
            closest_scan = None
            min_rt_diff = float('inf')
            
            for scan_idx, rt in enumerate(precursor_data.get('retention_times', [])):
                rt_diff = abs(rt - precursor_rt)
                if rt_diff < min_rt_diff and len(precursor_data['intensities'][scan_idx]) > 0:
                    min_rt_diff = rt_diff
                    closest_scan = scan_idx
            
            # Only proceed if we have a scan within 0.5 minutes of the target RT
            if min_rt_diff > 0.5 or closest_scan is None:
                print(f"Skipping MS2 plot for {precursor_mz:.4f} @ RT {precursor_rt:.2f}: No MS2 scan within 0.5 min of target RT (closest is {min_rt_diff:.2f} min)")
                skipped_count += 1
                continue
                
            # Use the closest scan for MS2 display
            max_intensity_scan = closest_scan
            
            # Get the MS2 data for the selected scan
            if len(precursor_data.get('fragments', [])) > max_intensity_scan:
                mz_array = np.array(precursor_data['fragments'][max_intensity_scan])
                intensity_array = np.array(precursor_data['intensities'][max_intensity_scan])
                scan_time = precursor_data['retention_times'][max_intensity_scan] if len(precursor_data['retention_times']) > max_intensity_scan else 0
                
                # Print RT difference for debugging
                print(f"Using MS2 scan at RT {scan_time:.2f} min (target RT: {precursor_rt:.2f}, diff: {abs(scan_time - precursor_rt):.2f} min)")
            else:
                print(f"Warning: Invalid scan index {max_intensity_scan} for precursor {precursor_mz}, skipping")
                continue
            
            # Format glycopeptide ID
            glycopeptide_id = f"{glycan_code}"
            if peptide:
                glycopeptide_id = f"{peptide}-{glycan_code}"
            
            # Plot the MS2 spectrum - ONLY showing matched fragments
            fig = plt.figure(figsize=(10, 6))
            ax = fig.add_subplot(111)
            
            # Prepare fragment matches
            fragment_matches = []
            for _, row in group_df.iterrows():
                fragment_matches.append({
                    'Experimental': row['Experimental_mz'],
                    'Intensity': row['Intensity'] if 'Intensity' in row else 0,
                    'Type': row['Type'] if 'Type' in row else '',
                    'Ions': row['Ions'] if 'Ions' in row else '',
                })
            
            # Dictionary to track label positions
            label_positions = {}
            
            # Find maximum intensity among matched fragments
            max_matched_intensity = 0
            
            if fragment_matches:
                # First find the maximum intensity among matched fragments
                for match in fragment_matches:
                    mz = match['Experimental']
                    matches = np.where(np.abs(mz_array - mz) <= mz * (20 / 1e6))[0]
                    if matches.size > 0:
                        peak_idx = matches[0]
                        ms2_intensity = intensity_array[peak_idx]
                        if ms2_intensity > max_matched_intensity:
                            max_matched_intensity = ms2_intensity
                
                # Ensure we have a valid max intensity (use original if no matches found)
                if max_matched_intensity <= 0:
                    max_matched_intensity = np.max(intensity_array) if len(intensity_array) > 0 else 1.0
                    print(f"Warning: No valid matched fragments, using global max intensity: {max_matched_intensity}")
                #else:
                    #print(f"Using max matched fragment intensity for scaling: {max_matched_intensity}")
                
                # Add intensities to fragment matches and sort by intensity
                for match in fragment_matches:
                    mz = match['Experimental']
                    matches = np.where(np.abs(mz_array - mz) <= mz * (20 / 1e6))[0]
                    if matches.size > 0:
                        peak_idx = matches[0]
                        match['MS2_Intensity'] = intensity_array[peak_idx]
                    else:
                        match['MS2_Intensity'] = 0
                
                # Sort by intensity (descending)
                fragment_matches.sort(key=lambda x: x['MS2_Intensity'], reverse=True)
                
                # Limit to top max_fragments_displayed fragments
                limited_matches = fragment_matches[:max_fragments_displayed] if len(fragment_matches) > max_fragments_displayed else fragment_matches
                
                # Add a note to the title if we limited the fragments
                title_suffix = f"\nShowing top {max_fragments_displayed} of {len(fragment_matches)} fragments" if len(fragment_matches) > max_fragments_displayed else ""
                
                # Sort by m/z for consistent appearance
                limited_matches.sort(key=lambda x: x['Experimental'])
                
                # Plot each matched fragment as a stem
                for match in limited_matches:
                    mz = match['Experimental']
                    
                    # Find the actual peak in the MS2 spectrum
                    matches = np.where(np.abs(mz_array - mz) <= mz * (20 / 1e6))[0]
                    if matches.size > 0:
                        peak_idx = matches[0]
                        ms2_intensity = intensity_array[peak_idx]
                        # Scale relative to max matched fragment intensity
                        relative_intensity = (ms2_intensity / max_matched_intensity) * 100
                        
                        # Plot the peak as a stem with red color
                        markerline, stemlines, baseline = ax.stem(
                            [mz], [relative_intensity], 
                            basefmt=' ', linefmt='gray', markerfmt='ro'
                        )
                        plt.setp(stemlines, 'linewidth', 2)
                        plt.setp(markerline, 'markersize', 3)
                        
                        # Add ion label
                        if 'Ions' in match:
                            # Determine if this is a low-intensity peak (less than 10% of max)
                            is_low_intensity = relative_intensity < 2
                            
                            # For low intensity peaks, start above peak instead of below
                            ion_height = relative_intensity + 1 if is_low_intensity else relative_intensity - 5
                            
                            # Make sure the label doesn't go below axis
                            ion_height = max(ion_height, 2)  # Keep labels at least 2 units above axis
                            
                            # Avoid label collisions
                            overlap = True
                            attempt_count = 0
                            while overlap and attempt_count < 5:
                                overlap = False
                                for pos in label_positions:
                                    if abs(mz - pos[0]) < 20 and abs(ion_height - pos[1]) < 10:
                                        overlap = True
                                        break
                                if overlap:
                                    # For low intensity peaks, move further up instead of down
                                    if is_low_intensity:
                                        ion_height += 5
                                    else:
                                        ion_height += 5
                                        # Make sure we don't go below axis while avoiding overlap
                                        ion_height = max(ion_height, 2)
                                    attempt_count += 1
                            
                            # Add to label positions
                            label_positions[(mz, ion_height)] = True
                            
                            # Add the ion label
                            ax.text(mz, ion_height, 
                                f"{match['Ions']}",
                                rotation=0, ha='center', va='bottom',
                                fontsize=7, color='red', weight='bold')
                            
                            # Add m/z value below
                            ax.text(mz, ion_height + 7,
                                f"{mz:.2f}",
                                rotation=0, ha='center', va='bottom',
                                fontsize=8, color='blue', weight='bold')

                            # Add type label above if available
                            if 'Type' in match:
                                # Check if it's a peptide y fragment (look for pattern like "y1", "y2", etc.)
                                # In the plot_ms2_spectra function, modify the is_peptide_y_fragment check:

                                # Check if it's a peptide y or b fragment (look for pattern like "y1", "y2", "b1", "b2", etc.)
                                is_peptide_fragment = (match['Type'].startswith('y') and match['Type'][1:].isdigit()) or \
                                                    (match['Type'].startswith('b') and match['Type'][1:].isdigit())
                                                                
                                # Set rotation based on type - always horizontal (0°) for peptide fragments
                                label_rotation = 0 if is_peptide_fragment or relative_intensity > 70 else 90
                                
                                ax.text(mz, ion_height + 12,
                                    f"{match['Type']}",
                                    rotation=label_rotation, ha='center', va='bottom',
                                    fontsize=8, color='black', weight='bold')
            
            # Determine time unit
            rt = scan_time
            rt_min = rt / 60.0 if rt > 100 else rt  # Convert to minutes if rt is in seconds
            
            # Add title with glycopeptide ID and precursor information
            ax.set_title(f"MS2 Spectrum for {glycopeptide_id}\nPrecursor m/z: {precursor_mz:.4f}, RT: {rt_min:.2f} min{title_suffix}",
                        fontsize=14, weight='bold')

            # Add maximum intensity annotation - use max matched intensity now
            ax.text(0.1, 1.01, f"{format_intensity(max_matched_intensity)}",
                    transform=ax.transAxes,
                    fontsize=14, va='top', ha='right', weight='bold',
                    bbox=dict(facecolor='white', ec='none', alpha=0.7))
            
            # Customize axes
            ax.set_xlabel('m/z', fontsize=14, weight='bold')
            ax.set_ylabel('Relative Abundance (%)', fontsize=14, weight='bold')
            ax.set_ylim(0, 110)
            for label in ax.get_xticklabels() + ax.get_yticklabels():
                label.set_fontweight('bold')

            # Set dynamic x-axis limits based on matched fragment range
            if fragment_matches:
                all_mz = [match['Experimental'] for match in fragment_matches]
                min_mz = max(min(all_mz) - 50, 0)
                max_mz = max(all_mz) + 50
                ax.set_xlim(min_mz, max_mz)
            
            # Remove top and right spines for cleaner look
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            
            plt.tight_layout()
            
            # Store the figure in the dictionary
            generated_figures[composite_key] = fig
            
            # Save the figure if output directory specified
            if output_dir:
                filename = f"{output_dir}/MS2_{glycan_code}_{precursor_mz:.4f}_{precursor_rt:.2f}.svg"
                try:
                    plt.savefig(filename, format='svg', bbox_inches='tight')
                    print(f"Saved SVG plot to {filename}")
                except Exception as e:
                    print(f"Error saving SVG plot: {str(e)}")
            
        return generated_figures
        
    except Exception as e:
        import traceback
        print(f"Error plotting MS2 spectra: {str(e)}")
        traceback.print_exc()
        return {}

def calculate_Fragments_Score(fragment_row, max_ppm_error=20, max_rt_window=None):
    """
    Calculate a comprehensive confidence score (0-100) for a matched fragment based on multiple parameters.
    
    Parameters considered:
    1. PPM deviation - lower deviation gets higher score (25%) - UPDATED
    2. Intensity - higher intensity gets higher score (15%) - ADJUSTED
    3. RT difference - smaller RT difference gets higher score (15%)
    4. Signal-to-Noise Ratio - higher SNR gets higher score (15%) - UPDATED
    5. Duplicate Count - more matched fragments get higher score (30%) - ADJUSTED
  
    
    Args:
        fragment_row: A row from the matched fragments DataFrame
        max_ppm_error: Maximum acceptable PPM error (default 20)
        max_rt_window: Maximum acceptable RT window in minutes
        
    Returns:
        Dictionary with score, rating, and detailed metrics
    """
    # Initialize scores
    max_rt_diff = 1.5 if max_rt_window is None else max_rt_window
    
    # Initialize all potential scores
    ppm_score = 0
    intensity_score = 0
    rt_score = 0
    snr_score = 0
    duplicate_score = 0
    
    # 1. PPM Deviation Score (25%) - lower is better - UPDATED FROM 15%
    if 'PPM_diff' in fragment_row:
        ppm_error = abs(fragment_row['PPM_diff'])
        # Convert to 0-20 scale (0 = max error, 20 = no error)
        ppm_score = 25 * max(0, (1 - ppm_error / max_ppm_error))
    
    # 2. Intensity Score (15%) - higher is better - REDUCED FROM 20%
    if 'Intensity' in fragment_row and fragment_row['Intensity'] > 0:
        # Use log scale for intensity (typically spans many orders of magnitude)
        log_intensity = np.log10(max(1, fragment_row['Intensity']))
        # Scale from 0-15 based on logarithmic intensity (4-7 is typical range)
        intensity_score = 15 * min(1, log_intensity / 7)
    
    # 3. RT Difference Score (15%) - smaller difference is better
    if 'scan_time' in fragment_row and 'precursor_rt' in fragment_row:
        rt_diff = abs(fragment_row['scan_time'] - fragment_row['precursor_rt'])
        # Convert to 0-15 scale (0 = max diff, 15 = no diff)
        rt_score = 15 * max(0, (1 - rt_diff / max_rt_diff))
    
    # 4. Signal-to-Noise Ratio Score (15%) - REDUCED FROM 20%
    if 'SNR' in fragment_row:
        snr = fragment_row['SNR']
    else:
        # Estimate SNR based on intensity
        estimated_snr = 0
        if 'Intensity' in fragment_row:
            log_intensity = np.log10(max(1, fragment_row['Intensity']))
            # Simplified formula without depending on peak width
            estimated_snr = log_intensity * 2  # Scale factor adjusted
            estimated_snr = min(30, estimated_snr)  # Cap at 30
        snr = estimated_snr
    
    # Scale SNR to score (typically 10+ is excellent) - NOW 15 points max
    snr_score = 15 * min(1.0, snr / 10.0)
    
    # 5. Duplicate Count Score (30%) - more duplicates is better - INCREASED FROM 25%
    if 'Duplicate_Count' in fragment_row:
        duplicate_count = fragment_row['Duplicate_Count']
        #print(f"DEBUG: Using Duplicate_Count = {duplicate_count} for scoring")
        # Scale from 0-30 with maximum at 5 duplicates
        duplicate_score = 30 * min(1.0, duplicate_count / 5.0)
    else:
        # Default to medium score if no data available
        duplicate_score = 15.0  # Half of maximum (30/2)
        #print(f"DEBUG: No Duplicate_Count field found, using default score 15.0")
    
    # Calculate total score (sum of all component scores)
    # New total: 25 + 15 + 15 + 15 + 30 = 100%
    total_score = (
        ppm_score + 
        intensity_score + 
        rt_score + 
        snr_score + 
        duplicate_score 
    )
    
    # Ensure score is between 0-100
    total_score = max(0, min(100, total_score))
    
    # Determine letter grade
    if total_score >= 90:
        letter_grade = "A"  # Excellent peak
    elif total_score >= 75:
        letter_grade = "B"  # Good peak
    elif total_score >= 65:
        letter_grade = "C"  # Fair peak
    elif total_score >= 50:
        letter_grade = "D"  # Poor peak
    else:
        letter_grade = "F"  # Failed peak
    
    # Determine original rating for backward compatibility
    if total_score >= 75:
        rating = "High"
    elif total_score >= 50:
        rating = "Medium"
    else:
        rating = "Low"

        # Create detailed score breakdown string
    score_details = (
        f"PPM:{ppm_score:.1f}/20, "
        f"Int:{intensity_score:.1f}/15, "
        f"RT:{rt_score:.1f}/15, "
        f"SNR:{snr_score:.1f}/15, "
        f"Dup:{duplicate_score:.1f}/30, "
    )
     
    # Return comprehensive dictionary with all scores
    return {
        'Score': total_score,
        'Rating': rating,
        'Letter_Grade': letter_grade,
        'PPM_Score': ppm_score,  
        'Intensity_Score': intensity_score,
        'RT_Score': rt_score,
        'SNR_Score': snr_score,
        'Duplicate_Score': duplicate_score,
        'Estimated_SNR': snr,
        'Score_Details': score_details
    }


#Optimizations
def get_multiprocessing_context():
    """Return appropriate multiprocessing context based on environment"""
    try:
        # When running as a frozen application (PyInstaller package)
        if getattr(sys, 'frozen', False):
            print("Running as frozen application - using spawn method for multiprocessing")
            return multiprocessing.get_context('spawn')
        else:
            # In development, use the default method
            print("Running in development mode - using default multiprocessing method")
            return multiprocessing
    except Exception as e:
        print(f"Warning: Error setting multiprocessing context: {e}")
        return multiprocessing
######
def process_single_file(mzml_file, ms1_ppm_tolerance, rt_window, back_window_ratio):
    """
    Process a single mzML file and extract fragment data.
    
    Args:
        mzml_file: Path to the mzML file to process
        
    Returns:
        Dictionary containing processed data for the mzML file
    """
    try:
        print(f"Processing file: {mzml_file}")
        file_basename = os.path.splitext(os.path.basename(mzml_file))[0]
        
        # Read target m/z values from Excel file
        excel_file = "glycan_list.xlsx"  # This should be a parameter or global variable
        target_mzs, mz_metadata, original_df = read_target_mzs_from_excel(excel_file)
        
        # Extract PRM fragments
        prm_data = extract_prm_fragments(
            mzml_file=mzml_file,
            target_mzs=target_mzs,
            mz_metadata=mz_metadata,
            ms1_ppm_tolerance=ms1_ppm_tolerance,
            rt_window=rt_window,
            back_window_ratio=back_window_ratio
        )
        
        # Analyze fragments
        results_df = analyze_fragments(prm_data, intensity_threshold=100)
        
        # Add file information
        results_df['File'] = file_basename
        
        return {
            'file': mzml_file,
            'basename': file_basename,
            'prm_data': prm_data,
            'results': results_df,
            'metadata': mz_metadata
        }
        
    except Exception as e:
        print(f"Error processing file {mzml_file}: {str(e)}")
        traceback.print_exc()
        return {
            'file': mzml_file,
            'basename': os.path.splitext(os.path.basename(mzml_file))[0],
            'error': str(e),
            'prm_data': {},
            'results': pd.DataFrame(),
            'metadata': {}
        }

def process_multiple_files(mzml_files, max_workers=None):
    """Process multiple mzML files in parallel with memory-efficient multiprocessing"""
    # Get the appropriate multiprocessing context for your environment
    mp_context = get_multiprocessing_context()
    
    # Default to CPU count if max_workers not specified
    if max_workers is None:
        max_workers = os.cpu_count()
    
    results = []
    print(f"Processing {len(mzml_files)} files using {max_workers} workers")
    
    # Use ProcessPoolExecutor with the appropriate context
    with ProcessPoolExecutor(max_workers=max_workers, 
                           mp_context=mp_context) as executor:
        # Use chunking for better performance with many files
        chunk_size = max(1, len(mzml_files) // (max_workers * 2))
        results = list(executor.map(process_single_file, mzml_files, 
                                  chunksize=chunk_size))
    
    return results
#####

#Main Processing Functions
def analyze_and_export_all_glycans(excel_input_file, excel_output_file, input_file, modification_type=6, 
                             mass_modification=0, rt_window=5.0, max_rt_window=None, ms1_ppm_tolerance=10, ms2_ppm_tolerance=20,  
                             fragment_types="all", use_strict_rt_window=True, use_provided_rt=True, 
                             use_excel_rt_window=True, use_excel_precursor=False, use_excel_pepmass=False, 
                             use_excel_peptide_mod=True, glycan_type="N", display_time_extension=5.0, back_window_ratio=0.1, 
                             output_dir=None, generate_eic_plots=True, generate_ms2_plots=False, max_fragments_displayed=30,
                             use_cam=True, custom_mods=False, fixed_mods=None, variable_mods=None, 
                             fdr_grade_cutoff=None, generate_glycan_by_ions=True, generate_peptide_by_ions=False, enable_custom_peptide_fragments=True,
                             generate_cz_peptide_fragment=False, generate_cz_glycan_fragment=False, max_rt_difference=1.0, 
                             prefer_fisher_py=True, intensity_threshold=1000, save_excel=True, use_intensity_instead_of_area=False, 
                             worker=None, use_comment_column=False, enable_fragment_removal=False, **kwargs):
    """
    Main function to analyze glycan/glycopeptide data and export results.
    
    This function processes Excel input files containing glycan/peptide information,
    generates theoretical fragments, matches them against experimental data from
    RAW/mzML files, and exports comprehensive results.
    """
    
    # Initialize return values for consistent error handling
    output_path = None
    formatted_cached_mzml_data = {}
    all_matched_fragments = pd.DataFrame()
    
    # Setup logging functions
    def log_info(message):
        if worker:
            worker.log_important_update(message, "INFO")
        print(f"INFO: {message}")

    def log_debug(message):
        if worker:
            worker.log_important_update(message, "DEBUG")
        print(f"DEBUG: {message}")

    def log_warning(message):
        if worker:
            worker.log_important_update(message, "WARNING")
        print(f"WARNING: {message}")

    def log_error(message):
        if worker:
            worker.log_important_update(message, "ERROR")
        print(f"ERROR: {message}")
    
    def log_section(message):
        """Log a section header with formatting"""
        separator = "=" * 60
        if worker:
            worker.log_important_update(separator, "INFO")
            worker.log_important_update(message, "INFO")
            worker.log_important_update(separator, "INFO")
        print(f"\n{separator}")
        print(f"{message}")
        print(f"{separator}\n")
    
    try:
        # =============================================================================
        # PARAMETER VALIDATION AND SETUP
        # =============================================================================
        
        # Validate fragment generation options
        if not any([generate_glycan_by_ions, generate_cz_glycan_fragment, 
                   generate_peptide_by_ions, generate_cz_peptide_fragment]):
            log_error("Error: At least one fragment type generation option must be enabled")
            log_error("Please enable: generate_glycan_by_ions, generate_cz_glycan_fragment, generate_peptide_by_ions, or generate_cz_peptide_fragment")
            return None, {}, pd.DataFrame()
        
        # Set default values for modification parameters
        fixed_mods = fixed_mods or []
        variable_mods = variable_mods or []
        
        # Process fragment_types parameter
        log_debug(f"Fragment types parameter: {fragment_types}")
        if isinstance(fragment_types, list):
            fragment_types = ",".join(fragment_types)
        
        if fragment_types.lower() != "all":
            fragment_type_list = [ft.strip().lower() for ft in fragment_types.lower().split(',')]
            fragment_types = ",".join(fragment_type_list)
            log_info(f"Using fragment types filter: {fragment_types}")
        
        # =============================================================================
        # FILE TYPE DETECTION AND VALIDATION
        # =============================================================================
        
        processing_file = None
        use_fisher_py = False
        
        if input_file:
            is_raw_file = input_file.lower().endswith('.raw')
            is_mzml_file = input_file.lower().endswith('.mzml')
            
            if is_raw_file:
                log_info(f"Detected RAW file: {input_file}")
                if prefer_fisher_py:
                    try:
                        import fisher_py
                        test_reader = fisher_py.RawFile(input_file)
                        log_info("fisher_py successfully initialized")
                        if hasattr(test_reader, 'Close'):
                            test_reader.Close()
                        elif hasattr(test_reader, 'close'):
                            test_reader.close()
                        
                        processing_file = input_file
                        use_fisher_py = True
                        log_info("Using fisher_py for direct RAW file processing")
                        
                    except ImportError:
                        log_error("fisher_py not installed. Please install with: pip install fisher_py")
                        return None, {}, pd.DataFrame()
                    except Exception as e:
                        log_error(f"fisher_py error: {e}")
                        return None, {}, pd.DataFrame()
                else:
                    log_error("RAW file processing disabled. Convert to mzML format first.")
                    return None, {}, pd.DataFrame()
                    
            elif is_mzml_file:
                log_info(f"Detected mzML file: {input_file}")
                processing_file = input_file
                use_fisher_py = False
            else:
                log_error(f"Unsupported file format: {input_file}")
                log_error("Please provide a .raw or .mzML file")
                return None, {}, pd.DataFrame()
        else:
            log_info("No input file provided - will only generate theoretical fragments")
        
        # =============================================================================
        # OUTPUT DIRECTORY SETUP
        # =============================================================================
        
        # Ensure output directory exists
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        else:
            output_dir = os.getcwd()
            log_warning("No output directory specified, using current directory")
        
        # Create file-specific subfolder for figures
        figures_dir = output_dir
        if processing_file:
            file_basename = os.path.splitext(os.path.basename(processing_file))[0]
            figures_dir = os.path.join(output_dir, f"figures_{file_basename}")
            os.makedirs(figures_dir, exist_ok=True)
            log_info(f"Created output directory for figures: {figures_dir}")
        
        # Set path for Excel output
        output_path = os.path.join(output_dir, excel_output_file)
        log_debug(f"Output will be saved to: {output_path}")
        
        # =============================================================================
        # EXCEL FILE LOADING AND VALIDATION
        # =============================================================================
        
        if not os.path.exists(excel_input_file):
            log_error(f"Input Excel file '{excel_input_file}' not found.")
            return None, {}, pd.DataFrame()
        
        # Load Excel file with ProcessStage support
        try:
            if worker:
                df_glycans = pd.read_excel(excel_input_file)
                worker.log_important_update("Loading Excel input file", "INFO")
            else:
                df_glycans = pd.read_excel(excel_input_file)
            
            log_info(f"Loaded Excel file with {len(df_glycans)} rows and {len(df_glycans.columns)} columns")
            
            if df_glycans.empty:
                log_error(f"Excel file '{excel_input_file}' is empty.")
                return None, {}, pd.DataFrame()
            
            # NEW: Check for Comment column if use_comment_column is True
            comment_column = None
            if use_comment_column:
                comment_column = next((col for col in df_glycans.columns if col.upper() == 'COMMENT'), None)
                if comment_column:
                    log_info(f"Found Comment column: '{comment_column}' - will parse glycopeptide strings")
                else:
                    log_error("use_comment_column=True but no 'Comment' column found in Excel file")
                    return None, {}, pd.DataFrame()
                
        except Exception as e:
            log_error(f"Failed to load Excel file: {e}")
            return None, {}, pd.DataFrame()
        # After Excel loading and before COLUMN VALIDATION section:

        # NEW: Process Comment column if enabled
        parsed_comment_data = {}  # Store parsed data by row index
        row_specific_glycan_types = {}  # Store glycan type per row
        row_specific_modifications = {}  # Store modifications per row

        if use_comment_column and comment_column:
            log_info("Processing Comment column to extract glycopeptide information...")
            
            for idx, row in df_glycans.iterrows():
                comment_value = row[comment_column]
                if pd.notna(comment_value) and str(comment_value).strip():
                    try:
                        parsed_result = parse_glycopeptide(str(comment_value).strip())
                        
                        if parsed_result['peptide'] and parsed_result['glycan']:
                            parsed_comment_data[idx] = parsed_result
                            
                            # Override row data with parsed values
                            df_glycans.loc[idx, 'Peptide'] = parsed_result['peptide']
                            df_glycans.loc[idx, 'Glycan'] = parsed_result['glycan']
                            
                            # Store row-specific glycan type (overrides global setting)
                            if parsed_result['glycan_type']:
                                row_specific_glycan_types[idx] = parsed_result['glycan_type']
                                log_info(f"Row {idx+1}: Detected {parsed_result['glycan_type']}-glycan")
                            
                            # Store row-specific modifications (overrides global settings)
                            if parsed_result['pep_modification']:
                                row_specific_modifications[idx] = parsed_result['pep_modification']
                                log_info(f"Row {idx+1}: Extracted modifications: {parsed_result['pep_modification']}")
                                
                            log_info(f"Row {idx+1}: Parsed - Peptide: {parsed_result['peptide']}, Glycan: {parsed_result['glycan']}")
                            
                        else:
                            log_warning(f"Row {idx+1}: Failed to parse Comment '{comment_value}' - missing peptide or glycan")
                            
                    except Exception as e:
                        log_error(f"Row {idx+1}: Error parsing Comment '{comment_value}': {e}")
            
            log_info(f"Successfully parsed {len(parsed_comment_data)} entries from Comment column")
            
            if parsed_comment_data:
                log_info("Comment column mode: Overriding global modification settings with row-specific data")
         # In analyze_and_export_all_glycans function, after other column detection:

        # Find charge column
        charge_column = None
        charge_column = next((col for col in df_glycans.columns if col.upper() == 'CHARGE'), None)
        if not charge_column:
            charge_column = next((col for col in df_glycans.columns if 'charge' in col.lower()), None)

        if charge_column:
            df_glycans[charge_column] = pd.to_numeric(df_glycans[charge_column], errors='coerce')
            log_info(f"Found charge column: '{charge_column}' - will use row-specific charge states")
        else:
            log_info("No charge column found - using default charge states 1-5")

        # =============================================================================
        # COLUMN VALIDATION
        # =============================================================================
        
        # Build list of required columns based on settings
        required_columns = []
        if use_excel_precursor:
            required_columns.append(('PRECURSOR_MZ', 'Precursor_mz'))
        if use_excel_rt_window:
            required_columns.append(('RT_WINDOW', 'RT_window'))
        if use_excel_pepmass:
            required_columns.append(('PEPMASS', 'PEPMass'))
        
        # Always required columns
        required_columns.append(('GLYCAN', 'Glycan'))
        if modification_type == 6:  # For glycopeptides
            required_columns.append(('PEPTIDE', 'Peptide'))
        
        # Check for required columns
        missing_columns = []
        empty_rows = {}
        
        for upper_name, display_name in required_columns:
            found_column = next((col for col in df_glycans.columns if col.upper() == upper_name), None)
            
            if not found_column:
                missing_columns.append(display_name)
            else:
                # Check for empty values
                empty_indices = df_glycans.index[df_glycans[found_column].isna()].tolist()
                if empty_indices:
                    empty_rows[display_name] = empty_indices
        
        # Handle validation errors
        if missing_columns:
            log_error(f"Missing required columns: {', '.join(missing_columns)}")
            return None, {}, pd.DataFrame()
        
        if empty_rows:
            log_error("Found empty values in required columns:")
            for col, indices in empty_rows.items():
                rows_str = ', '.join(str(idx + 1) for idx in indices[:5])
                if len(indices) > 5:
                    rows_str += f" and {len(indices) - 5} more"
                log_error(f"   • Column '{col}' has empty values in rows: {rows_str}")
            return None, {}, pd.DataFrame()
        
        # Add row_id for tracking
        df_glycans['row_id'] = df_glycans.index
        log_info(f"Excel columns found: {list(df_glycans.columns)}")
        
        # =============================================================================
        # COLUMN IDENTIFICATION
        # =============================================================================
        
        # Find peptide modification column
        pep_mod_column = next((col for col in df_glycans.columns if col.upper() == 'PEP_MODIFICATION'), None)
        if not pep_mod_column:
            pep_mod_column = next((col for col in df_glycans.columns if 
                                'modification' in col.lower() and 
                                ('pep' in col.lower() or 'peptide' in col.lower())), None)
        
        # Find RT column
        rt_column = next((col for col in df_glycans.columns if col.upper() == 'RT'), None)
        if not rt_column:
            potential_rt = [col for col in df_glycans.columns if 'rt' in col.lower() or 'time' in col.lower()]
            if potential_rt:
                rt_column = potential_rt[0]
                log_info(f"Using '{rt_column}' as the RT column")
            else:
                log_warning("No suitable RT column found. File processing will be skipped.")
        
        # Find RT window column
        rt_window_column = None
        if use_excel_rt_window:
            rt_window_column = next((col for col in df_glycans.columns if col.upper() == 'RT_WINDOW'), None)
            if rt_window_column:
                df_glycans[rt_window_column] = pd.to_numeric(df_glycans[rt_window_column], errors='coerce')
        
        # Find peptide mass column
        pepmass_column = None
        if use_excel_pepmass:
            pepmass_column = next((col for col in df_glycans.columns if col.upper() == 'PEPMASS'), None)
            if pepmass_column:
                df_glycans[pepmass_column] = pd.to_numeric(df_glycans[pepmass_column], errors='coerce')
        
        # Find precursor m/z column
        precursor_mz_column = None
        if use_excel_precursor:
            precursor_mz_column = next((col for col in df_glycans.columns if col.upper() == 'PRECURSOR_MZ'), None)
            if precursor_mz_column:
                df_glycans[precursor_mz_column] = pd.to_numeric(df_glycans[precursor_mz_column], errors='coerce')
        
        # =============================================================================
        # EXTRACT MODIFICATION INFORMATION
        # =============================================================================
        
        peptide_mods = {}  # Maps peptide_glycan -> mod_string
        peptide_masses = {}  # Maps peptide_glycan -> custom mass
        
        # Load peptide modifications from Excel
        if pep_mod_column:
            for idx, row in df_glycans.iterrows():
                peptide = row.get('Peptide', '')
                glycan = row.get('Glycan', '')
                if pd.notna(row.get(pep_mod_column)) and str(row[pep_mod_column]).strip():
                    key = f"{peptide}_{glycan}"
                    peptide_mods[key] = str(row[pep_mod_column])
            log_info(f"Loaded {len(peptide_mods)} custom peptide modifications from Excel")
        
        # Load custom peptide masses
        if use_excel_pepmass and pepmass_column:
            for idx, row in df_glycans.iterrows():
                peptide = row.get('Peptide', '')
                glycan = row.get('Glycan', '')
                if pd.notna(row.get(pepmass_column)):
                    key = f"{peptide}_{glycan}"
                    peptide_masses[key] = float(row[pepmass_column])
            log_info(f"Loaded {len(peptide_masses)} custom peptide masses from Excel")
        
        # =============================================================================
        # CREATE UNIQUE GLYCAN-PEPTIDE PAIRS
        # =============================================================================
        
        unique_pairs = []
        processed_pairs = set()
        
        for idx, row in df_glycans.iterrows():
            glycan_code = row['Glycan']
            peptide = row['Peptide'] if 'Peptide' in df_glycans.columns and modification_type == 6 else None
            
            pair_key = f"{glycan_code}_{peptide}"
            if pair_key not in processed_pairs:
                unique_pairs.append((idx, glycan_code, peptide))
                processed_pairs.add(pair_key)
        
        log_info(f"Found {len(df_glycans)} total entries, {len(unique_pairs)} unique glycan/glycopeptide combinations")
        
        # =============================================================================
        # SETUP MASS CALCULATOR
        # =============================================================================
        
        calculator = GlycanMassCalculator()
        ensure_peptide_masses_initialized(calculator)
        calculator.calculate_MONO_MASSES(modification_type)
        
        modification_types = {
            0: "Free_End", 1: "Reduced_End", 2: "Permethylated_Free_End", 
            3: "Permethylated_Reduced_End", 4: "2AB_Labeled", 
            5: "2AB_Labeled_Permethylated", 6: "PEP"
        }
        mod_sheet_name = modification_types.get(modification_type, "Unknown")
        
        # =============================================================================
        # INITIALIZE RESULT DATAFRAMES
        # =============================================================================
        
        all_unique_fragments = pd.DataFrame()
        all_masses = pd.DataFrame()
        all_matched_fragments = pd.DataFrame()
        all_raw_matches = pd.DataFrame()
        fragment_table_cache = {}
        cached_mzml_data = {}
        
        # =============================================================================
        # FIRST PASS: CALCULATE MASSES AND PROCESS INPUT FILE
        # =============================================================================
        
        if processing_file and os.path.exists(processing_file) and rt_column:
            log_section("FIRST PASS: CALCULATING TARGET M/Z VALUES")
            
            all_target_mzs = []
            all_mz_metadata = {}

            # Calculate masses for each entry
            for idx, row in df_glycans.iterrows():
                glycan_code = row['Glycan']
                peptide = row['Peptide'] if 'Peptide' in df_glycans.columns and modification_type == 6 else None
                
                # Initialize current_glycan_type here - BEFORE it's used
                current_glycan_type = glycan_type  # Default from parameters
                
                # Override with row-specific glycan type if using Comment column
                if use_comment_column and idx in row_specific_glycan_types:
                    current_glycan_type = row_specific_glycan_types[idx]
                
                # Get modification information
                current_use_cam = use_cam
                current_fixed_mods = fixed_mods.copy()
                current_variable_mods = variable_mods.copy()
                current_mod_string = None
                
                # Override with row-specific modifications if using Comment column
                if use_comment_column and idx in row_specific_modifications:
                    current_mod_string = row_specific_modifications[idx]
                    # When using comment column mods, disable GUI mods
                    current_use_cam = False
                    current_fixed_mods = []
                    current_variable_mods = []
                else:
                    # Use Excel modifications if available
                    pair_key = f"{peptide}_{glycan_code}"
                    if pair_key in peptide_mods:
                        current_mod_string = peptide_mods[pair_key]
                
                log_info(f"Calculating masses for entry {idx+1}/{len(df_glycans)}: Glycan={glycan_code}, Peptide={peptide or 'None'}")
                
                # Calculate glycan mass
                try:
                    hexnac, hex, fuc, neuac, neugc = calculator.parse_glycan_code(glycan_code)
                    glycan_base_mass = (hexnac * calculator.MONO_MASSES['HexNAc'] +
                                       hex * calculator.MONO_MASSES['Hex'] +
                                       fuc * calculator.MONO_MASSES['Fuc'] +
                                       neuac * calculator.MONO_MASSES['NeuAc'] +
                                       neugc * calculator.MONO_MASSES['NeuGc'])
                except Exception as e:
                    log_error(f"Failed to parse glycan code '{glycan_code}': {e}")
                    continue

                # Calculate peptide mass
                peptide_mass = 0.0
                if modification_type == 6 and peptide:
                    pair_key = f"{peptide}_{glycan_code}"
                    
                    if use_excel_pepmass and pair_key in peptide_masses:
                        peptide_mass = peptide_masses[pair_key]
                        log_info(f"Using Excel-provided peptide mass: {peptide_mass:.4f} Da")
                    else:
                        # FIXED: Use current_mod_string from Comment column parsing
                        # Get modification string if available
                        mod_string_to_use = current_mod_string if current_mod_string else peptide_mods.get(pair_key)
                        
                        # Calculate peptide mass with the correct modifications
                        cache_key = create_comprehensive_peptide_cache_key(
                            peptide, 
                            use_cam=current_use_cam,           # Use current (may be overridden)
                            fixed_mods=current_fixed_mods,     # Use current (may be overridden) 
                            variable_mods=current_variable_mods, # Use current (may be overridden)
                            mod_string=mod_string_to_use       # Use current mod string
                        )
                        
                        if cache_key not in calculator.PEPTIDE_MASSES:
                            calculator.PEPTIDE_MASSES[cache_key] = calculator.calculate_peptide_mass(
                                peptide, 
                                use_cam=current_use_cam,           # FIXED: Use current instead of global
                                fixed_mods=current_fixed_mods,     # FIXED: Use current instead of global
                                variable_mods=current_variable_mods, # FIXED: Use current instead of global
                                mod_string=mod_string_to_use,      # FIXED: Use parsed mod string
                                debug=True
                            )
                            log_info(f"Calculated peptide mass: {calculator.PEPTIDE_MASSES[cache_key]:.4f} Da")
                        
                        peptide_mass = calculator.PEPTIDE_MASSES[cache_key]
                
                # Calculate total mass
                if modification_type == 6 and peptide:
                    total_mass = peptide_mass + glycan_base_mass
                else:
                    total_mass = glycan_base_mass + calculator.REDUCING_END_MASSES[modification_type]
                
                modified_mass = total_mass + mass_modification
                
                # Determine charge states to use
                if charge_column and pd.notna(row[charge_column]):
                    # Use specific charge from Excel
                    specified_charge = int(row[charge_column])
                    if 1 <= specified_charge <= 10:  # Validate charge range
                        charge_states = [specified_charge]
                        log_info(f"Row {idx+1}: Using Excel-specified charge state: {specified_charge}")
                    else:
                        # Invalid charge, fall back to default
                        charge_states = [1, 2, 3, 4, 5]
                        log_warning(f"Row {idx+1}: Invalid charge {specified_charge}, using default range")
                else:
                    # Use default charge range
                    charge_states = [1, 2, 3, 4, 5]

                # Store mass data
                mass_data = {
                    'Glycan': str(glycan_code),
                    'Peptide': peptide or '-',
                    'Glycan_Type': current_glycan_type,
                    'Modifications': get_modification_display_string(
                        current_use_cam, current_fixed_mods, current_variable_mods, 
                        current_mod_string, peptide
                    ),
                    'Glycan_Mass': round(glycan_base_mass, 4),
                    'Peptide_Mass': round(peptide_mass, 4) if peptide else 0.0,
                    'Total_Mass': round(total_mass, 4),
                    'Modified_Mass': round(modified_mass, 4)
                }
                
                # Get RT and window values
                rt_value = float(row[rt_column]) if rt_column and pd.notna(row[rt_column]) else None
                custom_rt_window = None
                if rt_window_column and pd.notna(row[rt_window_column]):
                    custom_rt_window = float(row[rt_window_column])
                
                # Handle precursor m/z with dynamic charge states
                use_excel_mz_value = (use_excel_precursor and precursor_mz_column and 
                                    pd.notna(row[precursor_mz_column]))

                if use_excel_mz_value:
                    excel_mz_value = float(row[precursor_mz_column])
                    
                    if charge_column and pd.notna(row[charge_column]):
                        # Use specified charge with Excel m/z
                        specified_charge = int(row[charge_column])
                        if 1 <= specified_charge <= 10:
                            unique_mz_key = f"{excel_mz_value}_{row['row_id']}"
                            all_target_mzs.append((excel_mz_value, unique_mz_key))
                            all_mz_metadata[unique_mz_key] = {
                                'Glycan': str(glycan_code), 'Peptide': peptide or '',
                                'RT': rt_value, 'RT_window': custom_rt_window,
                                'GlycanIndex': idx, 'row_id': row['row_id'],
                                'mz': excel_mz_value, 'is_excel_provided': True,
                                'charge': specified_charge
                            }
                            mass_data['Excel_Precursor_Used'] = "Yes"
                            mass_data['Excel_Precursor_mz'] = round(excel_mz_value, 4)
                            mass_data['Specified_Charge'] = specified_charge
                            # FIXED: Add single m/z column instead of multiple z-specific columns
                            mass_data['m/z'] = round(excel_mz_value, 4)
                        else:
                            log_warning(f"Invalid charge {specified_charge} for Excel m/z, skipping")
                    else:
                        # Excel m/z without specified charge - determine best charge
                        best_charge = None
                        min_error = float('inf')
                        
                        for charge in [1, 2, 3, 4, 5]:
                            calculated_mz = calculator.calculate_mz(modified_mass, charge)
                            error = abs(calculated_mz - excel_mz_value)
                            if error < min_error:
                                min_error = error
                                best_charge = charge
                        
                        if best_charge and 150 <= excel_mz_value <= 1800:
                            unique_mz_key = f"{excel_mz_value}_{row['row_id']}"
                            all_target_mzs.append((excel_mz_value, unique_mz_key))
                            all_mz_metadata[unique_mz_key] = {
                                'Glycan': str(glycan_code), 'Peptide': peptide or '',
                                'RT': rt_value, 'RT_window': custom_rt_window,
                                'GlycanIndex': idx, 'row_id': row['row_id'],
                                'mz': excel_mz_value, 'is_excel_provided': True,
                                'charge': best_charge
                            }
                        mass_data['Excel_Precursor_Used'] = "Yes"
                        mass_data['Excel_Precursor_mz'] = round(excel_mz_value, 4)
                        mass_data['Determined_Charge'] = best_charge
                        # FIXED: Add single m/z column
                        mass_data['m/z'] = round(excel_mz_value, 4)
                else:
                    mass_data['Excel_Precursor_Used'] = "No"
                    mass_data['Excel_Precursor_mz'] = None
                    
                    # FIXED: Calculate m/z using the specified charge or first valid charge
                    if charge_column and pd.notna(row[charge_column]):
                        # Use the specified charge for m/z calculation
                        specified_charge = int(row[charge_column])
                        if 1 <= specified_charge <= 10:
                            mz = calculator.calculate_mz(modified_mass, specified_charge)
                            mass_data['m/z'] = round(mz, 4)
                            mass_data['Specified_Charge'] = specified_charge
                            
                            # Add to target list if within range
                            if 150 <= mz <= 1800:
                                unique_mz_key = f"{mz}_{row['row_id']}"
                                all_target_mzs.append((mz, unique_mz_key))
                                all_mz_metadata[unique_mz_key] = {
                                    'Glycan': str(glycan_code), 'Peptide': peptide or '',
                                    'RT': rt_value, 'RT_window': custom_rt_window,
                                    'GlycanIndex': idx, 'row_id': row['row_id'],
                                    'mz': mz, 'is_excel_provided': False,
                                    'charge': specified_charge
                                }
                        else:
                            # Invalid specified charge, use default first charge
                            default_charge = charge_states[0] if charge_states else 1
                            mz = calculator.calculate_mz(modified_mass, default_charge)
                            mass_data['m/z'] = round(mz, 4)
                            mass_data['Charge_Range'] = f"{min(charge_states)}-{max(charge_states)}" if charge_states else "1"
                            log_warning(f"Row {idx+1}: Invalid charge {specified_charge}, using charge {default_charge} for m/z calculation")
                    else:
                        # No specified charge, use first charge from range for display
                        display_charge = charge_states[0] if charge_states else 1
                        mz = calculator.calculate_mz(modified_mass, display_charge)
                        mass_data['m/z'] = round(mz, 4)
                        mass_data['Charge_Range'] = f"{min(charge_states)}-{max(charge_states)}" if charge_states else "1"
                        
                        # Still add all charge states to target list for analysis
                        for charge in charge_states:
                            mz_for_charge = calculator.calculate_mz(modified_mass, charge)
                            if 150 <= mz_for_charge <= 1800:
                                unique_mz_key = f"{mz_for_charge}_{row['row_id']}"
                                all_target_mzs.append((mz_for_charge, unique_mz_key))
                                all_mz_metadata[unique_mz_key] = {
                                    'Glycan': str(glycan_code), 'Peptide': peptide or '',
                                    'RT': rt_value, 'RT_window': custom_rt_window,
                                    'GlycanIndex': idx, 'row_id': row['row_id'],
                                    'mz': mz_for_charge, 'is_excel_provided': False,
                                    'charge': charge
                                }

                # Add glycopeptide column
                mass_data['Glycopeptide'] = f"{peptide}-{glycan_code}" if peptide and modification_type == 6 else '-'
                
                # Add to masses DataFrame
                all_masses = pd.concat([all_masses, pd.DataFrame([mass_data])], ignore_index=True)
            
            log_info(f"Calculated masses for {len(df_glycans)} entries")
            log_info(f"Total target m/z values for processing: {len(all_target_mzs)}")
            
            # Process input file
            if all_target_mzs:
                try:
                    if worker:
                        with ProcessStage(worker, f"Processing {'RAW' if use_fisher_py else 'mzML'} file"):
                            cached_mzml_data = _process_input_file(
                                processing_file, all_target_mzs, all_mz_metadata,
                                use_fisher_py, ms1_ppm_tolerance, rt_window, back_window_ratio
                            )
                    else:
                        cached_mzml_data = _process_input_file(
                            processing_file, all_target_mzs, all_mz_metadata,
                            use_fisher_py, ms1_ppm_tolerance, rt_window, back_window_ratio
                        )
                    
                    log_info(f"Processed file with {len(cached_mzml_data)} matching precursors")
                    
                except Exception as e:
                    log_error(f"Failed to process input file: {e}")
                    cached_mzml_data = {}
        
        # =============================================================================
        # SECOND PASS: PROCESS EACH UNIQUE GLYCAN/GLYCOPEPTIDE
        # =============================================================================
        
        log_section("SECOND PASS: PROCESSING EACH UNIQUE GLYCAN/GLYCOPEPTIDE")
        
        for idx, glycan_code, peptide in unique_pairs:
            try:
                log_info(f"Processing pair {idx+1}/{len(unique_pairs)}: Glycan={glycan_code}, Peptide={peptide or '-'}")
                
                # NEW: Override parameters if Comment column was used
                current_glycan_type = glycan_type  # Default global setting
                current_fixed_mods = fixed_mods.copy() if fixed_mods else []
                current_variable_mods = variable_mods.copy() if variable_mods else []
                current_use_cam = use_cam
                current_mod_string = None
                
                if use_comment_column and idx in parsed_comment_data:
                    # Override glycan type for this specific row
                    if idx in row_specific_glycan_types:
                        current_glycan_type = row_specific_glycan_types[idx]
                        log_info(f"Row {idx+1}: Using row-specific glycan type: {current_glycan_type}")
                    
                    # Override modifications for this specific row
                    if idx in row_specific_modifications:
                        current_mod_string = row_specific_modifications[idx]
                        # Clear global modification settings when using Comment column data
                        current_fixed_mods = []
                        current_variable_mods = []
                        current_use_cam = False  # Will be handled by mod_string if present
                        log_info(f"Row {idx+1}: Using row-specific modifications: {current_mod_string}")
                        log_info(f"Row {idx+1}: Overriding global modification settings")
                
                # Validate peptide sequence
                if peptide and modification_type == 6:
                    valid_amino_acids = set("ACDEFGHIKLMNPQRSTVWY")
                    invalid_chars = [aa for aa in peptide.upper() if aa not in valid_amino_acids]
                    if invalid_chars:
                        log_error(f"Invalid characters {invalid_chars} in peptide '{peptide}'. Skipping.")
                        continue
                
                # Generate fragments with row-specific parameters
                fragment_table = _generate_fragments_for_pair(
                    glycan_code, peptide, modification_type, calculator,
                    fragment_table_cache, worker, current_glycan_type,
                    current_use_cam, current_fixed_mods, current_variable_mods,  # Use current instead of global
                    {f"{peptide}_{glycan_code}": current_mod_string} if current_mod_string else peptide_mods,
                    generate_glycan_by_ions, generate_cz_glycan_fragment,
                    generate_peptide_by_ions, generate_cz_peptide_fragment,
                    enable_custom_peptide_fragments
                )
                
                if fragment_table.empty:
                    log_warning(f"No fragments generated for {glycan_code}, skipping")
                    continue
                
                # Add to all fragments
                all_unique_fragments = pd.concat([all_unique_fragments, fragment_table], ignore_index=True, copy=False)
                
                # Match with experimental data if available
                if cached_mzml_data and rt_column:
                    matched_fragments, raw_matches = _match_experimental_data(
                        glycan_code, peptide, df_glycans, cached_mzml_data,
                        fragment_table, worker, rt_window_column, max_rt_window,
                        use_excel_rt_window, ms2_ppm_tolerance, fdr_grade_cutoff,
                        modification_type, prefer_fisher_py, back_window_ratio,
                        use_strict_rt_window, use_provided_rt, generate_eic_plots,
                        generate_ms2_plots, figures_dir, display_time_extension,
                        fragment_types, max_fragments_displayed, use_intensity_instead_of_area
                    )
                    
                    if not matched_fragments.empty:
                        all_matched_fragments = pd.concat([all_matched_fragments, matched_fragments], ignore_index=True)
                    if not raw_matches.empty:
                        all_raw_matches = pd.concat([all_raw_matches, raw_matches], ignore_index=True)
                
            except Exception as e:
                log_error(f"Error processing glycan {glycan_code}: {e}")
                continue

        # =============================================================================
        # FRAGMENT REMOVAL STEP (AFTER ALL ANALYSIS IS COMPLETE)
        # =============================================================================

        # NEW: Interactive fragment removal step (if enabled and we have results)
        if enable_fragment_removal and not all_matched_fragments.empty:
            log_info("Fragment removal enabled - will be available in Output tab after analysis")
        else:
            log_info("Fragment removal disabled or no fragments available")

        # =============================================================================
        # PREPARE RESULTS FOR EXPORT
        # =============================================================================

        # Initialize formatted data
        formatted_cached_mzml_data = {'prm_data': cached_mzml_data}

        if worker:
            with ProcessStage(worker, "Preparing results for export"):
                _prepare_results_for_export(
                    all_unique_fragments, all_matched_fragments, all_raw_matches
                )
        else:
            _prepare_results_for_export(
                all_unique_fragments, all_matched_fragments, all_raw_matches
            )
        
        # =============================================================================
        # WRITE RESULTS TO EXCEL
        # =============================================================================
        
        if save_excel:
            try:
                if worker:
                    with ProcessStage(worker, "Writing results to Excel"):
                        _write_excel_results(output_path, all_unique_fragments, all_masses, 
                                           all_matched_fragments, mod_sheet_name)
                else:
                    _write_excel_results(output_path, all_unique_fragments, all_masses, 
                                       all_matched_fragments, mod_sheet_name)
                
                log_info(f"Results saved to {output_path}")
                
            except Exception as e:
                log_error(f"Failed to write Excel file: {e}")
                output_path = None
        else:
            log_info("Excel output saving disabled")
            output_path = None
        
        # =============================================================================
        # LOG SUMMARY
        # =============================================================================
        
        log_section("ANALYSIS COMPLETE")
        log_info(f"Unique fragments: {len(all_unique_fragments)} fragments")
        log_info(f"Masses: {len(all_masses)} glycan/glycopeptide entries")
        
        if not all_matched_fragments.empty:
            log_info(f"Matched fragments: {len(all_matched_fragments)} fragments")
        else:
            log_info("No matched fragments generated")
        
        return output_path, formatted_cached_mzml_data, all_matched_fragments
        
    except Exception as e:
        log_error(f"Critical error in analyze_and_export_all_glycans: {e}")
        traceback.print_exc()
        return None, {}, pd.DataFrame()


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_modification_display_string(use_cam, fixed_mods, variable_mods, mod_string, peptide):
    """Generate a human-readable modification display string"""
    modifications = []
    
    # Handle Excel-provided modification string first
    if mod_string and mod_string.strip():
        modifications.append(f"Excel: {mod_string}")
    else:
        # Handle GUI modifications
        if use_cam:
            if peptide and 'C' in peptide:
                cys_count = peptide.count('C')
                if cys_count == 1:
                    modifications.append("CAM")
                else:
                    modifications.append(f"CAM:{cys_count}")
            else:
                modifications.append("CAM")
        
        # Add other fixed modifications
        for mod in fixed_mods:
            if mod != "CAM:C":  # Skip CAM since we handled it above
                if ':' in mod:
                    mod_name, residue = mod.split(':', 1)
                    if peptide and residue in peptide:
                        residue_count = peptide.count(residue)
                        if residue_count == 1:
                            modifications.append(mod_name)
                        else:
                            modifications.append(f"{mod_name}:{residue_count}")
                    else:
                        modifications.append(mod_name)
                else:
                    modifications.append(mod)
        
        # Add variable modifications (marked with *)
        for mod in variable_mods:
            if ':' in mod:
                mod_name, residue = mod.split(':', 1)
                if peptide and residue in peptide:
                    residue_count = peptide.count(residue)
                    if residue_count == 1:
                        modifications.append(f"{mod_name}*")
                    else:
                        modifications.append(f"{mod_name}*:{residue_count}")
                else:
                    modifications.append(f"{mod_name}*")
            else:
                modifications.append(f"{mod}*")
    
    return ", ".join(modifications) if modifications else "None"

def _process_input_file(processing_file, all_target_mzs, all_mz_metadata, 
                       use_fisher_py, ms1_ppm_tolerance, rt_window, back_window_ratio):  
    """Process RAW or mzML input file to extract fragment data."""
    search_mzs = [item[0] for item in all_target_mzs]
    
    # Call the appropriate extraction function
    if use_fisher_py:
        prm_data = extract_prm_fragments_from_raw_fisher(
            processing_file, target_mzs=search_mzs, target_keys=all_target_mzs,
            mz_metadata=all_mz_metadata, ms1_ppm_tolerance=ms1_ppm_tolerance, 
            rt_window=rt_window, back_window_ratio=back_window_ratio
        )
    else:
        prm_data = extract_prm_fragments_with_unique_keys(
            processing_file, target_mzs=search_mzs, target_keys=all_target_mzs,
            mz_metadata=all_mz_metadata, ms1_ppm_tolerance=ms1_ppm_tolerance,  
            rt_window=rt_window, back_window_ratio=back_window_ratio
        )
    
    # Check if any precursors were found
    if not prm_data:  # Empty dict = no precursors found
        print("ERROR: No matching precursors found in the input file.")
        print("ERROR: Unable to proceed with fragment analysis.")
        
        # Return a special structure to indicate failure
        return {
            'status': 'error',
            'message': 'No matching precursors found',
            'data': {}
        }
    
    # Return the data if precursors were found
    return prm_data

def _generate_fragments_for_pair(glycan_code, peptide, modification_type, calculator,
                                fragment_table_cache, worker, glycan_type, use_cam,
                                fixed_mods, variable_mods, peptide_mods,
                                generate_glycan_by_ions, generate_cz_glycan_fragment,
                                generate_peptide_by_ions, generate_cz_peptide_fragment,
                                enable_custom_peptide_fragments):
    """Generate theoretical fragments for a glycan-peptide pair."""
    
    # Get modification string
    pair_key = f"{peptide}_{glycan_code}"
    mod_string = peptide_mods.get(pair_key) if peptide else None
    
    # Create cache key
    fragment_cache_key = create_comprehensive_fragment_cache_key(
        glycan_code, peptide, modification_type=modification_type,
        use_cam=use_cam, fixed_mods=fixed_mods, variable_mods=variable_mods,
        mod_string=mod_string, glycan_type=glycan_type
    )
    
    # Check cache first
    if fragment_cache_key in fragment_table_cache:
        return fragment_table_cache[fragment_cache_key]
    
    # Generate new fragments
    try:
        if worker:
            with ProcessStage(worker, f"Generating theoretical fragments for {glycan_code}"):
                # FIXED: Remove the unsupported parameters from predict_glycan_structure call
                results, glycan = predict_glycan_structure(
                    glycan_code, glycan_type, peptide=peptide
                )
        else:
            # FIXED: Remove the unsupported parameters from predict_glycan_structure call
            results, glycan = predict_glycan_structure(
                glycan_code, glycan_type, peptide=peptide
            )
        
        if not results:
            return pd.DataFrame()
        
        # Collect unique fragments with the modification parameters
        unique_fragments = collect_unique_fragments(
            results, modification_type=modification_type, peptide=peptide,
            use_cam=use_cam, fixed_mods=fixed_mods, variable_mods=variable_mods,
            mod_string=mod_string
        )
        
        # Generate fragment table
        fragment_table = pd.DataFrame()
        
        # Process glycan fragments
        if generate_glycan_by_ions or generate_cz_glycan_fragment:
            fragment_table = generate_extended_fragment_table(
                unique_fragments, glycan_code, modification_type=modification_type,
                peptide=peptide, use_cam=use_cam, fixed_mods=fixed_mods,
                variable_mods=variable_mods, mod_string=mod_string,
                generate_cz_glycan_fragment=generate_cz_glycan_fragment, 
                generate_glycan_by_ions=generate_glycan_by_ions,
                generate_peptide_by_ions=generate_peptide_by_ions,
                generate_cz_peptide_fragment=generate_cz_peptide_fragment,
                include_byy=True
            )
            
            # Filter if only C/Z fragments wanted
            if not generate_glycan_by_ions and generate_cz_glycan_fragment:
                cz_fragment_types = ['c', 'z', 'cz', 'zz', 'czz', 'bzz']
                cz_filter = fragment_table.apply(lambda row: 
                    row['FragmentType'] in cz_fragment_types or
                    any(pattern in str(row['Type']) for pattern in ['-C', 'Z-', 'ZZ-']), axis=1)
                fragment_table = fragment_table[cz_filter]
        
        # Process peptide fragments
        if (generate_peptide_by_ions or generate_cz_peptide_fragment) and peptide:
            peptide_fragments = generate_peptide_fragments(
                peptide, glycan_code, use_cam=use_cam, fixed_mods=fixed_mods,
                variable_mods=variable_mods, mod_string=mod_string,
                enable_custom_peptide_fragments=enable_custom_peptide_fragments,
                generate_cz_peptide_fragment=generate_cz_peptide_fragment
            )
            
            fragment_table = combine_glycan_and_peptide_fragments(
                fragment_table, peptide_fragments, glycan_code, peptide,
                generate_cz_peptide=generate_cz_peptide_fragment,
                generate_cz_glycan=generate_cz_glycan_fragment,
                generate_peptide_by_ions=generate_peptide_by_ions,
                generate_glycan_by_ions=generate_glycan_by_ions,
                enable_custom_peptide_fragments=enable_custom_peptide_fragments
            )
        
        # Add metadata columns
        if not fragment_table.empty:
            fragment_table['Glycan'] = str(glycan_code)
            fragment_table['Glycopeptide'] = f"{peptide}-{glycan_code}" if peptide and modification_type == 6 else '-'
            
            # Update labels based on modification type
            end_labels = {1: 'freeend', 4: '2AB', 5: '2AB', 6: 'PEP'}
            end_label = end_labels.get(modification_type, 'redend')
            
            fragment_table['Type'] = fragment_table['Type'].str.replace('redend', end_label)
            fragment_table['Fragment'] = fragment_table['Fragment'].str.replace('redend', end_label)
        
        # Cache the result
        fragment_table_cache[fragment_cache_key] = fragment_table
        return fragment_table
        
    except Exception as e:
        print(f"Error generating fragments for {glycan_code}: {e}")
        return pd.DataFrame()
    
def filter_fragments_by_generation_settings(fragment_df, generate_glycan_by_ions=True, 
                                          generate_peptide_by_ions=True, 
                                          generate_cz_glycan_fragment=True, 
                                          generate_cz_peptide_fragment=True):
    """
    Clean fragment filtering based on generation settings.
    Remove unwanted fragment types after all fragments are generated.
    """
    if fragment_df.empty:
        return fragment_df
    
    print(f"DEBUG: Filtering fragments - Input: {len(fragment_df)} fragments")
    print(f"  generate_glycan_by_ions: {generate_glycan_by_ions}")
    print(f"  generate_cz_glycan_fragment: {generate_cz_glycan_fragment}")
    print(f"  generate_peptide_by_ions: {generate_peptide_by_ions}")
    print(f"  generate_cz_peptide_fragment: {generate_cz_peptide_fragment}")
    
    # FIXED: Separate BYY from regular BY fragments
    glycan_by_types = ['b', 'y', 'by', 'yy']  # ← Removed 'byy' from here
    glycan_byy_types = ['byy']  # ← Handle BYY separately
    glycan_cz_types = ['c', 'z', 'cz', 'zz', 'czz']
    peptide_by_types = ['b', 'y', 'c', 'z']  # Peptide fragments (check Is_Peptide_Fragment column)
    
    # BZZ is a special case - it's C/Z conversion of glycan BY ions
    # Include BZZ only if BOTH glycan BY and glycan C/Z are enabled
    bzz_types = ['bzz']
    
    # Create filter mask
    keep_mask = pd.Series([True] * len(fragment_df), index=fragment_df.index)
    
    # Filter glycan BY fragments (excluding BYY)
    if not generate_glycan_by_ions:
        fragment_type_mask = fragment_df['FragmentType'].isin(glycan_by_types)
        
        if 'Is_Peptide_Fragment' in fragment_df.columns:
            peptide_mask = fragment_df['Is_Peptide_Fragment'] == False
        else:
            peptide_mask = pd.Series([True] * len(fragment_df), index=fragment_df.index)
        
        glycan_by_mask = fragment_type_mask & peptide_mask
        
        if not isinstance(glycan_by_mask, pd.Series):
            glycan_by_mask = pd.Series([glycan_by_mask] * len(fragment_df), index=fragment_df.index)
        
        keep_mask &= ~glycan_by_mask
        print(f"  Removed {glycan_by_mask.sum()} glycan BY fragments (excluding BYY)")
    
    # FIXED: Handle BYY fragments separately with proper logic
    # BYY fragments should be included when generate_glycan_by_ions=True
    # regardless of C/Z setting (they are BY-type fragments, not C/Z-type)
    if not generate_glycan_by_ions:
        byy_mask = fragment_df['FragmentType'].isin(glycan_byy_types)
        
        if not isinstance(byy_mask, pd.Series):
            byy_mask = pd.Series([byy_mask] * len(fragment_df), index=fragment_df.index)
        
        keep_mask &= ~byy_mask
        print(f"  Removed {byy_mask.sum()} BYY fragments (generate_glycan_by_ions=False)")
    else:
        print(f"  Keeping BYY fragments (generate_glycan_by_ions=True)")
    
    # Filter glycan C/Z fragments
    if not generate_cz_glycan_fragment:
        fragment_type_mask = fragment_df['FragmentType'].isin(glycan_cz_types)
        
        if 'Is_Peptide_Fragment' in fragment_df.columns:
            peptide_mask = fragment_df['Is_Peptide_Fragment'] == False
        else:
            peptide_mask = pd.Series([True] * len(fragment_df), index=fragment_df.index)
        
        glycan_cz_mask = fragment_type_mask & peptide_mask
        
        if not isinstance(glycan_cz_mask, pd.Series):
            glycan_cz_mask = pd.Series([glycan_cz_mask] * len(fragment_df), index=fragment_df.index)
        
        keep_mask &= ~glycan_cz_mask
        print(f"  Removed {glycan_cz_mask.sum()} glycan C/Z fragments")
        
        # Also remove BZZ if C/Z glycan fragments are disabled
        bzz_mask = fragment_df['FragmentType'].isin(bzz_types)
        
        if not isinstance(bzz_mask, pd.Series):
            bzz_mask = pd.Series([bzz_mask] * len(fragment_df), index=fragment_df.index)
        
        keep_mask &= ~bzz_mask
        print(f"  Removed {bzz_mask.sum()} BZZ fragments (C/Z disabled)")
    
    # Filter peptide fragments
    if not generate_peptide_by_ions:
        if 'Is_Peptide_Fragment' in fragment_df.columns:
            peptide_mask = fragment_df['Is_Peptide_Fragment'] == True
        else:
            peptide_mask = pd.Series([False] * len(fragment_df), index=fragment_df.index)
        
        if not isinstance(peptide_mask, pd.Series):
            peptide_mask = pd.Series([peptide_mask] * len(fragment_df), index=fragment_df.index)
        
        keep_mask &= ~peptide_mask
        print(f"  Removed {peptide_mask.sum()} peptide fragments")
    
    # Apply filter
    filtered_df = fragment_df[keep_mask].copy()
    
    print(f"DEBUG: Filtering complete - Output: {len(filtered_df)} fragments")
    return filtered_df

def _match_experimental_data(glycan_code, peptide, df_glycans, cached_mzml_data,
                           fragment_table, worker, rt_window_column, max_rt_window,
                           use_excel_rt_window, ms2_ppm_tolerance, fdr_grade_cutoff,
                           modification_type, prefer_fisher_py, back_window_ratio,
                           use_strict_rt_window, use_provided_rt, generate_eic_plots,
                           generate_ms2_plots, figures_dir, display_time_extension,
                           fragment_types, max_fragments_displayed, use_intensity_instead_of_area):
    """Match theoretical fragments with experimental data."""
    
    all_matched = pd.DataFrame()
    all_raw = pd.DataFrame()
    
    try:
        # Find matching rows in Excel
        matching_rows = df_glycans[df_glycans['Glycan'] == glycan_code]
        if peptide and 'Peptide' in df_glycans.columns:
            matching_rows = matching_rows[matching_rows['Peptide'] == peptide]
        
        for _, excel_row in matching_rows.iterrows():
            row_id = excel_row['row_id']
            
            # Get RT window
            effective_rt_window = max_rt_window
            if use_excel_rt_window and rt_window_column and pd.notna(excel_row[rt_window_column]):
                effective_rt_window = float(excel_row[rt_window_column])
            
            # Find cached data for this row
            matching_data = {}
            for cached_key, data in cached_mzml_data.items():
                if isinstance(cached_key, str) and '_' in cached_key:
                    key_parts = cached_key.split('_')
                    if len(key_parts) >= 2 and str(key_parts[1]) == str(row_id):
                        matching_data[cached_key] = data
            
            if not matching_data:
                continue
            
            # Analyze fragments
            results_df = analyze_fragments(matching_data, intensity_threshold=1000)
            
            if results_df.empty:
                continue
            
            # Add metadata
            results_df['Glycan'] = str(glycan_code)
            results_df['Peptide'] = peptide or ''
            results_df['precursor_rt'] = excel_row.get('RT', 0.0)
            
            # Match with theoretical database
            input_method = "fisher_py" if prefer_fisher_py else "mzml"
            matched_df, raw_matches_df = match_fragments_with_database(
                results_df, fragment_table, max_rt_window=effective_rt_window,
                 ms2_ppm_tolerance=ms2_ppm_tolerance, fdr_grade_cutoff=fdr_grade_cutoff,
                modification_type=modification_type, input_method=input_method
            )
            
            if not matched_df.empty:
                # Integrate fragment areas
                integrated_matches = extract_fragment_areas_from_matches(
                    cached_mzml_data, matched_df, back_window_ratio=back_window_ratio,
                    max_rt_window=effective_rt_window, use_strict_rt_window=use_strict_rt_window,
                    use_provided_rt=use_provided_rt
                )
                
                if not integrated_matches.empty:
                    all_matched = pd.concat([all_matched, integrated_matches], ignore_index=True)
                    
                    # Generate plots if requested
                    if generate_eic_plots:
                        plot_fragment_eics(
                            cached_mzml_data, integrated_matches, glycan_code, peptide,
                            rt_window=effective_rt_window, max_rt_window=effective_rt_window,
                            use_strict_rt_window=use_strict_rt_window, use_provided_rt=use_provided_rt,
                            display_time_extension=display_time_extension, fragment_types=fragment_types,
                            output_dir=figures_dir, max_fragments_displayed=max_fragments_displayed,
                            use_intensity_instead_of_area=use_intensity_instead_of_area
                        )
                    
                    if generate_ms2_plots:
                        plot_ms2_spectra(
                            cached_mzml_data, integrated_matches, glycan_code, peptide,
                            output_dir=figures_dir, max_fragments_displayed=max_fragments_displayed
                        )
            
            if not raw_matches_df.empty:
                all_raw = pd.concat([all_raw, raw_matches_df], ignore_index=True)
    
    except Exception as e:
        print(f"Error matching experimental data for {glycan_code}: {e}")
    
    return all_matched, all_raw

def _prepare_results_for_export(all_unique_fragments, all_matched_fragments, all_raw_matches):
    """Prepare result DataFrames for export by cleaning and adding necessary columns."""
    
    # Remove legacy columns
    legacy_columns = ['Glycan-5digit']
    for df in [all_unique_fragments, all_matched_fragments, all_raw_matches]:
        for col in legacy_columns:
            if col in df.columns:
                df.drop(columns=[col], inplace=True)
    
    # Remove unwanted columns from unique fragments sheet
    unwanted_unique_columns = ['Glycopeptides', 'Theoretical_mz', 'Is_Peptide_Fragment']
    if not all_unique_fragments.empty:
        for col in unwanted_unique_columns:
            if col in all_unique_fragments.columns:
                all_unique_fragments.drop(columns=[col], inplace=True)
    
    # Add Fragment column mapping if needed
    if not all_unique_fragments.empty:
        if 'Fragment' not in all_unique_fragments.columns and 'fragment_id' in all_unique_fragments.columns:
            all_unique_fragments['Fragment'] = all_unique_fragments['fragment_id']

def prepare_matched_fragments_for_export(matched_fragments_df):
    """Prepare matched fragments DataFrame for Excel export with proper column order and cleanup"""
    if matched_fragments_df.empty:
        return matched_fragments_df
    
    # Make a copy to avoid modifying original
    df_export = matched_fragments_df.copy()
    
    # Remove unwanted columns
    columns_to_remove = ['Max_Intensity', 'rt_difference', 'Duplicate_Count']
    for col in columns_to_remove:
        if col in df_export.columns:
            df_export = df_export.drop(columns=[col])
    
    # Rename FDR_Grade to Grade for Excel export only
    if 'FDR_Grade' in df_export.columns:
        df_export = df_export.rename(columns={'FDR_Grade': 'Grade'})
    
    # Define desired column order
    desired_order = [
        'Precursor_mz', 'precursor_rt', 'Glycan', 'Glycopeptides', 
        'Fragment', 'FragmentType', 'Ions', 'Type', 'Match_type',
        'Theoretical_mz', 'Experimental_mz', 'Fragment_mz', 'PPM_diff',
        'scan_time', 'Intensity', 'Area', 'Integration_Start', 'Integration_End', 
        'Peak_Width', 'Total_Data_Points', 'Data_Points_Used',
        'Fragments_Score', 'Grade', 'Fragments_Rating', 'Score_Details', 
        'Duplicate_Count', 'row_id'
    ]
    
    # Reorder columns (only include columns that actually exist)
    existing_columns = [col for col in desired_order if col in df_export.columns]
    remaining_columns = [col for col in df_export.columns if col not in existing_columns]
    final_column_order = existing_columns + remaining_columns
    
    return df_export[final_column_order]

def _write_excel_results(output_path, all_unique_fragments, all_masses, all_matched_fragments, mod_sheet_name):
    """Write results to Excel file with proper formatting."""
    
    def round_for_export(df):
        """Round numeric columns for export."""
        if df.empty:
            return df
        
        df_export = df.copy()
        mz_columns = [col for col in df.columns if 'mz' in col.lower() or 'mass' in col.lower()]
        rt_columns = [col for col in df.columns if 'rt' in col.lower() or 'time' in col.lower()]
        
        for col in mz_columns:
            if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
                df_export[col] = df_export[col].round(4)
        
        for col in rt_columns:
            if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
                df_export[col] = df_export[col].round(2)
        
        return df_export
    
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        round_for_export(all_unique_fragments).to_excel(writer, sheet_name='Unique_Fragments', index=False)
        round_for_export(all_masses).to_excel(writer, sheet_name=f"{mod_sheet_name}_Masses", index=False)
        
        if not all_matched_fragments.empty:
            # Prepare matched fragments for export with proper formatting
            prepared_matched_fragments = prepare_matched_fragments_for_export(all_matched_fragments)
            round_for_export(prepared_matched_fragments).to_excel(writer, sheet_name='Matched_Fragments', index=False)

def create_prm_quantification_summary(output_dir, all_results, fdr_grade_cutoff=None, 
                                    fragment_types="all", use_intensity_instead_of_area=False): 
    """
    Create a summary of PRM quantification results from multiple mzML files.
    
    Args:
        output_dir: Directory to save the summary report
        all_results: Dictionary mapping mzML filenames to DataFrames of matched fragments
        fdr_grade_cutoff: Minimum FDR grade to include in summary (A, B, C, D, or None for all)
        fragment_types: Which fragment types to include ("all", "b", "y", "by", "yy")
        use_intensity_instead_of_area: Whether to use intensity instead of area for metrics
        
    Returns:
        Path to the saved summary report
    """
    try:
        import pandas as pd
        import os
        import numpy as np
        from datetime import datetime
        
        # Determine metric name and column
        metric_name = "Intensity" if use_intensity_instead_of_area else "Area"
        metric_column = "Intensity" if use_intensity_instead_of_area else "Area"
        
        # Get current timestamp for filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Handle the input data properly - no Excel reading needed
        filtered_results = {}
        
        for file_path, data in all_results.items():
            if isinstance(data, pd.DataFrame):
                # Data is already a DataFrame (from memory)
                filtered_results[file_path] = data
                print(f"Using in-memory data for {file_path}: {len(data)} fragments")
            else:
                print(f"Skipping invalid data for {file_path}: {type(data)}")
        
        # Check if we have results to summarize
        if not filtered_results:
            print("No results to summarize.")
            return None
            
        # ===== SUMMARY 1: AGGREGATED PRECURSOR SUMMARY =====
        summary_rows = []
        
        # Get all unique Glycopeptides, Precursor_mz, precursor_rt combinations
        unique_precursors = set()
        file_mapping = {}  # Map basename to full filename for lookup
        
        for file_path, df in filtered_results.items():
            base_filename = os.path.splitext(os.path.basename(file_path))[0]
            file_mapping[base_filename] = file_path
            
            if 'Glycopeptides' in df.columns and 'Precursor_mz' in df.columns and 'precursor_rt' in df.columns:
                for _, row in df.iterrows():
                    # Handle cases where Glycopeptides might have row suffix
                    glycopeptide = row['Glycopeptides']
                    if isinstance(glycopeptide, str) and '_row' in glycopeptide:
                        glycopeptide = glycopeptide.split('_row')[0]
                    # Handle original_glycopeptide if present
                    if 'original_glycopeptide' in df.columns and pd.notna(row['original_glycopeptide']):
                        glycopeptide = row['original_glycopeptide']
                    key = (glycopeptide, row['Precursor_mz'], row['precursor_rt'])
                    unique_precursors.add(key)
        
        print(f"Found {len(unique_precursors)} unique glycopeptide-precursor combinations")
        
        # Get all unique file base filenames
        base_filenames = sorted(list(file_mapping.keys()))
        print(f"File basenames for column headers: {base_filenames}")
        
        # Determine which fragment types to include
        fragment_types_to_include = ['All']
        if fragment_types.lower() != "all":
            selected_type = fragment_types.lower()
            if selected_type in ['b', 'y', 'by', 'yy'] and selected_type != 'all':
                fragment_types_to_include.append(selected_type)
        
        print(f"Including fragment types in summary: {fragment_types_to_include}")
        
        # Process each unique precursor for Summary 1
        for glycopeptide, precursor_mz, precursor_rt in sorted(unique_precursors):
            # Create dictionaries for selected fragment types only
            fragment_types_dict = {frag_type: {} for frag_type in fragment_types_to_include}
            
            # Initialize fields for each fragment type
            for frag_type in fragment_types_dict.keys():
                fragment_types_dict[frag_type] = {
                    'Glycopeptides': glycopeptide,
                    'Precursor_mz': precursor_mz,
                    'Precursor_rt': precursor_rt,
                    'Fragment_type': frag_type
                }
                
                # Initialize metrics for each file with dynamic naming
                for base_filename in base_filenames:
                    fragment_types_dict[frag_type][f'No_of_Fragments_{base_filename}'] = 0.0
                    fragment_types_dict[frag_type][f'Total_{metric_name.lower()}_{base_filename}'] = 0.0
                    fragment_types_dict[frag_type][f'Fragments_Score_{base_filename}'] = 0.0
                    fragment_types_dict[frag_type][f'Fragments_Rating_{base_filename}'] = 0.0
            
            # Process each file's data
            for base_filename in base_filenames:
                # Get the full filename and corresponding data
                full_filename = file_mapping[base_filename]
                if full_filename not in filtered_results:
                    continue
                    
                # Get the data for this file
                df = filtered_results[full_filename]
                
                # Filter to this specific precursor
                precursor_df = df[(df['Glycopeptides'].str.contains(str(glycopeptide), na=False, regex=False)) & 
                                  (np.isclose(df['Precursor_mz'], precursor_mz, rtol=1e-4)) & 
                                  (np.isclose(df['precursor_rt'], precursor_rt, rtol=1e-2))]
                
                if precursor_df.empty:
                    continue
                    
                # Update metrics for ALL fragment types using the selected metric
                fragment_types_dict['All'][f'No_of_Fragments_{base_filename}'] = len(precursor_df)
                
                # Use the appropriate column based on the preference
                if metric_column in precursor_df.columns:
                    total_metric = float(precursor_df[metric_column].sum())
                else:
                    # Fallback to Area if Intensity not available, or vice vers
                    print(f"Warning: No {metric_column} column found for {base_filename}")
                
                fragment_types_dict['All'][f'Total_{metric_name.lower()}_{base_filename}'] = total_metric
                
                # Calculate FDR score for ALL fragments
                if 'Fragments_Score' in precursor_df.columns:
                    avg_score = precursor_df['Fragments_Score'].mean()
                    fragment_types_dict['All'][f'Fragments_Score_{base_filename}'] = round(float(avg_score), 2)
                    
                    # Calculate overall rating based on average score
                    if avg_score >= 75:
                        overall_rating = "High"
                    elif avg_score >= 50:
                        overall_rating = "Medium"
                    else:
                        overall_rating = "Low"
                    
                    fragment_types_dict['All'][f'Fragments_Rating_{base_filename}'] = overall_rating
                
                # Update metrics for selected specific fragment type (if applicable)
                if 'FragmentType' in precursor_df.columns and len(fragment_types_to_include) > 1:
                    selected_type = fragment_types_to_include[1]
                    ftype_df = precursor_df[precursor_df['FragmentType'] == selected_type]
                    if not ftype_df.empty:
                        fragment_types_dict[selected_type][f'No_of_Fragments_{base_filename}'] = len(ftype_df)
                        
                        # Use the appropriate metric for the specific fragment type
                        if metric_column in ftype_df.columns:
                            type_total_metric = float(ftype_df[metric_column].sum())
                        else:
                            fallback_column = "Area" if use_intensity_instead_of_area else "Intensity"
                            if fallback_column in ftype_df.columns:
                                type_total_metric = float(ftype_df[fallback_column].sum())
                            else:
                                type_total_metric = 0.0
                        
                        fragment_types_dict[selected_type][f'Total_{metric_name.lower()}_{base_filename}'] = type_total_metric
                        
                        if 'Fragments_Score' in ftype_df.columns:
                            type_avg_score = ftype_df['Fragments_Score'].mean()
                            fragment_types_dict[selected_type][f'Fragments_Score_{base_filename}'] = round(float(type_avg_score), 2)
                            
                            if type_avg_score >= 75:
                                type_rating = "High"
                            elif type_avg_score >= 50:
                                type_rating = "Medium"
                            else:
                                type_rating = "Low"
                            
                            fragment_types_dict[selected_type][f'Fragments_Rating_{base_filename}'] = type_rating
            
            # Add rows to summary
            for frag_type in fragment_types_dict.keys():
                summary_rows.append(fragment_types_dict[frag_type])
        
        # Create Summary 1 DataFrame
        summary_df = pd.DataFrame(summary_rows)
        
        # Ensure numeric columns are properly typed
        numeric_columns = {
            'Precursor_mz': 'float64',
            'Precursor_rt': 'float64'
        }
        
        # Add dynamic numeric columns based on base filenames and metric preference
        for base_filename in base_filenames:
            numeric_columns.update({
                f'No_of_Fragments_{base_filename}': 'int64',
                f'Total_{metric_name.lower()}_{base_filename}': 'float64',
                f'Fragments_Score_{base_filename}': 'float64'
            })
            
        # Convert columns to proper numeric types
        for col, dtype in numeric_columns.items():
            if col in summary_df.columns:
                summary_df[col] = pd.to_numeric(summary_df[col], errors='coerce').astype(dtype)
        
        # REORGANIZE COLUMNS BY METRICS INSTEAD OF BY FILE
        fixed_columns = ['Glycopeptides', 'Precursor_mz', 'Precursor_rt', 'Fragment_type']
        metric_prefixes = ['No_of_Fragments_', f'Total_{metric_name.lower()}_', 'Fragments_Score_', 'Fragments_Rating_']
        
        new_column_order = fixed_columns.copy()
        for prefix in metric_prefixes:
            for base_filename in base_filenames:
                column_name = f"{prefix}{base_filename}"
                if column_name in summary_df.columns:
                    new_column_order.append(column_name)
        
        existing_columns = [col for col in new_column_order if col in summary_df.columns]
        reorganized_df = summary_df[existing_columns]
        
        # ===== SUMMARY 2: INDIVIDUAL FRAGMENT AREAS ACROSS FILES =====
        print(f"\nCreating Summary 2: Individual fragment {metric_name.lower()}s across files...")
        
        # Get all unique fragments across all files
        unique_fragments_global = set()
        
        # First pass: collect all unique fragment identifiers
        for file_path, df in filtered_results.items():
            if 'Glycopeptides' in df.columns and 'Type' in df.columns and 'Theoretical_mz' in df.columns:
                for _, row in df.iterrows():
                    # Clean up glycopeptide name
                    glycopeptide = row['Glycopeptides']
                    if isinstance(glycopeptide, str) and '_row' in glycopeptide:
                        glycopeptide = glycopeptide.split('_row')[0]
                    if 'original_glycopeptide' in df.columns and pd.notna(row['original_glycopeptide']):
                        glycopeptide = row['original_glycopeptide']
                    
                    # Filter by fragment type if specified
                    if fragment_types.lower() != "all":
                        if 'FragmentType' in df.columns and df.columns:
                            if row['FragmentType'].lower() != fragment_types.lower():
                                continue
                    
                    # Create unique fragment key
                    fragment_key = (
                        glycopeptide,
                        row['Precursor_mz'],
                        row['precursor_rt'],
                        row['Type'],  # This is the Fragment name like "Hex1-B"
                        row.get('FragmentType', 'unknown'),
                        row['Theoretical_mz']
                    )
                    unique_fragments_global.add(fragment_key)
        
        print(f"Found {len(unique_fragments_global)} unique fragments across all files")
        
        # Second pass: create rows for each unique fragment with metrics from all files
        fragment_summary_rows = []
        
        for fragment_key in sorted(unique_fragments_global):
            glycopeptide, precursor_mz, precursor_rt, fragment_name, fragment_type, theoretical_mz = fragment_key
            
            # Initialize row data
            row_data = {
                'Glycopeptides': glycopeptide,
                'Precursor_mz': precursor_mz,
                'Precursor_rt': precursor_rt,
                'Fragment': fragment_name,
                'Fragment_type': fragment_type,
                'Theoretical_mz': theoretical_mz
            }
            
            # Initialize metric columns for each file with dynamic naming
            metric_values_for_files = []
            for base_filename in base_filenames:
                row_data[f'{metric_name}_{base_filename}'] = 0.0
                metric_values_for_files.append(0.0)
            
            # Fill in actual metric values from each file
            for base_filename in base_filenames:
                full_filename = file_mapping[base_filename]
                if full_filename not in filtered_results:
                    continue
                
                df = filtered_results[full_filename]
                
                # Find matching fragment in this file
                matching_fragments = df[
                    (df['Glycopeptides'].str.contains(str(glycopeptide), na=False, regex=False)) &
                    (np.isclose(df['Precursor_mz'], precursor_mz, rtol=1e-4)) &
                    (np.isclose(df['precursor_rt'], precursor_rt, rtol=1e-2)) &
                    (df['Type'] == fragment_name) &
                    (np.isclose(df['Theoretical_mz'], theoretical_mz, rtol=1e-6))
                ]
                
                if not matching_fragments.empty:
                    # Use the preferred metric column
                    if metric_column in matching_fragments.columns:
                        metric_value = float(matching_fragments.iloc[0][metric_column])
                    else:
                        # Fallback to the other metric if preferred is not available
                        fallback_column = "Area" if use_intensity_instead_of_area else "Intensity"
                        if fallback_column in matching_fragments.columns:
                            metric_value = float(matching_fragments.iloc[0][fallback_column])
                        else:
                            metric_value = 0.0
                    
                    row_data[f'{metric_name}_{base_filename}'] = metric_value
                    # Update the metric values list for statistics
                    file_index = base_filenames.index(base_filename)
                    metric_values_for_files[file_index] = metric_value
            
            # Calculate statistics
            non_zero_values = [value for value in metric_values_for_files if value > 0]
            num_files = len(base_filenames)
            num_files_with_fragment = len(non_zero_values)
            
            # Fragment prevalence (% of files where fragment is detected)
            row_data['Fragment_Prevalence'] = round(100 * num_files_with_fragment / num_files, 2) if num_files > 0 else 0.0
            
            # CV% (coefficient of variation) - only for fragments found in multiple files
            if len(non_zero_values) > 1:
                cv_percent = (np.std(non_zero_values) / np.mean(non_zero_values)) * 100
                row_data['CV_Percent'] = round(cv_percent, 2)
            else:
                row_data['CV_Percent'] = np.nan
            
            fragment_summary_rows.append(row_data)
        
        # Create Summary 2 DataFrame
        summary2_df = pd.DataFrame(fragment_summary_rows)
        
        if not summary2_df.empty:
            # Sort by Glycopeptides, Precursor_mz, then by Fragment_type
            sort_columns = ['Glycopeptides', 'Precursor_mz', 'Fragment_type', 'Theoretical_mz']
            summary2_df = summary2_df.sort_values(sort_columns)
            
            # Ensure proper column ordering with dynamic metric naming
            fixed_cols = ['Glycopeptides', 'Precursor_mz', 'Precursor_rt', 'Fragment', 'Fragment_type', 'Theoretical_mz']
            metric_cols = [f'{metric_name}_{base_filename}' for base_filename in base_filenames]
            stats_cols = ['Fragment_Prevalence', 'CV_Percent']
            
            final_column_order = fixed_cols + metric_cols + stats_cols
            
            # Only include columns that exist
            existing_cols = [col for col in final_column_order if col in summary2_df.columns]
            summary2_df = summary2_df[existing_cols]
            
            print(f"Summary 2 contains {len(summary2_df)} individual fragment entries")
        else:
            print("No fragments available for Summary 2")
        
        # Save to Excel
        summary_path = os.path.join(output_dir, f"PRM_Quantification_Summary_{timestamp}.xlsx")
        with pd.ExcelWriter(summary_path, engine='openpyxl') as writer:
            reorganized_df.to_excel(writer, sheet_name='Summary_1', index=False)
            
            if not summary2_df.empty:
                summary2_df.to_excel(writer, sheet_name='Summary_2', index=False)
            else:
                # Create empty DataFrame with dynamic column names
                empty_cols = ['Glycopeptides', 'Precursor_mz', 'Precursor_rt', 'Fragment', 'Fragment_type', 'Theoretical_mz'] + [f'{metric_name}_{bf}' for bf in base_filenames] + ['Fragment_Prevalence', 'CV_Percent']
                pd.DataFrame(columns=empty_cols).to_excel(writer, sheet_name='Summary_2', index=False)
                    
        print(f"Created summary with {len(summary_rows)} rows for {len(filtered_results)} files")
        print(f"Summary 1: {len(reorganized_df)} aggregated precursor entries")
        print(f"Summary 2: {len(summary2_df) if not summary2_df.empty else 0} individual fragment entries")
        print(f"Summary saved with timestamp: {timestamp}")
        return summary_path
        
    except Exception as e:
        import traceback
        print(f"Error creating PRM quantification summary: {str(e)}")
        traceback.print_exc()
        return None
    

###### GUI SECTION STARTS HERE ######

# GUI Components Start Here
import sys
import os
import json
import glob
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QTabWidget, QLabel, QLineEdit, 
                            QPushButton, QTextEdit, QProgressBar, QCheckBox,QTableWidgetItem,
                            QComboBox, QSpinBox, QDoubleSpinBox, QGroupBox,QTableWidget,
                            QFileDialog, QMessageBox, QScrollArea, QListWidget,QDialog,
                            QSplitter, QFrame, QGridLayout, QFormLayout,QInputDialog,
                            QAbstractItemView, QTreeWidgetItem, QHeaderView,QTreeWidget)
from PyQt5.QtCore import QThread, pyqtSignal, QTimer, Qt
from PyQt5.QtGui import QFont, QPalette, QColor, QIcon, QPixmap

 
class AnalysisWorker(QThread):
    progress_update = pyqtSignal(int)
    status_update = pyqtSignal(str)
    log_update = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)
    
    def __init__(self, params):
        super().__init__()
        self.params = params
        self.is_cancelled = False
        self.all_results = {}  # Store results for summary
        self.cached_mzml_data = {}  # Store cached data for EIC display
        
    def run(self):
        """Enhanced worker run method with proper error tracking"""
        try:
            self.status_update.emit("Starting analysis...")
            self.log_update.emit("Starting analysis...")
            self.progress_update.emit(10)
            
            # Get parameters for multiple file processing
            input_files = self.params.get('input_files', [])
            output_dir = self.params.get('output_dir', 'glycan_analysis_output')
            
            # ENHANCED: Multi-file data storage structure
            self.all_file_results = {}  # Comprehensive file results
            critical_errors = []  # Track critical errors
            
            if len(input_files) == 1:
                # Single file processing
                input_file = input_files[0]
                file_basename = os.path.splitext(os.path.basename(input_file))[0]
                self.log_update.emit(f"Processing single file: {file_basename}")
                
                # Process file and store comprehensive results
                file_results = self._process_single_file(input_file, file_basename)
                
                # Check for critical error in result
                if file_results is None or file_results.get('critical_error'):
                    error_msg = file_results.get('error_message', 'Unknown error') if file_results else 'Processing failed'
                    critical_errors.append(f"{file_basename}: {error_msg}")
                elif file_results:
                    self.all_file_results[file_basename] = file_results
                    # Also store in legacy format for backward compatibility
                    if file_results.get('matched_fragments') is not None:
                        self.all_results[file_basename] = file_results['matched_fragments']
                        self.cached_mzml_data = file_results.get('cached_data', {})
                
                self.progress_update.emit(80)
                
            elif len(input_files) > 1:
                # Multiple file processing
                self.log_update.emit(f"Processing {len(input_files)} files:")
                
                for i, input_file in enumerate(input_files):
                    if self.is_cancelled:
                        break
                        
                    file_basename = os.path.splitext(os.path.basename(input_file))[0]
                    self.log_update.emit(f"\n--- Processing file {i+1}/{len(input_files)}: {file_basename} ---")
                    
                    # Process each file and store comprehensive results
                    file_results = self._process_single_file(input_file, file_basename)
                    
                    # Check for critical error in result
                    if file_results is None or file_results.get('critical_error'):
                        error_msg = file_results.get('error_message', 'Unknown error') if file_results else 'Processing failed'
                        critical_errors.append(f"{file_basename}: {error_msg}")
                    elif file_results:
                        self.all_file_results[file_basename] = file_results
                        # Also store in legacy format
                        if file_results.get('matched_fragments') is not None:
                            self.all_results[file_basename] = file_results['matched_fragments']
                    
                    # Update progress
                    progress = 20 + (60 * (i + 1) / len(input_files))
                    self.progress_update.emit(int(progress))
                    
                    # Store cached data from the LAST file for EIC display
                    if file_results and file_results.get('cached_data'):
                        self.cached_mzml_data = file_results['cached_data']
            
            else:
                self.log_update.emit("No input files provided")
                self.finished_signal.emit(False, "No input files provided")
                return
            
            # Generate PRM Summary if we have results and no critical errors
            if self.all_results and not critical_errors:
                self.log_update.emit("Creating PRM quantification summary...")
                
                try:
                    summary_path = create_prm_quantification_summary(
                        output_dir=output_dir,
                        all_results=self.all_results,
                        fdr_grade_cutoff=self.params.get('fdr_grade_cutoff'),
                        fragment_types=self.params.get('fragment_types', 'all'),
                        use_intensity_instead_of_area=self.params.get('use_intensity_instead_of_area', False)
                    )
                    
                    if summary_path:
                        self.log_update.emit(f"PRM summary saved: {os.path.basename(summary_path)}")
                    else:
                        self.log_update.emit("Failed to create PRM summary")
                        
                except Exception as e:
                    self.log_update.emit(f"Error creating summary: {str(e)}")
            else:
                self.log_update.emit("No results available for summary generation or critical errors occurred")
            
            self.progress_update.emit(100)
            
            # FIXED: Report success only if there are results AND no critical errors
            if critical_errors:
                error_summary = "\n".join(critical_errors[:3])
                if len(critical_errors) > 3:
                    error_summary += f"\n...and {len(critical_errors) - 3} more errors"
                self.finished_signal.emit(False, f"Analysis failed with errors: {error_summary}")
            elif self.all_results:
                num_files = len(self.all_file_results)
                self.finished_signal.emit(True, f"Analysis completed successfully. Processed {num_files} files.")
            else:
                self.finished_signal.emit(False, "Analysis completed but no results were generated")
                
        except Exception as e:
            error_msg = f"Analysis failed: {str(e)}\n{traceback.format_exc()}"
            self.log_update.emit(error_msg)
            self.finished_signal.emit(False, f"Analysis failed: {str(e)}")
        
    def _process_single_file(self, input_file, file_basename):
        """Process a single file and return comprehensive results - CLI-style logic"""
        try:
            # Update parameters for this file
            file_params = self.params.copy()
            file_params['input_file'] = input_file
            file_params['excel_output_file'] = f"results_{file_basename}.xlsx"
            file_params['worker'] = self  # Pass worker for logging
            
            # Process the file
            output_path, cached_data, matched_fragments = analyze_and_export_all_glycans(**file_params)
            
            # FIXED: Follow CLI logic - success depends on matched_fragments, not Excel output
            if matched_fragments is not None and not matched_fragments.empty:
                # SUCCESS: We have valid matched fragments
                self.all_results[input_file] = matched_fragments  # Store like CLI
                
                num_fragments = len(matched_fragments)
                num_precursors = matched_fragments['Precursor_mz'].nunique()
                
                # Log like CLI
                self.log_update.emit(f"Added {num_fragments} matched fragments to summary")
                excel_status = f" -> Output saved to: {output_path}" if output_path else " -> Results processed in memory only"
                self.log_update.emit(f"Finished processing {file_basename}{excel_status}")
                
                # Create successful result structure
                file_results = {
                    'file_path': input_file,
                    'file_basename': file_basename,
                    'output_path': output_path,  # Can be None - that's OK
                    'matched_fragments': matched_fragments,  # This is what matters
                    'cached_data': cached_data.get('prm_data', {}) if cached_data else {},
                    'analysis_params': file_params.copy(),
                    'processing_timestamp': datetime.now().isoformat(),
                    'fragment_removal_state': {},
                    'critical_error': False,
                    'success': True  # Add explicit success flag
                }
                
                # Update cached data for EIC display
                if cached_data and cached_data.get('prm_data'):
                    self.cached_mzml_data.update(cached_data['prm_data'])
                    
                return file_results
                
            else:
                # NO MATCHED FRAGMENTS: This is the actual failure condition
                self.log_update.emit(f"No matched fragments available for summary - {file_basename}")
                return {
                    'file_path': input_file,
                    'file_basename': file_basename,
                    'critical_error': True,
                    'error_message': "No matched fragments generated",
                    'processing_timestamp': datetime.now().isoformat(),
                    'success': False
                }
                
        except Exception as e:
            self.log_update.emit(f"✗ {file_basename}: Processing failed - {str(e)}")
            return {
                'file_path': input_file,
                'file_basename': file_basename,
                'critical_error': True,
                'error_message': str(e),
                'processing_timestamp': datetime.now().isoformat(),
                'exception': str(e),
                'traceback': traceback.format_exc(),
                'success': False
            }
        
    def cancel(self):
        self.is_cancelled = True
        self.terminate()

    def log_important_update(self, message, level="INFO"):
        """Forward important updates to the GUI log - ENHANCED VERSION"""
        # Define important message patterns - EXPANDED LIST
        important_patterns = [
            # Process stages
            "Starting:",
            "Completed:",
            "Failed:",
            "Loading Excel",
            "Processing RAW file", 
            "Processing mzML file",
            "Created output directory",
            
            # Analysis phases
            "FIRST PASS:",
            "SECOND PASS:",
            "ANALYSIS COMPLETE",
            "PARAMETER VALIDATION",
            "FILE TYPE DETECTION",
            "EXCEL FILE LOADING",
            "COLUMN VALIDATION",
            
            # Mass calculations
            "Calculating masses for",
            "Calculated peptide mass:",
            "Total target m/z values:",
            
            # File processing
            "Found MS2 data:",
            "Finished processing",
            "Successfully processed RAW file",
            "Processed file with .* matching precursors",
            
            # Fragment generation
            "Predicting structures for",
            "Generated .* possible structures",
            "Total unique structures generated:",
            "Unique fragments: Total=",
            "Generated .* fragments",
            
            # Matching and integration
            "Matching fragments against theoretical database",
            "Total matches found:",
            "Final results:",
            "Successfully integrated",
            "Generated .* EIC plots",
            "Generated .* MS2 plots",
            
            # Output
            "Writing results to",
            "Results saved to",
            "All glycan/glycopeptide data saved",
            "Created summary with .* rows",
            "Summary saved",
            
            # Important info messages
            "INFO:",
            "Loaded Excel file with",
            "Found .* unique glycan",
            "Using .* for direct RAW",
            "Applied intensity threshold:",
            "Fragments with intensity",
            "RT filtering results:",
            "Deduplication complete:",
            "FDR Grade filtering results:",
            "Final fragment counts:",
            
            # Processing details
            "Processing pair .*/.*:",
            "Processing target:",
            "Processing precursor",
            "Found .* theoretical fragments",
            "Found .* data points",
            "Integration window:",
            "Peak width:",
            "Max intensity:",
            
            # Excel and column detection
            "Excel columns found:",
            "Using .* as the RT column",
            "Loaded .* custom peptide modifications",
            "Loaded .* custom peptide masses",
            
            # File detection and validation
            "Detected RAW file:",
            "Detected mzML file:",
            "fisher_py successfully initialized",
            "Using fisher_py for direct RAW",
            
            # Modification and calculation info
            "Using Excel-provided peptide mass:",
            "Calculated peptide mass for",
            "Using peptide cache key:",
            "Peptide mass in cache:",
            
            # Fragment processing
            "Adding custom fragments",
            "Generating C/Z fragments",
            "Applied RT filter BEFORE database matching",
            "RT filtering results:",
            "Fragments before RT filter:",
            "Fragments after RT filter:",
            
            # Summary generation
            "Creating PRM quantification summary",
            "Found .* unique glycopeptide-precursor combinations",
            "Including fragment types in summary:",
            "Summary 1: .* aggregated precursor entries",
            "Summary 2: .* individual fragment entries"
        ]
        
        # Check if message matches important patterns OR is ERROR/WARNING
        is_important = level in ["ERROR", "WARNING", "CRITICAL"]
        
        if not is_important:
            for pattern in important_patterns:
                if re.search(pattern, message, re.IGNORECASE):
                    is_important = True
                    break
        
        # Also log messages that contain key process indicators
        key_indicators = [
            "m/z", "RT", "fragments", "glycan", "peptide", "mass", "score", 
            "intensity", "area", "precursor", "theoretical", "experimental",
            "matched", "generated", "calculated", "processed", "saved",
            "loaded", "found", "detected", "applied", "filtered"
        ]
        
        if not is_important:
            # Check if message contains multiple key indicators (likely important)
            indicator_count = sum(1 for indicator in key_indicators 
                                if indicator.lower() in message.lower())
            if indicator_count >= 2:
                is_important = True
        
        if is_important:
            # Format message with level and timestamp
            timestamp = datetime.now().strftime("%H:%M:%S")
            formatted_message = f"[{timestamp}] {level}: {message}"
            self.log_update.emit(formatted_message)
    
class MassCalculatorWorker(QThread):
    """Worker thread for mass calculations"""
    calculation_finished = pyqtSignal(object)  
    
    def __init__(self, input_data, calc_type, use_cam, fixed_mods, variable_mods, use_excel_peptide_mod=False):
        super().__init__()
        self.input_data = input_data
        self.calc_type = calc_type
        self.use_cam = use_cam
        self.fixed_mods = fixed_mods or []
        self.variable_mods = variable_mods or []
        self.use_excel_peptide_mod = use_excel_peptide_mod
    
    def run(self):
        try:
            if self.calc_type == "manual":
                # Manual calculation for single glycan/peptide
                results = self.calculate_single_mass()
            else:
                # Batch calculation from Excel file
                results = self.calculate_batch_masses()
            
            self.calculation_finished.emit(results)
            
        except Exception as e:
            error_msg = f"Calculation error: {str(e)}"
            print(f"MassCalculatorWorker error: {error_msg}")
            self.calculation_finished.emit(error_msg)

class GlycanAnalysisGUI(QMainWindow):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        super().__init__()
        self.setWindowTitle("GlypPRM")
        self.setGeometry(100, 100, 1000, 750)
        self.setMinimumSize(800, 600)
        # Add this to your initialization
        self.glycopeptide_specific_params = {}
        
        # Initialize variables
        self.analysis_worker = None
        self.mass_calc_worker = None
        self.start_time = None
        
        # ENHANCED: Multi-file data storage
        self.all_analysis_results = {}  # Store results from all analyzed files
        self.current_file_key = None    # Currently viewed file
        self.file_navigation_enabled = False  # Whether multi-file navigation is available
        
        # Legacy single-file storage (for backward compatibility)
        self.current_matched_fragments = pd.DataFrame()
        self.current_cached_data = {}
        self.current_analysis_params = {}
        
        # Fragment removal state tracking
        self.fragment_removal_states = {}  # Per-file removal states
        self.global_removal_scope = False   # Whether to apply removals globally
        
        # Other existing initialization...
        self.fragment_interface_visible = True
        self.current_figure = None
        self.selected_glycopeptide = None
        self.current_viewer_mode = 'eic'
        
        # Setup logging and UI
        self.setup_logging_redirect()
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_timer)
        self.setup_ui()
        self.load_settings()
        self.load_calc_settings()
        self.apply_theme()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        
        # Timer display at the top
        self.timer_label = QLabel("00:00")
        self.timer_label.setAlignment(Qt.AlignRight)
        self.timer_label.setStyleSheet("font-size: 16px; font-weight: bold; padding: 2px;")
        main_layout.addWidget(self.timer_label)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # Create tabs
        self.create_setup_tab()  # Now contains Analysis Parameters and Modifications
        self.create_run_analysis_tab()  # File inputs, buttons, log
        self.create_output_tab()  # NEW: Output management and fragment removal
        self.create_mass_calculator_tab()  # Mass calculation utility
        self.create_help_tab()  # Comprehensive help
        
        # Progress bar (hidden by default)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        # Status bar
        self.status_label = QLabel("Ready to start analysis")
        main_layout.addWidget(self.status_label)
        
        # In your UI setup method, add this label:
        self.results_status_label = QLabel("Ready to display results")
        self.results_status_label.setStyleSheet("color: blue; font-weight: bold;")

        # Connect all controls to auto-save function
        self.connect_auto_save_signals()

    def get_selected_calc_variable_mods(self):
        """Helper method to get selected variable modifications for calculator"""
        variable_mods = []
        if not self.calc_use_excel_peptide_mod.isChecked():
            for item in self.calc_variable_mods.selectedItems():
                variable_mods.append(item.text())
        
        return variable_mods

    def get_selected_calc_fixed_mods(self):
        """Helper method to get selected fixed modifications for calculator"""
        fixed_mods = []
        if self.calc_use_cam.isChecked():
            fixed_mods.append("CAM:C")
        
        # Add other selected fixed modifications
        for item in self.calc_additional_fixed_mods.selectedItems():
            fixed_mods.append(item.text())
        
        return fixed_mods

    def format_modifications_display(self, fixed_mods, variable_mods, peptide_sequence=None):
        """Format modifications for display in results table"""
        mod_parts = []
        
        # Process fixed modifications
        for mod in fixed_mods:
            if ':' in mod:
                mod_name, residue = mod.split(':', 1)
                if peptide_sequence and residue in peptide_sequence:
                    residue_count = peptide_sequence.count(residue)
                    if residue_count == 1:
                        mod_parts.append(mod_name)
                    else:
                        mod_parts.append(f"{mod_name}:{residue_count}")
                else:
                    mod_parts.append(mod_name)
            else:
                mod_parts.append(mod)
        
        # Process variable modifications (marked with *)
        for mod in variable_mods:
            if ':' in mod:
                mod_name, residue = mod.split(':', 1)
                if peptide_sequence and residue in peptide_sequence:
                    residue_count = peptide_sequence.count(residue)
                    if residue_count == 1:
                        mod_parts.append(f"{mod_name}*")
                    else:
                        mod_parts.append(f"{mod_name}*:{residue_count}")
                else:
                    mod_parts.append(f"{mod_name}*")
            else:
                mod_parts.append(f"{mod}*")
        
        return ", ".join(mod_parts) if mod_parts else "None" 

    def toggle_comment_column_mode(self, checked):
        """Disable relevant functions when Comment Column mode is enabled"""
        if checked:
            # Disable modification controls
            self.use_cam.setEnabled(False)
            self.additional_fixed_mods.setEnabled(False)
            self.variable_mods.setEnabled(False)
            self.use_excel_peptide_mod.setEnabled(False)
            self.glycan_type.setEnabled(False)  # Will be determined per row
            
            # Update tooltips to show they're disabled
            self.use_cam.setToolTip("DISABLED: Using Comment column modifications")
            self.additional_fixed_mods.setToolTip("DISABLED: Using Comment column modifications")
            self.variable_mods.setToolTip("DISABLED: Using Comment column modifications")
            self.use_excel_peptide_mod.setToolTip("DISABLED: Using Comment column modifications")
            self.glycan_type.setToolTip("DISABLED: Glycan type determined from Comment column per row")
            
        else:
            # Re-enable modification controls
            self.use_cam.setEnabled(True)
            self.additional_fixed_mods.setEnabled(True)
            self.use_excel_peptide_mod.setEnabled(True)
            self.glycan_type.setEnabled(True)
            
            # Restore original tooltips
            self.use_cam.setToolTip("Carbamidomethylation of cysteine (+57.0215 Da)\nCommonly used alkylation agent: iodoacetamide")
            self.additional_fixed_mods.setToolTip("Select multiple fixed modifications\nHold Ctrl to select multiple items")
            self.use_excel_peptide_mod.setToolTip("Use peptide modifications from Excel PEP_Modification column\nOverrides GUI modification settings")
            self.glycan_type.setToolTip("Select glycan type:\n• N-glycan: Asparagine-linked glycans\n• O-glycan: Serine/Threonine-linked glycans")
            
            # Re-apply the variable mods toggle state
            self.toggle_variable_mods(self.use_excel_peptide_mod.isChecked())
            
    def update_gui_log(self, message, level="INFO"):
        """Update GUI log with important messages only"""
        if hasattr(self, 'setup_log_text') and self.setup_log_text is not None:
            timestamp = datetime.now().strftime("%H:%M:%S")
            formatted_message = f"[{timestamp}] {level}: {message}"
            
            # Thread-safe GUI update for PyQt5
            try:
                self.setup_log_text.append(formatted_message)
                # Auto-scroll to bottom
                scrollbar = self.setup_log_text.verticalScrollBar()
                scrollbar.setValue(scrollbar.maximum())
            except Exception as e:
                print(f"GUI log update failed: {e}")
        else:
            # Fallback to console if GUI not available
            print(f"GUI LOG - {level}: {message}")

    def connect_auto_save_signals(self):
        """Connect all GUI controls to auto-save their values when changed"""
        try:
            # Connect input fields
            self.input_excel.textChanged.connect(self.auto_save_settings)
            self.input_file.textChanged.connect(self.auto_save_settings)
            self.output_dir.textChanged.connect(self.auto_save_settings)
            
            # Connect combo boxes
            self.glycan_type.currentTextChanged.connect(self.auto_save_settings)
            self.fdr_grade_cutoff.currentTextChanged.connect(self.auto_save_settings)
            
            # Connect spin boxes
            self.rt_window.valueChanged.connect(self.auto_save_settings)
            self.max_rt_window.valueChanged.connect(self.auto_save_settings)
            self.max_rt_difference.valueChanged.connect(self.auto_save_settings)
            self.back_window_ratio.valueChanged.connect(self.auto_save_settings)
            self.display_time_extension.valueChanged.connect(self.auto_save_settings)
            self.max_fragments_displayed.valueChanged.connect(self.auto_save_settings)
            # NEW: Connect PPM tolerance controls
            self.ms1_ppm_tolerance.valueChanged.connect(self.auto_save_settings)
            self.ms2_ppm_tolerance.valueChanged.connect(self.auto_save_settings)
            
            # Connect checkboxes
            self.use_cam.toggled.connect(self.auto_save_settings)
            self.use_excel_pepmass.toggled.connect(self.auto_save_settings)
            self.use_excel_peptide_mod.toggled.connect(self.auto_save_settings)
            self.generate_glycan_by_ions.toggled.connect(self.auto_save_settings)
            self.generate_peptide_by_ions.toggled.connect(self.auto_save_settings)
            self.generate_cz_glycan.toggled.connect(self.auto_save_settings)
            self.generate_cz_peptide.toggled.connect(self.auto_save_settings)
            self.save_excel.toggled.connect(self.auto_save_settings)
            self.generate_eic_plots.toggled.connect(self.auto_save_settings)
            self.generate_ms2_plots.toggled.connect(self.auto_save_settings)
            self.use_excel_precursor.toggled.connect(self.auto_save_settings)
            self.use_excel_rt_window.toggled.connect(self.auto_save_settings)
            self.use_excel_rt_window.toggled.connect(self.toggle_max_rt_window) 
            self.use_intensity_instead_of_area.toggled.connect(self.auto_save_settings)
            self.use_comment_column.toggled.connect(self.auto_save_settings)
            self.enable_fragment_removal.toggled.connect(self.auto_save_settings)
            
            # Connect list widgets (multiple selection)
            self.additional_fixed_mods.itemSelectionChanged.connect(self.auto_save_settings)
            self.variable_mods.itemSelectionChanged.connect(self.auto_save_settings)
            
            # Connect calculator controls
            self.calc_use_cam.toggled.connect(self.auto_save_calc_settings)
            self.calc_use_excel_peptide_mod.toggled.connect(self.auto_save_calc_settings)
            self.calc_additional_fixed_mods.itemSelectionChanged.connect(self.auto_save_calc_settings)
            self.calc_variable_mods.itemSelectionChanged.connect(self.auto_save_calc_settings)
            
        except Exception as e:
            print(f"Warning: Could not connect all auto-save signals: {e}")
            
    def auto_save_settings(self):
        """Automatically save settings when any control changes"""
        try:
            # Get selected modifications for saving - MULTIPLE SELECTION SUPPORT
            selected_fixed_mods = [item.text() for item in self.additional_fixed_mods.selectedItems()]
            selected_variable_mods = [item.text() for item in self.variable_mods.selectedItems()]
            
            settings = {
                'input_excel': self.input_excel.text(),
                'input_file': self.input_file.text(),
                'output_dir': self.output_dir.text(),
                'glycan_type': self.glycan_type.currentText(),
                'rt_window': self.rt_window.value(),
                'max_rt_window': self.max_rt_window.value(),
                'max_rt_difference': self.max_rt_difference.value(),
                'back_window_ratio': self.back_window_ratio.value(),
                # NEW: Save PPM tolerance settings
                'ms1_ppm_tolerance': self.ms1_ppm_tolerance.value(),
                'ms2_ppm_tolerance': self.ms2_ppm_tolerance.value(),
                'use_cam': self.use_cam.isChecked(),
                'selected_fixed_mods': selected_fixed_mods,
                'selected_variable_mods': selected_variable_mods,
                'use_excel_pepmass': self.use_excel_pepmass.isChecked(),
                'use_excel_peptide_mod': self.use_excel_peptide_mod.isChecked(),
                'generate_glycan_by_ions': self.generate_glycan_by_ions.isChecked(),
                'generate_peptide_by_ions': self.generate_peptide_by_ions.isChecked(),
                'generate_cz_glycan': self.generate_cz_glycan.isChecked(),
                'generate_cz_peptide': self.generate_cz_peptide.isChecked(),
                'save_excel': self.save_excel.isChecked(),
                'generate_eic_plots': self.generate_eic_plots.isChecked(),
                'generate_ms2_plots': self.generate_ms2_plots.isChecked(),
                'use_excel_precursor': self.use_excel_precursor.isChecked(),
                'use_excel_rt_window': self.use_excel_rt_window.isChecked(),
                'use_intensity_instead_of_area': self.use_intensity_instead_of_area.isChecked(),
                'fdr_grade_cutoff': self.fdr_grade_cutoff.currentText(),
                'display_time_extension': self.display_time_extension.value(),
                'max_fragments_displayed': self.max_fragments_displayed.value(),
                'enable_fragment_removal': self.enable_fragment_removal.isChecked(),
                'use_comment_column': self.use_comment_column.isChecked()
            }
            
            with open('gui_settings.json', 'w') as f:
                json.dump(settings, f, indent=2)
                
        except Exception as e:
            # Silently handle save errors to avoid interrupting user workflow
            pass
        
    def auto_save_calc_settings(self):
        """Automatically save calculator settings when any control changes"""
        try:
            # Get selected modifications for calculator
            selected_calc_fixed_mods = [item.text() for item in self.calc_additional_fixed_mods.selectedItems()]
            selected_calc_variable_mods = [item.text() for item in self.calc_variable_mods.selectedItems()]
            
            calc_settings = {
                'calc_use_cam': self.calc_use_cam.isChecked(),
                'calc_use_excel_peptide_mod': self.calc_use_excel_peptide_mod.isChecked(),
                'calc_selected_fixed_mods': selected_calc_fixed_mods,
                'calc_selected_variable_mods': selected_calc_variable_mods,
            }
            
            with open('calc_settings.json', 'w') as f:
                json.dump(calc_settings, f, indent=2)
                
        except Exception as e:
            # Silently handle save errors
            pass

    def load_settings(self):
        """Load settings automatically on startup"""
        try:
            if os.path.exists('gui_settings.json'):
                with open('gui_settings.json', 'r') as f:
                    settings = json.load(f)
                
                # Temporarily disconnect signals to avoid triggering auto-save during loading
                self.disconnect_auto_save_signals()
                
                # Restore settings
                self.input_excel.setText(settings.get('input_excel', ''))
                self.input_file.setText(settings.get('input_file', ''))
                self.output_dir.setText(settings.get('output_dir', 'glycan_analysis_output'))
                
                # Combo boxes
                if 'glycan_type' in settings:
                    index = self.glycan_type.findText(settings['glycan_type'])
                    if index >= 0:
                        self.glycan_type.setCurrentIndex(index)
                
                if 'fdr_grade_cutoff' in settings:
                    index = self.fdr_grade_cutoff.findText(settings['fdr_grade_cutoff'])
                    if index >= 0:
                        self.fdr_grade_cutoff.setCurrentIndex(index)
                
                # Restore multiple selections - FIXED AND VARIABLE MODS
                if 'selected_fixed_mods' in settings:
                    for i in range(self.additional_fixed_mods.count()):
                        item = self.additional_fixed_mods.item(i)
                        if item.text() in settings['selected_fixed_mods']:
                            item.setSelected(True)
                
                if 'selected_variable_mods' in settings:
                    for i in range(self.variable_mods.count()):
                        item = self.variable_mods.item(i)
                        if item.text() in settings['selected_variable_mods']:
                            item.setSelected(True)
                
                # Spin boxes
                self.rt_window.setValue(settings.get('rt_window', 5.0))
                self.max_rt_window.setValue(settings.get('max_rt_window', 1.5))
                self.max_rt_difference.setValue(settings.get('max_rt_difference', 1.0))
                self.back_window_ratio.setValue(settings.get('back_window_ratio', 0.5))
                self.display_time_extension.setValue(settings.get('display_time_extension', 5.0))
                self.max_fragments_displayed.setValue(settings.get('max_fragments_displayed', 30))
                # NEW: Load PPM tolerance settings
                self.ms1_ppm_tolerance.setValue(settings.get('ms1_ppm_tolerance', 10.0))
                self.ms2_ppm_tolerance.setValue(settings.get('ms2_ppm_tolerance', 20.0))
                
                # Checkboxes
                self.use_cam.setChecked(settings.get('use_cam', True))
                self.use_excel_pepmass.setChecked(settings.get('use_excel_pepmass', False))
                self.use_excel_peptide_mod.setChecked(settings.get('use_excel_peptide_mod', False))
                self.generate_glycan_by_ions.setChecked(settings.get('generate_glycan_by_ions', True))
                self.generate_peptide_by_ions.setChecked(settings.get('generate_peptide_by_ions', False))
                self.generate_cz_glycan.setChecked(settings.get('generate_cz_glycan', False))
                self.generate_cz_peptide.setChecked(settings.get('generate_cz_peptide', False))
                self.save_excel.setChecked(settings.get('save_excel', True))
                self.generate_eic_plots.setChecked(settings.get('generate_eic_plots', True))
                self.generate_ms2_plots.setChecked(settings.get('generate_ms2_plots', False))
                self.use_excel_precursor.setChecked(settings.get('use_excel_precursor', True))
                self.use_excel_rt_window.setChecked(settings.get('use_excel_rt_window', True))
                self.use_intensity_instead_of_area.setChecked(settings.get('use_intensity_instead_of_area', False))
                self.use_comment_column.setChecked(settings.get('use_comment_column', False))
                self.enable_fragment_removal.setChecked(settings.get('enable_fragment_removal', False))
                
                # APPLY TOGGLE STATES AFTER LOADING
                self.toggle_max_rt_window(self.use_excel_rt_window.isChecked())
                self.toggle_variable_mods(self.use_excel_peptide_mod.isChecked())
                if hasattr(self, 'use_comment_column'):
                    self.toggle_comment_column_mode(self.use_comment_column.isChecked())
                
                # Reconnect auto-save signals
                self.connect_auto_save_signals()
                
                self.add_log("Settings loaded automatically")
        except Exception as e:
            # Reconnect signals even if loading fails
            self.connect_auto_save_signals()
            self.add_log(f"Failed to load settings: {str(e)}")
            
    def load_calc_settings(self):
        """Load calculator settings automatically on startup"""
        try:
            if os.path.exists('calc_settings.json'):
                with open('calc_settings.json', 'r') as f:
                    calc_settings = json.load(f)
                
                # Restore calculator settings
                self.calc_use_cam.setChecked(calc_settings.get('calc_use_cam', True))
                self.calc_use_excel_peptide_mod.setChecked(calc_settings.get('calc_use_excel_peptide_mod', False))
                
                # Restore multiple selections for calculator
                if 'calc_selected_fixed_mods' in calc_settings:
                    for i in range(self.calc_additional_fixed_mods.count()):
                        item = self.calc_additional_fixed_mods.item(i)
                        if item.text() in calc_settings['calc_selected_fixed_mods']:
                            item.setSelected(True)
                
                if 'calc_selected_variable_mods' in calc_settings:
                    for i in range(self.calc_variable_mods.count()):
                        item = self.calc_variable_mods.item(i)
                        if item.text() in calc_settings['calc_selected_variable_mods']:
                            item.setSelected(True)
                
                # Apply toggle state for calculator
                self.toggle_calc_variable_mods(self.calc_use_excel_peptide_mod.isChecked())
                
        except Exception as e:
            pass  # Silently handle loading errors

    def disconnect_auto_save_signals(self):
        """Temporarily disconnect auto-save signals during loading"""
        try:
            # Disconnect input fields
            self.input_excel.textChanged.disconnect()
            self.input_file.textChanged.disconnect()
            self.output_dir.textChanged.disconnect()
            
            # Disconnect combo boxes
            self.glycan_type.currentTextChanged.disconnect()
            self.fdr_grade_cutoff.currentTextChanged.disconnect()
            
            # Disconnect spin boxes
            self.rt_window.valueChanged.disconnect()
            self.max_rt_window.valueChanged.disconnect()
            self.max_rt_difference.valueChanged.disconnect()
            self.back_window_ratio.valueChanged.disconnect()
            self.display_time_extension.valueChanged.disconnect()
            self.max_fragments_displayed.valueChanged.disconnect()
            # NEW: Disconnect PPM tolerance controls
            self.ms1_ppm_tolerance.valueChanged.disconnect()
            self.ms2_ppm_tolerance.valueChanged.disconnect()
            
            # Disconnect checkboxes
            self.use_cam.toggled.disconnect()
            self.use_excel_pepmass.toggled.disconnect()
            self.use_excel_peptide_mod.toggled.disconnect()
            self.generate_glycan_by_ions.toggled.disconnect()
            self.generate_peptide_by_ions.toggled.disconnect()
            self.generate_cz_glycan.toggled.disconnect()
            self.generate_cz_peptide.toggled.disconnect()
            self.save_excel.toggled.disconnect()
            self.generate_eic_plots.toggled.disconnect()
            self.generate_ms2_plots.toggled.disconnect()
            self.use_excel_precursor.toggled.disconnect()
            self.use_excel_rt_window.toggled.disconnect()
            self.use_intensity_instead_of_area.toggled.disconnect()
            self.use_comment_column.toggled.disconnect()
            
            # Disconnect list widgets
            self.additional_fixed_mods.itemSelectionChanged.disconnect()
            self.variable_mods.itemSelectionChanged.disconnect()
            
        except Exception as e:
            # Some signals might not be connected yet, ignore errors
            pass
        
    def create_mass_calculator_tab(self):
        """Mass Calculator utility tab with improved layout and scroll area"""
        # Create main widget with scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        calc_widget = QWidget()
        layout = QVBoxLayout(calc_widget)
        
        # Manual calculation section
        manual_group = QGroupBox("Manual Mass Calculator")
        manual_layout = QFormLayout(manual_group)
        
        self.calc_glycan_input = QLineEdit()
        self.calc_glycan_input.setPlaceholderText("e.g., HexNAc4Hex5NeuAc2")
        self.calc_glycan_input.setToolTip("Enter glycan composition using standard notation:\nHex, HexNAc, Fuc, NeuAc, or 4502\nExample: HexNAc4Hex5NeuAc2 = 4 HexNAc, 5 Hex,  2 NeuAc")
        manual_layout.addRow("Glycan Code:", self.calc_glycan_input)
        
        self.calc_peptide_input = QLineEdit()
        self.calc_peptide_input.setPlaceholderText("e.g., LCPDCPLLAPLNDSR")
        self.calc_peptide_input.setToolTip("Enter peptide sequence using single-letter amino acid codes\nLeave empty for glycan-only calculations")
        manual_layout.addRow("Peptide Sequence:", self.calc_peptide_input)
        
        calc_button = QPushButton("Calculate Masses")
        calc_button.clicked.connect(self.calculate_manual_masses)
        calc_button.setToolTip("Calculate masses and m/z values for all charge states")
        manual_layout.addRow(calc_button)
        
        layout.addWidget(manual_group)
        
        # Batch calculation section
        batch_group = QGroupBox("Batch Mass Calculator")
        batch_layout = QVBoxLayout(batch_group)
        
        # File upload
        upload_layout = QHBoxLayout()
        self.calc_file_input = QLineEdit()
        self.calc_file_input.setPlaceholderText("Select Excel file...")
        self.calc_file_input.setToolTip("Excel file with Glycan and Peptide columns\nSame format as analysis input files")
        upload_layout.addWidget(QLabel("Excel File:"))
        upload_layout.addWidget(self.calc_file_input)
        
        browse_calc_btn = QPushButton("Browse")
        browse_calc_btn.clicked.connect(lambda: self.browse_file(self.calc_file_input, "Excel files (*.xlsx *.xls)"))
        upload_layout.addWidget(browse_calc_btn)
        
        upload_button = QPushButton("Calculate from File")
        upload_button.clicked.connect(self.calculate_batch_masses)
        upload_button.setToolTip("Calculate masses for all entries in the Excel file")
        upload_layout.addWidget(upload_button)
        
        batch_layout.addLayout(upload_layout)
        layout.addWidget(batch_group)
        
        # IMPROVED Modification settings for calculator - SIDE BY SIDE LAYOUT
        calc_mod_group = QGroupBox("Calculator Modification Settings")
        calc_mod_main_layout = QVBoxLayout(calc_mod_group)
        
        # Excel peptide modifications option at top
        self.calc_use_excel_peptide_mod = QCheckBox("Use Excel Peptide Modifications")
        self.calc_use_excel_peptide_mod.setToolTip("Use peptide modifications from Excel PEP_Modification column\nOverrides GUI modification settings")
        self.calc_use_excel_peptide_mod.toggled.connect(self.toggle_calc_variable_mods)
        calc_mod_main_layout.addWidget(self.calc_use_excel_peptide_mod)
        
        # Side-by-side layout for Fixed and Variable modifications
        mods_side_by_side = QHBoxLayout()
        
        # LEFT SIDE - Fixed modifications
        fixed_mod_widget = QWidget()
        fixed_mod_layout = QVBoxLayout(fixed_mod_widget)
        fixed_mod_layout.setContentsMargins(5, 5, 5, 5)
        
        # CAM checkbox
        self.calc_use_cam = QCheckBox("CAM:C")
        self.calc_use_cam.setChecked(True)
        self.calc_use_cam.setToolTip("Apply carbamidomethylation to cysteine residues")
        fixed_mod_layout.addWidget(self.calc_use_cam)
        
        fixed_mod_layout.addWidget(QLabel("Additional Fixed Modifications:"))
        self.calc_additional_fixed_mods = QListWidget()
        self.calc_additional_fixed_mods.setSelectionMode(QListWidget.MultiSelection)
        self.calc_additional_fixed_mods.setMaximumHeight(120)  # Reduced height
        self.calc_additional_fixed_mods.addItems([
            "PAM:C", "Palm:C", "Carbamyl:K", "Carbamyl:N-term", 
            "TMT6:K", "TMT6:N-term", "TMT10:K", "TMT10:N-term", 
            "TMT16:K", "TMT16:N-term", "iTRAQ4:K", "iTRAQ4:N-term", 
            "iTRAQ8:K", "iTRAQ8:N-term"
        ])
        self.calc_additional_fixed_mods.setToolTip("Select multiple fixed modifications\nHold Ctrl to select multiple")
        fixed_mod_layout.addWidget(self.calc_additional_fixed_mods)
        
        # RIGHT SIDE - Variable modifications
        var_mod_widget = QWidget()
        var_mod_layout = QVBoxLayout(var_mod_widget)
        var_mod_layout.setContentsMargins(5, 5, 5, 5)
        
        var_mod_layout.addWidget(QLabel("Variable Modifications:"))
        self.calc_variable_mods = QListWidget()
        self.calc_variable_mods.setSelectionMode(QListWidget.MultiSelection)
        self.calc_variable_mods.setMaximumHeight(150)  # Reduced height
        self.calc_variable_mods.addItems([
            "Ox:M", "Deam:N", "Deam:Q", "Phos:S", "Phos:T", "Phos:Y",
            "Ac:K", "Ac:N-term", "Methyl:K", "Methyl:R", "DiMethyl:K", "DiMethyl:R",
            "TriMethyl:K", "Pyro-glu:N-term-Q", "Pyro-cmC:N-term-C-CAM", "Formyl:K",
            "Formyl:N-term", "Myristoyl:N-term-G", "GG:K", "HexNAc:S", "HexNAc:T",
            "Nitration:Y", "Sulf:Y", "Biotin:K", "Malonyl:K", "Succinyl:K",
            "Farnesyl:C", "SUMO1-GG:K"
        ])
        self.calc_variable_mods.setToolTip("Select multiple variable modifications\nHold Ctrl to select multiple\nDisabled when using Excel modifications")
        var_mod_layout.addWidget(self.calc_variable_mods)
        
        # Add both sides to horizontal layout with equal stretching
        mods_side_by_side.addWidget(fixed_mod_widget, 1)
        mods_side_by_side.addWidget(var_mod_widget, 1)
        
        calc_mod_main_layout.addLayout(mods_side_by_side)
        layout.addWidget(calc_mod_group)
        
        # Results table - REDUCED HEIGHT
        results_group = QGroupBox("Calculation Results")
        results_layout = QVBoxLayout(results_group)
        
        self.calc_results_table = QTextEdit()
        self.calc_results_table.setReadOnly(True)
        self.calc_results_table.setMaximumHeight(180)  # Reduced from 200 to 180
        self.calc_results_table.setToolTip("Mass calculation results table")
        results_layout.addWidget(self.calc_results_table)
        
        # Export button
        export_button = QPushButton("Export Results to Excel")
        export_button.clicked.connect(self.export_calc_results)
        export_button.setToolTip("Save calculation results to Excel file")
        results_layout.addWidget(export_button)
        
        layout.addWidget(results_group)
        
        # Store results DataFrame for export
        self.calc_results_df = pd.DataFrame()
        
        # Set the scroll area widget
        scroll_area.setWidget(calc_widget)
        
        # Add the scroll area to the tab
        self.tab_widget.addTab(scroll_area, "Mass Calculator")

    def calculate_manual_masses(self):
        """Calculate masses for manual input with enhanced functionality"""
        glycan = self.calc_glycan_input.text().strip()
        peptide = self.calc_peptide_input.text().strip()
        
        # Allow glycan-only calculations
        if not glycan:
            QMessageBox.warning(self, "Input Error", "Please enter a glycan code")
            return
        
        try:
            # Get selected modifications
            fixed_mods = self.get_selected_calc_fixed_mods()
            variable_mods = self.get_selected_calc_variable_mods()
            
            # Create modification display string
            mod_display = self.format_modifications_display(fixed_mods, variable_mods, peptide)
            
            # Create a fresh calculator instance
            calculator = GlycanMassCalculator(
                modification_type=6,
                use_cam=self.calc_use_cam.isChecked(),
                fixed_mods=fixed_mods,
                variable_mods=variable_mods,
                peptide=None
            )
            
            # Parse glycan composition
            hexnac, hex, fuc, neuac, neugc = calculator.parse_glycan_code(glycan)
            
            # Calculate glycan mass
            glycan_composition = {
                'HexNAc': hexnac,
                'Hex': hex,
                'Fuc': fuc,
                'NeuAc': neuac,
                'NeuGc': neugc
            }
            
            # Calculate glycan mass without peptide to get correct glycan-only mass
            glycan_mass = calculator.calculate_fragment_mass(glycan_composition, 'y_ions', peptide=None)
            glycan_mass += 18.0153  # Add water for proper glycan mass

            peptide_mass = 0.0
            if peptide:
                # Create separate calculator for peptide mass calculation
                peptide_calculator = GlycanMassCalculator(
                    modification_type=6,
                    use_cam=self.calc_use_cam.isChecked(),
                    fixed_mods=fixed_mods,
                    variable_mods=variable_mods,
                    peptide=peptide
                )
                peptide_mass = peptide_calculator.calculate_peptide_mass(peptide)
            
            # Create results
            results = []
            
            # Always add glycan-only entry
            results.append({
                'Type': 'Glycan Only',
                'Glycan': glycan,
                'Peptide': 'N/A',
                'Modifications': 'N/A',
                'Mass': round(glycan_mass, 4),
                'mz_1H': round(calculator.calculate_mz(glycan_mass, 1), 4),
                'mz_2H': round(calculator.calculate_mz(glycan_mass, 2), 4),
                'mz_3H': round(calculator.calculate_mz(glycan_mass, 3), 4),
                'mz_4H': round(calculator.calculate_mz(glycan_mass, 4), 4),
                'mz_5H': round(calculator.calculate_mz(glycan_mass, 5), 4),
                'mz_6H': round(calculator.calculate_mz(glycan_mass, 6), 4)
            })
            
            # Add peptide-only entry if peptide provided
            if peptide:
                results.append({
                    'Type': 'Peptide Only',
                    'Glycan': 'N/A',
                    'Peptide': peptide,
                    'Modifications': mod_display,
                    'Mass': round(peptide_mass, 4),
                    'mz_1H': round(calculator.calculate_mz(peptide_mass, 1), 4),
                    'mz_2H': round(calculator.calculate_mz(peptide_mass, 2), 4),
                    'mz_3H': round(calculator.calculate_mz(peptide_mass, 3), 4),
                    'mz_4H': round(calculator.calculate_mz(peptide_mass, 4), 4),
                    'mz_5H': round(calculator.calculate_mz(peptide_mass, 5), 4),
                    'mz_6H': round(calculator.calculate_mz(peptide_mass, 6), 4)
                })
                
                # Add glycopeptide entry
                total_mass = glycan_mass + peptide_mass - 18.0153  # Subtract water for glycosidic bond
                results.append({
                    'Type': 'Glycopeptide',
                    'Glycan': glycan,
                    'Peptide': peptide,
                    'Modifications': mod_display,
                    'Mass': round(total_mass, 4),
                    'mz_1H': round(calculator.calculate_mz(total_mass, 1), 4),
                    'mz_2H': round(calculator.calculate_mz(total_mass, 2), 4),
                    'mz_3H': round(calculator.calculate_mz(total_mass, 3), 4),
                    'mz_4H': round(calculator.calculate_mz(total_mass, 4), 4),
                    'mz_5H': round(calculator.calculate_mz(total_mass, 5), 4),
                    'mz_6H': round(calculator.calculate_mz(total_mass, 6), 4)
                })
            
            # Display results
            self.display_calculation_results(pd.DataFrame(results))
            
        except Exception as e:
            QMessageBox.critical(self, "Calculation Error", f"Error calculating masses: {str(e)}")

    def calculate_batch_masses(self):
        """Calculate masses from uploaded Excel file with enhanced functionality"""
        file_path = self.calc_file_input.text().strip()
        
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "File Error", "Please select a valid Excel file")
            return
        
        try:
            # Read Excel file
            df = pd.read_excel(file_path)
            
            if df.empty:
                QMessageBox.warning(self, "File Error", "Excel file is empty")
                return
            
            # Find column names (case insensitive)
            glycan_col = next((col for col in df.columns if col.upper() == 'GLYCAN'), None)
            peptide_col = next((col for col in df.columns if col.upper() == 'PEPTIDE'), None)
            
            if not glycan_col:
                QMessageBox.warning(self, "File Error", "Missing required 'Glycan' column")
                return
            
            # Get selected modifications
            fixed_mods = self.get_selected_calc_fixed_mods()
            variable_mods = self.get_selected_calc_variable_mods()
            
            results = []
            
            # Process each row
            for idx, row in df.iterrows():
                try:
                    glycan = str(row[glycan_col]).strip() if pd.notna(row[glycan_col]) else ''
                    peptide = str(row[peptide_col]).strip() if peptide_col and pd.notna(row[peptide_col]) else ''
                    
                    if not glycan:
                        continue
                    
                    # Create modification display for this peptide
                    mod_display = self.format_modifications_display(fixed_mods, variable_mods, peptide)
                    
                    # Create calculator for glycan-only calculation
                    glycan_calculator = GlycanMassCalculator(
                        modification_type=6,
                        use_cam=self.calc_use_cam.isChecked(),
                        fixed_mods=fixed_mods,
                        variable_mods=variable_mods,
                        peptide=None
                    )
                    
                    # Parse glycan and calculate masses
                    hexnac, hex, fuc, neuac, neugc = glycan_calculator.parse_glycan_code(glycan)
                    
                    glycan_composition = {
                        'HexNAc': hexnac,
                        'Hex': hex,
                        'Fuc': fuc,
                        'NeuAc': neuac,
                        'NeuGc': neugc
                    }
                    
                    # Calculate glycan mass without peptide
                    glycan_mass = glycan_calculator.calculate_fragment_mass(glycan_composition, 'y_ions', peptide=None)
                    glycan_mass += 18.0153  # Add water for proper glycan mass

                    peptide_mass = 0.0
                    if peptide:
                        # Create separate calculator for peptide
                        peptide_calculator = GlycanMassCalculator(
                            modification_type=6,
                            use_cam=self.calc_use_cam.isChecked(),
                            fixed_mods=fixed_mods,
                            variable_mods=variable_mods,
                            peptide=peptide
                        )
                        peptide_mass = peptide_calculator.calculate_peptide_mass(peptide)
                    
                    # Calculate appropriate total mass based on input
                    if peptide:
                        total_mass = glycan_mass + peptide_mass - 18.0153  # Glycopeptide
                        mass_type = "Glycopeptide"
                    else:
                        total_mass = glycan_mass  # Glycan only
                        mass_type = "Glycan Only"
                        mod_display = "N/A"  # No modifications for glycan-only
                    
                    # Add result row
                    result_entry = {
                        'Row': idx + 1,
                        'Glycan': glycan,
                        'Peptide': peptide if peptide else 'N/A',
                        'Modifications': mod_display,
                        'Type': mass_type,
                        'Glycan_Mass': round(glycan_mass, 4),
                        'Peptide_Mass': round(peptide_mass, 4) if peptide else 0.0,
                        'Total_Mass': round(total_mass, 4),
                        'mz_1H': round(glycan_calculator.calculate_mz(total_mass, 1), 4),
                        'mz_2H': round(glycan_calculator.calculate_mz(total_mass, 2), 4),
                        'mz_3H': round(glycan_calculator.calculate_mz(total_mass, 3), 4),
                        'mz_4H': round(glycan_calculator.calculate_mz(total_mass, 4), 4),
                        'mz_5H': round(glycan_calculator.calculate_mz(total_mass, 5), 4),
                        'mz_6H': round(glycan_calculator.calculate_mz(total_mass, 6), 4)
                    }
                    results.append(result_entry)
                    
                except Exception as row_error:
                    print(f"Error processing row {idx + 1}: {row_error}")
                    continue
            
            if not results:
                QMessageBox.warning(self, "Processing Error", "No valid entries found in Excel file")
                return
            
            # Display results
            self.display_calculation_results(pd.DataFrame(results))
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error processing batch calculation: {str(e)}")

    def display_calculation_results(self, results):
        """Enhanced display calculation results with better formatting"""
        if isinstance(results, str):  # Error message
            self.calc_results_table.setHtml(f"<p style='color: red;'>{results}</p>")
            return
        
        if results.empty:
            self.calc_results_table.setHtml("<p style='color: orange;'>No results to display. Please check your input.</p>")
            return
        
        # Store results for export
        self.calc_results_df = results
        
        # Format results as HTML table with better styling
        html = "<h3 style='color: #2980b9;'>Mass Calculation Results</h3>"
        html += "<table border='1' style='border-collapse: collapse; width: 100%; font-size: 11px;'>"
        
        # Header with styling
        html += "<tr style='background-color: #3498db; color: white; font-weight: bold;'>"
        for col in results.columns:
            html += f"<th style='padding: 5px; border: 1px solid #ccc;'>{col}</th>"
        html += "</tr>"
        
        # Data rows with alternating colors
        for i, (_, row) in enumerate(results.iterrows()):
            row_color = "#f8f9fa" if i % 2 == 0 else "#ffffff"
            html += f"<tr style='background-color: {row_color};'>"
            
            for col in results.columns:
                value = row[col]
                if isinstance(value, float):
                    formatted_value = f"{value:.4f}"
                else:
                    formatted_value = str(value)
                html += f"<td style='padding: 3px; border: 1px solid #ccc; text-align: center;'>{formatted_value}</td>"
            html += "</tr>"
        
        html += "</table>"
        html += f"<p style='margin-top: 10px; color: #666;'><i>Total: {len(results)} result(s)</i></p>"
        
        self.calc_results_table.setHtml(html)

    def create_modifications_internal_tab(self, parent_tab_widget):
        """Modifications internal tab with multiple selection support and scroll area"""
        # Create scroll area for modifications tab
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        mod_widget = QWidget()
        main_layout = QHBoxLayout(mod_widget)
        
        # Left column - Excel Settings and Fixed Modifications
        left_column = QVBoxLayout()
        
        # Excel options
        excel_group = QGroupBox("Excel Settings")
        excel_layout = QVBoxLayout(excel_group)
        
        self.use_excel_pepmass = QCheckBox("Use Excel PepMass Column")
        self.use_excel_pepmass.setToolTip("Use custom peptide masses from Excel PepMass column\nOverrides calculated peptide masses")
        excel_layout.addWidget(self.use_excel_pepmass)
        
        self.use_excel_peptide_mod = QCheckBox("Use Excel Peptide Modifications")
        self.use_excel_peptide_mod.toggled.connect(self.toggle_variable_mods)
        self.use_excel_peptide_mod.setToolTip("Use peptide modifications from Excel PEP_Modification column\nOverrides GUI modification settings")
        excel_layout.addWidget(self.use_excel_peptide_mod)
        
        left_column.addWidget(excel_group)
        
        # Fixed modifications section
        fixed_group = QGroupBox("Fixed Modifications")
        fixed_group.setToolTip("Modifications applied to ALL peptides in the analysis")
        fixed_layout = QVBoxLayout(fixed_group)
        
        self.use_cam = QCheckBox("CAM (Carbamidomethyl on Cysteine)")
        self.use_cam.setChecked(True)
        self.use_cam.setToolTip("Carbamidomethylation of cysteine (+57.0215 Da)\nCommonly used alkylation agent: iodoacetamide")
        fixed_layout.addWidget(self.use_cam)
        
        # Additional Fixed Modifications - REMOVED height restrictions
        fixed_layout.addWidget(QLabel("Additional Fixed Modifications:"))
        self.additional_fixed_mods = QListWidget()
        self.additional_fixed_mods.setSelectionMode(QListWidget.MultiSelection)
        # REMOVED: setMinimumHeight and setMaximumHeight to allow expansion
        fixed_modifications = [
            "PAM:C",           # Propionamide (Cys) - acrylamide
            "Palm:C",          # Palmitoylation (Cys)
            "Carbamyl:K",      # Carbamylation (Lys)
            "Carbamyl:N-term", # Carbamylation (N-terminus)
            "TMT6:K",          # TMT 6-plex (Lys)
            "TMT6:N-term",     # TMT 6-plex (N-terminus)
            "TMT10:K",         # TMT 10-plex (Lys)
            "TMT10:N-term",    # TMT 10-plex (N-terminus)
            "TMT16:K",         # TMTpro 16-plex (Lys)
            "TMT16:N-term",    # TMTpro 16-plex (N-terminus)
            "iTRAQ4:K",        # iTRAQ 4-plex (Lys)
            "iTRAQ4:N-term",   # iTRAQ 4-plex (N-terminus)
            "iTRAQ8:K",        # iTRAQ 8-plex (Lys)
            "iTRAQ8:N-term"    # iTRAQ 8-plex (N-terminus)
        ]
        self.additional_fixed_mods.addItems(fixed_modifications)
        self.additional_fixed_mods.setToolTip("Select multiple fixed modifications\nHold Ctrl to select multiple items")
        fixed_layout.addWidget(self.additional_fixed_mods)
        
        left_column.addWidget(fixed_group)
        
        # Right column - Variable modifications
        right_column = QVBoxLayout()
        
        # Variable modifications section
        var_group = QGroupBox("Variable Modifications")
        var_group.setToolTip("Modifications that may or may not be present on peptides")
        var_layout = QVBoxLayout(var_group)
        
        self.variable_mods = QListWidget()
        self.variable_mods.setSelectionMode(QListWidget.MultiSelection)
        # REMOVED: setMinimumHeight and setMaximumHeight to allow expansion
        variable_modifications = [
            # Common oxidation and deamidation
            "Ox:M",            # Oxidation (Met) +15.9949 Da
            "Deam:N",          # Deamidation (Asn) +0.9840 Da
            "Deam:Q",          # Deamidation (Gln) +0.9840 Da
            
            # Phosphorylation
            "Phos:S",          # Phosphorylation (Ser) +79.9663 Da
            "Phos:T",          # Phosphorylation (Thr) +79.9663 Da
            "Phos:Y",          # Phosphorylation (Tyr) +79.9663 Da
            
            # Acetylation
            "Ac:K",            # Acetylation (Lys) +42.0106 Da
            "Ac:N-term",       # Acetylation (N-terminus) +42.0106 Da
            
            # Methylation
            "Methyl:K",        # Methylation (Lys) +14.0157 Da
            "Methyl:R",        # Methylation (Arg) +14.0157 Da
            "DiMethyl:K",      # Dimethylation (Lys) +28.0314 Da
            "DiMethyl:R",      # Dimethylation (Arg) +28.0314 Da
            "TriMethyl:K",     # Trimethylation (Lys) +42.0471 Da
            
            # N-terminal modifications
            "Pyro-glu:N-term-Q",      # Pyroglutamic acid from Gln -17.0265 Da
            "Pyro-cmC:N-term-C-CAM",  # Pyroglutamic acid from CAM-Cys +39.9949 Da
            "Formyl:K",               # Formylation (Lys) +27.9949 Da
            "Formyl:N-term",          # Formylation (N-terminus) +27.9949 Da
            "Myristoyl:N-term-G",     # Myristoylation (N-term Gly) +210.1984 Da
            
            # Post-translational modifications
            "GG:K",            # GlyGly (Lys) - ubiquitination remnant +114.0429 Da
            "HexNAc:S",        # O-GlcNAc (Ser) +203.0794 Da
            "HexNAc:T",        # O-GlcNAc (Thr) +203.0794 Da
            "Nitration:Y",     # Nitration (Tyr) +44.9851 Da
            "Sulf:Y",          # Sulfation (Tyr) +79.9568 Da
            "Biotin:K",        # Biotinylation (Lys) +226.0776 Da
            "Malonyl:K",       # Malonylation (Lys) +86.0004 Da
            "Succinyl:K",      # Succinylation (Lys) +100.0160 Da
            "Farnesyl:C",      # Farnesylation (Cys) +204.1878 Da
            "SUMO1-GG:K"       # SUMOylation remnant (Lys) +484.2281 Da
        ]
        
        self.variable_mods.addItems(variable_modifications)
        self.variable_mods.setToolTip("Select multiple variable modifications\nHold Ctrl to select multiple items\nDisabled when using Excel modifications")
        var_layout.addWidget(self.variable_mods)
        
        right_column.addWidget(var_group)
        
        # REMOVED: addStretch() calls to prevent expansion
        
        # Add columns to main layout with equal stretch
        main_layout.addLayout(left_column, 1)
        main_layout.addLayout(right_column, 1)
        
        # Set the scroll area widget
        scroll_area.setWidget(mod_widget)
        
        parent_tab_widget.addTab(scroll_area, "Modifications")

    def setup_logging_redirect(self):
        """Redirect stdout and stderr to GUI log"""
        import sys
        
        class GuiLogStream:
            def __init__(self, gui_instance):
                self.gui = gui_instance
                self.original_stdout = sys.stdout
                self.original_stderr = sys.stderr
            
            def write(self, text):
                if text.strip():  # Only log non-empty messages
                    # Send to GUI log in main thread
                    if hasattr(self.gui, 'add_log'):
                        # Use QTimer to ensure thread safety
                        QTimer.singleShot(0, lambda: self.gui.add_log(text.strip()))
                # Also write to original stdout for debugging
                self.original_stdout.write(text)
            
            def flush(self):
                self.original_stdout.flush()
        
        # Create custom stream and redirect
        self.log_stream = GuiLogStream(self)
        sys.stdout = self.log_stream
        sys.stderr = self.log_stream
    
    def closeEvent(self, event):
        """Restore original stdout/stderr when closing"""
        import sys
        if hasattr(self, 'log_stream'):
            sys.stdout = self.log_stream.original_stdout
            sys.stderr = self.log_stream.original_stderr
        event.accept()

    def create_setup_tab(self):
        """Setup tab with internal tabs for Analysis Parameters and Modifications - with scroll area"""
        # Create main widget with scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        setup_widget = QWidget()
        setup_layout = QVBoxLayout(setup_widget)
        
        # Create internal tab widget
        setup_tab_widget = QTabWidget()
        
        # Analysis Parameters internal tab
        self.create_analysis_params_internal_tab(setup_tab_widget)
        
        # Modifications internal tab
        self.create_modifications_internal_tab(setup_tab_widget)
        
        setup_layout.addWidget(setup_tab_widget)
        
        # Set the scroll area widget
        scroll_area.setWidget(setup_widget)
        
        # Add the scroll area to the main tab widget
        self.tab_widget.addTab(scroll_area, "Setup")

    def create_help_tab(self):
        """Comprehensive help tab with internal tabs"""
        help_widget = QWidget()
        help_layout = QVBoxLayout(help_widget)
        
        # Create internal tab widget for help sections
        help_tab_widget = QTabWidget()
        
        # Overview tab
        self.create_help_overview_tab(help_tab_widget)
        
        # Input Format tab
        self.create_help_input_format_tab(help_tab_widget)
        
        # Parameters tab
        self.create_help_parameters_tab(help_tab_widget)
        
        # Modifications tab
        self.create_help_modifications_tab(help_tab_widget)
        
        # Output tab
        self.create_help_output_tab(help_tab_widget)
        
        # Troubleshooting tab
        self.create_help_troubleshooting_tab(help_tab_widget)
        
        help_layout.addWidget(help_tab_widget)
        self.tab_widget.addTab(help_widget, "Help")

    def create_help_overview_tab(self, parent_tab_widget):
        """Overview help tab"""
        overview_widget = QWidget()
        layout = QVBoxLayout(overview_widget)
        
        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setHtml("""
        <h2>GlypPRM</h2>
        
        <h3>Overview</h3>
        <p>GlypPRM is a comprehensive tool for analyzing glycopeptides PRM after LC-MS/MS analysis. 
        It processes targeted analysis of glycopeptides.</p>

        <h3>Key Features</h3>
        <ul>
        <li><b>Glycan Structure Prediction:</b> Automatically predicts N-glycan and O-glycan structures</li>
        <li><b>Fragment Generation:</b> Generates theoretical B, Y, C, and Z fragments</li>
        <li><b>Mass Spectrometry Integration:</b> Processes .raw and .mzML files</li>
        <li><b>Fragment Matching:</b> Matches theoretical fragments with experimental data</li>
        <li><b>Quantification:</b> Calculates fragment areas and intensities</li>
        <li><b>Visualization:</b> Generates EIC plots and MS2 spectra</li>
        </ul>
        
        <h3>Workflow</h3>
        <ol>
        <li><b>Prepare Input:</b> Create Excel file with glycan/peptide information</li>
        <li><b>Configure Analysis:</b> Set parameters in Setup tab</li>
        <li><b>Run Analysis:</b> Load files and start analysis in Run Analysis tab</li>
        <li><b>Review Results:</b> Examine output files and plots</li>
        </ol>
        
        <h3>Supported Formats</h3>
        <ul>
        <li><b>Input Data:</b> Thermo .raw files, .mzML files</li>
        <li><b>Input Lists:</b> Excel .xlsx/.xls files</li>
        <li><b>Output:</b> Excel files, SVG plots</li>
        </ul>
        """)
        
        layout.addWidget(help_text)
        parent_tab_widget.addTab(overview_widget, "Overview")

    def create_help_input_format_tab(self, parent_tab_widget):
        """Input format help tab"""
        input_widget = QWidget()
        layout = QVBoxLayout(input_widget)
        
        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setHtml("""
        <h2>Input File Formats</h2>
        
        <h3>Required Excel Columns</h3>
        <table border="1" style="border-collapse: collapse; width: 100%;">
        <tr style="background-color: #f0f0f0;">
            <th>Column Name</th>
            <th>Required</th>
            <th>Description</th>
            <th>Example</th>
        </tr>
        <tr>
            <td><b>Glycan</b></td>
            <td>Yes</td>
            <td>Glycan composition using standard notation</td>
            <td>HexNAc(5)Hex(4)Fuc(1), 5410</td>
        </tr>
        <tr>
            <td><b>Peptide</b></td>
            <td>Yes</td>
            <td>Peptide sequence using single-letter codes</td>
            <td>LCPDCPLLAPLNDSR</td>
        </tr>
        <tr>
            <td><b>RT</b></td>
            <td>Yes</td>
            <td>Retention time in minutes</td>
            <td>25.5, 30.2</td>
        </tr>
        </table>
        
        <h3>Optional Excel Columns</h3>
        <table border="1" style="border-collapse: collapse; width: 100%;">
        <tr style="background-color: #f0f0f0;">
            <th>Column Name</th>
            <th>Description</th>
            <th>Example</th>
        </tr>
        <tr>
            <td><b>Precursor_mz</b></td>
            <td>Custom precursor m/z value</td>
            <td>1234.5678</td>
        </tr>
        <tr>
            <td><b>RT_window</b></td>
            <td>Custom Scan window for MS2 fragment collection for this entry</td>
            <td>1.5</td>
        </tr>
        <tr>
            <td><b>PepMass</b></td>
            <td>Custom peptide mass</td>
            <td>1685.7890</td>
        </tr>
        <tr>
            <td><b>PEP_Modification</b></td>
            <td>Peptide modifications</td>
            <td>Ox:M15, Phos:S10</td>
        </tr>
        <tr style="background-color: #e6f7ff;">
            <td><b>Comment</b></td>
            <td>Glycopeptide string with modifications (alternative format)</td>
            <td>LCPDCPLLAPLNDS[+2027.79]R.T, S.VTAPDTASTLLEK[+365.13]T</td>
        </tr>
        </table>
        
        <h3>Comment Column Glycopeptide Parsing</h3>
        <p><b>Alternative Input Method:</b> Instead of separate Glycan/Peptide columns, you can use a single Comment column with glycopeptide strings.</p>
        
        <h4>Comment Column Format: This is exactly as provided after Byonic run of raw full scan glycopeptides analysis</h4>
        <ul>
        <li><b>Basic format:</b> PEPTIDESEQUENCE[+mass].SUFFIX_AA GLYCAN_CODE</li>
        <li><b>With prefix:</b> PREFIX_AA.PEPTIDESEQUENCE[+mass].SUFFIX_AA GLYCAN_CODE</li>
        <li><b>N-terminal modifications:</b> [+mass].PEPTIDESEQUENCE[+peptide_mass].SUFFIX_AA GLYCAN_CODE</li>
        </ul>
        
        <h4>Comment Column Examples</h4>
        <table border="1" style="border-collapse: collapse; width: 100%;">
        <tr style="background-color: #e6f7ff;">
            <th>Comment Column Entry</th>
            <th>Parsed Peptide</th>
            <th>Parsed Glycan</th>
            <th>Glycan Type</th>
            <th>Modifications</th>
        </tr>
        <tr>
            <td>LCPDCPLLAPLNDS[+2027.79]R.T</td>
            <td>LCPDCPLLAPLNDSR</td>
            <td>Derived from mass</td>
            <td>N</td>
            <td>(+2027.79):S14</td>
        </tr>
        <tr>
            <td>S.VTAPDTASTLLEK[+365.13]T</td>
            <td>VTAPDTASTLLEK</td>
            <td>Derived from mass</td>
            <td>O</td>
            <td>(+365.13):K13</td>
        </tr>
        <tr>
            <td>[+42.01].VTAPDTASTLLEK[+365.13]T</td>
            <td>VTAPDTASTLLEK</td>
            <td>Derived from mass</td>
            <td>O</td>
            <td>(+42.01):Nterm; (+365.13):K13</td>
        </tr>
        <tr>
            <td>PEPTIDE[+1234.56]K.A H5N4F1</td>
            <td>PEPTIDEK</td>
            <td>H5N4F1</td>
            <td>N</td>
            <td>(+1234.56):K8</td>
        </tr>
        </table>
        
        <h4>Comment Column Benefits</h4>
        <ul>
        <li><b>Automatic glycan type detection:</b> N-glycan (N/K modification) vs O-glycan (S/T modification)</li>
        <li><b>Site-specific modifications:</b> Exact modification positions automatically determined</li>
        <li><b>Flexible format:</b> Handles various glycopeptide string formats</li>
        <li><b>Override capability:</b> Overrides GUI modification settings per row</li>
        </ul>
        
        <h4>Using Comment Column Mode</h4>
        <ol>
        <li>Enable "Use Comment Column for Glycopeptide Parsing" in Setup → Analysis Parameters</li>
        <li>Include Comment column in Excel file with glycopeptide strings</li>
        <li>Glycan and Peptide columns become optional (can be empty)</li>
        <li>GUI modification settings are disabled (row-specific modifications used instead)</li>
        </ol>
        
        <h3>Glycan Notation</h3>
        <ul>
        <li><b>Hex:</b> Hexose (mannose, galactose) - 162.0528 Da</li>
        <li><b>HexNAc:</b> N-acetylhexosamine (GlcNAc, GalNAc) - 203.0794 Da</li>
        <li><b>Fuc:</b> Fucose - 146.0579 Da</li>
        <li><b>NeuAc:</b> N-acetylneuraminic acid (sialic acid) - 291.0954 Da</li>
        <li><b>NeuGc:</b> N-glycolylneuraminic acid - 307.0903 Da</li>
        </ul>
        
        <h3>Standard Input Examples</h3>
        
        <h4>N-Glycan Example:</h4>
        <table border="1" style="border-collapse: collapse; width: 100%;">
        <tr style="background-color: #e6f3ff;">
            <th>Glycan</th>
            <th>Peptide</th>
            <th>RT</th>
        </tr>
        <tr><td>4502</td><td>LCPDCPLLAPLNDSR</td><td>25.5</td></tr>
        <tr><td>HexNAc4Hex5NeuAc2</td><td>LCPDCPLLAPLNDSR</td><td>30.2</td></tr>
        <tr><td>HexNAc4Hex5Fuc1NeuAc2</td><td>LCPDCPLLAPLNDSR</td><td>35.8</td></tr>
        </table>
        
        <h4>O-Glycan Example:</h4>
        <table border="1" style="border-collapse: collapse; width: 100%;">
        <tr style="background-color: #e6ffe6;">
            <th>Glycan</th>
            <th>Peptide</th>
            <th>RT</th>
        </tr>
        <tr><td>1101</td><td>VTAPDTASTLLEAK</td><td>25.2</td></tr>
        <tr><td>HexNAc2Hex2NeuAc2</td><td>VTAPDTASTLLEAK</td><td>28.5</td></tr>
        <tr><td>Hex2</td><td>VTAPDTASTLLEAK</td><td>22.1</td></tr>
        </table>
        
        <h4>Comment Column Example:</h4>
        <table border="1" style="border-collapse: collapse; width: 100%;">
        <tr style="background-color: #fff2e6;">
            <th>Comment</th>
            <th>RT</th>
            <th>Notes</th>
        </tr>
        <tr><td>LCPDCPLLAPLNDS[+2027.79]R.T</td><td>25.5</td><td>N-glycan automatically detected</td></tr>
        <tr><td>S.VTAPDTASTLLEK[+365.13]T</td><td>28.5</td><td>O-glycan automatically detected</td></tr>
        <tr><td>[+42.01].PEPTIDE[+1234.56]K.A</td><td>30.2</td><td>N-terminal + site modification</td></tr>
        </table>
        """)
        
        layout.addWidget(help_text)
        parent_tab_widget.addTab(input_widget, "Input Formats")
        
    def create_help_parameters_tab(self, parent_tab_widget):
        """Parameters help tab"""
        params_widget = QWidget()
        layout = QVBoxLayout(params_widget)
        
        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setHtml("""
        <h2>Analysis Parameters Guide</h2>
        
        <h3>Glycan Analysis Settings</h3>
        <ul>
        <li><b>Glycan Type:</b>
            <ul>
            <li><b>N-glycan:</b> Asparagine-linked glycans, typically larger and more complex</li>
            <li><b>O-glycan:</b> Serine/Threonine-linked glycans, typically smaller and simpler</li>
            </ul>
        </li>
        </ul>
        
        <h3>Retention Time Parameters</h3>
        <ul>
        <li><b>RT Window (5.0 min default):</b> Initial search window around target RT
            <ul>
            <li>Larger values: More inclusive, may capture more noise</li>
            <li>Smaller values: More selective, may miss targets</li>
            </ul>
        </li>
        <li><b>Max RT Window (1.5 min default):</b> Maximum window for peak integration
            <ul>
            <li>Should be smaller than RT Window</li>
            <li>Depends on peak width in your chromatography</li>
            <li>Typical range: 1-5 minutes</li>
            <li>For better result use the RT_window column in input excel to set this for each glycopeptides</li>
            </ul>
        </li>
        <li><b>Max RT Difference (1.0 min default):</b> Maximum allowed RT deviation
            <ul>
            <li>Filters fragments too far from expected RT</li>
            <li>Smaller values = stricter filtering</li>
            <li>Adjust based on RT reproducibility</li>
            </ul>
        </li>
        <li><b>Back Window Ratio (0.4 default):</b> Asymmetric RT window
            <ul>
            <li>0.1 = 40% before target RT, 60% after</li>
            <li>Useful for gradient elution where peaks tail</li>
            <li>Range: 0.1-0.9 typically</li>
            </ul>
        </li>
        </ul>
    
        
        <h3>Fragment Generation Options</h3>
        <li><b>Glycan Fragments:</b>
            <ul>
            <li><b>B/Y Ions:</b> Standard glycan fragmentation (recommended)</li>
            <li><b>C/Z Ions:</b> Alternative fragmentation patterns</li>
            </ul>
        </li>
        <li><b>Peptide Fragments:</b>
            <ul>
            <li><b>B/Y Ions:</b> Peptide backbone fragmentation</li>
            <li><b>C/Z Ions:</b> For ETD/ECD fragmentation</li>
            </ul>
        </li>
        </ul>
                          
        # Fragment Removal Options
        <h3>Fragment Curation Options</h3>
        <ul>
        <li><b>Interactive Fragment Removal:</b> Allows manual curation of fragment matches
            <ul>
            <li>Launched after analysis is complete</li>
            <li>Review fragment quality scores and EIC appearance</li>
            <li>Remove poor-quality fragments from quantification</li>
            <li>Automatically regenerates plots with filtered data</li>
            <li>Useful for removing interference or poor integrations</li>
            </ul>
        </li>
        </ul>
                          
        """)
        
        layout.addWidget(help_text)
        parent_tab_widget.addTab(params_widget, "Parameters")

    def create_help_modifications_tab(self, parent_tab_widget):
        """Modifications help tab"""
        mod_widget = QWidget()
        layout = QVBoxLayout(mod_widget)
        
        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setHtml("""
        <h2>Modifications Guide</h2>
        
        <h3>Fixed vs Variable Modifications</h3>
        <ul>
        <li><b>Fixed Modifications:</b> Applied to ALL peptides in the analysis
            <ul>
            <li>Use for sample preparation modifications (e.g., alkylation)</li>
            <li>Use for labeling reagents (e.g., TMT, iTRAQ)</li>
            <li>Always present on specified residues</li>
            </ul>
        </li>
        <li><b>Variable Modifications:</b> May or may not be present
            <ul>
            <li>Use for biological modifications (e.g., phosphorylation)</li>
            <li>Use for oxidation and other artifacts</li>
            <li>Increases search complexity</li>
            </ul>
        </li>
        </ul>
        
        <h3>Common Fixed Modifications</h3>
        <table border="1" style="border-collapse: collapse; width: 100%;">
        <tr style="background-color: #f0f0f0;">
            <th>Modification</th>
            <th>Mass (Da)</th>
            <th>Description</th>
        </tr>
        <tr><td>CAM:C</td><td>+57.0215</td><td>Carbamidomethylation (iodoacetamide)</td></tr>
        <tr><td>PAM:C</td><td>+71.0371</td><td>Propionamide (acrylamide)</td></tr>
        <tr><td>TMT6:K</td><td>+229.1629</td><td>TMT 6-plex on lysine</td></tr>
        <tr><td>TMT6:N-term</td><td>+229.1629</td><td>TMT 6-plex on N-terminus</td></tr>
        <tr><td>iTRAQ4:K</td><td>+144.1059</td><td>iTRAQ 4-plex on lysine</td></tr>
        </table>
        
        <h3>Common Variable Modifications</h3>
        <table border="1" style="border-collapse: collapse; width: 100%;">
        <tr style="background-color: #f0f0f0;">
            <th>Modification</th>
            <th>Mass (Da)</th>
            <th>Description</th>
        </tr>
        <tr><td>Ox:M</td><td>+15.9949</td><td>Oxidation of methionine</td></tr>
        <tr><td>Deam:N</td><td>+0.9840</td><td>Deamidation of asparagine</td></tr>
        <tr><td>Deam:Q</td><td>+0.9840</td><td>Deamidation of glutamine</td></tr>
        <tr><td>Phos:S</td><td>+79.9663</td><td>Phosphorylation of serine</td></tr>
        <tr><td>Phos:T</td><td>+79.9663</td><td>Phosphorylation of threonine</td></tr>
        <tr><td>Phos:Y</td><td>+79.9663</td><td>Phosphorylation of tyrosine</td></tr>
        <tr><td>Ac:K</td><td>+42.0106</td><td>Acetylation of lysine</td></tr>
        <tr><td>Ac:N-term</td><td>+42.0106</td><td>N-terminal acetylation</td></tr>
        </table>
        
        <h3>Excel Modification Format</h3>
        <p>When using Excel modifications, use this format in the PEP_Modification column:</p>
        <ul>
        <li><b>Single modification:</b> Ox:M15 (oxidation at position 15)</li>
        <li><b>Multiple modifications:</b> Ox:M15,Phos:S10 (comma-separated)</li>
        <li><b>N-terminal:</b> Ac:N-term (N-terminal acetylation)</li>
        <li><b>C-terminal:</b> Amid:C-term (C-terminal amidation)</li>
        <li><b>Custom:</b> AA+Position:MassChange (Q7:56.78)</li>
        </ul>
        
        <h3>Best Practices</h3>
        <ul>
        <li>Always include CAM:C if samples were treated with iodoacetamide</li>
        <li>Only use the variable modification on the app when all the possible AA are modified</li>
        <li>Use Excel modifications for site-specific known modifications</li>
        <li>Use Excel modifications for other modifications not listed by on the app using this format (Q7:56.78), meaning AA at position 7 is going to get addition of 56.78 Da</li>
        <li>Verify modification masses in your analysis result</li>
        </ul>
        """)
        
        layout.addWidget(help_text)
        parent_tab_widget.addTab(mod_widget, "Modifications")

    def create_help_output_tab(self, parent_tab_widget):
        """Output help tab"""
        output_widget = QWidget()
        layout = QVBoxLayout(output_widget)
        
        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setHtml("""
        <h2>Output Files and Interpretation</h2>
        
        <h3>PRM Quantification Excel Output</h3>
        <ul>
        <li><b>Summary1</b> Total sum of Intensities or Areas of all fragments for each glycopeptide across all processed raw/mzml files
            <ul>
            <li>Contains number of fragment, m/z, Cummulative fragments rating</li>
            </ul>
        </li>
        <li><b>Summary2:</b> Individual Fragments Intensities or Areas across all fragments for each glycopeptide across all processed raw/mzml files
            <ul>
            <li>Shows Fragments Prevalence and CVs across processed files</li>
            </ul>
        </li>
        </ul>
                          
        <h3>Optional Excel Output Sheets</h3>
        <ul>
        <li><b>Unique_Fragments:</b> All theoretical fragments generated
            <ul>
            <li>Contains fragment types, masses, charges</li>
            <li>Used for method development and troubleshooting</li>
            </ul>
        </li>
        <li><b>PEP_Masses:</b> Calculated precursor masses
            <ul>
            <li>Glycan masses, peptide masses, total masses</li>
            <li>m/z values for different charge states</li>
            </ul>
        </li>
        <li><b>Matched_Fragments:</b> Experimental fragments matched to theoretical
            <ul>
            <li>Contains quantitative results (areas, intensities)</li>
            <li>Fragment scoring and quality metrics</li>
            <li>Main results for data analysis</li>
            </ul>
        </li>
        </ul>
        
        <h3>Key Result Columns</h3>
        <table border="1" style="border-collapse: collapse; width: 100%;">
        <tr style="background-color: #f0f0f0;">
            <th>Column</th>
            <th>Description</th>
        </tr>
        
        <h3>EIC Plots</h3>
        <ul>
        <li><b>Extracted Ion Chromatograms</b> for each glycopeptide</li>
        <li>Shows elution profiles of all matched fragments</li>
        <li>Integration boundaries highlighted</li>
        <li>Useful for quality assessment and method optimization</li>
        </ul>
        
        <h3>MS2 Plots</h3>
        <ul>
        <li><b>MS2 spectra</b> showing matched fragments</li>
        <li>Annotated with fragment identifications</li>
        <li>Intensity scaling relative to base peak</li>
        <li>Useful for fragment validation</li>
        </ul>
        
        <h3>Quality Metrics</h3>
        <ul>
        <li><b>Fragments_Score (0-100):</b>
            <ul>
            <li>90-100: Excellent (Grade A)</li>
            <li>75-89: Good (Grade B)</li>
            <li>65-74: Fair (Grade C)</li>
            <li>50-64: Poor (Grade D)</li>
            <li>0-49: Failed (Grade F)</li>
            </ul>
        </li>
        <li><b>Scoring factors:</b>
            <ul>
            <li>Mass accuracy (PPM error)</li>
            <li>Signal intensity</li>
            <li>Retention time agreement</li>
            <li>Signal-to-noise ratio</li>
            <li>Fragment reproducibility</li>
            </ul>
        </li>
        </ul>
        
        <h3>Data Analysis Tips</h3>
        <ul>
        <li>Filter results by FDR_Grade for high-confidence identifications</li>
        <li>Use Area values for quantitative comparisons</li>
        <li>Review EIC plots for integration quality</li>
        <li>Compare fragment patterns between samples</li>
        </ul>
        """)
        
        layout.addWidget(help_text)
        parent_tab_widget.addTab(output_widget, "Output & Results")

    def create_help_troubleshooting_tab(self, parent_tab_widget):
        """Troubleshooting help tab"""
        trouble_widget = QWidget()
        layout = QVBoxLayout(trouble_widget)
        
        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setHtml("""
        <h2>Troubleshooting Guide</h2>
        
        <h3>Common Issues and Solutions</h3>
        
        <h4>No Fragments Found</h4>
        <ul>
        <li><b>Check RT values:</b> Ensure RT in Excel matches actual elution time</li>
        <li><b>Increase RT window:</b> Try larger RT Window parameter</li>
        <li><b>Verify precursor:</b> Confirm glycopeptide actually elutes at specified RT</li>
        </ul>
        
        <h4>Poor Quality Scores</h4>
        <ul>
        <li><b>Mass calibration:</b> Large PPM errors indicate calibration issues</li>
        <li><b>RT reproducibility:</b> Large RT differences indicate chromatography issues</li>
        <li><b>Low intensity:</b> May indicate low abundance or poor ionization</li>
        <li><b>Integration issues:</b> Check EIC plots for peak shape problems</li>
        </ul>
        
        <h4>File Processing Errors</h4>
        <ul>
        <li><b>mzML files:</b> Check file integrity and format</li>
        <li><b>Excel files:</b> Verify required columns are present</li>
        <li><b>Missing data:</b> Check for empty cells in required columns</li>
        </ul>
        
        
        <h3>Performance Tips</h3>
        <ul>
        <li><b>Use RAW files:</b> Faster processing</li>
        <li><b>Optimize RT windows:</b> Smaller windows = faster processing</li>
        <li><b>Use Excel to set variable modifications:</b> Set Fixed modification on the app</li>
        </ul>
        
        <h3>Quality Control</h3>
        <ul>
        <li><b>Review blank runs:</b> Ensure no contamination</li>
        <li><b>Compare replicates:</b> Assess reproducibility</li>
        <li><b>Validate fragments:</b> Manually inspect EIC and MS2 plots</li>
        </ul>
        
        <h3>Getting Help</h3>
        <ul>
        <li>Check analysis log for detailed error messages</li>
        <li>Review parameter tooltips for guidance</li>
        <li>Start with simple examples before complex analyses</li>
        <li>Use Mass Calculator to verify expected masses</li>
        </ul>
        """)
        
        layout.addWidget(help_text)
        parent_tab_widget.addTab(trouble_widget, "Troubleshooting")

    def export_calc_results(self):
        """Export calculation results to Excel"""
        if self.calc_results_df.empty:
            QMessageBox.warning(self, "Error", "No results to export")
            return
        
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Results", "mass_calculations.xlsx", "Excel files (*.xlsx)"
        )
        
        if filename:
            try:
                self.calc_results_df.to_excel(filename, index=False)
                QMessageBox.information(self, "Success", f"Results exported to: {filename}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to export results: {str(e)}")

    def browse_directory(self, line_edit):
        directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if directory:
            line_edit.setText(directory)

    def browse_file(self, line_edit, file_filter):
        """Enhanced file browser that supports multiple file selection"""
        if "Data files" in file_filter:
            # For data files, allow multiple selection
            files, _ = QFileDialog.getOpenFileNames(
                self, 
                "Select Data Files (Multiple Selection Allowed)", 
                "", 
                file_filter
            )
            if files:
                # Join multiple files with semicolon separator
                line_edit.setText(";".join(files))
                self.add_log(f"Selected {len(files)} data files")
        else:
            # For Excel files, single selection only
            file, _ = QFileDialog.getOpenFileName(
                self, 
                "Select File", 
                "", 
                file_filter
            )
            if file:
                line_edit.setText(file)

    def browse_working_folder(self):
        """Enhanced folder browser that auto-populates all data files"""
        folder = QFileDialog.getExistingDirectory(
            self, 
            "Select Working Folder", 
            ""
        )
        
        if folder:
            self.working_folder.setText(folder)
            
            # Auto-populate output directory with the same folder
            self.output_dir.setText(folder)
            self.add_log(f"Auto-populated output directory: {folder}")
            
            # Auto-populate Excel file (first .xlsx or .xls found)
            excel_files = []
            for ext in ['*.xlsx', '*.xls']:
                excel_files.extend(glob.glob(os.path.join(folder, ext)))
            
            if excel_files:
                self.input_excel.setText(excel_files[0])
                self.add_log(f"Auto-populated Excel file: {os.path.basename(excel_files[0])}")
            else:
                self.add_log("No Excel files found in selected folder")
            
            # Auto-populate data files (ALL .raw and .mzML found)
            data_files = []
            for ext in ['*.raw', '*.mzML']:
                data_files.extend(glob.glob(os.path.join(folder, ext)))
            
            if data_files:
                # Sort files for consistent ordering
                data_files.sort()
                self.input_file.setText(";".join(data_files))
                self.add_log(f"Auto-populated {len(data_files)} data files:")
                for i, file in enumerate(data_files, 1):
                    self.add_log(f"  {i}. {os.path.basename(file)}")
            else:
                self.add_log("No data files (.raw or .mzML) found in selected folder")

    def create_run_analysis_tab(self):
        """Run Analysis tab with file inputs, buttons, and log with scroll area"""
        # Create scroll area for run analysis tab
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        run_widget = QWidget()
        layout = QVBoxLayout(run_widget)
        
        # Input files section
        input_group = QGroupBox("Input Files")
        input_layout = QGridLayout(input_group)
        input_layout.setSpacing(5)
        
        # Excel input file
        input_layout.addWidget(QLabel("Input Excel File:"), 0, 0)
        self.input_excel = QLineEdit()
        self.input_excel.setReadOnly(True)  # Make read-only
        self.input_excel.setToolTip("Excel file containing glycan/glycopeptide information\nRequired columns: Glycan, Peptide (for glycopeptides), RT\nSelect using Browse or Working Folder")
        input_layout.addWidget(self.input_excel, 0, 1)
        browse_excel_btn = QPushButton("Browse")
        browse_excel_btn.clicked.connect(lambda: self.browse_file(self.input_excel, "Excel files (*.xlsx *.xls)"))
        input_layout.addWidget(browse_excel_btn, 0, 2)
        
        # Raw/mzML file
        input_layout.addWidget(QLabel("Raw/mzML File:"), 1, 0)
        self.input_file = QLineEdit()
        self.input_file.setReadOnly(True)  # Make read-only
        self.input_file.setToolTip("Mass spectrometry data file(s)\nSupported formats: .raw (Thermo), .mzML\nSelect using Browse or Working Folder")
        input_layout.addWidget(self.input_file, 1, 1)
        browse_file_btn = QPushButton("Browse")
        browse_file_btn.clicked.connect(lambda: self.browse_file(self.input_file, "Data files (*.raw *.mzML)"))
        input_layout.addWidget(browse_file_btn, 1, 2)
        
        # Working folder option
        input_layout.addWidget(QLabel("Working Folder (auto-populate):"), 3, 0)
        self.working_folder = QLineEdit()
        self.working_folder.setReadOnly(True)  # Make read-only
        self.working_folder.setToolTip("Select folder to auto-populate Excel and data files\nWill find first .xlsx and .raw/.mzML files and set as output directory")
        input_layout.addWidget(self.working_folder, 3, 1)
        browse_folder_btn = QPushButton("Browse")
        browse_folder_btn.clicked.connect(self.browse_working_folder)
        input_layout.addWidget(browse_folder_btn, 3, 2)
        
        # Output directory - MOVED HERE under working folder
        input_layout.addWidget(QLabel("Output Directory:"), 2, 0)
        self.output_dir = QLineEdit("glycan_analysis_output")
        self.output_dir.setReadOnly(True)  # Make read-only
        self.output_dir.setToolTip("Directory where all output files will be saved\nSelect using Browse or auto-populated by Working Folder")
        input_layout.addWidget(self.output_dir, 2, 1)
        browse_output_btn = QPushButton("Browse")
        browse_output_btn.clicked.connect(lambda: self.browse_directory(self.output_dir))
        input_layout.addWidget(browse_output_btn, 2, 2)
        
        input_layout.setColumnStretch(1, 1)
        layout.addWidget(input_group)
        
        # Control buttons - SIDE BY SIDE LAYOUT
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)  # Add spacing between buttons
        
        self.start_button = QPushButton("Start Analysis")
        self.start_button.setMinimumHeight(30)  # Make buttons taller
        self.start_button.clicked.connect(self.start_analysis)
        self.start_button.setToolTip("Begin glycan/glycopeptide analysis with current settings")
        button_layout.addWidget(self.start_button)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setMinimumHeight(30)  # Make buttons taller
        self.cancel_button.clicked.connect(self.cancel_analysis)
        self.cancel_button.setEnabled(False)
        self.cancel_button.setToolTip("Cancel running analysis")
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        
        # Analysis log area - MODIFIED for flexible sizing
        log_group = QGroupBox("Analysis Log")
        log_layout = QVBoxLayout(log_group)
        
        self.setup_log_text = QTextEdit()
        # REMOVED fixed height to allow expanding with window
        # self.setup_log_text.setMaximumHeight(250)  # This line removed
        self.setup_log_text.setMinimumHeight(200)  # Set minimum height instead
        self.setup_log_text.setToolTip("Real-time analysis progress and status messages")
        log_layout.addWidget(self.setup_log_text)
        
        # Clear log button
        self.clear_log_btn = QPushButton("Clear Log")
        self.clear_log_btn.clicked.connect(self.clear_setup_log)
        self.clear_log_btn.setToolTip("Clear the analysis log")
        log_layout.addWidget(self.clear_log_btn)
        
        layout.addWidget(log_group)
        # REMOVED layout.addStretch() to allow log to expand
        
        # Set the scroll area widget
        scroll_area.setWidget(run_widget)
        
        self.tab_widget.addTab(scroll_area, "Run Analysis")
            
    def create_analysis_params_internal_tab(self, parent_tab_widget):
        """Analysis Parameters internal tab with side-by-side layout and scroll area"""
        # Create scroll area for analysis parameters tab
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        params_widget = QWidget()
        main_layout = QHBoxLayout(params_widget)
        
        # Left column
        left_column = QVBoxLayout()


        # Glycan Analysis Settings
        glycan_group = QGroupBox("Glycan Analysis Settings")
        glycan_layout = QFormLayout(glycan_group)

        self.use_comment_column = QCheckBox("Use Comment Column for Glycopeptide Parsing")
        self.use_comment_column.setToolTip("Parse glycopeptide strings from Comment column\nOverrides individual Glycan/Peptide columns and modification settings")
        self.use_comment_column.toggled.connect(self.toggle_comment_column_mode)
        glycan_layout.addRow(self.use_comment_column)

        self.glycan_type = QComboBox()
        self.glycan_type.addItems(["N", "O"])
        self.glycan_type.setToolTip("Select glycan type:\n• N-glycan: Asparagine-linked glycans\n• O-glycan: Serine/Threonine-linked glycans")
        glycan_layout.addRow("Glycan Type:", self.glycan_type)
        
        left_column.addWidget(glycan_group)
        
        # PPM Tolerance Settings - NEW SECTION
        ppm_group = QGroupBox("Mass Accuracy Settings")
        ppm_layout = QFormLayout(ppm_group)
        
        self.ms1_ppm_tolerance = QDoubleSpinBox()
        self.ms1_ppm_tolerance.setRange(0.1, 100.0)
        self.ms1_ppm_tolerance.setValue(10.0)
        self.ms1_ppm_tolerance.setSuffix(" ppm")
        self.ms1_ppm_tolerance.setSingleStep(0.5)
        self.ms1_ppm_tolerance.setDecimals(1)
        self.ms1_ppm_tolerance.setToolTip("PPM tolerance for precursor (MS1) matching\nTypical range: 5-15 ppm for high-resolution instruments\nControls how closely measured precursor m/z must match theoretical")
        ppm_layout.addRow("MS1 PPM Tolerance:", self.ms1_ppm_tolerance)
        
        self.ms2_ppm_tolerance = QDoubleSpinBox()
        self.ms2_ppm_tolerance.setRange(1.0, 100.0)
        self.ms2_ppm_tolerance.setValue(20.0)
        self.ms2_ppm_tolerance.setSuffix(" ppm")
        self.ms2_ppm_tolerance.setSingleStep(1.0)
        self.ms2_ppm_tolerance.setDecimals(1)
        self.ms2_ppm_tolerance.setToolTip("PPM tolerance for fragment (MS2) matching\nTypical range: 10-50 ppm depending on instrument\nControls how closely measured fragment m/z must match theoretical")
        ppm_layout.addRow("MS2 PPM Tolerance:", self.ms2_ppm_tolerance)
        
        left_column.addWidget(ppm_group)
        
        # RT Parameters
        rt_group = QGroupBox("Retention Time Parameters")
        rt_layout = QFormLayout(rt_group)
        
        self.rt_window = QDoubleSpinBox()
        self.rt_window.setRange(0.1, 60.0)
        self.rt_window.setValue(5.0)
        self.rt_window.setSuffix(" min")
        self.rt_window.setToolTip("Total RT window for initial fragment searching\nRecommended: 5-10 minutes for LC gradients")
        rt_layout.addRow("RT Window:", self.rt_window)
        
        self.max_rt_window = QDoubleSpinBox()
        self.max_rt_window.setRange(0.1, 10.0)
        self.max_rt_window.setValue(1.5)
        self.max_rt_window.setSuffix(" min")
        self.max_rt_window.setToolTip("Maximum RT window for peak integration\nRecommended: 2-5 minutes depending on peak width\nDisabled when using Excel RT window values")
        rt_layout.addRow("Max RT Window:", self.max_rt_window)
        
        self.max_rt_difference = QDoubleSpinBox()
        self.max_rt_difference.setRange(0.1, 5.0)
        self.max_rt_difference.setValue(1.0)
        self.max_rt_difference.setSuffix(" min")
        self.max_rt_difference.setToolTip("Maximum allowed RT difference for fragment matching\nSmaller values = stricter RT matching")
        rt_layout.addRow("Max RT Difference:", self.max_rt_difference)
        
        self.back_window_ratio = QDoubleSpinBox()
        self.back_window_ratio.setRange(0.1, 0.9)
        self.back_window_ratio.setValue(0.5)
        self.back_window_ratio.setDecimals(2)
        self.back_window_ratio.setSingleStep(0.1)
        self.back_window_ratio.setToolTip("Ratio of RT window to search before the target RT\n0.5 = 50% before, 50% after target RT")
        rt_layout.addRow("Back Window Ratio:", self.back_window_ratio)
        
        left_column.addWidget(rt_group)
        
        # Analysis Quality Settings
        quality_group = QGroupBox("Analysis Quality Settings")
        quality_layout = QFormLayout(quality_group)
        
        self.use_intensity_instead_of_area = QCheckBox("Use Intensity Instead of Area")
        self.use_intensity_instead_of_area.setToolTip("Use peak intensity instead of integrated area for quantification\nUseful for high-resolution data with narrow peaks")
        quality_layout.addRow(self.use_intensity_instead_of_area)
        
        self.fdr_grade_cutoff = QComboBox()
        self.fdr_grade_cutoff.addItems(["None", "A", "B", "C", "D"])
        self.fdr_grade_cutoff.setCurrentText("None")
        self.fdr_grade_cutoff.setToolTip("Minimum FDR grade for including fragments:\n• A: Excellent (90-100 score)\n• B: Good (75-89 score)\n• C: Fair (65-74 score)\n• D: Poor (50-64 score)\n• None: Include all fragments")
        quality_layout.addRow("FDR Grade Cutoff:", self.fdr_grade_cutoff)
        
        left_column.addWidget(quality_group)
        
        # Right column
        right_column = QVBoxLayout()
        
        # Excel Options Group
        excel_group = QGroupBox("Excel Data Options")
        excel_layout = QVBoxLayout(excel_group)
        
        self.use_excel_precursor = QCheckBox("Use Excel Precursor m/z Values")
        self.use_excel_precursor.setChecked(True)
        self.use_excel_precursor.setToolTip("Use precursor m/z values from Excel Precursor_mz column\nIf disabled, calculates m/z from masses")
        excel_layout.addWidget(self.use_excel_precursor)
        
        self.use_excel_rt_window = QCheckBox("Use Excel RT Window Values")
        self.use_excel_rt_window.setChecked(True)
        self.use_excel_rt_window.setToolTip("Use custom scan window from Excel RT_window column\nIf disabled, uses Max RT Window parameter\nWhen enabled, Max RT Window is disabled")
        self.use_excel_rt_window.toggled.connect(self.toggle_max_rt_window)  
        excel_layout.addWidget(self.use_excel_rt_window)
        
        right_column.addWidget(excel_group)
        
        # Fragment Generation Options
        frag_group = QGroupBox("Fragment Generation Options")
        frag_layout = QVBoxLayout(frag_group)
        
        # Organize checkboxes in a grid layout for better space usage
        checkbox_grid = QGridLayout()
        
        # Glycan fragment options
        self.generate_glycan_by_ions = QCheckBox("Generate Glycan BY Ions")
        self.generate_glycan_by_ions.setChecked(True)
        self.generate_glycan_by_ions.setToolTip("Generate standard glycan B and Y ions\nRecommended: Always enabled for glycan analysis")
        checkbox_grid.addWidget(self.generate_glycan_by_ions, 0, 0)
        
        self.generate_cz_glycan = QCheckBox("Generate C/Z Glycan Fragments")
        self.generate_cz_glycan.setToolTip("Generate C and Z type glycan fragments\nUseful for advanced fragmentation studies")
        checkbox_grid.addWidget(self.generate_cz_glycan, 2, 0)
        
        # Peptide fragment options
        self.generate_peptide_by_ions = QCheckBox("Generate Peptide BY Ions")
        self.generate_peptide_by_ions.setToolTip("Generate peptide b and y ions\nEnable for glycopeptide analysis")
        checkbox_grid.addWidget(self.generate_peptide_by_ions, 1, 0)
        
        self.generate_cz_peptide = QCheckBox("Generate C/Z Peptide Fragments")
        self.generate_cz_peptide.setToolTip("Generate peptide c and z ions\nUseful for ETD/ECD fragmentation")
        checkbox_grid.addWidget(self.generate_cz_peptide, 3, 0)
        
        frag_layout.addLayout(checkbox_grid)
        right_column.addWidget(frag_group)
        
        # Output Settings
        output_group = QGroupBox("Output Settings")
        output_layout = QVBoxLayout(output_group)
        
        # Display Time Extension 
        display_time_layout = QHBoxLayout()
        display_time_layout.addWidget(QLabel("Display Time Extension:"))
        self.display_time_extension = QDoubleSpinBox()
        self.display_time_extension.setRange(0.0, 10.0)
        self.display_time_extension.setValue(5.0)
        self.display_time_extension.setSuffix(" min")
        self.display_time_extension.setToolTip("Extra time to display on each side of the chromatogram plots\nExpands the time window for better visualization")
        display_time_layout.addWidget(self.display_time_extension)
        display_time_layout.addStretch()
        output_layout.addLayout(display_time_layout)
        
        # Max fragments displayed
        max_frag_layout = QHBoxLayout()
        max_frag_layout.addWidget(QLabel("Max Fragments Displayed:"))
        self.max_fragments_displayed = QSpinBox()
        self.max_fragments_displayed.setRange(5, 100)
        self.max_fragments_displayed.setValue(30)
        self.max_fragments_displayed.setToolTip("Maximum number of fragments to display in plots and legends\nReduces clutter in visualizations")
        max_frag_layout.addWidget(self.max_fragments_displayed)
        max_frag_layout.addStretch()
        output_layout.addLayout(max_frag_layout)
        
        # Output options in grid layout
        output_options_grid = QGridLayout()
        
        self.save_excel = QCheckBox("Save additional Fragmentation details (Optional)")
        self.save_excel.setChecked(False)
        self.save_excel.setToolTip("Save additional Fragmentation details (Optional)\nContains all theoretical fragments, matched fragments, and glycan/peptide masses\nUseful for information and validation\nAll glycopeptide fragments and their quantification are always saved in the main output Excel file")
        output_options_grid.addWidget(self.save_excel, 2, 0)
        
        self.generate_eic_plots = QCheckBox("Generate EIC Plots")
        self.generate_eic_plots.setChecked(True)
        self.generate_eic_plots.setToolTip("Generate Extracted Ion Chromatograms\nUseful for visualizing fragment elution profiles")
        output_options_grid.addWidget(self.generate_eic_plots, 0, 0)
        
        self.generate_ms2_plots = QCheckBox("Generate MS2 Plots")
        self.generate_ms2_plots.setToolTip("Generate MS2 spectrum plots\nUseful for fragment identification validation")
        output_options_grid.addWidget(self.generate_ms2_plots, 1, 0)
        
        output_layout.addLayout(output_options_grid)
        right_column.addWidget(output_group)
        
        # Add stretch to balance columns
        left_column.addStretch()
        right_column.addStretch()
        
        # Add columns to main layout
        main_layout.addLayout(left_column)
        main_layout.addLayout(right_column)
        
        # Set the scroll area widget
        scroll_area.setWidget(params_widget)
        
        parent_tab_widget.addTab(scroll_area, "Analysis Parameters")

    def get_parameters(self):
        """Enhanced parameter collection with multiple file support"""
        # Get selected modifications for multiple selection support
        selected_fixed_mods = [item.text() for item in self.additional_fixed_mods.selectedItems()]
        selected_variable_mods = [item.text() for item in self.variable_mods.selectedItems()]
        
        # Build the complete fixed_mods list including CAM
        fixed_mods = []
        if self.use_cam.isChecked():
            fixed_mods.append("CAM:C")
        fixed_mods.extend(selected_fixed_mods)
        
        # Parse input files (handle multiple files separated by semicolon)
        input_files = []
        input_file_text = self.input_file.text().strip()
        
        if input_file_text:
            # Split by semicolon and clean up paths
            file_paths = [path.strip() for path in input_file_text.split(';') if path.strip()]
            
            # Validate each file exists
            for file_path in file_paths:
                if os.path.exists(file_path):
                    input_files.append(file_path)
                else:
                    self.add_log(f"Warning: File not found: {file_path}")
        
        return {
            'excel_input_file': self.input_excel.text(),
            'input_files': input_files,
            'output_dir': self.output_dir.text() or 'glycan_analysis_output',
            'glycan_type': self.glycan_type.currentText(),
            'rt_window': self.rt_window.value(),
            'max_rt_window': self.max_rt_window.value(),
            'max_rt_difference': self.max_rt_difference.value(),
            'back_window_ratio': self.back_window_ratio.value(),
            # NEW: Add PPM tolerance parameters
            'ms1_ppm_tolerance': self.ms1_ppm_tolerance.value(),
            'ms2_ppm_tolerance': self.ms2_ppm_tolerance.value(),
            'use_cam': self.use_cam.isChecked(),
            'fixed_mods': fixed_mods,
            'variable_mods': selected_variable_mods,
            'custom_mods': True,
            'use_excel_pepmass': self.use_excel_pepmass.isChecked(),
            'use_excel_peptide_mod': self.use_excel_peptide_mod.isChecked(),
            'generate_glycan_by_ions': self.generate_glycan_by_ions.isChecked(),
            'generate_peptide_by_ions': self.generate_peptide_by_ions.isChecked(),
            'generate_cz_glycan_fragment': self.generate_cz_glycan.isChecked(),
            'generate_cz_peptide_fragment': self.generate_cz_peptide.isChecked(),
            'save_excel': self.save_excel.isChecked(),
            'generate_eic_plots': self.generate_eic_plots.isChecked(),
            'generate_ms2_plots': self.generate_ms2_plots.isChecked(),
            'use_excel_precursor': self.use_excel_precursor.isChecked(),
            'use_excel_rt_window': self.use_excel_rt_window.isChecked(),
            'use_intensity_instead_of_area': self.use_intensity_instead_of_area.isChecked(),
            'fdr_grade_cutoff': self.fdr_grade_cutoff.currentText() if self.fdr_grade_cutoff.currentText() != "None" else None,
            'display_time_extension': self.display_time_extension.value(),
            'max_fragments_displayed': self.max_fragments_displayed.value(),
            'use_comment_column': self.use_comment_column.isChecked(),
            'enable_fragment_removal': self.enable_fragment_removal.isChecked()
        }
  
    def toggle_max_rt_window(self, checked):
        """Disable Max RT Window when Use Excel RT Window is checked"""
        self.max_rt_window.setEnabled(not checked)
        
        # Update tooltip to reflect current state
        if checked:
            self.max_rt_window.setToolTip("Maximum RT window for peak integration\nDISABLED: Using Excel RT_window column values instead")
        else:
            self.max_rt_window.setToolTip("Maximum RT window for peak integration\nRecommended: 2-5 minutes depending on peak width")
        
    def toggle_variable_mods(self, checked):
        """Disable variable modifications when using Excel modifications"""
        self.variable_mods.setEnabled(not checked)

    def toggle_calc_variable_mods(self, checked):
        """Disable variable modifications in calculator when using Excel modifications"""
        self.calc_variable_mods.setEnabled(not checked)

    def get_selected_fixed_mods(self):
        """Helper method to get selected fixed modifications"""
        fixed_mods = []
        if self.calc_use_cam.isChecked():
            fixed_mods.append("CAM:C")
        
        # Add other selected fixed modifications
        for item in self.calc_additional_fixed_mods.selectedItems():
            fixed_mods.append(item.text())
        
        return fixed_mods

    def get_selected_variable_mods(self):
        """Helper method to get selected variable modifications"""
        variable_mods = []
        if not self.calc_use_excel_peptide_mod.isChecked():
            for item in self.calc_variable_mods.selectedItems():
                variable_mods.append(item.text())
        
        return variable_mods
          
    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def update_status(self, status):
        self.status_label.setText(status)

    def add_log(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        
        # Only add to setup tab log (remove main log functionality)
        if hasattr(self, 'setup_log_text'):
            self.setup_log_text.append(formatted_message)
            # Auto-scroll to bottom
            setup_scrollbar = self.setup_log_text.verticalScrollBar()
            setup_scrollbar.setValue(setup_scrollbar.maximum())

    def clear_setup_log(self):
        """Clear only the setup tab log"""
        if hasattr(self, 'setup_log_text'):
            self.setup_log_text.clear()
     
    def start_analysis(self):
        """Enhanced start analysis with proper multiple file support"""
        # Validate inputs
        if not os.path.exists(self.input_excel.text()):
            QMessageBox.warning(self, "Error", "Please select a valid Excel input file")
            return
        
        # Parse input files
        input_file_text = self.input_file.text().strip()
        input_files = []
        
        if input_file_text:
            # Handle multiple files separated by semicolon
            file_paths = [path.strip() for path in input_file_text.split(';') if path.strip()]
            
            # Validate each file
            valid_files = []
            for file_path in file_paths:
                if os.path.exists(file_path):
                    valid_files.append(file_path)
                else:
                    self.add_log(f"Warning: File not found: {file_path}")
            
            input_files = valid_files
        
        # Check for data files
        has_specified_files = len(input_files) > 0
        
        if not has_specified_files:
            # Check for files in current directory
            mzml_files = glob.glob("*.mzML")
            raw_files = glob.glob("*.raw")
            
            if not mzml_files and not raw_files:
                QMessageBox.warning(self, "Error", 
                                "No data files found. Please either:\n"
                                "1. Select specific RAW or mzML files, or\n"
                                "2. Use 'Browse Folder' to auto-populate files, or\n"
                                "3. Place data files in the current directory")
                return
            
            # Ask user if they want to process all files in directory
            file_count = len(mzml_files) + len(raw_files)
            reply = QMessageBox.question(self, "Multiple Files Found", 
                                    f"Found {file_count} data files in current directory.\n"
                                    "Do you want to process all of them?",
                                    QMessageBox.Yes | QMessageBox.No)
            
            if reply == QMessageBox.No:
                return
            
            # Use files from current directory
            input_files = mzml_files + raw_files
        
        # Log file processing information
        if len(input_files) > 1:
            self.add_log(f"Starting analysis of {len(input_files)} files:")
            for i, file_path in enumerate(input_files, 1):
                self.add_log(f"  {i}. {os.path.basename(file_path)}")
        elif len(input_files) == 1:
            self.add_log(f"Starting analysis of single file: {os.path.basename(input_files[0])}")
        else:
            self.add_log("Starting analysis with files from current directory")
        
        # Get parameters and start analysis
        params = self.get_parameters()
        params['input_files'] = input_files  # Pass the list of files
        
        self.analysis_worker = AnalysisWorker(params)
        self.analysis_worker.progress_update.connect(self.update_progress)
        self.analysis_worker.status_update.connect(self.update_status)
        self.analysis_worker.log_update.connect(self.add_log)
        self.analysis_worker.finished_signal.connect(self.analysis_finished)
        
        # Update UI for starting analysis
        self.start_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # Set initial status
        self.status_label.setText("Starting analysis...")
        
        # Clear log before starting
        self.clear_setup_log()
        
        # Start timer - RESET FIRST
        self.timer_label.setText("00:00")
        self.start_time = datetime.now()
        self.timer.start(1000)  # Update every second
        
        # Start analysis
        self.analysis_worker.start()
        self.add_log("Analysis started...")

    def cancel_analysis(self):
        if self.analysis_worker:
            self.analysis_worker.cancel()
            self.add_log("Analysis cancelled by user")
            
            # Reset UI state when cancelled
            self.timer.stop()
            self.start_time = None
            self.start_button.setEnabled(True)
            self.cancel_button.setEnabled(False)
            self.progress_bar.setVisible(False)
            self.status_label.setText("Analysis cancelled - Ready to start new analysis")
            self.timer_label.setText("00:00")

    def update_timer(self):
        if self.start_time:
            elapsed = datetime.now() - self.start_time
            elapsed_str = str(elapsed).split('.')[0]  # Remove microseconds
            self.timer_label.setText(f"{elapsed_str}")
        else:
            # If start_time is None, stop the timer
            self.timer.stop()
            self.timer_label.setText("00:00") 

    def apply_theme(self):
        simple_style = """
        QMainWindow {
            background-color: #FFFFFF;
            color: #000000;
        }
        QTabWidget::pane {
            border: 1px solid #CCCCCC;
            background-color: #FFFFFF;
        }
        QTabBar::tab {
            background-color: #F0F0F0;
            color: #000000;
            padding: 8px 16px;
            margin-right: 2px;
            border: 1px solid #CCCCCC;
            border-radius: 4px;
        }
        QTabBar::tab:selected {
            background-color: #E0E0E0;
            border-bottom: 2px solid #CCCCCC;
        }
        QTabBar::tab:hover {
            background-color: #E8E8E8;
        }
        QGroupBox {
            font-weight: bold;
            border: 2px solid #CCCCCC;
            border-radius: 5px;
            margin-top: 10px;
            padding-top: 10px;
            background-color: #FFFFFF;
            color: #000000;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
            color: #000000;
        }
        /* Default button style - BLUE */
        QPushButton {
            background-color: #3498DB;
            color: white;
            border: 1px solid #2980B9;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #5DADE2;
        }
        QPushButton:pressed {
            background-color: #2980B9;
        }
        QPushButton:disabled {
            background-color: #CCCCCC;
            color: #666666;
            border: 1px solid #AAAAAA;
        }
        /* START BUTTON - GREEN */
        QPushButton[text="Start Analysis"] {
            background-color: #27AE60;
            border: 1px solid #229954;
        }
        QPushButton[text="Start Analysis"]:hover {
            background-color: #2ECC71;
        }
        QPushButton[text="Start Analysis"]:pressed {
            background-color: #229954;
        }
        /* CANCEL BUTTON - RED */
        QPushButton[text="Cancel"] {
            background-color: #E74C3C;
            border: 1px solid #C0392B;
        }
        QPushButton[text="Cancel"]:hover {
            background-color: #EC7063;
        }
        QPushButton[text="Cancel"]:pressed {
            background-color: #C0392B;
        }
        QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox, QListWidget {
            background-color: #FFFFFF;
            border: 1px solid #CCCCCC;
            color: #000000;
            padding: 4px;
            border-radius: 2px;
            selection-background-color: #2980b9;
        }
        QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
            border: 2px solid #3498DB;
        }
        QListWidget::item:selected {
            background-color: #E6F2FF;
            color: #000000;
        }
        QProgressBar {
            border: 1px solid #CCCCCC;
            border-radius: 2px;
            text-align: center;
            background-color: #FFFFFF;
            color: #000000;
        }
        QProgressBar::chunk {
            background-color: #3498DB;
            border-radius: 2px;
        }
        QLabel {
            color: #000000;
        }
        QCheckBox {
            color: #000000;
        }
        QCheckBox::indicator:checked {
            background-color: #3498DB;
            border: 1px solid #2980B9;
        }
        QCheckBox::indicator:unchecked {
            background-color: #FFFFFF;
            border: 1px solid #CCCCCC;
        }
        QScrollBar:vertical {
            background-color: #F0F0F0;
            width: 15px;
            border: 1px solid #CCCCCC;
        }
        QScrollBar::handle:vertical {
            background-color: #CCCCCC;
            border-radius: 3px;
            min-height: 20px;
        }
        QScrollBar::handle:vertical:hover {
            background-color: #AAAAAA;
        }
        """
        self.setStyleSheet(simple_style)
##
    def create_output_tab(self):
        """Enhanced Output tab with multi-file navigation and fragment management - FIXED VERSION"""
        # Create scroll area for output tab
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        output_widget = QWidget()
        main_layout = QVBoxLayout(output_widget)
        
        # Create main splitter for better space utilization
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.setHandleWidth(8)
        
        # =============================================================================
        # LEFT PANEL - Fragment Management
        # =============================================================================
        left_panel = QWidget()
        left_panel.setMinimumWidth(600)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(5, 5, 5, 5)
        
        # FILE NAVIGATION SECTION
        file_nav_group = QGroupBox("File Navigation")
        file_nav_layout = QVBoxLayout(file_nav_group)
        
        # Navigation controls
        nav_controls_layout = QHBoxLayout()
        
        self.prev_file_btn = QPushButton("◄ Previous")
        self.prev_file_btn.clicked.connect(self.navigate_to_previous_file)
        self.prev_file_btn.setEnabled(False)
        self.prev_file_btn.setMinimumHeight(30)
        nav_controls_layout.addWidget(self.prev_file_btn)
        
        self.file_info_label = QLabel("No files loaded")
        self.file_info_label.setAlignment(Qt.AlignCenter)
        self.file_info_label.setStyleSheet("""
            font-size: 12px; 
            font-weight: bold; 
            color: #2c3e50; 
            padding: 5px; 
            background-color: #ecf0f1; 
            border-radius: 4px;
        """)
        nav_controls_layout.addWidget(self.file_info_label, 1)
        
        self.next_file_btn = QPushButton("Next ►")
        self.next_file_btn.clicked.connect(self.navigate_to_next_file)
        self.next_file_btn.setEnabled(False)
        self.next_file_btn.setMinimumHeight(30)
        nav_controls_layout.addWidget(self.next_file_btn)
        
        file_nav_layout.addLayout(nav_controls_layout)
        
        # File selection dropdown
        dropdown_layout = QHBoxLayout()
        dropdown_layout.addWidget(QLabel("Select File:"))
        
        self.file_selector = QComboBox()
        self.file_selector.currentTextChanged.connect(self.on_file_selection_changed)
        self.file_selector.setMinimumHeight(25)
        dropdown_layout.addWidget(self.file_selector, 1)
        
        file_nav_layout.addLayout(dropdown_layout)
        
        # Initially hide file navigation
        file_nav_group.setVisible(False)
        left_layout.addWidget(file_nav_group)
        self.file_nav_group = file_nav_group

        # Fragment Removal section
        removal_group = QGroupBox("Fragment Curation Interface")
        removal_layout = QVBoxLayout(removal_group)
        
        # Fragment removal scope selection
        scope_layout = QHBoxLayout()
        scope_layout.addWidget(QLabel("Removal Scope:"))
        
        self.scope_current_file = QPushButton("Current File Only")
        self.scope_current_file.setCheckable(True)
        self.scope_current_file.setChecked(True)
        self.scope_current_file.clicked.connect(lambda: self.set_removal_scope(False))
        self.scope_current_file.setMinimumHeight(25)
        scope_layout.addWidget(self.scope_current_file)
        
        self.scope_all_files = QPushButton("All Files (Global)")
        self.scope_all_files.setCheckable(True)
        self.scope_all_files.clicked.connect(lambda: self.set_removal_scope(True))
        self.scope_all_files.setMinimumHeight(25)
        scope_layout.addWidget(self.scope_all_files)
        
        scope_layout.addStretch()
        removal_layout.addLayout(scope_layout)

        # Add reproducibility filter buttons
        repro_filter_layout = self.setup_reproducibility_filter_buttons()
        removal_layout.addLayout(repro_filter_layout)

        # Enable fragment removal option
        self.enable_fragment_removal = QCheckBox("Enable Interactive Fragment Removal")
        self.enable_fragment_removal.setToolTip("Enable interactive removal of poor-quality fragments after analysis\nAllows manual curation of fragment matches before final output")
        self.enable_fragment_removal.setStyleSheet("font-size: 12px; font-weight: bold;")
        removal_layout.addWidget(self.enable_fragment_removal)
        
        # Enhanced fragment tree widget with reproducibility
        self.fragment_tree = QTreeWidget()
        self.fragment_tree.setHeaderLabels([
            'Glycopeptides', 
            'Count', 
            'Precursor m/z', 
            'Fragment Type', 
            'Theoretical m/z', 
            'Grade', 
            'Status',
            'Files'
        ])

        # Enable sorting
        self.fragment_tree.setSortingEnabled(True)
        self.fragment_tree.sortByColumn(0, Qt.AscendingOrder)

        # Set column widths
        self.fragment_tree.setColumnWidth(0, 200)
        self.fragment_tree.setColumnWidth(1, 60)
        self.fragment_tree.setColumnWidth(2, 100)
        self.fragment_tree.setColumnWidth(3, 100)
        self.fragment_tree.setColumnWidth(4, 110)
        self.fragment_tree.setColumnWidth(5, 60)
        self.fragment_tree.setColumnWidth(6, 80)
        self.fragment_tree.setColumnWidth(7, 120)
        self.fragment_tree.setSelectionMode(QAbstractItemView.MultiSelection)
        self.fragment_tree.itemChanged.connect(self.on_fragment_item_changed)
        self.fragment_tree.itemClicked.connect(self.on_fragment_tree_click)
        self.fragment_tree.setMinimumHeight(300)
        self.fragment_tree.setMaximumHeight(500)
        
        # Enhanced tree styling
        self.fragment_tree.setStyleSheet("""
            QTreeWidget {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 11px;
                border: 2px solid #bdc3c7;
                border-radius: 6px;
                background-color: #ffffff;
                alternate-background-color: #f8f9fa;
            }
            QTreeWidget::item {
                height: 24px;
                padding: 2px;
                color: #000000;
            }
            QTreeWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
            QTreeWidget::item:hover {
                background-color: #ecf0f1;
                color: #000000;
            }
            QTreeWidget::item:selected:hover {
                background-color: #2980b9;
                color: white;
            }
            QHeaderView::section {
                background-color: #34495e;
                color: white;
                font-weight: bold;
                padding: 6px;
                border: none;
            }
        """)
        self.fragment_tree.setAlternatingRowColors(True)
        removal_layout.addWidget(self.fragment_tree)
        
        # Add sorting instructions
        sorting_label = QLabel("💡 Tip: Click column headers to sort. Use 'Files (Reproducibility)' column to identify poorly reproducible fragments.")
        sorting_label.setStyleSheet("color: blue; font-style: italic; margin: 5px; font-size: 10px;")
        removal_layout.addWidget(sorting_label)

        # Fragment removal buttons - FIXED DUPLICATES
        removal_buttons_layout = QHBoxLayout()
        removal_buttons_layout.setSpacing(10)
        
        self.auto_remove_repro_btn = QPushButton("Remove Poor Rep. Frags.")
        self.auto_remove_repro_btn.setToolTip("Removes fragments with poor reproducibility across files")
        self.auto_remove_repro_btn.clicked.connect(self.auto_remove_poor_reproducibility)
        self.auto_remove_repro_btn.setEnabled(False)
        removal_buttons_layout.addWidget(self.auto_remove_repro_btn)

        self.show_repro_report_btn = QPushButton("Reproducibility Report")
        self.show_repro_report_btn.setToolTip("Show detailed fragment reproducibility statistics")
        self.show_repro_report_btn.clicked.connect(self.show_reproducibility_report)
        self.show_repro_report_btn.setEnabled(False)
        removal_buttons_layout.addWidget(self.show_repro_report_btn)
        
        self.restore_all_btn = QPushButton("Restore All")
        self.restore_all_btn.clicked.connect(self.restore_all_fragments)
        self.restore_all_btn.setEnabled(False)
        self.restore_all_btn.setMinimumHeight(35)
        removal_buttons_layout.addWidget(self.restore_all_btn)  # REMOVED DUPLICATE
        
        self.apply_removals_btn = QPushButton("Apply Removals")
        self.apply_removals_btn.clicked.connect(self.apply_fragment_removals)
        self.apply_removals_btn.setEnabled(False)
        self.apply_removals_btn.setMinimumHeight(35)
        removal_buttons_layout.addWidget(self.apply_removals_btn)
        
        removal_layout.addLayout(removal_buttons_layout)
        
        # Status labels
        self.removal_status_label = QLabel("Fragment removal not available - run analysis first")
        self.removal_status_label.setStyleSheet("""
            font-size: 11px; 
            color: #7f8c8d; 
            padding: 4px; 
            background-color: #f8f9fa; 
            border-radius: 3px;
        """)
        removal_layout.addWidget(self.removal_status_label)
        
        self.removal_stats_label = QLabel("")
        self.removal_stats_label.setStyleSheet("""
            font-size: 11px; 
            color: #2c3e50; 
            font-weight: bold; 
            padding: 4px; 
            background-color: #e8f4fd; 
            border-radius: 3px;
        """)
        removal_layout.addWidget(self.removal_stats_label)
        
        left_layout.addWidget(removal_group)
        
        # =============================================================================
        # RIGHT PANEL - Plot Viewer
        # =============================================================================
        right_panel = QWidget()
        right_panel.setMinimumWidth(600)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(5, 5, 5, 5)

        # Plot Viewer section
        viewer_group = QGroupBox("Plot Viewer - Fragment Quality Assessment")
        viewer_layout = QVBoxLayout(viewer_group)

        # Viewer mode selection
        viewer_mode_layout = QHBoxLayout()
        self.viewer_mode_eic = QPushButton("EIC View")
        self.viewer_mode_eic.setCheckable(True)
        self.viewer_mode_eic.setChecked(True)
        self.viewer_mode_eic.clicked.connect(lambda: self.switch_viewer_mode('eic'))
        self.viewer_mode_eic.setMinimumHeight(40)
        viewer_mode_layout.addWidget(self.viewer_mode_eic)

        self.viewer_mode_ms2 = QPushButton("MS2 View")
        self.viewer_mode_ms2.setCheckable(True)
        self.viewer_mode_ms2.clicked.connect(lambda: self.switch_viewer_mode('ms2'))
        self.viewer_mode_ms2.setMinimumHeight(40)
        viewer_mode_layout.addWidget(self.viewer_mode_ms2)

        viewer_mode_layout.addStretch()
        viewer_layout.addLayout(viewer_mode_layout)

        # Plot info display with word wrapping
        self.plot_info_label = QLabel("Click on a glycopeptide in the fragment tree to view plots")
        self.plot_info_label.setStyleSheet("""
            font-size: 12px; 
            font-weight: bold; 
            color: #34495e; 
            padding: 8px; 
            background-color: #ecf0f1; 
            border-radius: 4px;
            text-align: center;
        """)
        self.plot_info_label.setAlignment(Qt.AlignCenter)
        self.plot_info_label.setWordWrap(True)
        self.plot_info_label.setMaximumHeight(60)
        self.plot_info_label.setMinimumHeight(40)
        viewer_layout.addWidget(self.plot_info_label)

        # Plot area
        self.plot_area = QLabel()
        self.plot_area.setMinimumHeight(400)
        self.plot_area.setStyleSheet("""
            QLabel {
                border: 2px solid #bdc3c7;
                border-radius: 6px;
                background-color: #ffffff;
                text-align: center;
                font-size: 14px;
                color: #7f8c8d;
            }
        """)
        self.plot_area.setText("Plot will appear here")
        self.plot_area.setAlignment(Qt.AlignCenter)
        viewer_layout.addWidget(self.plot_area)

        # ADD EIC PARAMETER CONTROLS HERE - AFTER PLOT AREA BUT BEFORE CONTROLS
        eic_params_group = self.create_eic_parameter_controls()
        viewer_layout.addWidget(eic_params_group)
        
        # Plot controls with export functionality
        plot_controls_layout = QHBoxLayout()
        plot_controls_layout.setSpacing(10)

        self.refresh_plot_btn = QPushButton("Refresh Plot")
        self.refresh_plot_btn.clicked.connect(self.refresh_current_plot)
        self.refresh_plot_btn.setEnabled(False)
        self.refresh_plot_btn.setMinimumHeight(40)
        plot_controls_layout.addWidget(self.refresh_plot_btn)

        self.save_plot_btn = QPushButton("Save Plot")
        self.save_plot_btn.clicked.connect(self.save_current_plot)
        self.save_plot_btn.setEnabled(False)
        self.save_plot_btn.setMinimumHeight(40)
        plot_controls_layout.addWidget(self.save_plot_btn)

        # Export button
        self.export_results_btn = QPushButton("Export Results with Summary")
        self.export_results_btn.clicked.connect(self.export_current_results)
        self.export_results_btn.setEnabled(False)
        self.export_results_btn.setMinimumHeight(40)
        self.export_results_btn.setToolTip("Export current results with automatic PRM summary generation")
        self.export_results_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                font-weight: bold;
                border: none;
                border-radius: 4px;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        plot_controls_layout.addWidget(self.export_results_btn)

        plot_controls_layout.addStretch()

        # Fragment quality indicator
        self.fragment_quality_label = QLabel("")
        self.fragment_quality_label.setStyleSheet("""
            font-size: 11px; 
            font-weight: bold; 
            padding: 4px 8px; 
            border-radius: 3px;
        """)
        plot_controls_layout.addWidget(self.fragment_quality_label)

        viewer_layout.addLayout(plot_controls_layout)

        # Visual separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("color: #bdc3c7; margin: 5px 0px;")
        viewer_layout.addWidget(separator)

        # Export status label - ONLY ONE DECLARATION
        self.export_status_label = QLabel("No results available for export")
        self.export_status_label.setStyleSheet("""
            font-size: 11px; 
            color: #7f8c8d;
                                            padding: 4px; 
            background-color: #f8f9fa; 
            border-radius: 3px;
            text-align: center;
        """)
        self.export_status_label.setAlignment(Qt.AlignCenter)
        viewer_layout.addWidget(self.export_status_label)

        # CRITICAL: Add the viewer_group to the right_layout
        right_layout.addWidget(viewer_group)
        
        # =============================================================================
        # Finalize Layout
        # =============================================================================
        
        # Add panels to splitter
        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(right_panel)
        main_splitter.setSizes([400, 600])
        
        # Add splitter to main layout
        main_layout.addWidget(main_splitter)
        # Set the scroll area widget
        scroll_area.setWidget(output_widget)
        
        # Add the scroll area to the tab
        self.tab_widget.addTab(scroll_area, "Output")
        
        # Initialize storage for analysis results and viewer state
        self.current_matched_fragments = pd.DataFrame()
        self.current_cached_data = {}
        self.current_analysis_params = {}
        self.fragment_interface_visible = True
        self.current_figure = None
        self.selected_glycopeptide = None
        self.current_viewer_mode = 'eic'
        
        # Initialize multi-file state
        self.current_file_index = 0
        self.available_files = []
        
    def safe_enable_button(self, button_name):
        """Safely enable a button if it exists and is valid"""
        try:
            if hasattr(self, button_name):
                button = getattr(self, button_name)
                if button and hasattr(button, 'setEnabled'):
                    button.setEnabled(True)
                    return True
        except RuntimeError:
            # Button was deleted
            pass
        return False

        # Use it in analysis_finished:
        buttons_to_enable = [
            'auto_remove_repro_btn',
            'restore_all_btn', 
            'apply_removals_btn',
            'export_results_btn',
            'show_repro_report_btn'
        ]

        for button_name in buttons_to_enable:
            if self.safe_enable_button(button_name):
                print(f"DEBUG: Enabled {button_name}")
            else:
                print(f"DEBUG: Could not enable {button_name}")
                 
    def navigate_to_previous_file(self):
        """Navigate to the previous file - FIXED WITH AUTO-SAVE"""
        if self.current_file_index > 0:
            # Save current removal state before navigating
            self._save_current_removal_state()
            
            self.current_file_index -= 1
            self.load_file_data(self.available_files[self.current_file_index])
            self.update_file_navigation_state()

    def navigate_to_next_file(self):
        """Navigate to the next file - FIXED WITH AUTO-SAVE"""
        if self.current_file_index < len(self.available_files) - 1:
            # Save current removal state before navigating
            self._save_current_removal_state()
            
            self.current_file_index += 1
            self.load_file_data(self.available_files[self.current_file_index])
            self.update_file_navigation_state()

    def on_file_selection_changed(self, file_name):
        """Handle file selection change from dropdown - FIXED WITH AUTO-SAVE"""
        if file_name and file_name in self.available_files:
            # Save current removal state before changing
            self._save_current_removal_state()
            
            self.current_file_index = self.available_files.index(file_name)
            self.load_file_data(file_name)
            self.update_file_navigation_state()

    def apply_fragment_removals(self):
        """Apply currently selected fragment removals - FIXED VERSION"""
        try:
            # Save current removal state first
            self._save_current_removal_state()
            
            # Check if there are any removals to apply
            if not hasattr(self, 'fragment_removal_states') or not self.fragment_removal_states:
                QMessageBox.information(self, "No Removals", "No fragments are marked for removal.")
                return
            
            # Confirm with user
            if self.global_removal_scope:
                scope_text = "GLOBALLY across ALL files"
            else:
                scope_text = f"in the CURRENT file ({self.current_file_key})"
                
                if self.current_file_key not in self.fragment_removal_states:
                    QMessageBox.warning(self, "No Removals", 
                                        f"No fragments are marked for removal in the current file ({self.current_file_key}).")
                    return
            
            # Confirm removal
            reply = QMessageBox.question(self, "Confirm Removal", 
                                    f"Apply fragment removals {scope_text}?\n\n"
                                    "This will permanently remove the selected fragments from analysis.",
                                    QMessageBox.Yes | QMessageBox.No,
                                    QMessageBox.No)
            
            if reply != QMessageBox.Yes:
                return
            
            # Backup original data if not already done
            if not hasattr(self, 'original_analysis_results') or not self.original_analysis_results:
                self._backup_original_data()
            
            # Apply removals based on scope
            if self.global_removal_scope:
                self._apply_removals_globally()
            else:
                self._apply_removals_to_current_file()
            
            # CRITICAL FIX: Refresh all displays with immediate plot update
            self._refresh_all_displays_after_change(is_restoration=False)
            
            # Update status
            remaining_count = len(self.current_matched_fragments)
            self.removal_status_label.setText(f"Applied removals {scope_text}: {remaining_count} fragments remaining")
            
            # Clear removal states after successful application
            if self.global_removal_scope:
                self.fragment_removal_states.clear()
            else:
                if self.current_file_key in self.fragment_removal_states:
                    del self.fragment_removal_states[self.current_file_key]
            
            self.add_log(f"Fragment removals applied successfully {scope_text}")
            
        except Exception as e:
            error_msg = f"Error applying removals: {str(e)}"
            self.add_log(error_msg)
            QMessageBox.critical(self, "Removal Error", error_msg)
            import traceback
            traceback.print_exc()
            
    def _refresh_displays_after_removal(self):
        """Refresh all displays after applying removals"""
        # Update export status
        if not self.current_matched_fragments.empty:
            num_fragments = len(self.current_matched_fragments)
            num_precursors = self.current_matched_fragments['Precursor_mz'].nunique()
            self.export_status_label.setText(f"Ready to export: {num_fragments} fragments from {num_precursors} precursors")
        else:
            self.export_status_label.setText("No fragments available for export")
        
        # REFRESH current plot if we have a selection
        if self.selected_glycopeptide:
            try:
                # Update the selected glycopeptide's fragments with filtered data
                glycopeptide = self.selected_glycopeptide['name']
                precursor_mz = self.selected_glycopeptide['precursor_mz']
                precursor_rt = self.selected_glycopeptide['precursor_rt']
                
                # Get updated fragments for this glycopeptide
                updated_fragments = self.current_matched_fragments[
                    (self.current_matched_fragments['Glycopeptides'] == glycopeptide) &
                    (np.isclose(self.current_matched_fragments['Precursor_mz'], precursor_mz, rtol=1e-4)) &
                    (np.isclose(self.current_matched_fragments['precursor_rt'], precursor_rt, rtol=1e-2))
                ]
                
                if not updated_fragments.empty:
                    # Update the stored selection with filtered fragments
                    self.selected_glycopeptide['fragments'] = updated_fragments
                    # Refresh the current plot
                    self.refresh_current_plot()
                    self.add_log(f"Refreshed {self.current_viewer_mode.upper()} plot with {len(updated_fragments)} remaining fragments")
                else:
                    # No fragments left for this glycopeptide
                    self.plot_area.setText("No fragments remaining for this glycopeptide after removal")
                    self.selected_glycopeptide = None
                    self.refresh_plot_btn.setEnabled(False)
                    self.save_plot_btn.setEnabled(False)
            except Exception as e:
                self.add_log(f"Error refreshing plot after removal: {e}")
        
        # Repopulate fragment tree with updated data
        self.populate_fragment_tree()
        self.update_removal_statistics()

    def set_removal_scope(self, global_scope):
        """Set the fragment removal scope (current file vs all files)"""
        self.global_removal_scope = global_scope
        
        # Update button states
        self.scope_current_file.setChecked(not global_scope)
        self.scope_all_files.setChecked(global_scope)
        
        # Update button styles for visual feedback
        if global_scope:
            self.scope_all_files.setStyleSheet("QPushButton { background-color: #e74c3c; color: white; }")
            self.scope_current_file.setStyleSheet("")
            scope_text = "GLOBAL (All Files)"
        else:
            self.scope_current_file.setStyleSheet("QPushButton { background-color: #3498db; color: white; }")
            self.scope_all_files.setStyleSheet("")
            scope_text = "CURRENT FILE ONLY"
        
        # Update status
        self.removal_status_label.setText(f"Removal scope: {scope_text}")
        self.add_log(f"Fragment removal scope changed to: {scope_text}")

    def update_file_navigation_state(self):
        """Update the state of file navigation controls"""
        if not self.available_files:
            return
        
        total_files = len(self.available_files)
        current_index = self.current_file_index
        
        # Update navigation buttons
        self.prev_file_btn.setEnabled(current_index > 0)
        self.next_file_btn.setEnabled(current_index < total_files - 1)
        
        # Update file info label
        current_file = self.available_files[current_index]
        self.file_info_label.setText(f"File {current_index + 1} of {total_files}: {current_file}")
        
        # Update dropdown selection (without triggering the signal)
        self.file_selector.blockSignals(True)
        self.file_selector.setCurrentText(current_file)
        self.file_selector.blockSignals(False)

    def load_file_data(self, file_key):
        """Load data for the specified file - FIXED TO UPDATE FRAGMENT TREE"""
        if file_key not in self.all_analysis_results:
            self.add_log(f"Warning: No data found for file {file_key}")
            return
        
        try:
            # Save current removal state before switching
            if self.current_file_key and not self.current_matched_fragments.empty:
                self._save_current_removal_state()
            
            # Load new file data
            file_data = self.all_analysis_results[file_key]
            self.current_file_key = file_key
            self.current_matched_fragments = file_data['matched_fragments'].copy()
            self.current_cached_data = file_data['cached_data']
            self.current_analysis_params = file_data.get('analysis_params', {})
            
            # CRITICAL FIX: Update fragment tree with new file data
            self.populate_fragment_tree()
            
            # Load removal state for this file AFTER populating tree
            self._load_removal_state_for_file(file_key)
            
            # Update displays
            self.update_results_display()
            self.update_removal_statistics()
            
            # Update export status
            if not self.current_matched_fragments.empty:
                num_fragments = len(self.current_matched_fragments)
                num_precursors = self.current_matched_fragments['Precursor_mz'].nunique()
                self.export_status_label.setText(f"Ready to export: {num_fragments} fragments from {num_precursors} precursors")
            else:
                self.export_status_label.setText("No fragments available for export")
            
            # Clear current plot selection
            self.selected_glycopeptide = None
            self.plot_area.setText("Select a glycopeptide to view EIC/MS2")
            self.refresh_plot_btn.setEnabled(False)
            self.save_plot_btn.setEnabled(False)
            
            self.add_log(f"Loaded data for file: {file_key} ({len(self.current_matched_fragments)} fragments)")
            
        except Exception as e:
            self.add_log(f"Error loading file data: {e}")

    def _load_removal_state_for_file(self, file_key):
        """Load the removal state for a specific file - ENHANCED"""
        if file_key in self.fragment_removal_states:
            # Apply saved removal state after tree is populated with a delay
            QTimer.singleShot(200, lambda: self._apply_saved_removal_state(file_key))
            self.add_log(f"Loading removal state for {file_key}")
        else:
            self.add_log(f"No removal state found for {file_key}")

    def on_results_table_click(self, event):
        """Handle clicks on the results table to show EIC"""
        try:
            # Get the position and text at that position
            cursor = self.results_table.cursorForPosition(event.pos())
            cursor.select(cursor.LineUnderCursor)
            line_text = cursor.selectedText()
            
            # Parse the clicked line to extract glycopeptide info
            if self.parse_results_table_click(line_text):
                # Successfully parsed and displayed EIC
                pass
            
        except Exception as e:
            print(f"Error handling results table click: {e}")

    def parse_results_table_click(self, line_text):
        """Enhanced parsing for clicked line from results table"""
        try:
            print(f"DEBUG: Raw clicked text: '{line_text}'")
            
            # Method 1: Try to extract from HTML table row with <strong> tags
            strong_pattern = r'<td><strong>([^<]+)</strong></td><td>([0-9.]+)</td><td>([0-9.]+)</td>'
            match = re.search(strong_pattern, line_text)
            if match:
                glycopeptide = match.group(1)
                precursor_mz = float(match.group(2))
                precursor_rt = float(match.group(3))
                print(f"DEBUG: Parsed with strong pattern: {glycopeptide}, {precursor_mz}, {precursor_rt}")
                self.show_eic_for_glycopeptide(glycopeptide, precursor_mz, precursor_rt)
                return True
            
            # Method 2: Try standard HTML table row without <strong>
            basic_pattern = r'<td>([^<]+)</td><td>([0-9.]+)</td><td>([0-9.]+)</td>'
            match = re.search(basic_pattern, line_text)
            if match:
                glycopeptide = match.group(1)
                precursor_mz = float(match.group(2))
                precursor_rt = float(match.group(3))
                print(f"DEBUG: Parsed with basic pattern: {glycopeptide}, {precursor_mz}, {precursor_rt}")
                self.show_eic_for_glycopeptide(glycopeptide, precursor_mz, precursor_rt)
                return True
            
            # Method 3: Handle concatenated format like your debug example
            # Pattern: PEPTIDE-GLYCAN + numbers (mz + rt concatenated)
            concat_pattern = r'^([A-Z]+-[A-Za-z0-9\(\)]+)([0-9]+\.[0-9]+)([0-9]+\.[0-9]+)$'
            match = re.search(concat_pattern, line_text)
            if match:
                glycopeptide = match.group(1)
                precursor_mz = float(match.group(2))
                precursor_rt = float(match.group(3))
                print(f"DEBUG: Parsed with concatenated pattern: {glycopeptide}, {precursor_mz}, {precursor_rt}")
                self.show_eic_for_glycopeptide(glycopeptide, precursor_mz, precursor_rt)
                return True
            
            # Method 4: Try to extract from any text containing the key components
            # Look for peptide-glycan pattern followed by numbers
            flexible_pattern = r'([A-Z]+-[A-Za-z0-9\(\)]+).*?([0-9]+\.[0-9]{3,}).*?([0-9]+\.[0-9]{1,})'
            match = re.search(flexible_pattern, line_text)
            if match:
                glycopeptide = match.group(1)
                precursor_mz = float(match.group(2))
                precursor_rt = float(match.group(3))
                print(f"DEBUG: Parsed with flexible pattern: {glycopeptide}, {precursor_mz}, {precursor_rt}")
                self.show_eic_for_glycopeptide(glycopeptide, precursor_mz, precursor_rt)
                return True
            
            print(f"DEBUG: No pattern matched for: '{line_text}'")
            return False
            
        except Exception as e:
            print(f"Error parsing results table click: {e}")
            return False
        
    def update_results_display(self):
        """Update the results display with current data - SIMPLIFIED VERSION"""
        try:
            if not self.current_matched_fragments.empty:
                # Update status only (no table)
                num_fragments = len(self.current_matched_fragments)
                num_precursors = self.current_matched_fragments['Precursor_mz'].nunique()
                
                # Calculate reproducibility stats if multi-file
                if hasattr(self, 'all_analysis_results') and len(self.all_analysis_results) > 1:
                    fragment_reproducibility = self._calculate_fragment_reproducibility()
                    total_files = len(self.all_analysis_results)
                    poor_repro_count = sum(1 for key, count in fragment_reproducibility.items() if count < total_files * 0.5)
                    status_text = f"Results: {num_fragments} fragments across {num_precursors} precursors | Poor reproducibility: {poor_repro_count} fragments"
                else:
                    status_text = f"Results: {num_fragments} fragments across {num_precursors} precursors"
                
                # Update export status label
                if hasattr(self, 'export_status_label'):
                    self.export_status_label.setText(status_text)
                else:
                    self.add_log(status_text)
                
            else:
                # No data
                if hasattr(self, 'export_status_label'):
                    self.export_status_label.setText("No results to display")
                else:
                    self.add_log("No results to display")
                    
        except Exception as e:
            self.add_log(f"Error updating results display: {e}")
            import traceback
            traceback.print_exc()
            
    def debug_results_table_content(self):
        """Debug method to check what's actually in the results table"""
        html_content = self.results_table.toHtml()
        print("DEBUG: Results table HTML content:")
        print(html_content[:1000])  # First 1000 characters
        
        # Also print the current matched fragments structure
        if not self.current_matched_fragments.empty:
            print("\nDEBUG: Current matched fragments columns:")
            print(self.current_matched_fragments.columns.tolist())
            print("\nDEBUG: First few rows:")
            print(self.current_matched_fragments.head())

    ###-Fragment tree methods-###
    def on_fragment_tree_click(self, item, column):
        """Handle clicks on fragment tree - show EIC for precursor or fragment-specific plot for fragments"""
        try:
            # Check if this is a fragment item (has a parent) or precursor item (no parent)
            if item.parent() is not None:
                # This is a fragment item - show individual fragment EIC plot
                self._show_individual_fragment_eic(item)
            else:
                # This is a precursor item - show full EIC as before
                self._show_precursor_eic_plot(item)
                
        except Exception as e:
            print(f"Error handling fragment tree click: {e}")
            self.add_log(f"Error handling fragment tree click: {e}")

    def _show_individual_fragment_eic(self, fragment_item):
        """Show actual EIC plot for individual fragment (Gaussian-like chromatogram)"""
        try:
            # Get fragment data from stored UserRole data
            glycopeptide = fragment_item.data(0, Qt.UserRole)
            precursor_mz = fragment_item.data(0, Qt.UserRole + 1)
            precursor_rt = fragment_item.data(0, Qt.UserRole + 2)
            fragment_type = fragment_item.data(0, Qt.UserRole + 3)
            theoretical_mz = fragment_item.data(0, Qt.UserRole + 4)
            
            if None in [glycopeptide, precursor_mz, precursor_rt, fragment_type, theoretical_mz]:
                self.add_log("Error: Missing fragment data for EIC plot")
                return
            
            # CRITICAL FIX: Disable MS2 view button when showing individual fragment
            if hasattr(self, 'viewer_mode_ms2'):
                self.viewer_mode_ms2.setEnabled(False)
                self.viewer_mode_ms2.setToolTip("MS2 view not available for individual fragments")
            
            # Ensure EIC mode is selected and enabled
            if hasattr(self, 'viewer_mode_eic'):
                self.viewer_mode_eic.setChecked(True)
                self.viewer_mode_eic.setEnabled(True)
                self.current_viewer_mode = 'eic'
            
            # Find the specific fragment in the data
            fragment_data = self.current_matched_fragments[
                (self.current_matched_fragments['Glycopeptides'] == glycopeptide) &
                (np.isclose(self.current_matched_fragments['Precursor_mz'], precursor_mz, rtol=1e-4)) &
                (np.isclose(self.current_matched_fragments['precursor_rt'], precursor_rt, rtol=1e-2)) &
                (self.current_matched_fragments['Type'] == fragment_type) &
                (np.isclose(self.current_matched_fragments['Theoretical_mz'], theoretical_mz, rtol=1e-4))
            ]
            
            if fragment_data.empty:
                self.add_log(f"No data found for fragment {fragment_type} of {glycopeptide}")
                return
            
            # Get the fragment row
            fragment_row = fragment_data.iloc[0]
            
            # Generate single-fragment EIC plot
            self._create_individual_fragment_eic_plot(fragment_row, glycopeptide, precursor_mz, precursor_rt)
            
        except Exception as e:
            self.add_log(f"Error showing individual fragment EIC: {e}")
            traceback.print_exc()

    def _show_precursor_eic_plot(self, precursor_item):
        """Show EIC plot for the entire precursor (existing functionality)"""
        try:
            # Extract glycopeptide info from precursor item
            glycopeptide = precursor_item.text(0)
            rt_text = precursor_item.text(6)  # "RT: XX.XX"
            precursor_mz = float(precursor_item.text(2))
            
            # Parse RT from "RT: XX.XX" format
            rt_match = re.search(r'RT:\s*([0-9.]+)', rt_text)
            if rt_match:
                precursor_rt = float(rt_match.group(1))
                
                # CRITICAL FIX: Re-enable MS2 view button when showing precursor
                if hasattr(self, 'viewer_mode_ms2'):
                    self.viewer_mode_ms2.setEnabled(True)
                    self.viewer_mode_ms2.setToolTip("View MS2 spectrum for this precursor")
                
                # Use existing method to show full EIC
                self.show_eic_for_glycopeptide(glycopeptide, precursor_mz, precursor_rt)
                self.add_log(f"Showing full EIC for precursor: {glycopeptide}")
            
        except Exception as e:
            self.add_log(f"Error showing precursor EIC: {e}")

    def switch_viewer_mode(self, mode):
        """Switch between EIC and MS2 viewing modes"""
        try:
            # Check if MS2 mode is disabled (individual fragment mode)
            if mode == 'ms2' and hasattr(self, 'viewer_mode_ms2') and not self.viewer_mode_ms2.isEnabled():
                self.add_log("MS2 view not available for individual fragments")
                return
            
            self.current_viewer_mode = mode
            
            # Update button states
            self.viewer_mode_eic.setChecked(mode == 'eic')
            self.viewer_mode_ms2.setChecked(mode == 'ms2')
            
            # Update button styles for visual feedback
            if mode == 'eic':
                self.viewer_mode_eic.setStyleSheet("QPushButton { background-color: #3498db; color: white; }")
                self.viewer_mode_ms2.setStyleSheet("")
            else:
                self.viewer_mode_ms2.setStyleSheet("QPushButton { background-color: #3498db; color: white; }")
                self.viewer_mode_eic.setStyleSheet("")
            
            # Refresh the current plot if we have a selection
            if self.selected_glycopeptide:
                self.refresh_current_plot()
            else:
                # Update placeholder text based on mode
                if mode == 'eic':
                    self.plot_area.setText("EIC plot will appear here")
                else:
                    self.plot_area.setText("MS2 spectrum will appear here")
            
            self.add_log(f"Switched to {mode.upper()} viewing mode")
            
        except Exception as e:
            self.add_log(f"Error switching viewer mode: {e}")

    def _create_individual_fragment_eic_plot(self, fragment_row, glycopeptide, precursor_mz, precursor_rt, ms2_ppm_tolerance=20):
        """Create actual EIC plot for a single fragment showing chromatographic peak - WITH SIMPLIFIED NOISE VISUALIZATION"""
        try:
            from matplotlib.figure import Figure
            from scipy.signal import savgol_filter
            from scipy.interpolate import interp1d
            import numpy as np
            
            fragment_type = fragment_row['Type']
            theoretical_mz = fragment_row['Theoretical_mz']
            observed_mz = fragment_row.get('Observed_mz', theoretical_mz)
            intensity = fragment_row.get('Intensity', 0)
            rt = fragment_row.get('RT', precursor_rt)
            mass_error = fragment_row.get('Mass_Error_ppm', 0)
            grade = fragment_row.get('FDR_Grade', 'F')
            area = fragment_row.get('Area', 0)
            score = fragment_row.get('Fragments_Score', 0)
            
            # Get cached data for this precursor
            row_id = fragment_row.get('row_id', 0)
            if isinstance(row_id, (float, np.float64, np.float32)):
                row_id = int(row_id)
            
            composite_key = f"{precursor_mz}_{row_id}"
            
            # Try to find the cached data
            if composite_key not in self.current_cached_data:
                # Try alternative key matching
                all_keys = list(self.current_cached_data.keys())
                alternative_keys = [k for k in all_keys if str(precursor_mz) in str(k)]
                if alternative_keys:
                    composite_key = alternative_keys[0]
                else:
                    self.plot_area.setText(f"No EIC data available for {fragment_type} of {glycopeptide}")
                    return
            
            # Get the cached MS data
            cached_data = self.current_cached_data[composite_key]
            
            # Extract chromatographic data for this specific fragment
            rt_values = []
            intensity_values = []
            experimental_mz_values = []
            ms2_ppm_tolerance = ms2_ppm_tolerance
            
            try:
                for scan_rt, fragments_array, intensities_array in zip(
                    cached_data['retention_times'], 
                    cached_data['fragments'], 
                    cached_data['intensities']
                ):
                    if len(fragments_array) == 0 or len(intensities_array) == 0:
                        continue
                    
                    # Ensure arrays are numpy arrays
                    if not isinstance(fragments_array, np.ndarray):
                        fragments_array = np.array(fragments_array)
                    if not isinstance(intensities_array, np.ndarray):
                        intensities_array = np.array(intensities_array)
                    
                    # Find fragments within PPM tolerance
                    tolerance_mz = theoretical_mz * (ms2_ppm_tolerance / 1e6)
                    matches = np.where(np.abs(fragments_array - theoretical_mz) <= tolerance_mz)[0]
                    
                    if len(matches) > 0:
                        # Take the most intense match if multiple
                        best_match_idx = matches[np.argmax(intensities_array[matches])]
                        rt_values.append(float(scan_rt))
                        intensity_values.append(float(intensities_array[best_match_idx]))
                        experimental_mz_values.append(float(fragments_array[best_match_idx]))
            
            except Exception as e:
                self.add_log(f"Error extracting chromatographic data: {e}")
                self.plot_area.setText(f"Error extracting EIC data for {fragment_type}")
                return
            
            if not rt_values:
                self.plot_area.setText(f"No chromatographic data found for {fragment_type}")
                return
            
            # CRITICAL FIX: Aggregate intensities for same RT values to create single peak
            # This solves the multiple peaks issue
            rt_intensity_dict = {}
            rt_mz_dict = {}
            
            for rt_val, intensity_val, mz_val in zip(rt_values, intensity_values, experimental_mz_values):
                # Round RT to avoid floating point precision issues
                rt_rounded = round(rt_val, 3)
                
                if rt_rounded in rt_intensity_dict:
                    # If we already have this RT, take the maximum intensity (best fragment match)
                    if intensity_val > rt_intensity_dict[rt_rounded]:
                        rt_intensity_dict[rt_rounded] = intensity_val
                        rt_mz_dict[rt_rounded] = mz_val
                else:
                    rt_intensity_dict[rt_rounded] = intensity_val
                    rt_mz_dict[rt_rounded] = mz_val
            
            # Convert back to sorted arrays
            sorted_rt_keys = sorted(rt_intensity_dict.keys())
            rt_array = np.array(sorted_rt_keys)
            intensity_array = np.array([rt_intensity_dict[rt] for rt in sorted_rt_keys])
            experimental_mz_array = np.array([rt_mz_dict[rt] for rt in sorted_rt_keys])
            
            self.add_log(f"Aggregated data: {len(rt_values)} raw points -> {len(rt_array)} unique RT points")
            
            # Keep original for area calculation
            original_intensity = intensity_array.copy()
            
            # SMOOTH CURVE GENERATION - ENHANCED VERSION
            if len(intensity_array) >= 3:
                try:
                    # Step 1: Remove any zero or very low intensity points for smoother interpolation
                    min_intensity_threshold = np.max(intensity_array) * 0.001  # 0.1% of max intensity
                    valid_mask = intensity_array >= min_intensity_threshold
                    
                    if np.sum(valid_mask) >= 3:  # Need at least 3 points for interpolation
                        rt_clean = rt_array[valid_mask]
                        intensity_clean = intensity_array[valid_mask]
                    else:
                        rt_clean = rt_array
                        intensity_clean = intensity_array
                    
                    # Step 2: Create high-resolution interpolation
                    rt_min, rt_max = rt_clean.min(), rt_clean.max()
                    rt_range = rt_max - rt_min
                    
                    # Create dense grid for smooth curve (10x resolution)
                    num_points = min(500, len(rt_clean) * 10)  # Up to 500 points for smoothness
                    rt_smooth = np.linspace(rt_min, rt_max, num_points)
                    
                    # Step 3: Interpolate using cubic spline for smoothness
                    if len(rt_clean) >= 4:
                        # Cubic spline interpolation for very smooth curves
                        try:
                            interpolator = interp1d(rt_clean, intensity_clean, kind='cubic', 
                                                bounds_error=False, fill_value=0)
                            intensity_smooth = interpolator(rt_smooth)
                            # Ensure no negative values
                            intensity_smooth = np.maximum(intensity_smooth, 0)
                        except:
                            # Fallback to quadratic
                            interpolator = interp1d(rt_clean, intensity_clean, kind='quadratic', 
                                                bounds_error=False, fill_value=0)
                            intensity_smooth = interpolator(rt_smooth)
                            intensity_smooth = np.maximum(intensity_smooth, 0)
                    else:
                        # Linear interpolation for few points
                        interpolator = interp1d(rt_clean, intensity_clean, kind='linear', 
                                            bounds_error=False, fill_value=0)
                        intensity_smooth = interpolator(rt_smooth)
                        intensity_smooth = np.maximum(intensity_smooth, 0)
                    
                    # Step 4: Optional additional smoothing with Savitzky-Golay filter
                    if len(intensity_smooth) >= 5:
                        window_length = min(11, len(intensity_smooth) if len(intensity_smooth) % 2 == 1 else len(intensity_smooth) - 1)
                        if window_length >= 3:
                            intensity_smooth = savgol_filter(intensity_smooth, window_length, polyorder=2)
                            intensity_smooth = np.maximum(intensity_smooth, 0)
                    
                except Exception as e:
                    self.add_log(f"Error in smooth interpolation, using original data: {e}")
                    rt_smooth = rt_array
                    intensity_smooth = intensity_array
            else:
                # Not enough points for interpolation
                rt_smooth = rt_array
                intensity_smooth = intensity_array
            
            # SIMPLIFIED NOISE REGION CALCULATION
            noise_regions = self.calculate_noise_regions_for_visualization(rt_array, original_intensity, precursor_rt)
            
            # Close any existing plots
            plt.close('all')
            
            # Create figure with single plot
            fig = Figure(figsize=(18, 10), facecolor='white')
            ax_eic = fig.add_subplot(1, 1, 1)
            
            # STEP 1: Plot smooth curve first
            ax_eic.plot(rt_smooth, intensity_smooth, 'b-', linewidth=2.5, alpha=0.9, 
                    label='Smooth EIC', zorder=3)
            
            # STEP 2: Fill under the smooth curve
            ax_eic.fill_between(rt_smooth, 0, intensity_smooth, alpha=0.3, color='blue', zorder=1)
            
            # STEP 3: REMOVED - No red data points plotted
            
            # STEP 4: Show percentile noise points with orange triangular markers
            # if noise_regions['percentile_points']:
            #     percentile_rt = noise_regions['percentile_points']
            #     # Create scatter plot for percentile noise points
            #     percentile_intensities = []
            #     for rt_point in percentile_rt:
            #         closest_idx = np.argmin(np.abs(rt_array - rt_point))
            #         percentile_intensities.append(original_intensity[closest_idx])
                
                #ax_eic.scatter(percentile_rt, percentile_intensities, 
                 #           color='orange', s=50, alpha=0.7, marker='v', 
                  #          label='Percentile Noise Points', zorder=5)
            
            # STEP 5: NEW - Draw horizontal dotted line for noise level
            if noise_regions['noise_level'] > 0:
                noise_level = noise_regions['noise_level']
                ax_eic.axhline(y=noise_level, color='red', linestyle=':', linewidth=2, alpha=0.8,
                            label=f'Noise Level (S/N Calc): {noise_level:.0f}', zorder=2)
            
            # STEP 6: Highlight the integration region if available
            integration_start = fragment_row.get('Integration_Start', None)
            integration_end = fragment_row.get('Integration_End', None)
            
            if integration_start is not None and integration_end is not None:
                # Filter smooth data in integration window
                integration_mask = (rt_smooth >= integration_start) & (rt_smooth <= integration_end)
                if np.any(integration_mask):
                    ax_eic.fill_between(
                        rt_smooth[integration_mask], 
                        0, 
                        intensity_smooth[integration_mask], 
                        alpha=0.6, 
                        color='green',
                        label=f'Integration: {integration_start:.3f}-{integration_end:.3f} min',
                        zorder=2
                    )
            
            # STEP 7: Mark the expected RT
            ax_eic.axvline(x=precursor_rt, color='red', linestyle='--', alpha=0.7, 
                        label=f'Expected RT: {precursor_rt:.2f}')

            # STEP 8: Find actual peak maximum from INTEGRATION REGION (most accurate approach)
            if len(intensity_smooth) > 0:
                # Get integration boundaries from fragment data
                integration_start = fragment_row.get('Integration_Start', None)
                integration_end = fragment_row.get('Integration_End', None)
                
                # BEST APPROACH: Use integration region for peak maximum
                if integration_start is not None and integration_end is not None:
                    # Find maximum within the INTEGRATION REGION from ORIGINAL data
                    integration_mask_orig = (rt_array >= integration_start) & (rt_array <= integration_end)
                    
                    if np.any(integration_mask_orig):
                        # Find maximum within the integration region from ORIGINAL data
                        valid_original_intensities = original_intensity[integration_mask_orig]
                        valid_rt_original = rt_array[integration_mask_orig]
                        valid_mz_original = experimental_mz_array[integration_mask_orig]
                        
                        if len(valid_original_intensities) > 0:
                            # Find the index of maximum intensity in integration region
                            local_max_idx = np.argmax(valid_original_intensities)
                            peak_max_rt = valid_rt_original[local_max_idx]
                            original_max_intensity = valid_original_intensities[local_max_idx]
                            peak_max_experimental_mz = valid_mz_original[local_max_idx]
                            region_type = "Integration Region"
                        else:
                            # Fallback: use expected RT
                            peak_max_rt = precursor_rt
                            closest_original_idx = np.argmin(np.abs(rt_array - precursor_rt))
                            original_max_intensity = original_intensity[closest_original_idx]
                            peak_max_experimental_mz = experimental_mz_array[closest_original_idx]
                            region_type = "Expected RT (fallback)"
                    else:
                        # No data within integration region, use expected RT
                        peak_max_rt = precursor_rt
                        closest_original_idx = np.argmin(np.abs(rt_array - precursor_rt))
                        original_max_intensity = original_intensity[closest_original_idx]
                        peak_max_experimental_mz = experimental_mz_array[closest_original_idx]
                        region_type = "Expected RT (no integration data)"
                else:
                    # Fallback to RT window approach if integration boundaries not available
                    max_rt_diff = getattr(self, 'max_rt_difference', 0.5)  # Default to 0.5 min
                    if hasattr(self, 'current_analysis_params') and 'max_rt_difference' in self.current_analysis_params:
                        max_rt_diff = self.current_analysis_params['max_rt_difference']
                    
                    rt_window_mask_orig = np.abs(rt_array - precursor_rt) <= max_rt_diff
                    
                    if np.any(rt_window_mask_orig):
                        # Find maximum within the RT window from ORIGINAL data
                        valid_original_intensities = original_intensity[rt_window_mask_orig]
                        valid_rt_original = rt_array[rt_window_mask_orig]
                        valid_mz_original = experimental_mz_array[rt_window_mask_orig]
                        
                        if len(valid_original_intensities) > 0:
                            # Find the index of maximum intensity in original data
                            local_max_idx = np.argmax(valid_original_intensities)
                            peak_max_rt = valid_rt_original[local_max_idx]
                            original_max_intensity = valid_original_intensities[local_max_idx]
                            peak_max_experimental_mz = valid_mz_original[local_max_idx]
                            region_type = f"RT Window (±{max_rt_diff:.1f} min)"
                        else:
                            # Fallback: use expected RT
                            peak_max_rt = precursor_rt
                            closest_original_idx = np.argmin(np.abs(rt_array - precursor_rt))
                            original_max_intensity = original_intensity[closest_original_idx]
                            peak_max_experimental_mz = experimental_mz_array[closest_original_idx]
                            region_type = "Expected RT (fallback)"
                    else:
                        # No data within RT window, use expected RT
                        peak_max_rt = precursor_rt
                        closest_original_idx = np.argmin(np.abs(rt_array - precursor_rt))
                        original_max_intensity = original_intensity[closest_original_idx]
                        peak_max_experimental_mz = experimental_mz_array[closest_original_idx]
                        region_type = "Expected RT (no RT window data)"
                        
                # STEP 9: Mark the peak maximum on the plot
                ax_eic.scatter([peak_max_rt], [original_max_intensity], 
                            color='red', s=100, marker='o', alpha=0.8, 
                            label=f'Peak Max: {original_max_intensity:.0f} ({region_type})', 
                            zorder=6, edgecolors='black', linewidth=1)
                
                # Add vertical line at peak maximum
                ax_eic.axvline(x=peak_max_rt, color='red', linestyle='-', alpha=0.5, 
                            linewidth=1, zorder=2)
                
                ax_eic.axvline(x=peak_max_rt, color='orange', linestyle=':', alpha=0.7, 
                            label=f'Peak Max: {peak_max_rt:.2f}')
                
                # Calculations
                rt_difference = precursor_rt - peak_max_rt
                pmp_difference = ((peak_max_experimental_mz - theoretical_mz) / theoretical_mz) * 1e6
                
                # Position annotation at fixed location
                y_max = np.max(intensity_smooth) if len(intensity_smooth) > 0 else np.max(original_intensity)
                annotation_x = rt_smooth[0] + 0.75 * (rt_smooth[-1] - rt_smooth[0])
                annotation_y = 0.8 * y_max
                
                # Show values in annotation with CORRECT intensity
                ax_eic.annotate(f'Max Intensity: {original_max_intensity:.0f}\n'  # <-- FIXED
                            f'Integrated Area: {area:.1f}\n'
                            f'Exp. m/z: {peak_max_experimental_mz:.4f}\n'
                            f'PPM Error: {pmp_difference:.2f}',
                            xy=(annotation_x, annotation_y),
                            xytext=(0, 0), textcoords='offset points',
                            bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.8),
                            fontsize=12,
                            horizontalalignment='center',
                            verticalalignment='center')
            else:
                rt_difference = 0.0
                pmp_difference = 0.0
                peak_max_rt = precursor_rt
                peak_max_experimental_mz = theoretical_mz
                original_max_intensity = np.max(original_intensity) if len(original_intensity) > 0 else 1.0
                # Add warning for this case
                self.add_log(f"WARNING: No smooth curve data available for {fragment_type}")
                max_rt_diff = 0.5  # Default for logging
            
            # Calculate Signal-to-Noise ratio WITH INTEGRATION REGION APPROACH
            # Use the integration region maximum intensity for S/N calculation
            signal_to_noise, noise_info = self.calculate_improved_snr_with_details_rt_constrained(
                rt_array, original_intensity, intensity_smooth, precursor_rt, original_max_intensity)
            
            # ENHANCED DEBUG LOGGING - Show actual calculation with integration region approach
            debug_calc = noise_info.get("debug_calculation", "N/A")
            method_used = noise_info.get('method_used', 'Unknown')
            noise_points = noise_info.get('noise_points_count', 0)
            noise_percentile = noise_info.get('noise_percentile_used', 0)
            calculated_noise = noise_info.get('final_noise', 0)
            
            # Verify that the noise level matches what's shown on the plot
            plot_noise_level = noise_regions.get('noise_level', 0)
            noise_match = abs(calculated_noise - plot_noise_level) < 0.01
            
            self.add_log(f"S/N Debug for {fragment_type}: {debug_calc}")
            self.add_log(f"S/N Method: {method_used}")
            self.add_log(f"S/N Noise Points: {noise_points} points ({noise_percentile}%)")
            self.add_log(f"Signal Level (integration region): {noise_info.get('signal_level', 0):.0f}")
            
            # Get integration boundaries for logging
            integration_start = fragment_row.get('Integration_Start', None)
            integration_end = fragment_row.get('Integration_End', None)
            
            if integration_start is not None and integration_end is not None:
                integration_width = integration_end - integration_start
                is_within_integration = integration_start <= peak_max_rt <= integration_end
                
                self.add_log(f"Integration Region: {integration_start:.3f} - {integration_end:.3f} min (width: {integration_width:.3f})")
                self.add_log(f"Peak Found at RT: {peak_max_rt:.3f} (from {region_type})")
                self.add_log(f"Peak within Integration: {'YES' if is_within_integration else 'NO - WARNING!'}")
                
                if not is_within_integration and region_type.startswith("Integration"):
                    self.add_log(f"WARNING: Peak maximum outside integration region!")
            else:
                # Fallback to RT window information
                max_rt_diff = getattr(self, 'max_rt_difference', 0.5)
                self.add_log(f"RT Window Applied: ±{max_rt_diff:.1f} min from {precursor_rt:.2f}")
                self.add_log(f"Peak Found at RT: {peak_max_rt:.3f} (from {region_type})")
                self.add_log(f"No integration boundaries available")
            
            rt_difference = abs(peak_max_rt - precursor_rt)
            self.add_log(f"RT Difference: {rt_difference:.3f} min from expected {precursor_rt:.3f}")
            self.add_log(f"Peak Selection: {region_type}")
            self.add_log(f"Calculated Noise: {calculated_noise:.0f}")
            self.add_log(f"Plot Line Noise: {plot_noise_level:.0f}")
            self.add_log(f"Noise Values Match: {'YES' if noise_match else 'NO - ERROR!'}")
            if not noise_match:
                self.add_log(f"WARNING: Noise calculation mismatch detected!")
            
            # Validation logging for integration region
            if integration_start is not None and integration_end is not None:
                if not (integration_start <= peak_max_rt <= integration_end) and region_type.startswith("Integration"):
                    self.add_log(f"ERROR: Peak maximum outside integration region!")
                else:
                    self.add_log(f"VALIDATED: Peak maximum within integration region constraints")
            else:
                # Fallback validation for RT window
                max_rt_diff = getattr(self, 'max_rt_difference', 0.5)
                if abs(rt_difference) > max_rt_diff:
                    self.add_log(f"ERROR: Peak RT difference ({abs(rt_difference):.3f}) exceeds max allowed ({max_rt_diff:.1f})!")
                else:
                    self.add_log(f"VALIDATED: Peak RT difference ({abs(rt_difference):.3f}) within allowed range")
            
            # Enhanced title
            ax_eic.set_xlabel('Retention Time (min)', fontsize=12)
            ax_eic.set_ylabel('Intensity', fontsize=12)
            ax_eic.set_title(f'{fragment_type} (m/z: {theoretical_mz:.4f}) of {glycopeptide}\n'
                            f'Grade: {grade} | PPM Error: {pmp_difference:.2f} ppm | S/N: {signal_to_noise:.1f} | Score: {score:.1f}', 
                            fontsize=12, fontweight='bold')
            ax_eic.grid(True, alpha=0.3)
            ax_eic.legend(loc='upper left', fontsize=9, ncol=2)  # Use 2 columns for legend
            
            # Format y-axis in scientific notation if needed
            if np.max(intensity_smooth) > 1e6:
                ax_eic.ticklabel_format(style='scientific', axis='y', scilimits=(0,0))
            
            # Add metrics to text box WITH INTEGRATION REGION INFO
            rt_difference = abs(peak_max_rt - precursor_rt)
            
            # Build metrics text with integration region information
            metrics_lines = [
                f'RT Difference: {rt_difference:.3f} min',
                f'Peak Width: {fragment_row.get("Peak_Width", 0):.2f} min',
                f'Data Points: {len(rt_array)} aggregated',
                f'Fragment Quality: {grade}',
                f'Smoothing: Cubic Spline + Savgol',
                f'S/N Debug: {debug_calc}',
                f'Noise Method: Mean of lowest 5%'
            ]
            
            # Add integration region or RT window information
            if integration_start is not None and integration_end is not None:
                integration_width = integration_end - integration_start
                is_within_integration = integration_start <= peak_max_rt <= integration_end
                metrics_lines.extend([
                    f'Integration: {integration_start:.3f}-{integration_end:.3f} min',
                    f'Peak in Region: {"YES" if is_within_integration else "NO"}',
                    f'Region Used: {region_type}'
                ])
            else:
                max_rt_diff = getattr(self, 'max_rt_difference', 0.5)
                metrics_lines.extend([
                    f'RT Window: ±{max_rt_diff:.1f} min',
                    f'No Integration Bounds'
                ])
            
            metrics_lines.append(f'Noise Match: {"YES" if noise_match else "ERROR!"}')
            metrics_text = '\n'.join(metrics_lines)
            
            # ax_eic.text(0.98, 0.98, metrics_text, transform=ax_eic.transAxes,
            #         bbox=dict(boxstyle='round,pad=0.5', facecolor='lightblue', alpha=0.8),
            #         verticalalignment='bottom', horizontalalignment='right', fontsize=8)
            
            # Use figure coordinates instead of axes coordinates to place outside plot
            ax_eic.text(1.02, 0.98, metrics_text, transform=ax_eic.transAxes,
                    bbox=dict(boxstyle='round,pad=0.5', facecolor='lightgreen', alpha=0.8),
                    verticalalignment='top', horizontalalignment='left', fontsize=12)

            # Color-code the plot border based on grade
            grade_colors = {
                'A': '#27ae60',  # Green
                'B': '#2ecc71',  # Light green
                'C': '#f39c12',  # Orange
                'D': '#e67e22',  # Dark orange
                'F': '#e74c3c'   # Red
            }
            
            # Add colored border
            for spine in ax_eic.spines.values():
                spine.set_color(grade_colors.get(grade, '#95a5a6'))
                spine.set_linewidth(3)
            
            # Adjust layout for better spacing
            fig.tight_layout(pad=1.0)
            fig.subplots_adjust(right=0.75)
            
            # Convert to QPixmap for display
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=100, bbox_inches='tight', 
                    facecolor='white', edgecolor='none')
            buf.seek(0)
            
            # Create QPixmap from buffer
            pixmap = QPixmap()
            pixmap.loadFromData(buf.getvalue())
            
            if not pixmap.isNull():
                # Scale pixmap to fit the label while maintaining aspect ratio
                label_size = self.plot_area.size()
                scaled_pixmap = pixmap.scaled(
                    label_size, 
                    Qt.KeepAspectRatio, 
                    Qt.SmoothTransformation
                )
                
                # Set the pixmap to the label
                self.plot_area.setPixmap(scaled_pixmap)
                
                # Store the figure reference
                self.current_figure = fig
            else:
                self.plot_area.setText("Error creating fragment EIC plot")
            
            buf.close()
            
            # Update button states
            if hasattr(self, 'refresh_plot_btn'):
                self.refresh_plot_btn.setEnabled(True)
            if hasattr(self, 'save_plot_btn'):
                self.save_plot_btn.setEnabled(True)
            
            # Store current selection with corrected values
            self.selected_fragment = {
                'glycopeptide': glycopeptide,
                'precursor_mz': precursor_mz,
                'precursor_rt': precursor_rt,
                'fragment_type': fragment_type,
                'theoretical_mz': theoretical_mz,
                'experimental_mz': peak_max_experimental_mz,
                'rt_difference': rt_difference,
                'pmp_difference': pmp_difference,
                'fragment_row': fragment_row
            }
            
            # Update plot info label WITH INTEGRATION REGION INFO
            if hasattr(self, 'plot_info_label'):
                integration_info = ""
                if integration_start is not None and integration_end is not None:
                    is_within_integration = integration_start <= peak_max_rt <= integration_end
                    integration_info = f" | Integration: {integration_start:.3f}-{integration_end:.3f} (peak {'✓' if is_within_integration else '✗'})"
                
                self.plot_info_label.setText(
                    f"EIC with Integration Region: {fragment_type} of {glycopeptide} | "
                    f"m/z: {theoretical_mz:.4f} (exp: {peak_max_experimental_mz:.4f}) | "
                    f"RT: {precursor_rt:.2f} (peak: {peak_max_rt:.2f}) | "
                    f"S/N: {debug_calc} | Grade: {grade} | Region: {region_type}{integration_info}"
                )
            
            self.add_log(f"Generated EIC with integration region for {fragment_type} (m/z: {theoretical_mz:.4f}, "
                        f"S/N: {debug_calc}, Peak: {region_type}) of {glycopeptide}")
            
            # Clean up
            plt.close('all')
            
        except Exception as e:
            self.add_log(f"Error creating simplified EIC plot: {e}")
            traceback.print_exc()
            
            # Show error message in plot area
            self.plot_area.setText(f"Error creating EIC plot: {str(e)}")
            
    def calculate_noise_regions_for_visualization(self, rt_array, original_intensity, precursor_rt):
        """Calculate noise regions for visualization on EIC plots - MATCHES S/N CALCULATION METHOD"""
        try:
            noise_regions = {
                'baseline_regions': [],  # No longer used
                'percentile_points': [],
                'noise_level': 0.0  # Add noise level for dotted line
            }
            
            if len(original_intensity) < 3:
                return noise_regions
            
            # Method: Percentile noise points (lowest 5% of intensities)
            sorted_intensities = np.sort(original_intensity)
            noise_cutoff = max(3, int(len(sorted_intensities) * 0.03))  # Use 3% for noise cutoff
            lowest_indices = np.argsort(original_intensity)[:noise_cutoff]
            noise_regions['percentile_points'] = rt_array[lowest_indices].tolist()
            
            # CRITICAL: Calculate noise level using SAME method as S/N calculation
            lowest_intensities = sorted_intensities[:noise_cutoff]
            noise_regions['noise_level'] = np.mean(lowest_intensities)  # Mean of lowest 5% (matches S/N calc)
            
            return noise_regions
            
        except Exception as e:
            print(f"Error calculating noise regions: {e}")
            return {
                'baseline_regions': [],
                'percentile_points': [],
                'noise_level': 0.0
            }

    def calculate_improved_snr_with_details_rt_constrained(self, rt_array, original_intensity, smoothed_intensity, precursor_rt, constrained_signal_level):
        """Calculate S/N ratio using RT-constrained signal level - PREVENTS WRONG PEAK ASSIGNMENT"""
        try:
            if len(original_intensity) < 3:
                return 1.0, {"final_noise": 1.0, "method_used": "fallback", "signal_level": 1.0, "debug_calculation": "1.0/1.0 = 1.0"}
            
            # Use the provided RT-constrained signal level instead of finding max from entire curve
            signal_level = constrained_signal_level
            
            # Use same noise calculation method as visualization (mean of lowest 5% intensities)
            sorted_intensities = np.sort(original_intensity)
            noise_cutoff = max(3, int(len(sorted_intensities) * 0.05))
            lowest_intensities = sorted_intensities[:noise_cutoff]
            
            # Use MEAN of lowest intensities to match visualization line
            noise_level = np.mean(lowest_intensities)
            method_used = "Mean of lowest 5% intensities (RT-constrained signal)"
            
            # Ensure minimum noise level to avoid division by zero
            min_noise_threshold = max(1.0, signal_level * 0.001)
            noise_level = max(noise_level, min_noise_threshold)
            
            # Calculate S/N ratio
            snr = signal_level / noise_level
            
            # Create debug calculation string
            debug_calculation = f"{signal_level:.0f}/{noise_level:.0f} = {snr:.1f}"
            
            # Reasonable bounds check
            if snr > 1000:
                snr = signal_level / (signal_level * 0.01)
                method_used = "Capped (was >1000)"
                debug_calculation = f"{signal_level:.0f}/{signal_level * 0.01:.0f} = {snr:.1f} (capped)"
            elif snr < 0.1:
                snr = 1.0
                method_used = "Minimum (was <0.1)"
                debug_calculation = "1.0 (minimum applied)"
            
            noise_info = {
                "final_noise": noise_level,
                "method_used": method_used,
                "signal_level": signal_level,
                "debug_calculation": debug_calculation,
                "noise_percentile_used": 5.0,
                "noise_points_count": len(lowest_intensities)
            }
            
            return snr, noise_info
            
        except Exception as e:
            # Fallback calculation if everything fails
            fallback_snr = 1.0
            noise_info = {
                "final_noise": 1.0,
                "method_used": "Error fallback",
                "signal_level": constrained_signal_level if 'constrained_signal_level' in locals() else 1.0,
                "debug_calculation": "1.0/1.0 = 1.0 (error fallback)"
            }
            return fallback_snr, noise_info

    def calculate_improved_snr_with_details(self, rt_array, original_intensity, smoothed_intensity, precursor_rt):
        """Calculate S/N ratio and return detailed noise information for visualization - FIXED TO MATCH VISUALIZATION"""
        try:
            if len(original_intensity) < 3:
                return 1.0, {"final_noise": 1.0, "method_used": "fallback", "signal_level": 1.0, "debug_calculation": "1.0/1.0 = 1.0"}
            
            # Signal is the maximum of smoothed intensity (peak signal)
            signal_level = np.max(smoothed_intensity)
            
            # FIXED: Use the SAME calculation as visualization (mean of lowest 3% intensities)
            sorted_intensities = np.sort(original_intensity)
            noise_cutoff = max(3, int(len(sorted_intensities) * 0.03))
            lowest_intensities = sorted_intensities[:noise_cutoff]
            
            # CRITICAL FIX: Use MEAN instead of STD to match the visualization line
            noise_level = np.mean(lowest_intensities)
            method_used = "Mean of lowest 5% intensities (matches visualization)"
            
            # Ensure minimum noise level to avoid division by zero
            min_noise_threshold = max(1.0, signal_level * 0.001)
            noise_level = max(noise_level, min_noise_threshold)
            
            # Calculate S/N ratio
            snr = signal_level / noise_level
            
            # Create debug calculation string
            debug_calculation = f"{signal_level:.0f}/{noise_level:.0f} = {snr:.1f}"
            
            # Reasonable bounds check
            if snr > 1000:
                snr = signal_level / (signal_level * 0.01)
                method_used = "Capped (was >1000)"
                debug_calculation = f"{signal_level:.0f}/{signal_level * 0.01:.0f} = {snr:.1f} (capped)"
            elif snr < 0.1:
                snr = 1.0
                method_used = "Minimum (was <0.1)"
                debug_calculation = "1.0 (minimum applied)"
            
            noise_info = {
                "final_noise": noise_level,
                "method_used": method_used,
                "signal_level": signal_level,
                "debug_calculation": debug_calculation,
                "noise_percentile_used": 5.0,
                "noise_points_count": len(lowest_intensities)
            }
            
            return snr, noise_info
            
        except Exception as e:
            # Fallback calculation if everything fails
            fallback_snr = 1.0
            noise_info = {
                "final_noise": 1.0,
                "method_used": "Error fallback",
                "signal_level": np.max(smoothed_intensity) if len(smoothed_intensity) > 0 else 1.0,
                "debug_calculation": "1.0/1.0 = 1.0 (error fallback)"
            }
            return fallback_snr, noise_info

    def calculate_improved_snr(self, rt_array, original_intensity, smoothed_intensity, precursor_rt):
        """Calculate improved S/N ratio using multiple methods - FIXED VERSION"""
        try:
            if len(original_intensity) < 3:
                return 1.0
            
            # Signal is the maximum of smoothed intensity (peak signal)
            signal_level = np.max(smoothed_intensity)
            
            # FIXED: Better noise estimation methods
            
            # Method 1: Use baseline regions (regions far from precursor RT)
            baseline_mask = np.abs(rt_array - precursor_rt) > 1.0  # Points > 1 min from expected RT
            if np.any(baseline_mask) and np.sum(baseline_mask) >= 3:
                baseline_intensities = original_intensity[baseline_mask]
                noise_level_baseline = np.std(baseline_intensities)
                # Use median of baseline as additional check
                baseline_median = np.median(baseline_intensities)
            else:
                noise_level_baseline = None
                baseline_median = 0
            
            # Method 2: Use lowest 10-20% of intensities as noise estimate
            sorted_intensities = np.sort(original_intensity)
            noise_cutoff = max(3, int(len(sorted_intensities) * 0.15))  # Use 15% instead of 20%
            lowest_intensities = sorted_intensities[:noise_cutoff]
            noise_level_percentile = np.std(lowest_intensities)
            
            # Method 3: Rolling minimum approach for noise floor
            if len(original_intensity) >= 5:
                try:
                    # Simple rolling minimum using numpy
                    window_size = min(5, len(original_intensity) // 3)
                    if window_size >= 3:
                        # Calculate rolling minimum manually
                        rolling_mins = []
                        for i in range(len(original_intensity) - window_size + 1):
                            window = original_intensity[i:i + window_size]
                            rolling_mins.append(np.min(window))
                        
                        if rolling_mins:
                            noise_level_rolling = np.std(rolling_mins)
                        else:
                            noise_level_rolling = noise_level_percentile
                    else:
                        noise_level_rolling = noise_level_percentile
                except:
                    noise_level_rolling = noise_level_percentile
            else:
                noise_level_rolling = noise_level_percentile
            
            # FIXED: Choose the most conservative (lowest) noise estimate
            # Lower noise estimate = higher S/N ratio for strong signals
            noise_estimates = [noise_level_percentile, noise_level_rolling]
            if noise_level_baseline is not None:
                noise_estimates.append(noise_level_baseline)
            
            # Remove any zero or negative noise estimates
            valid_noise_estimates = [n for n in noise_estimates if n > 0]
            
            if valid_noise_estimates:
                # Use the median of valid estimates to avoid outliers
                noise_level = np.median(valid_noise_estimates)
            else:
                # Fallback: use a small fraction of the signal as noise
                noise_level = signal_level * 0.01  # 1% of signal as fallback
            
            # FIXED: Ensure minimum noise level to avoid division by zero
            # But don't make it too high to avoid artificially low S/N
            min_noise_threshold = max(1.0, signal_level * 0.001)  # 0.1% of signal or 1.0, whichever is higher
            noise_level = max(noise_level, min_noise_threshold)
            
            # Calculate S/N ratio
            snr = signal_level / noise_level
            
            # DIAGNOSTIC: Log the calculation for debugging
            if hasattr(self, 'add_log'):
                self.add_log(f"S/N Calculation: Signal={signal_level:.1f}, Noise={noise_level:.2f}, S/N={snr:.1f}")
            
            # Reasonable bounds check
            if snr > 1000:  # Unreasonably high
                snr = signal_level / (signal_level * 0.01)  # Use 1% of signal as noise
            elif snr < 0.1:  # Unreasonably low
                snr = 1.0  # Default
            
            return snr
            
        except Exception as e:
            # Fallback calculation if everything fails
            if len(original_intensity) > 0 and np.max(smoothed_intensity) > 0:
                signal = np.max(smoothed_intensity)
                # Use 5% of maximum intensity as noise estimate
                noise = max(signal * 0.05, 1.0)
                fallback_snr = signal / noise
                if hasattr(self, 'add_log'):
                    self.add_log(f"S/N fallback calculation: {fallback_snr:.1f}")
                return fallback_snr
            else:
                return 1.0

    def debug_snr_calculation(self, rt_array, original_intensity, smoothed_intensity, precursor_rt, fragment_type):
        """Debug method to show detailed S/N calculation"""
        signal = np.max(smoothed_intensity)
        
        # Show different noise estimation methods
        baseline_mask = np.abs(rt_array - precursor_rt) > 1.0
        if np.any(baseline_mask):
            baseline_noise = np.std(original_intensity[baseline_mask])
            print(f"{fragment_type}: Baseline noise = {baseline_noise:.2f}")
        
        sorted_intensities = np.sort(original_intensity)
        percentile_noise = np.std(sorted_intensities[:int(len(sorted_intensities) * 0.15)])
        print(f"{fragment_type}: Percentile noise = {percentile_noise:.2f}")
        
        print(f"{fragment_type}: Signal = {signal:.1f}, Final S/N = {signal/max(baseline_noise, percentile_noise, 1.0):.1f}")
                    
    def toggle_fragment_interface(self):
        """Toggle the visibility of the fragment removal interface"""
        self.fragment_interface_visible = not self.fragment_interface_visible
        
        # Toggle visibility of interface elements
        self.fragment_tree.setVisible(self.fragment_interface_visible)
        self.auto_remove_df_btn.setVisible(self.fragment_interface_visible)
        self.restore_all_btn.setVisible(self.fragment_interface_visible)
        self.apply_removals_btn.setVisible(self.fragment_interface_visible)
        self.removal_stats_label.setVisible(self.fragment_interface_visible)
        
        # Update button text
        if self.fragment_interface_visible:
            self.show_fragments_btn.setText("Hide Fragment Removal Interface")
            self.populate_fragment_tree()
            self.update_removal_statistics()
        else:
            self.show_fragments_btn.setText("Show Fragment Removal Interface")

    def populate_fragment_tree(self):
        """Populate fragment tree with correct reproducibility information"""
        try:
            self.fragment_tree.clear()
            
            if self.current_matched_fragments.empty:
                return
            
            # Calculate fragment reproducibility across all files
            fragment_reproducibility = self._calculate_fragment_reproducibility()
            
            # DEBUG: Print what keys are actually in fragment_reproducibility
            if fragment_reproducibility:
                sample_keys = list(fragment_reproducibility.keys())[:5]  # First 5 keys
                self.add_log(f"DEBUG: Sample reproducibility keys: {sample_keys}")
            
            # Group by precursor
            grouped = self.current_matched_fragments.groupby(['Glycopeptides', 'Precursor_mz', 'precursor_rt'])
            
            for (glycopeptide, precursor_mz, precursor_rt), group in grouped:
                # Create precursor item
                precursor_item = QTreeWidgetItem([
                    glycopeptide,
                    str(len(group)),
                    f"{precursor_mz:.4f}",
                    "", "", "", 
                    f"RT: {precursor_rt:.2f}",
                    ""
                ])
                
                precursor_item.setFlags(precursor_item.flags() | Qt.ItemIsTristate)
                self.fragment_tree.addTopLevelItem(precursor_item)
                
                # Add fragment children with reproducibility data
                for _, fragment in group.iterrows():
                    fragment_type = fragment['Type']
                    theoretical_mz = fragment['Theoretical_mz']
                    grade = fragment.get('FDR_Grade', 'F')
                    
                    # Try different key formats to match what _calculate_fragment_reproducibility returns
                    possible_keys = [f"{glycopeptide}_{fragment_type}_{precursor_mz}_{precursor_rt}_{theoretical_mz:.4f}"
                    ]
                    
                    # Find which key format works
                    reproducibility_count = 1  # Default
                    used_key = None
                    
                    for key in possible_keys:
                        if key in fragment_reproducibility:
                            reproducibility_count = fragment_reproducibility[key]
                            used_key = key
                            break
                    
                    # DEBUG: Log which key was used (remove after fixing)
                    if used_key:
                        self.add_log(f"DEBUG: Found reproducibility for {fragment_type} using key: {used_key}")
                    else:
                        self.add_log(f"DEBUG: No reproducibility found for {fragment_type}, tried keys: {possible_keys[:3]}")
                    
                    total_files = len(self.all_analysis_results) if hasattr(self, 'all_analysis_results') else 1
                    reproducibility_text = f"{reproducibility_count}/{total_files}"
                    
                    fragment_item = QTreeWidgetItem([
                        fragment_type,
                        "", "",
                        fragment.get('FragmentType', 'Unknown'),
                        f"{theoretical_mz:.4f}",
                        grade,
                        "ACTIVE",
                        reproducibility_text
                    ])
                    
                    fragment_item.setFlags(fragment_item.flags() | Qt.ItemIsUserCheckable)
                    fragment_item.setCheckState(0, Qt.Unchecked)
                    
                    # Store data for removal
                    fragment_item.setData(0, Qt.UserRole, glycopeptide)
                    fragment_item.setData(0, Qt.UserRole + 1, precursor_mz)
                    fragment_item.setData(0, Qt.UserRole + 2, precursor_rt)
                    fragment_item.setData(0, Qt.UserRole + 3, fragment_type)
                    fragment_item.setData(0, Qt.UserRole + 4, theoretical_mz)
                    
                    # Color code based on reproducibility
                    if reproducibility_count == 1:
                        fragment_item.setBackground(7, QColor(255, 200, 200))
                    elif reproducibility_count < total_files * 0.5:
                        fragment_item.setBackground(7, QColor(255, 255, 200))
                    else:
                        fragment_item.setBackground(7, QColor(200, 255, 200))
                    
                    precursor_item.addChild(fragment_item)
            
            # Apply any existing removal states
            if hasattr(self, 'fragment_removal_states') and self.current_file_key in self.fragment_removal_states:
                self._apply_saved_removal_state(self.current_file_key)
            
            self.add_log(f"Fragment tree populated: {self.fragment_tree.topLevelItemCount()} precursors")
            
        except Exception as e:
            self.add_log(f"Error populating fragment tree: {e}")
            import traceback
            traceback.print_exc()

    def _setup_results_table_click_handler(self):
            """Setup click handler for results table"""
            try:
                # Connect mouse press event to our handler
                self.results_table.mousePressEvent = self.on_results_table_click
            except Exception as e:
                self.add_log(f"Warning: Could not setup results table click handler: {e}")

    def _uncheck_all_fragments_in_tree(self):
            """Uncheck all fragments in the fragment tree"""
            try:
                for i in range(self.fragment_tree.topLevelItemCount()):
                    precursor_item = self.fragment_tree.topLevelItem(i)
                    
                    for j in range(precursor_item.childCount()):
                        fragment_item = precursor_item.child(j)
                        fragment_item.setCheckState(0, Qt.Unchecked)
                        fragment_item.setText(6, "ACTIVE")  # Reset status column
                
                self.add_log("Unchecked all fragments in tree")
                
            except Exception as e:
                self.add_log(f"Error unchecking fragments: {e}")

    def _refresh_all_displays_after_restoration(self):
            """Refresh all displays after fragment restoration"""
            try:
                # Refresh fragment tree with current file data
                self.populate_fragment_tree()
                self.add_log("Refreshed fragment tree")
                
                # Refresh results table
                self.update_results_display()
                self.add_log("Refreshed results table")
                
                # Clear any EIC/MS2 plots if they exist
                if hasattr(self, 'eic_figure') and self.eic_figure:
                    self.eic_figure.clear()
                    if hasattr(self, 'eic_canvas'):
                        self.eic_canvas.draw()
                
                if hasattr(self, 'ms2_figure') and self.ms2_figure:
                    self.ms2_figure.clear()
                    if hasattr(self, 'ms2_canvas'):
                        self.ms2_canvas.draw()
                
                self.add_log("Cleared plot displays for refresh")
                
            except Exception as e:
                self.add_log(f"Error refreshing displays: {e}")

    ##--EIC/MS2 viewer methods--###
    def get_eic_parameters(self, glycopeptide=None):
        try:
            # Start with default parameters
            params = {
                'max_rt_window': 1.5,
                'back_window_ratio': 0.5,
                'display_time_extension': 5.0,
                'max_fragments_displayed': 20,
                'use_intensity_instead_of_area': False  # Add this default
            }
            
            # Get current GUI settings
            if hasattr(self, 'max_fragments_displayed') and self.max_fragments_displayed:
                params['max_fragments_displayed'] = self.max_fragments_displayed.value()
                print(f"DEBUG: Using user-set fragment count: {params['max_fragments_displayed']}")
            
            # CRITICAL FIX: Get the intensity setting from GUI
            if hasattr(self, 'use_intensity_instead_of_area') and self.use_intensity_instead_of_area:
                params['use_intensity_instead_of_area'] = self.use_intensity_instead_of_area.isChecked()
                print(f"DEBUG: Using intensity instead of area: {params['use_intensity_instead_of_area']}")
            
            # Apply other parameter customizations...
            if hasattr(self, 'rt_window') and self.rt_window:
                params['rt_window'] = self.rt_window.value()
            
            if hasattr(self, 'max_rt_window') and self.max_rt_window:
                params['max_rt_window'] = self.max_rt_window.value()
            
            if hasattr(self, 'back_window_ratio') and self.back_window_ratio:
                params['back_window_ratio'] = self.back_window_ratio.value()
            
            if hasattr(self, 'display_time_extension') and self.display_time_extension:
                params['display_time_extension'] = self.display_time_extension.value()
            
            return params
        except Exception as e:
            self.add_log(f"Error getting EIC parameters: {e}")
            return params  # Return what we have so far
        
    def generate_eic_for_display(self, matching_fragments, glycopeptide, precursor_mz, precursor_rt):
        """Generate EIC plot for display in the viewer - PARAMETER FIX"""

        try:            
            # Store original fragment count
            original_fragment_count = len(matching_fragments)
            print(f"DEBUG: Total fragments before EIC generation: {original_fragment_count}")
            
            print(f"DEBUG: Starting EIC generation for {glycopeptide}")
            
            # Get specific parameters for this glycopeptide - CRITICAL FIX
            params = self.get_eic_parameters(glycopeptide)
            print(f"DEBUG: Using parameters: {params}")
            
            max_fragments = params.get('max_fragments_displayed', 25)
            print(f"DEBUG: Using max fragments: {max_fragments}")

            # CRITICAL FIX: Ensure use_intensity_instead_of_area is properly passed
            use_intensity = params.get('use_intensity_instead_of_area', False)
            print(f"DEBUG: Using intensity instead of area: {use_intensity}")
            
            # Check if we have glycopeptide-specific parameters and apply them
            if hasattr(self, 'glycopeptide_specific_params') and glycopeptide in self.glycopeptide_specific_params:
                specific_params = self.glycopeptide_specific_params[glycopeptide]
                
                # Check if parameters are file-scoped and we're in the correct file
                if specific_params.get('file_scope', False):
                    current_file = self.current_file_key if hasattr(self, 'current_file_key') else None
                    specific_file = specific_params.get('file_key')
                    
                    # Only apply if global or matching current file
                    if not specific_file or specific_file == current_file:
                        # Override standard parameters with glycopeptide-specific ones
                        for key, value in specific_params.items():
                            if key not in ['file_scope', 'file_key']:
                                params[key] = value
                        print(f"DEBUG: Using glycopeptide-specific parameters for {glycopeptide}")
                else:
                    # Global parameters - apply regardless of file
                    for key, value in specific_params.items():
                        if key not in ['file_scope', 'file_key']:
                            params[key] = value
                    print(f"DEBUG: Using global glycopeptide-specific parameters for {glycopeptide}")
            
            # Use user-set fragment limit with fallback
            max_fragments = params.get('max_fragments_displayed', 25)
            print(f"DEBUG: Using max fragments setting from parameters: {max_fragments}")
            
            # Get row_id and ensure it's an integer to match cache format
            row_id = matching_fragments['row_id'].iloc[0] if 'row_id' in matching_fragments.columns else 0
            
            # Convert float row_id to int if needed (fixes key format mismatch)
            if isinstance(row_id, (float, np.float64, np.float32)):
                original_row_id = row_id
                row_id = int(row_id)
                print(f"DEBUG: Converted row_id from {original_row_id} to {row_id}")

            # Create composite key with standardized format
            composite_key = f"{precursor_mz}_{row_id}"
            print(f"DEBUG: Initial composite key: {composite_key}")
            
            # ENHANCED ERROR HANDLING FOR CACHED DATA LOOKUP
            if composite_key not in self.current_cached_data:
                print(f"DEBUG: Composite key '{composite_key}' not found in cached data.")
                print(f"DEBUG: Searching for alternative keys for precursor m/z {precursor_mz:.6f}")
                
                # Get all available keys for debugging
                all_keys = list(self.current_cached_data.keys())
                print(f"DEBUG: Available cached data keys ({len(all_keys)}): {all_keys[:10]}...")
                
                # Try direct format variations first
                format_variations = [
                    f"{precursor_mz}_{row_id}",  # Original format
                    f"{precursor_mz:.4f}_{row_id}",  # 4 decimal places
                    f"{precursor_mz:.6f}_{row_id}",  # 6 decimal places
                    f"{float(precursor_mz)}_{row_id}",  # Explicit float format
                ]
                
                for variation in format_variations:
                    if variation in self.current_cached_data:
                        composite_key = variation
                        print(f"DEBUG: Found direct match with format variation: {composite_key}")
                        break
                
                # If still not found, try more sophisticated matching strategies
                if composite_key not in self.current_cached_data:
                    # Try different matching strategies
                    alternative_keys = []
                    
                    # Strategy 1: Match by row_id priority
                    row_matches = []
                    for k in all_keys:
                        key_parts = str(k).split('_')
                        if len(key_parts) >= 2:
                            try:
                                key_row = int(float(key_parts[1]))  # Handle both int and float formats
                                key_mz = float(key_parts[0])
                                
                                # If row_id matches and m/z is close
                                if key_row == row_id and np.isclose(key_mz, precursor_mz, rtol=1e-4):
                                    row_matches.append(k)
                            except ValueError:
                                continue
                    
                    if row_matches:
                        print(f"DEBUG: Found {len(row_matches)} keys with matching row_id {row_id}")
                        alternative_keys.extend(row_matches)
                    
                    # Strategy 2: Simple string matching (original approach)
                    if not alternative_keys:
                        string_matches = [k for k in all_keys if str(precursor_mz) in str(k)]
                        if string_matches:
                            print(f"DEBUG: Found {len(string_matches)} keys containing '{precursor_mz}' as substring")
                            alternative_keys.extend(string_matches)
                    
                    # Strategy 3: Match using different precisions for the m/z value
                    if not alternative_keys:
                        for precision in range(2, 7):
                            formatted_mz = f"{precursor_mz:.{precision}f}"
                            precision_matches = [k for k in all_keys if formatted_mz in str(k)]
                            if precision_matches:
                                print(f"DEBUG: Found {len(precision_matches)} keys with '{formatted_mz}' (precision {precision})")
                                alternative_keys.extend(precision_matches)
                    
                    # Strategy 4: Try numerical matching with tolerance
                    if not alternative_keys:
                        try:
                            numerical_matches = []
                            for k in all_keys:
                                # Try to extract m/z part from composite key
                                key_parts = str(k).split('_')
                                if len(key_parts) >= 1:
                                    try:
                                        key_mz = float(key_parts[0])
                                        if np.isclose(key_mz, precursor_mz, rtol=1e-4):
                                            numerical_matches.append(k)
                                    except ValueError:
                                        continue
                            
                            if numerical_matches:
                                print(f"DEBUG: Found {len(numerical_matches)} keys with numerically similar m/z values")
                                alternative_keys.extend(numerical_matches)
                        except Exception as e:
                            print(f"DEBUG: Error during numerical matching: {e}")
                    
                    # Remove duplicates
                    alternative_keys = list(dict.fromkeys(alternative_keys))
                    
                    if alternative_keys:
                        # Select the best matching key
                        composite_key = alternative_keys[0]
                        print(f"DEBUG: Using alternative key '{composite_key}' instead of original key")
                        
                        # Extract and update row_id from the selected key for consistency
                        try:
                            key_parts = str(composite_key).split('_')
                            if len(key_parts) >= 2:
                                selected_row_id = int(float(key_parts[1]))
                                print(f"DEBUG: Updated row_id from {row_id} to {selected_row_id} based on selected key")
                                
                                # Create a copy of matching_fragments with updated row_id
                                if 'row_id' in matching_fragments.columns:
                                    matching_fragments = matching_fragments.copy()
                                    matching_fragments['row_id'] = selected_row_id
                                    #print(f"DEBUG: Number of fragments after updating row_id: {len(matching_fragments)}")
                        except Exception as e:
                            print(f"DEBUG: Error extracting row_id from key: {e}")
                    else:
                        # Create detailed error message
                        error_msg = (
                            f"No EIC data available for {glycopeptide}\n\n"
                            f"• Precursor m/z: {precursor_mz:.6f}\n"
                            f"• RT: {precursor_rt:.2f} min\n"
                            f"• Row ID: {row_id}\n"
                            f"• Searched key: {composite_key}\n"
                            f"• Available keys: {len(all_keys)}\n"
                            f"• Fragment count: {len(matching_fragments)}"
                        )
                        print(f"ERROR: {error_msg}")
                        
                        # Style the error message with HTML formatting
                        styled_error = f"""
                        <div style='background-color:#fff0f0; padding:10px; border-left:4px solid #d9534f;'>
                            <h3 style='color:#d9534f; margin-top:0;'>No EIC Data Available</h3>
                            <p><b>Glycopeptide:</b> {glycopeptide}</p>
                            <p><b>Precursor m/z:</b> {precursor_mz:.6f}</p>
                            <p><b>RT:</b> {precursor_rt:.2f} min</p>
                            <p><b>Row ID:</b> {row_id}</p>
                            <p><b>Available cached keys:</b> {len(all_keys)}</p>
                            <p><b>Fragment count:</b> {len(matching_fragments)}</p>
                        </div>
                        """
                        
                        self.plot_area.setText(styled_error)
                        return
            
            # Create cached data with exactly the key we found
            if composite_key in self.current_cached_data:
                cached_data = {composite_key: self.current_cached_data[composite_key]}
                print(f"DEBUG: Using cached data with key {composite_key}")
            else:
                self.plot_area.setText(f"Internal error: Key {composite_key} lost during processing")
                return
            
            # Clear any existing plots
            plt.close('all')
            
            try:
                # Split glycopeptide properly
                if '-' in glycopeptide:
                    peptide = glycopeptide.split('-')[0]
                    glycan = glycopeptide.split('-')[1]
                else:
                    peptide = None
                    glycan = glycopeptide

                # Generate EIC plot with proper parameter passing
                figures = plot_fragment_eics(
                    cached_data,
                    matching_fragments,
                    glycan,
                    peptide,
                    rt_window=params.get('rt_window', 5.0),
                    max_rt_window=params.get('max_rt_window', 1.5),
                    use_strict_rt_window=params.get('use_strict_rt_window', True),
                    use_provided_rt=params.get('use_provided_rt', True),
                    back_window_ratio=params.get('back_window_ratio', 0.5),
                    output_dir=None,
                    display_time_extension=params.get('display_time_extension', 5.0),
                    use_intensity_instead_of_area=use_intensity,  # CRITICAL FIX: Pass this parameter
                    fragment_types=params.get('fragment_types', "all"),
                    max_fragments_displayed=max_fragments
                )
                
                #print(f"DEBUG: Number of fragments after updating row_id: {len(matching_fragments)}")
                
                if figures and composite_key in figures:
                    figure = figures[composite_key]
                    
                    # Fix the title in the figure to show correct metric
                    metric_name = "Intensity" if use_intensity else "Area"
                    for ax in figure.axes:
                        title = ax.get_title()
                        if "Showing top" in title:
                            # Extract the fragments shown count
                            max_frags = int(title.split("Showing top ")[1].split(" of")[0])
                            # Create new title with correct total count and metric
                            new_title = re.sub(
                                r"Showing top (\d+) of \d+", 
                                f"Showing top {max_frags} of {original_fragment_count}", 
                                title
                            )
                            # Also update any "Total Area" references to "Total Intensity" if needed
                            if use_intensity:
                                new_title = new_title.replace("Total Area", "Total Intensity")
                            ax.set_title(new_title)
                        
                        # Fix legend labels if they exist
                        legend = ax.get_legend()
                        if legend and use_intensity:
                            for text in legend.get_texts():
                                label = text.get_text()
                                if "Total Area" in label:
                                    text.set_text(label.replace("Total Area", "Total Intensity"))
                    
                    # Update the figure in the dictionary
                    figures[composite_key] = figure
                    
                    # Convert matplotlib figure to QPixmap for display
                    buf = io.BytesIO()
                    figure.savefig(buf, format='png', dpi=100, bbox_inches='tight', 
                                facecolor='white', edgecolor='none')
                    buf.seek(0)
                    
                    # Create QPixmap from buffer
                    pixmap = QPixmap()
                    pixmap.loadFromData(buf.getvalue())
                    
                    if not pixmap.isNull():
                        print(f"DEBUG: Created pixmap successfully, size: {pixmap.size()}")
                        
                        # Scale pixmap to fit the label while maintaining aspect ratio
                        label_size = self.plot_area.size()
                        scaled_pixmap = pixmap.scaled(
                            label_size, 
                            Qt.KeepAspectRatio, 
                            Qt.SmoothTransformation
                        )
                        
                        # Set the pixmap to the label
                        self.plot_area.setPixmap(scaled_pixmap)
                        
                        # Store the figure reference
                        self.current_figure = figure
                    else:
                        self.plot_area.setText("Error creating EIC plot image")
                    
                    buf.close()
                else:
                    available_keys = list(figures.keys()) if figures else []
                    self.plot_area.setText(
                        f"Failed to generate EIC plot for {glycopeptide}\n"
                        f"Composite key: {composite_key}\n"
                        f"Available figure keys: {available_keys}"
                    )
            
            except Exception as plot_error:
                print(f"DEBUG: EIC plot generation error: {plot_error}")
                import traceback
                traceback.print_exc()
                self.plot_area.setText(f"Error generating EIC plot: {str(plot_error)}")
            
            # Clean up
            plt.close('all')
            
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            print(f"DEBUG: generate_eic_for_display error: {error_msg}")
            import traceback
            traceback.print_exc()
            self.plot_area.setText(error_msg)
            
    def show_eic_for_glycopeptide(self, glycopeptide, precursor_mz, precursor_rt, row_id=None):
        """Show plot for the selected glycopeptide based on current viewer mode"""
        try:
            if self.current_matched_fragments.empty:
                return
            
            # Create base filter conditions
            conditions = [
                (self.current_matched_fragments['Glycopeptides'] == glycopeptide),
                (np.isclose(self.current_matched_fragments['Precursor_mz'], precursor_mz, rtol=1e-4)),
                (np.isclose(self.current_matched_fragments['precursor_rt'], precursor_rt, rtol=1e-2))
            ]
            
            # Add row_id filter if provided
            if row_id is not None and 'row_id' in self.current_matched_fragments.columns:
                conditions.append(self.current_matched_fragments['row_id'] == row_id)
            
            # Apply all conditions
            matching_fragments = self.current_matched_fragments[
                np.logical_and.reduce(conditions)
            ]
            
            if matching_fragments.empty:
                self.plot_info_label.setText(f"No fragments found for {glycopeptide} (Row: {row_id})")
                return
            
            # Get row_id for display and key generation
            actual_row_id = matching_fragments['row_id'].iloc[0] if 'row_id' in matching_fragments.columns else 0
            
            # Update info label with row_id included
            num_fragments = len(matching_fragments)
            avg_score = matching_fragments['Fragments_Score'].mean() if 'Fragments_Score' in matching_fragments.columns else 0
            best_grade = matching_fragments['FDR_Grade'].mode().iloc[0] if 'FDR_Grade' in matching_fragments.columns and not matching_fragments['FDR_Grade'].empty else "N/A"
            
            mode_text = "EIC" if self.current_viewer_mode == 'eic' else "MS2"
            self.plot_info_label.setText(
                f"{mode_text} for {glycopeptide} | Row: {actual_row_id} | m/z: {precursor_mz:.4f} | RT: {precursor_rt:.2f} min | "
                f"Fragments: {num_fragments} | Avg Score: {avg_score:.1f}"
            )
            
            # Update fragment quality indicator
            if best_grade in ['A', 'B']:
                quality_color = "#27ae60"  # Green
                quality_text = "HIGH QUALITY"
            elif best_grade in ['C']:
                quality_color = "#f39c12"  # Orange
                quality_text = "MEDIUM QUALITY"
            elif best_grade in ['D']:
                quality_color = "#e67e22"  # Dark orange
                quality_text = "LOW QUALITY"
            else:
                quality_color = "#e74c3c"  # Red
                quality_text = "POOR QUALITY"
            
            self.fragment_quality_label.setText(quality_text)
            self.fragment_quality_label.setStyleSheet(f"""
                font-size: 11px; 
                font-weight: bold; 
                padding: 4px 8px; 
                border-radius: 3px;
                background-color: {quality_color};
                color: white;
            """)
            
            # Generate and display plot based on current mode
            if self.current_viewer_mode == 'eic':
                self.generate_eic_for_display(matching_fragments, glycopeptide, precursor_mz, precursor_rt)
            else:
                self.generate_ms2_for_display(matching_fragments, glycopeptide, precursor_mz, precursor_rt)

            # Store current selection with row_id
            self.selected_glycopeptide = {
                'name': glycopeptide,
                'precursor_mz': precursor_mz,
                'precursor_rt': precursor_rt,
                'row_id': actual_row_id,
                'fragments': matching_fragments
            }
            
            # Enable and update the EIC parameter controls for this glycopeptide
            if hasattr(self, 'enable_eic_parameter_controls'):
                self.enable_eic_parameter_controls(True)
                self.update_eic_parameter_controls(glycopeptide)
        
            
            # Enable plot controls
            self.refresh_plot_btn.setEnabled(True)
            self.save_plot_btn.setEnabled(True)
            
        except Exception as e:
            self.plot_info_label.setText(f"Error showing plot: {str(e)}")
            print(f"Error in show_eic_for_glycopeptide: {e}")

    def create_eic_parameter_controls(self):
        """Create controls for adjusting EIC plot parameters"""
        # Create the parameters panel
        params_group = QGroupBox("EIC Plot Parameters")
        params_layout = QGridLayout()
        
        # Max RT Window control
        self.max_rt_window_label = QLabel("Max RT Window (min):")
        self.max_rt_window_spinner = QDoubleSpinBox()
        self.max_rt_window_spinner.setRange(0.1, 10.0)
        self.max_rt_window_spinner.setSingleStep(0.1)
        self.max_rt_window_spinner.setValue(1.5)
        self.max_rt_window_spinner.setToolTip("Maximum retention time window to display (minutes)")
        
        # Back Window Ratio control
        self.back_window_ratio_label = QLabel("Back Window Ratio:")
        self.back_window_ratio_spinner = QDoubleSpinBox()
        self.back_window_ratio_spinner.setRange(0.0, 1.0)
        self.back_window_ratio_spinner.setSingleStep(0.05)
        self.back_window_ratio_spinner.setValue(0.5)
        self.back_window_ratio_spinner.setToolTip("Ratio of the window to display before the retention time")
        
        # Display Time Extension control
        self.display_time_ext_label = QLabel("Display Time Extension (min):")
        self.display_time_ext_spinner = QDoubleSpinBox()
        self.display_time_ext_spinner.setRange(0.0, 10.0)
        self.display_time_ext_spinner.setSingleStep(0.5)
        self.display_time_ext_spinner.setValue(5.0)
        self.display_time_ext_spinner.setToolTip("Extra time to display on each side of the RT window")
        
        # Apply buttons
        self.apply_params_current_btn = QPushButton("Apply to Current")
        self.apply_params_current_btn.setToolTip("Apply parameters to current glycopeptide only")
        self.apply_params_current_btn.clicked.connect(self.apply_eic_params_to_current)
        
        self.apply_params_global_btn = QPushButton("Apply Globally")
        self.apply_params_global_btn.setToolTip("Apply parameters to all instances of this glycopeptide")
        self.apply_params_global_btn.clicked.connect(self.apply_eic_params_globally)
        
        # Reset button
        self.reset_params_btn = QPushButton("Reset to Default")
        self.reset_params_btn.setToolTip("Reset parameters to default values")
        self.reset_params_btn.clicked.connect(self.reset_eic_params)
        
        # Add to layout
        params_layout.addWidget(self.max_rt_window_label, 0, 0)
        params_layout.addWidget(self.max_rt_window_spinner, 0, 1)
        params_layout.addWidget(self.back_window_ratio_label, 1, 0)
        params_layout.addWidget(self.back_window_ratio_spinner, 1, 1)
        params_layout.addWidget(self.display_time_ext_label, 2, 0)
        params_layout.addWidget(self.display_time_ext_spinner, 2, 1)
        
        # Buttons in a horizontal layout
        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(self.apply_params_current_btn)
        buttons_layout.addWidget(self.apply_params_global_btn)
        buttons_layout.addWidget(self.reset_params_btn)
        
        params_layout.addLayout(buttons_layout, 3, 0, 1, 2)
        params_group.setLayout(params_layout)
        
        # Initially disable until a glycopeptide is selected
        self.enable_eic_parameter_controls(False)
        
        return params_group

    def refresh_current_eic(self):
        """Refresh the currently displayed EIC - FIXED VERSION"""
        if not self.selected_glycopeptide:
            QMessageBox.warning(self, "No EIC", "No EIC currently selected to refresh.")
            return
        
        try:
            self.add_log("Refreshing EIC display...")
            
            # Clear the current display
            self.eic_plot_area.clear()
            self.eic_plot_area.setText("Refreshing EIC...")
            
            # Regenerate the EIC display
            self.generate_eic_for_display(
                self.selected_glycopeptide['fragments'],
                self.selected_glycopeptide['name'],
                self.selected_glycopeptide['precursor_mz'],
                self.selected_glycopeptide['precursor_rt']
            )
            
            self.add_log("EIC refreshed successfully")
            
        except Exception as e:
            error_msg = f"Failed to refresh EIC: {str(e)}"
            self.eic_plot_area.setText("Error refreshing EIC")
            self.add_log(f"Error refreshing EIC: {error_msg}")
            QMessageBox.critical(self, "Refresh Error", error_msg)
            import traceback
            traceback.print_exc()
    
    def save_current_eic(self):
        """Save the current EIC to file - ENHANCED VERSION WITH USER PARAMETERS"""
        if not self.selected_glycopeptide:
            QMessageBox.warning(self, "No EIC", "No EIC currently displayed to save.")
            return
        
        try:
            # Get default filename
            glycopeptide_name = self.selected_glycopeptide['name'].replace('/', '_').replace('\\', '_')
            default_filename = f"EIC_{glycopeptide_name}.png"
            
            filename, _ = QFileDialog.getSaveFileName(
                self, "Save EIC Plot", 
                default_filename, 
                "PNG files (*.png);;SVG files (*.svg);;PDF files (*.pdf);;All files (*.*)"
            )
            
            if filename:
                # Get user parameters - ADDED
                params = self.get_parameters() if hasattr(self, 'get_parameters') else {}
                
                # Check for glycopeptide-specific parameters - ADDED
                glycopeptide = self.selected_glycopeptide['name']
                if hasattr(self, 'glycopeptide_specific_params') and glycopeptide in self.glycopeptide_specific_params:
                    specific_params = self.glycopeptide_specific_params[glycopeptide]
                    # Override with specific parameters
                    for key, value in specific_params.items():
                        if key not in ['file_scope', 'file_key']:
                            params[key] = value
                    self.add_log(f"Using glycopeptide-specific parameters for saving")
                
                # Method 1: If we have a current figure stored, save it directly
                if hasattr(self, 'current_figure') and self.current_figure:
                    self.current_figure.savefig(filename, dpi=300, bbox_inches='tight')
                    QMessageBox.information(self, "EIC Saved", f"EIC saved to:\n{filename}")
                    self.add_log(f"EIC saved to: {filename}")
                    return
                
                # Method 2: Regenerate and save the plot
                matching_fragments = self.selected_glycopeptide['fragments']
                precursor_mz = self.selected_glycopeptide['precursor_mz']
                precursor_rt = self.selected_glycopeptide['precursor_rt']
                
                # Get cached data
                row_id = matching_fragments['row_id'].iloc[0] if 'row_id' in matching_fragments.columns else 0
                composite_key = f"{precursor_mz}_{row_id}"
                
                # Try to find the right cached data key
                if composite_key not in self.current_cached_data:
                    alternative_keys = [k for k in self.current_cached_data.keys() if str(precursor_mz) in str(k)]
                    if alternative_keys:
                        composite_key = alternative_keys[0]
                    else:
                        QMessageBox.warning(self, "Save Error", "No EIC data available for saving.")
                        return
                
                cached_data = {composite_key: self.current_cached_data[composite_key]}
                
                # Split glycopeptide name
                if '-' in glycopeptide:
                    peptide = glycopeptide.split('-')[0]
                    glycan = glycopeptide.split('-')[1]
                else:
                    peptide = None
                    glycan = glycopeptide
                
                # Generate plot and save with user parameters - MODIFIED
                figures = plot_fragment_eics(
                    cached_data, 
                    matching_fragments,
                    glycan,  # glycan code
                    peptide,  # peptide sequence
                    rt_window=params.get('rt_window', 5.0),
                    max_rt_window=params.get('max_rt_window', 1.5),
                    use_strict_rt_window=params.get('use_strict_rt_window', True),
                    use_provided_rt=params.get('use_provided_rt', True),
                    back_window_ratio=params.get('back_window_ratio', 0.5),
                    output_dir=os.path.dirname(filename),
                    display_time_extension=params.get('display_time_extension', 5.0),
                    use_intensity_instead_of_area=params.get('use_intensity_instead_of_area', False),
                    fragment_types=params.get('fragment_types', "all"),
                    max_fragments_displayed=params.get('max_fragments_displayed',20)
                )
                
                # Save the generated figure
                if figures and composite_key in figures:
                    figure = figures[composite_key]
                    figure.savefig(filename, dpi=300, bbox_inches='tight')
                    QMessageBox.information(self, "EIC Saved", f"EIC saved to:\n{filename}")
                    self.add_log(f"EIC saved using parameters: max_rt_window={params.get('max_rt_window', 1.5)}, " + 
                                f"back_window_ratio={params.get('back_window_ratio', 0.5)}, " +
                                f"display_time_extension={params.get('display_time_extension', 5.0)}")
                else:
                    QMessageBox.warning(self, "Save Error", "Failed to generate EIC for saving.")
                    
        except Exception as e:
            error_msg = f"Failed to save EIC: {str(e)}"
            QMessageBox.critical(self, "Save Error", error_msg)
            self.add_log(f"Error saving EIC: {error_msg}")
            import traceback
            traceback.print_exc()
                                                  
    def generate_ms2_for_display(self, matching_fragments, glycopeptide, precursor_mz, precursor_rt):
        """Generate MS2 plot for display in the viewer"""
        try:
            # Get user parameters from settings
            params = self.get_eic_parameters(glycopeptide)
            
            # REMOVED: Don't override max_fragments_displayed with display_time_extension
            # Use the value directly from params (default 20)
            max_fragments = params.get('max_fragments_displayed', 25)
            print(f"DEBUG: Using max fragments for MS2: {max_fragments}")
            
            # Get row_id for composite key - IMPORTANT
            row_id = matching_fragments['row_id'].iloc[0] if 'row_id' in matching_fragments.columns else 0
            composite_key = f"{precursor_mz}_{row_id}"
            
            print(f"DEBUG: Using composite key {composite_key} for {glycopeptide}")
            
            if composite_key not in self.current_cached_data:
                # More sophisticated key matching - try finding keys with matching row_id
                alternative_keys = []
                
                # Try keys that match both the m/z (approximately) and exact row_id
                for k in self.current_cached_data.keys():
                    key_parts = str(k).split('_')
                    if len(key_parts) >= 2:
                        key_mz = float(key_parts[0])
                        key_row = int(key_parts[1])
                        
                        # Match on both approximate m/z and exact row_id
                        if np.isclose(key_mz, precursor_mz, rtol=1e-4) and key_row == row_id:
                            alternative_keys.append(k)
                            break
                
                # If no match with row_id, try just m/z as fallback
                if not alternative_keys:
                    alternative_keys = [k for k in self.current_cached_data.keys() 
                                    if np.isclose(float(str(k).split('_')[0]), precursor_mz, rtol=1e-4)]
                
                if alternative_keys:
                    composite_key = alternative_keys[0]
                    print(f"DEBUG: Found alternative key {composite_key}")
                else:
                    self.plot_area.setText(f"No MS2 data available for {glycopeptide} (Row: {row_id})")
                    return
            
            cached_data = {composite_key: self.current_cached_data[composite_key]}
            
            # Clear any existing plots
            plt.close('all')
            
            try:
                # Split glycopeptide properly
                if '-' in glycopeptide:
                    peptide = glycopeptide.split('-')[0]
                    glycan = glycopeptide.split('-')[1]
                else:
                    peptide = None
                    glycan = glycopeptide
                
                # Generate MS2 plot
                figures = plot_ms2_spectra(
                    cached_data,
                    matching_fragments,
                    glycan,
                    peptide,
                    output_dir=None,
                    max_fragments_displayed=max_fragments 
                    #intensity_threshold=params.get('intensity_threshold', 0),
                )
                
                if figures and composite_key in figures:
                    figure = figures[composite_key]
                    
                    # Convert matplotlib figure to QPixmap for display
                    buf = io.BytesIO()
                    figure.savefig(buf, format='png', dpi=100, bbox_inches='tight', 
                                facecolor='white', edgecolor='none')
                    buf.seek(0)
                    
                    # Create QPixmap from buffer
                    pixmap = QPixmap()
                    pixmap.loadFromData(buf.getvalue())
                    
                    if not pixmap.isNull():
                        # Scale pixmap to fit the label while maintaining aspect ratio
                        label_size = self.plot_area.size()
                        scaled_pixmap = pixmap.scaled(
                            label_size, 
                            Qt.KeepAspectRatio, 
                            Qt.SmoothTransformation
                        )
                        
                        # Set the pixmap to the label
                        self.plot_area.setPixmap(scaled_pixmap)
                        
                        # Store the figure reference
                        self.current_figure = figure
                    else:
                        self.plot_area.setText("Error creating MS2 plot image")
                    
                    buf.close()
                else:
                    self.plot_area.setText("Failed to generate MS2 plot")
            
            except Exception as plot_error:
                print(f"DEBUG: MS2 plot generation error: {plot_error}")
                self.plot_area.setText(f"Error generating MS2 plot: {str(plot_error)}")
            
            # Clean up
            plt.close('all')
            
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            print(f"DEBUG: generate_ms2_for_display error: {error_msg}")
            self.plot_area.setText(error_msg)

    def refresh_current_plot(self):
        """Refresh the currently displayed plot"""
        try:
            if hasattr(self, 'selected_fragment') and self.selected_fragment:
                # Refresh fragment-specific plot
                fragment_row = self.selected_fragment['fragment_row']
                glycopeptide = self.selected_fragment['glycopeptide']
                precursor_mz = self.selected_fragment['precursor_mz']
                precursor_rt = self.selected_fragment['precursor_rt']
                
                #self._create_fragment_specific_plot(fragment_row, glycopeptide, precursor_mz, precursor_rt)
                self.add_log("Refreshed fragment-specific plot")
                
            elif hasattr(self, 'selected_glycopeptide') and self.selected_glycopeptide:
                # Refresh precursor EIC plot
                glycopeptide = self.selected_glycopeptide['name']
                precursor_mz = self.selected_glycopeptide['precursor_mz']
                precursor_rt = self.selected_glycopeptide['precursor_rt']
                row_id = self.selected_glycopeptide.get('row_id')
                
                self.show_eic_for_glycopeptide(glycopeptide, precursor_mz, precursor_rt, row_id)
                self.add_log("Refreshed precursor EIC plot")
                
            else:
                self.add_log("No plot to refresh")
                
        except Exception as e:
            self.add_log(f"Error refreshing plot: {e}")
    
    def save_current_plot(self):
        """Save the current plot (EIC or MS2) to file - ENHANCED VERSION WITH USER PARAMETERS"""
        if not self.selected_glycopeptide:
            QMessageBox.warning(self, "No Plot", "No plot currently displayed to save.")
            return
        
        try:
            # Get default filename based on plot type
            glycopeptide_name = self.selected_glycopeptide['name'].replace('/', '_').replace('\\', '_')
            plot_type = self.current_viewer_mode.upper()
            default_filename = f"{plot_type}_{glycopeptide_name}.png"
            
            filename, _ = QFileDialog.getSaveFileName(
                self, f"Save {plot_type} Plot", 
                default_filename, 
                "PNG files (*.png);;SVG files (*.svg);;PDF files (*.pdf);;All files (*.*)"
            )
            
            if filename:
                # Get user parameters - ADDED
                params = self.get_parameters() if hasattr(self, 'get_parameters') else {}
                
                # Check for glycopeptide-specific parameters - ADDED
                glycopeptide = self.selected_glycopeptide['name']
                if hasattr(self, 'glycopeptide_specific_params') and glycopeptide in self.glycopeptide_specific_params:
                    specific_params = self.glycopeptide_specific_params[glycopeptide]
                    # Override with specific parameters
                    for key, value in specific_params.items():
                        if key not in ['file_scope', 'file_key']:
                            params[key] = value
                    self.add_log(f"Using glycopeptide-specific parameters for saving {plot_type}")
                
                # Method 1: If we have a current figure stored, save it directly
                if hasattr(self, 'current_figure') and self.current_figure:
                    self.current_figure.savefig(filename, dpi=300, bbox_inches='tight')
                    QMessageBox.information(self, f"{plot_type} Saved", f"{plot_type} saved to:\n{filename}")
                    self.add_log(f"{plot_type} saved to: {filename}")
                    return
                
                # Method 2: Regenerate and save the plot
                matching_fragments = self.selected_glycopeptide['fragments']
                precursor_mz = self.selected_glycopeptide['precursor_mz']
                precursor_rt = self.selected_glycopeptide['precursor_rt']
                
                # Get cached data
                row_id = matching_fragments['row_id'].iloc[0] if 'row_id' in matching_fragments.columns else 0
                composite_key = f"{precursor_mz}_{row_id}"
                
                if composite_key not in self.current_cached_data:
                    alternative_keys = [k for k in self.current_cached_data.keys() if str(precursor_mz) in str(k)]
                    if alternative_keys:
                        composite_key = alternative_keys[0]
                    else:
                        QMessageBox.warning(self, "Save Error", f"No {plot_type} data available for saving.")
                        return
                
                cached_data = {composite_key: self.current_cached_data[composite_key]}
                
                # Split glycopeptide name
                if '-' in glycopeptide:
                    peptide = glycopeptide.split('-')[0]
                    glycan = glycopeptide.split('-')[1]
                else:
                    peptide = None
                    glycan = glycopeptide
                
                # Generate and save plot based on current mode - MODIFIED TO USE PARAMETERS
                if self.current_viewer_mode == 'eic':
                    figures = plot_fragment_eics(
                        cached_data, 
                        matching_fragments, 
                        glycan, 
                        peptide,
                        rt_window=params.get('rt_window', 5.0),
                        max_rt_window=params.get('max_rt_window', 1.5),
                        use_strict_rt_window=params.get('use_strict_rt_window', True),
                        use_provided_rt=params.get('use_provided_rt', True),
                        back_window_ratio=params.get('back_window_ratio', 0.5),
                        output_dir=os.path.dirname(filename),
                        display_time_extension=params.get('display_time_extension', 5.0),
                        use_intensity_instead_of_area=params.get('use_intensity_instead_of_area', False),
                        fragment_types=params.get('fragment_types', "all"),
                        max_fragments_displayed=params.get('max_fragments_displayed', 25)
                    )
                    
                    # Log parameters used for EIC
                    self.add_log(f"EIC parameters: max_rt_window={params.get('max_rt_window', 1.5)}, " + 
                                f"back_window_ratio={params.get('back_window_ratio', 0.5)}, " +
                                f"display_time_extension={params.get('display_time_extension', 5.0)}")
                else:
                    figures = plot_ms2_spectra(
                        cached_data, 
                        matching_fragments, 
                        glycan, 
                        peptide,
                        output_dir=os.path.dirname(filename), 
                        max_fragments_displayed=params.get('max_fragments_displayed', 25),
                        intensity_threshold=params.get('intensity_threshold', 1000),
                        mass_accuracy=params.get('mass_accuracy', 0.02)
                    )
                    
                    # Log parameters used for MS2
                    self.add_log(f"MS2 parameters: max_fragments={params.get('max_fragments_displayed', 30)}, " +
                                f"intensity_threshold={params.get('intensity_threshold', 1000)}")
                
                # Save the generated figure
                if figures and composite_key in figures:
                    figure = figures[composite_key]
                    figure.savefig(filename, dpi=300, bbox_inches='tight')
                    QMessageBox.information(self, f"{plot_type} Saved", f"{plot_type} saved to:\n{filename}")
                    self.add_log(f"{plot_type} saved to: {filename}")
                else:
                    QMessageBox.warning(self, "Save Error", f"Failed to generate {plot_type} for saving.")
                    
        except Exception as e:
            error_msg = f"Failed to save {self.current_viewer_mode.upper()}: {str(e)}"
            QMessageBox.critical(self, "Save Error", error_msg)
            self.add_log(f"Error saving plot: {error_msg}")
            import traceback
            traceback.print_exc()
                    
    ##Manupulation of EIC parameters##
    def enable_eic_parameter_controls(self, enabled=True):
            """Enable or disable the EIC parameter controls"""
            self.max_rt_window_spinner.setEnabled(enabled)
            self.back_window_ratio_spinner.setEnabled(enabled)
            self.display_time_ext_spinner.setEnabled(enabled)
            self.apply_params_current_btn.setEnabled(enabled)
            self.apply_params_global_btn.setEnabled(enabled)
            self.reset_params_btn.setEnabled(enabled)

    def recalculate_fragment_area_with_new_params(self, glycopeptide, precursor_mz, precursor_rt, 
                                                fragment_type, new_params, ms2_ppm_tolerance=20):
        """Recalculate fragment area using new parameters and original data points - FIXED"""
        try:
            # Get the original cached data for this precursor
            if not hasattr(self, 'current_cached_data') or not self.current_cached_data:
                self.add_log("No cached data available for recalculation")
                return None
            
            # Find the row_id for this glycopeptide
            matching_fragments = self.current_matched_fragments[
                (self.current_matched_fragments['Glycopeptides'] == glycopeptide) &
                (np.isclose(self.current_matched_fragments['Precursor_mz'], precursor_mz, rtol=1e-4)) &
                (np.isclose(self.current_matched_fragments['precursor_rt'], precursor_rt, rtol=1e-2)) &
                (self.current_matched_fragments['Type'] == fragment_type)
            ]
            
            if matching_fragments.empty:
                self.add_log(f"No matching fragment found for {fragment_type}")
                return None
                
            try:
                row_id = str(int(matching_fragments.iloc[0]['row_id']))
                composite_key = f"{precursor_mz}_{row_id}"
            except (KeyError, ValueError, TypeError) as e:
                self.add_log(f"Error extracting row_id: {e}")
                return None
            
            if composite_key not in self.current_cached_data:
                # Try alternative key matching
                available_keys = list(self.current_cached_data.keys())
                matching_keys = [key for key in available_keys if key.endswith(f"_{row_id}")]
                
                if matching_keys:
                    composite_key = matching_keys[0]
                    self.add_log(f"Using alternative key: {composite_key}")
                else:
                    self.add_log(f"No cached data for key {composite_key}")
                    return None
                
            data = self.current_cached_data[composite_key]
            
            try:
                fragment_mz = float(matching_fragments.iloc[0]['Theoretical_mz'])
            except (KeyError, ValueError, TypeError) as e:
                self.add_log(f"Error extracting fragment m/z: {e}")
                return None
            
            # Calculate new quantification window
            try:
                windows = self.calculate_quantification_window(precursor_rt, new_params)
            except Exception as e:
                self.add_log(f"Error calculating quantification window: {e}")
                return None
            
            # STEP 1: Collect ALL matching data points (with error handling)
            all_rt_values = []
            all_intensity_values = []
            ms2_ppm_tolerance = ms2_ppm_tolerance
            
            try:
                for rt, fragments_array, intensities_array in zip(
                    data['retention_times'], data['fragments'], data['intensities']
                ):
                    if len(fragments_array) == 0 or len(intensities_array) == 0:
                        continue
                    
                    # Ensure arrays are numpy arrays
                    if not isinstance(fragments_array, np.ndarray):
                        fragments_array = np.array(fragments_array)
                    if not isinstance(intensities_array, np.ndarray):
                        intensities_array = np.array(intensities_array)
                    
                    # Find ALL fragments within PPM tolerance in this scan
                    tolerance_mz = fragment_mz * (ms2_ppm_tolerance / 1e6)
                    matches = np.where(np.abs(fragments_array - fragment_mz) <= tolerance_mz)[0]
                    
                    # Add ALL matching fragments from this scan
                    for match_idx in matches:
                        try:
                            rt_val = float(rt)
                            intensity_val = float(intensities_array[match_idx])
                            if not (np.isnan(rt_val) or np.isnan(intensity_val) or np.isinf(rt_val) or np.isinf(intensity_val)):
                                all_rt_values.append(rt_val)
                                all_intensity_values.append(intensity_val)
                        except (ValueError, TypeError, IndexError):
                            continue
            
            except Exception as e:
                self.add_log(f"Error collecting data points: {e}")
                return None
            
            if not all_rt_values:
                self.add_log("No valid data points found")
                return None
            
            # STEP 2: Convert to arrays and sort by RT
            try:
                rt_array = np.array(all_rt_values, dtype=np.float64)
                intensity_array = np.array(all_intensity_values, dtype=np.float64)
                
                # Remove any NaN or infinite values
                valid_mask = np.isfinite(rt_array) & np.isfinite(intensity_array)
                rt_array = rt_array[valid_mask]
                intensity_array = intensity_array[valid_mask]
                
                if len(rt_array) == 0:
                    self.add_log("No valid data points after filtering")
                    return None
                
                # Sort by RT to ensure proper integration
                sort_indices = np.argsort(rt_array)
                rt_array = rt_array[sort_indices]
                intensity_array = intensity_array[sort_indices]
                
            except Exception as e:
                self.add_log(f"Error processing arrays: {e}")
                return None
            
            # STEP 3: Apply NEW RT window filter
            try:
                rt_mask = (rt_array >= windows['quant_start']) & (rt_array <= windows['quant_end'])
                filtered_rt = rt_array[rt_mask]
                filtered_intensity = intensity_array[rt_mask]
                
                if len(filtered_rt) == 0:
                    # No points in quantification window, but we have points - use closest points
                    closest_idx = np.argmin(np.abs(rt_array - precursor_rt))
                    filtered_rt = np.array([rt_array[closest_idx]])
                    filtered_intensity = np.array([intensity_array[closest_idx]])
                    self.add_log(f"No points in quant window, using closest point at RT {filtered_rt[0]:.3f}")
                
            except Exception as e:
                self.add_log(f"Error applying RT filter: {e}")
                return None
            
            # STEP 4: Calculate area using NEW parameters with FIXED trapz
            try:
                if len(filtered_rt) < 2:
                    area = float(filtered_intensity[0] * 0.01) if len(filtered_intensity) > 0 else 0.0
                    max_intensity = float(filtered_intensity[0]) if len(filtered_intensity) > 0 else 0.0
                    integration_start = float(filtered_rt[0]) if len(filtered_rt) > 0 else float(windows['quant_start'])
                    integration_end = float(filtered_rt[0]) if len(filtered_rt) > 0 else float(windows['quant_end'])
                    width = 0.01
                else:
                    # FIXED: Use trapz instead of trapz with proper error handling
                    try:
                        area = float(trapz(y=filtered_intensity, x=filtered_rt))
                    except Exception as trap_error:
                        self.add_log(f"trapz integration failed: {trap_error}, using simple sum")
                        # Fallback to simple rectangular integration
                        dt = np.mean(np.diff(filtered_rt)) if len(filtered_rt) > 1 else 0.01
                        area = float(np.sum(filtered_intensity) * dt)
                    
                    max_intensity = float(np.max(filtered_intensity))
                    integration_start = float(filtered_rt[0])
                    integration_end = float(filtered_rt[-1])
                    width = float(integration_end - integration_start)
                
                # Ensure all values are finite
                if not all(np.isfinite([area, max_intensity, integration_start, integration_end, width])):
                    self.add_log("Non-finite values in calculation results")
                    return None
                
            except Exception as e:
                self.add_log(f"Error in area calculation: {e}")
                return None
            
            # Create result with error checking
            try:
                result = {
                    'area': area,
                    'max_intensity': max_intensity,
                    'integration_start': integration_start,
                    'integration_end': integration_end,
                    'peak_width': width,
                    'data_points_used': len(filtered_rt),
                    'total_data_points': len(all_rt_values),
                    'quant_start': float(windows['quant_start']),
                    'quant_end': float(windows['quant_end']),
                    'original_rt_data': rt_array,
                    'original_intensity_data': intensity_array
                }
                
                self.add_log(f"Recalculated area for {fragment_type}: {area:.2f} (used {len(filtered_rt)} of {len(all_rt_values)} points)")
                return result
                
            except Exception as e:
                self.add_log(f"Error creating result dictionary: {e}")
                return None
            
        except Exception as e:
            self.add_log(f"CRITICAL ERROR in recalculate_fragment_area_with_new_params: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _update_fragment_areas_with_new_params(self, glycopeptide, precursor_mz, precursor_rt, new_params):
        """Update fragment areas in current data using new parameters - FIXED"""
        try:
            # Find all fragments for this glycopeptide
            mask = (
                (self.current_matched_fragments['Glycopeptides'] == glycopeptide) &
                (np.isclose(self.current_matched_fragments['Precursor_mz'], precursor_mz, rtol=1e-4)) &
                (np.isclose(self.current_matched_fragments['precursor_rt'], precursor_rt, rtol=1e-2))
            )
            
            matching_indices = self.current_matched_fragments.index[mask]
            updated_count = 0
            failed_count = 0
            
            for idx in matching_indices:
                try:
                    fragment_type = self.current_matched_fragments.loc[idx, 'Type']
                    
                    # Recalculate area with new parameters
                    result = self.recalculate_fragment_area_with_new_params(
                        glycopeptide, precursor_mz, precursor_rt, fragment_type, new_params
                    )
                    
                    if result and result['area'] is not None:
                        # Update the area and related fields in current_matched_fragments
                        self.current_matched_fragments.loc[idx, 'Area'] = result['area']
                        
                        # Update other fields if they exist
                        if 'Integration_Start' in self.current_matched_fragments.columns:
                            self.current_matched_fragments.loc[idx, 'Integration_Start'] = result['integration_start']
                        if 'Integration_End' in self.current_matched_fragments.columns:
                            self.current_matched_fragments.loc[idx, 'Integration_End'] = result['integration_end']
                        if 'Peak_Width' in self.current_matched_fragments.columns:
                            self.current_matched_fragments.loc[idx, 'Peak_Width'] = result['peak_width']
                        if 'Max_Intensity' in self.current_matched_fragments.columns:
                            self.current_matched_fragments.loc[idx, 'Max_Intensity'] = result['max_intensity']
                        
                        updated_count += 1
                    else:
                        failed_count += 1
                        self.add_log(f"Failed to recalculate area for fragment {fragment_type}")
                        
                except Exception as fragment_error:
                    failed_count += 1
                    self.add_log(f"Error updating fragment at index {idx}: {fragment_error}")
                    continue
            
            # Also update the stored results
            if hasattr(self, 'all_analysis_results') and self.current_file_key in self.all_analysis_results:
                self.all_analysis_results[self.current_file_key]['matched_fragments'] = self.current_matched_fragments.copy()
            
            if updated_count > 0:
                self.add_log(f"Updated areas for {updated_count} fragments using new parameters")
            if failed_count > 0:
                self.add_log(f"Failed to update {failed_count} fragments")
            
        except Exception as e:
            self.add_log(f"CRITICAL ERROR in _update_fragment_areas_with_new_params: {e}")
            import traceback
            traceback.print_exc()

    def calculate_quantification_window(self, precursor_rt, params):
        """Calculate the quantification window based on corrected back_window definition - FIXED"""
        try:
            max_rt_window = float(params.get('max_rt_window', 1.5))
            back_window_ratio = float(params.get('back_window_ratio', 0.5))
            display_time_extension = float(params.get('display_time_extension', 5.0))
            precursor_rt = float(precursor_rt)
            
            # Validate inputs
            if max_rt_window <= 0 or back_window_ratio < 0 or back_window_ratio > 1:
                raise ValueError(f"Invalid parameters: max_rt_window={max_rt_window}, back_window_ratio={back_window_ratio}")
            
            # CORRECTED: back_window is percentage of max_rt_window extending AFTER RT
            back_window = max_rt_window * back_window_ratio
            forward_window = max_rt_window - back_window
            
            # Quantification window
            quant_start = precursor_rt - back_window
            quant_end = precursor_rt + forward_window
            
            # Display window (extends beyond quantification)
            display_start = quant_start - display_time_extension
            display_end = quant_end + display_time_extension
            
            result = {
                'quant_start': float(quant_start),
                'quant_end': float(quant_end),
                'display_start': float(display_start),
                'display_end': float(display_end),
                'back_window': float(back_window),
                'forward_window': float(forward_window)
            }
            
            # Validate results
            if not all(np.isfinite(list(result.values()))):
                raise ValueError("Non-finite values in quantification window calculation")
            
            return result
            
        except Exception as e:
            self.add_log(f"Error calculating quantification window: {e}")
            # Return safe defaults
            return {
                'quant_start': float(precursor_rt - 0.25),
                'quant_end': float(precursor_rt + 2.25),
                'display_start': float(precursor_rt - 2.25),
                'display_end': float(precursor_rt + 4.25),
                'back_window': 0.25,
                'forward_window': 2.25
            }
        
    def apply_eic_params_to_current(self):
        """Apply current EIC parameters to the current glycopeptide with live recalculation"""
        if not hasattr(self, 'selected_glycopeptide') or not self.selected_glycopeptide:
            QMessageBox.warning(self, "No Selection", "Please select a glycopeptide first.")
            return
        
        glycopeptide = self.selected_glycopeptide['name']
        precursor_mz = self.selected_glycopeptide['precursor_mz']
        precursor_rt = self.selected_glycopeptide['precursor_rt']
        
        # Get current parameter values
        new_params = {
            'max_rt_window': self.max_rt_window_spinner.value(),
            'back_window_ratio': self.back_window_ratio_spinner.value(),
            'display_time_extension': self.display_time_ext_spinner.value()
        }
        
        # Debug output
        self.add_log(f"Applying NEW parameters to {glycopeptide}:")
        self.add_log(f"  - max_rt_window: {new_params['max_rt_window']}")
        self.add_log(f"  - back_window_ratio: {new_params['back_window_ratio']}")
        self.add_log(f"  - display_time_extension: {new_params['display_time_extension']}")
        
        # Calculate what the new quantification window will be
        windows = self.calculate_quantification_window(precursor_rt, new_params)
        self.add_log(f"  - New quantification window: {windows['quant_start']:.2f} to {windows['quant_end']:.2f}")
        
        # Store parameters for this glycopeptide
        if not hasattr(self, 'glycopeptide_specific_params'):
            self.glycopeptide_specific_params = {}
            
        if glycopeptide not in self.glycopeptide_specific_params:
            self.glycopeptide_specific_params[glycopeptide] = {}
            
        self.glycopeptide_specific_params[glycopeptide].update({
            **new_params,
            'file_scope': True,
            'file_key': self.current_file_key
        })
        
        # LIVE RECALCULATION: Update areas in the current data
        self._update_fragment_areas_with_new_params(glycopeptide, precursor_mz, precursor_rt, new_params)
        
        self.add_log(f"Applied parameters to {glycopeptide} in current file with live recalculation")
        
        # Regenerate the plot with new parameters and updated areas
        self.regenerate_current_plot()

    def regenerate_current_plot(self):
        """Regenerate the current plot with updated parameters and shaded quantification area"""
        if not hasattr(self, 'selected_glycopeptide') or not self.selected_glycopeptide:
            return
        
        try:
            glycopeptide = self.selected_glycopeptide['name']
            precursor_mz = self.selected_glycopeptide['precursor_mz']
            precursor_rt = self.selected_glycopeptide['precursor_rt']
            row_id = self.selected_glycopeptide.get('row_id')
            
            # Get current parameters
            params = self.get_eic_parameters(glycopeptide)
            windows = self.calculate_quantification_window(precursor_rt, params)
            
            self.add_log(f"Regenerating plot for {glycopeptide} with NEW quantification window:")
            self.add_log(f"  - Quantification: {windows['quant_start']:.2f} to {windows['quant_end']:.2f}")
            self.add_log(f"  - Display: {windows['display_start']:.2f} to {windows['display_end']:.2f}")
            
            # Force clear current figure to ensure regeneration
            if hasattr(self, 'current_figure') and self.current_figure:
                plt.close(self.current_figure)
                self.current_figure = None
            
            # Show the plot with new parameters - this will use the updated quantification windows
            self.show_eic_for_glycopeptide(glycopeptide, precursor_mz, precursor_rt, row_id)
            self.add_log(f"Plot regenerated with updated quantification area shading")
            
        except Exception as e:
            self.add_log(f"Error regenerating plot: {e}")
            import traceback
            traceback.print_exc()

    def update_eic_parameter_controls(self, glycopeptide=None):
        """Update parameter controls with values for current glycopeptide - ENHANCED VERSION"""
        try:
            if not hasattr(self, 'glycopeptide_specific_params'):
                self.glycopeptide_specific_params = {}
            
            if not glycopeptide or glycopeptide not in self.glycopeptide_specific_params:
                # Use default values
                self.max_rt_window_spinner.setValue(1.5)
                self.back_window_ratio_spinner.setValue(0.5)
                self.display_time_ext_spinner.setValue(5.0)
                self.add_log(f"Updated controls with default parameters for {glycopeptide or 'no selection'}")
            else:
                # Use glycopeptide-specific values
                params = self.glycopeptide_specific_params[glycopeptide]
                
                # Check if parameters are file-specific and match current file
                if params.get('file_scope', False):
                    param_file_key = params.get('file_key')
                    if param_file_key and param_file_key != self.current_file_key:
                        # File-specific params don't match current file, use defaults
                        self.max_rt_window_spinner.setValue(1.5)
                        self.back_window_ratio_spinner.setValue(0.5)
                        self.display_time_ext_spinner.setValue(5.0)
                        self.add_log(f"Using default parameters for {glycopeptide} (file-specific params not for current file)")
                        return
                
                # Apply stored parameters
                self.max_rt_window_spinner.setValue(params.get('max_rt_window', 1.5))
                self.back_window_ratio_spinner.setValue(params.get('back_window_ratio', 0.5))
                self.display_time_ext_spinner.setValue(params.get('display_time_extension', 5.0))
                
                scope = "file-specific" if params.get('file_scope', False) else "global"
                self.add_log(f"Updated controls with {scope} parameters for {glycopeptide}")
                
                # Show current quantification window
                if hasattr(self, 'selected_glycopeptide') and self.selected_glycopeptide:
                    precursor_rt = self.selected_glycopeptide['precursor_rt']
                    windows = self.calculate_quantification_window(precursor_rt, params)
                    self.add_log(f"  - Current quantification window: {windows['quant_start']:.2f} to {windows['quant_end']:.2f}")
                    
        except Exception as e:
            self.add_log(f"Error updating parameter controls: {e}")
            # Fallback to defaults
            self.max_rt_window_spinner.setValue(1.5)
            self.back_window_ratio_spinner.setValue(0.5)
            self.display_time_ext_spinner.setValue(5.0)

    def apply_eic_params_globally(self):
        """Apply current EIC parameters to all instances of this glycopeptide globally with live recalculation"""
        if not hasattr(self, 'selected_glycopeptide') or not self.selected_glycopeptide:
            QMessageBox.warning(self, "No Selection", "Please select a glycopeptide first.")
            return
        
        try:
            glycopeptide = self.selected_glycopeptide['name']
            
            # Get current parameter values
            new_params = {
                'max_rt_window': self.max_rt_window_spinner.value(),
                'back_window_ratio': self.back_window_ratio_spinner.value(),
                'display_time_extension': self.display_time_ext_spinner.value()
            }
            
            self.add_log(f"Applying GLOBAL parameters to {glycopeptide}:")
            self.add_log(f"  - max_rt_window: {new_params['max_rt_window']}")
            self.add_log(f"  - back_window_ratio: {new_params['back_window_ratio']}")
            self.add_log(f"  - display_time_extension: {new_params['display_time_extension']}")
            
            # Initialize storage if needed
            if not hasattr(self, 'glycopeptide_specific_params'):
                self.glycopeptide_specific_params = {}
                
            # Store global parameters for this glycopeptide
            self.glycopeptide_specific_params[glycopeptide] = {
                **new_params,
                'file_scope': False  # Global parameters
            }
            
            # Apply to ALL files containing this glycopeptide
            updated_files = 0
            total_fragments_updated = 0
            
            for file_key, file_data in self.all_analysis_results.items():
                matched_fragments = file_data['matched_fragments']
                
                # Find all instances of this glycopeptide in this file
                glycopeptide_mask = matched_fragments['Glycopeptides'] == glycopeptide
                
                if not glycopeptide_mask.any():
                    continue  # No instances in this file
                
                # Group by precursor to handle multiple RT instances
                glycopeptide_data = matched_fragments[glycopeptide_mask]
                file_updated_count = 0
                
                for (precursor_mz, precursor_rt), group in glycopeptide_data.groupby(['Precursor_mz', 'precursor_rt']):
                    # Temporarily switch to this file for recalculation
                    original_file_key = self.current_file_key
                    original_cached_data = getattr(self, 'current_cached_data', None)
                    original_matched_fragments = self.current_matched_fragments.copy()
                    
                    try:
                        # Set context for this file
                        self.current_file_key = file_key
                        self.current_cached_data = file_data.get('cached_data', {})
                        self.current_matched_fragments = matched_fragments.copy()
                        
                        # Update areas for this precursor instance
                        self._update_fragment_areas_with_new_params(
                            glycopeptide, precursor_mz, precursor_rt, new_params
                        )
                        
                        # Update the stored data
                        file_data['matched_fragments'] = self.current_matched_fragments.copy()
                        file_updated_count += len(group)
                        
                    finally:
                        # Restore original context
                        self.current_file_key = original_file_key
                        if original_cached_data is not None:
                            self.current_cached_data = original_cached_data
                        self.current_matched_fragments = original_matched_fragments
                
                if file_updated_count > 0:
                    updated_files += 1
                    total_fragments_updated += file_updated_count
                    self.add_log(f"  - Updated {file_updated_count} fragments in {file_key}")
            
            # Update current display if it contains this glycopeptide
            if self.current_file_key in self.all_analysis_results:
                self.current_matched_fragments = self.all_analysis_results[self.current_file_key]['matched_fragments'].copy()
            
            self.add_log(f"Applied global parameters to {glycopeptide}: {total_fragments_updated} fragments updated across {updated_files} files")
            
            # Regenerate the current plot
            self.regenerate_current_plot()
            
        except Exception as e:
            self.add_log(f"Error applying global parameters: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Failed to apply global parameters: {e}")

    def reset_eic_params(self):
        """Reset EIC parameters to default values with live recalculation"""
        if not hasattr(self, 'selected_glycopeptide') or not self.selected_glycopeptide:
            QMessageBox.warning(self, "No Selection", "Please select a glycopeptide first.")
            return
        
        try:
            glycopeptide = self.selected_glycopeptide['name']
            precursor_mz = self.selected_glycopeptide['precursor_mz']
            precursor_rt = self.selected_glycopeptide['precursor_rt']
            
            self.add_log(f"Resetting parameters for {glycopeptide} to defaults")
            
            # Remove specific parameters for this glycopeptide
            if hasattr(self, 'glycopeptide_specific_params') and glycopeptide in self.glycopeptide_specific_params:
                old_params = self.glycopeptide_specific_params[glycopeptide].copy()
                was_global = not old_params.get('file_scope', False)
                del self.glycopeptide_specific_params[glycopeptide]
                
                if was_global:
                    self.add_log("  - Removed global parameters, will recalculate ALL files")
                else:
                    self.add_log("  - Removed file-specific parameters")
            
            # Reset control values to defaults
            default_params = {
                'max_rt_window': 1.5,
                'back_window_ratio': 0.5,
                'display_time_extension': 5.0
            }
            
            self.max_rt_window_spinner.setValue(default_params['max_rt_window'])
            self.back_window_ratio_spinner.setValue(default_params['back_window_ratio'])
            self.display_time_ext_spinner.setValue(default_params['display_time_extension'])
            
            # Show new quantification window
            windows = self.calculate_quantification_window(precursor_rt, default_params)
            self.add_log(f"  - New quantification window: {windows['quant_start']:.2f} to {windows['quant_end']:.2f}")
            
            # Recalculate areas with default parameters
            if hasattr(self, 'glycopeptide_specific_params') and glycopeptide in self.glycopeptide_specific_params:
                # Had global parameters, need to reset all files
                self._reset_areas_globally(glycopeptide, default_params)
            else:
                # File-specific or no special parameters, just reset current
                self._update_fragment_areas_with_new_params(
                    glycopeptide, precursor_mz, precursor_rt, default_params
                )
            
            self.add_log(f"Reset complete for {glycopeptide}")
            
            # Regenerate the plot with default parameters
            self.regenerate_current_plot()
            
        except Exception as e:
            self.add_log(f"Error resetting parameters: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Failed to reset parameters: {e}")

    def _reset_areas_globally(self, glycopeptide, default_params):
        """Reset areas for a glycopeptide globally across all files"""
        try:
            updated_files = 0
            total_fragments_updated = 0
            
            for file_key, file_data in self.all_analysis_results.items():
                matched_fragments = file_data['matched_fragments']
                
                # Find all instances of this glycopeptide in this file
                glycopeptide_mask = matched_fragments['Glycopeptides'] == glycopeptide
                
                if not glycopeptide_mask.any():
                    continue
                
                # Group by precursor to handle multiple RT instances
                glycopeptide_data = matched_fragments[glycopeptide_mask]
                file_updated_count = 0
                
                for (precursor_mz, precursor_rt), group in glycopeptide_data.groupby(['Precursor_mz', 'precursor_rt']):
                    # Temporarily switch to this file for recalculation
                    original_file_key = self.current_file_key
                    original_cached_data = getattr(self, 'current_cached_data', None)
                    original_matched_fragments = self.current_matched_fragments.copy()
                    
                    try:
                        # Set context for this file
                        self.current_file_key = file_key
                        self.current_cached_data = file_data.get('cached_data', {})
                        self.current_matched_fragments = matched_fragments.copy()
                        
                        # Update areas with default parameters
                        self._update_fragment_areas_with_new_params(
                            glycopeptide, precursor_mz, precursor_rt, default_params
                        )
                        
                        # Update the stored data
                        file_data['matched_fragments'] = self.current_matched_fragments.copy()
                        file_updated_count += len(group)
                        
                    finally:
                        # Restore original context
                        self.current_file_key = original_file_key
                        if original_cached_data is not None:
                            self.current_cached_data = original_cached_data
                        self.current_matched_fragments = original_matched_fragments
                
                if file_updated_count > 0:
                    updated_files += 1
                    total_fragments_updated += file_updated_count
                    self.add_log(f"  - Reset {file_updated_count} fragments in {file_key}")
            
            # Update current display
            if self.current_file_key in self.all_analysis_results:
                self.current_matched_fragments = self.all_analysis_results[self.current_file_key]['matched_fragments'].copy()
            
            self.add_log(f"Global reset complete: {total_fragments_updated} fragments across {updated_files} files")
            
        except Exception as e:
            self.add_log(f"Error in global reset: {e}")
            import traceback
            traceback.print_exc()

    ##--Removal Functions--##
    def on_fragment_item_changed(self, item, column):
        """Handle changes to fragment tree items (marking for removal) - FIXED VERSION"""
        try:
            # Ignore parent items or non-checkable items
            if item.parent() is None or not (item.flags() & Qt.ItemIsUserCheckable):
                return
                
            # Get stored data from the item - INCLUDING theoretical_mz
            glycopeptide = item.data(0, Qt.UserRole)
            precursor_mz = item.data(0, Qt.UserRole + 1)
            precursor_rt = item.data(0, Qt.UserRole + 2)
            fragment_type = item.data(0, Qt.UserRole + 3)
            theoretical_mz = item.data(0, Qt.UserRole + 4)
            
            # Verify data exists - INCLUDING theoretical_mz
            if None in [glycopeptide, precursor_mz, precursor_rt, fragment_type, theoretical_mz]:
                self.add_log(f"Warning: Missing data in tree item {item.text(0)}")
                return
                
            # FIXED: Create the EXACT same key format that will be used in removal
            fragment_key = f"{glycopeptide}_{fragment_type}_{precursor_mz}_{precursor_rt}_{theoretical_mz:.4f}"
            
            # Initialize removal state structures if needed
            if not hasattr(self, 'fragment_removal_states'):
                self.fragment_removal_states = {}
                
            if self.current_file_key not in self.fragment_removal_states:
                self.fragment_removal_states[self.current_file_key] = []
            
            # Update removal state based on checkbox
            if item.checkState(0) == Qt.Checked:
                # Add to removal list if not already there
                if fragment_key not in self.fragment_removal_states[self.current_file_key]:
                    self.fragment_removal_states[self.current_file_key].append(fragment_key)
                    item.setText(6, "MARKED")  # Update status column
                    self.add_log(f"Marked {fragment_type} (m/z: {theoretical_mz:.4f}) of {glycopeptide} for removal")
            else:
                # Remove from removal list if present
                if fragment_key in self.fragment_removal_states[self.current_file_key]:
                    self.fragment_removal_states[self.current_file_key].remove(fragment_key)
                    item.setText(6, "ACTIVE")  # Reset status column
                    self.add_log(f"Unmarked {fragment_type} (m/z: {theoretical_mz:.4f}) of {glycopeptide} for removal")
            
            # Clean up empty entries
            if not self.fragment_removal_states[self.current_file_key]:
                del self.fragment_removal_states[self.current_file_key]
            
            # Enable or disable apply button based on whether there are removals
            if hasattr(self, 'apply_removals_btn'):
                has_removals = hasattr(self, 'fragment_removal_states') and bool(self.fragment_removal_states)
                self.apply_removals_btn.setEnabled(has_removals)
                
            # Update removal statistics
            self.update_removal_statistics()
            
        except Exception as e:
            self.add_log(f"Error in fragment item changed: {e}")
            import traceback
            traceback.print_exc()

    def _apply_removals_to_current_file(self):
        """Apply removals to current file only - FIXED VERSION"""
        if self.current_file_key not in self.fragment_removal_states:
            self.add_log(f"No removal states found for {self.current_file_key}")
            return
        
        removal_list = self.fragment_removal_states[self.current_file_key]
        
        if not removal_list:
            self.add_log(f"No fragments marked for removal in {self.current_file_key}")
            return
        
        self.add_log(f"Applying {len(removal_list)} fragment removals to {self.current_file_key}")
        
        matched_fragments = self.current_matched_fragments.copy()
        if matched_fragments.empty:
            self.add_log(f"Warning: No fragments in {self.current_file_key}")
            return
        
        # Create indices to keep (instead of a mask)
        indices_to_keep = []
        removed_count = 0
        
        for idx, row in matched_fragments.iterrows():
            should_remove = False
            
            try:
                glycopeptide = row['Glycopeptides']
                fragment_type = row['Type']
                precursor_mz = row['Precursor_mz']
                precursor_rt = row['precursor_rt']
                theoretical_mz = row['Theoretical_mz']
                
                # FIXED: Create the EXACT same fragment key format
                fragment_key = f"{glycopeptide}_{fragment_type}_{precursor_mz}_{precursor_rt}_{theoretical_mz:.4f}"
                
                # Check if this fragment is in the removal list
                if fragment_key in removal_list:
                    should_remove = True
                    removed_count += 1
                    self.add_log(f"Removing fragment: {fragment_key}")
                            
            except Exception as e:
                self.add_log(f"Error checking fragment at index {idx}: {e}")
                # Keep fragment if there's an error
                
            if not should_remove:
                indices_to_keep.append(idx)
        
        # Create filtered dataframe
        if indices_to_keep:
            filtered_fragments = matched_fragments.loc[indices_to_keep].reset_index(drop=True)
        else:
            # Create empty dataframe with same columns
            filtered_fragments = matched_fragments.iloc[0:0].copy()
        
        # CRITICAL: Update both current and stored data
        original_count = len(matched_fragments)
        self.current_matched_fragments = filtered_fragments.copy()
        self.all_analysis_results[self.current_file_key]['matched_fragments'] = filtered_fragments.copy()
        
        remaining_count = len(filtered_fragments)
        self.add_log(f"Applied {removed_count} removals to {self.current_file_key}")
        self.add_log(f"Original: {original_count}, Removed: {removed_count}, Remaining: {remaining_count}")

    def _apply_removals_globally(self):
        """Apply removals to all files based on stored removal states - FIXED VERSION"""
        total_removed = 0
        files_processed = 0
        
        # Check if we have any removal states
        if not hasattr(self, 'fragment_removal_states') or not self.fragment_removal_states:
            self.removal_status_label.setText("No fragments marked for removal globally")
            self.add_log("No fragments marked for removal - no removal states found")
            return
        
        # Get the source file key that has the removal state
        source_file_key = self.current_file_key
        if source_file_key not in self.fragment_removal_states:
            # Try to find any file with removal states
            for key in self.fragment_removal_states.keys():
                source_file_key = key
                break
        
        if source_file_key not in self.fragment_removal_states:
            self.add_log("No removal states found for any file")
            return
        
        # Get the removal list from the source file
        source_removal_list = self.fragment_removal_states[source_file_key]
        self.add_log(f"Applying global removals based on {len(source_removal_list)} fragments from {source_file_key}")
        
        # Apply the same removal pattern to ALL files
        for target_file_key in self.all_analysis_results.keys():
            if target_file_key not in self.all_analysis_results:
                self.add_log(f"Warning: File {target_file_key} not found in results")
                continue
                
            file_data = self.all_analysis_results[target_file_key]
            matched_fragments = file_data['matched_fragments'].copy()
            
            if matched_fragments.empty:
                self.add_log(f"Warning: No fragments in {target_file_key}")
                continue
            
            # Create indices to keep for this file
            indices_to_keep = []
            file_removed_count = 0
            
            for idx, row in matched_fragments.iterrows():
                should_remove = False
                
                try:
                    glycopeptide = row['Glycopeptides']
                    fragment_type = row['Type']
                    precursor_mz = row['Precursor_mz']
                    precursor_rt = row['precursor_rt']
                    theoretical_mz = row['Theoretical_mz']
                    
                    # FIXED: Create the EXACT same fragment key format
                    fragment_key = f"{glycopeptide}_{fragment_type}_{precursor_mz}_{precursor_rt}_{theoretical_mz:.4f}"
                    
                    # Check if this fragment should be removed
                    if fragment_key in source_removal_list:
                        should_remove = True
                        file_removed_count += 1
                        
                except Exception as e:
                    self.add_log(f"Error processing fragment in {target_file_key}: {e}")
                    # Keep fragment if there's an error
                
                if not should_remove:
                    indices_to_keep.append(idx)
            
            # Apply the filtering to this file
            if indices_to_keep:
                filtered_fragments = matched_fragments.loc[indices_to_keep].reset_index(drop=True)
            else:
                filtered_fragments = matched_fragments.iloc[0:0].copy()
            
            self.all_analysis_results[target_file_key]['matched_fragments'] = filtered_fragments
            
            total_removed += file_removed_count
            files_processed += 1
            
            self.add_log(f"Applied {file_removed_count} removals to {target_file_key} (remaining: {len(filtered_fragments)})")
        
        # Update current file display if it was processed
        if self.current_file_key in self.all_analysis_results:
            self.current_matched_fragments = self.all_analysis_results[self.current_file_key]['matched_fragments'].copy()
            self.add_log(f"Updated current file display: {len(self.current_matched_fragments)} fragments remaining")
        
        # Update displays with immediate plot regeneration
        self.removal_status_label.setText(f"Applied global removals: {total_removed} fragments removed across {files_processed} files")
        self._refresh_all_displays_after_change(is_restoration=False)
        
        self.add_log(f"Global removal complete: {total_removed} fragments removed across {files_processed} files")

    def _save_current_removal_state(self):
        """Save the current fragment removal state - FIXED VERSION"""
        if not self.current_file_key:
            return
        
        # Extract removal state from fragment tree
        removal_list = []
        
        for i in range(self.fragment_tree.topLevelItemCount()):
            precursor_item = self.fragment_tree.topLevelItem(i)
            
            for j in range(precursor_item.childCount()):
                fragment_item = precursor_item.child(j)
                if fragment_item.checkState(0) == Qt.Checked:
                    # Get the stored data to create the exact same key format used in removal
                    glycopeptide = fragment_item.data(0, Qt.UserRole)
                    precursor_mz = fragment_item.data(0, Qt.UserRole + 1)
                    precursor_rt = fragment_item.data(0, Qt.UserRole + 2)
                    fragment_type = fragment_item.data(0, Qt.UserRole + 3)
                    theoretical_mz = fragment_item.data(0, Qt.UserRole + 4)
                    
                    # FIXED: Use exact same key format as removal expects
                    fragment_key = f"{glycopeptide}_{fragment_type}_{precursor_mz}_{precursor_rt}_{theoretical_mz:.4f}"
                    removal_list.append(fragment_key)
        
        # Store removal state
        if self.global_removal_scope and removal_list:
            for file_key in self.all_analysis_results.keys():
                self.fragment_removal_states[file_key] = removal_list.copy()
        elif removal_list:
            self.fragment_removal_states[self.current_file_key] = removal_list
        elif self.current_file_key in self.fragment_removal_states:
            if self.global_removal_scope:
                self.fragment_removal_states.clear()
            else:
                del self.fragment_removal_states[self.current_file_key]

    def _apply_saved_removal_state(self, file_key):
        """Apply saved removal state to the fragment tree - FIXED VERSION"""
        if file_key not in self.fragment_removal_states:
            return
        
        removal_list = self.fragment_removal_states[file_key]
        restored_count = 0
        
        self.add_log(f"Applying removal state for {file_key}: {len(removal_list)} fragments to mark")
        
        for i in range(self.fragment_tree.topLevelItemCount()):
            precursor_item = self.fragment_tree.topLevelItem(i)
            
            for j in range(precursor_item.childCount()):
                fragment_item = precursor_item.child(j)
                
                # Get fragment data from the item
                glycopeptide = fragment_item.data(0, Qt.UserRole)
                precursor_mz = fragment_item.data(0, Qt.UserRole + 1)
                precursor_rt = fragment_item.data(0, Qt.UserRole + 2)
                fragment_type = fragment_item.data(0, Qt.UserRole + 3)
                theoretical_mz = fragment_item.data(0, Qt.UserRole + 4)
                
                if all(x is not None for x in [glycopeptide, precursor_mz, precursor_rt, fragment_type, theoretical_mz]):
                    # Create fragment key to match removal state format
                    fragment_key = f"{glycopeptide}_{fragment_type}_{precursor_mz}_{precursor_rt}_{theoretical_mz:.4f}"
                    
                    if fragment_key in removal_list:
                        fragment_item.setCheckState(0, Qt.Checked)
                        fragment_item.setText(6, "MARKED")
                        restored_count += 1
        
        if restored_count > 0:
            self.add_log(f"Applied removal state: {restored_count} fragments marked for removal in {file_key}")
            self.update_removal_statistics()

    def _refresh_all_displays_after_change(self, is_restoration=False):
        """Refresh displays after fragment changes with immediate plot update"""
        try:
            # Store current selection
            current_selection = None
            if hasattr(self, 'selected_glycopeptide') and self.selected_glycopeptide:
                current_selection = self.selected_glycopeptide.copy()
            
            # Step 1: Repopulate fragment tree
            self.populate_fragment_tree()
            
            # Step 2: Update results display
            self.update_results_display()
            
            # Step 3: Update statistics
            self.update_removal_statistics()
            
            # Step 4: CRITICAL FIX - Immediately refresh plot
            if current_selection:
                try:
                    glycopeptide = current_selection['name']
                    precursor_mz = current_selection['precursor_mz']
                    precursor_rt = current_selection['precursor_rt']
                    row_id = current_selection.get('row_id')
                    
                    # Check if this glycopeptide still has fragments after removal
                    matching_fragments = self.current_matched_fragments[
                        (self.current_matched_fragments['Glycopeptides'] == glycopeptide) &
                        (np.isclose(self.current_matched_fragments['Precursor_mz'], precursor_mz, rtol=1e-4)) &
                        (np.isclose(self.current_matched_fragments['precursor_rt'], precursor_rt, rtol=1e-2))
                    ]
                    
                    if not matching_fragments.empty:
                        # Fragments still exist - regenerate plot
                        self.show_eic_for_glycopeptide(glycopeptide, precursor_mz, precursor_rt, row_id)
                        self.add_log(f"Refreshed plot for {glycopeptide} with {len(matching_fragments)} remaining fragments")
                    else:
                        # No fragments left - clear plot
                        self.plot_area.setText("No fragments remaining for this glycopeptide after removal")
                        self.selected_glycopeptide = None
                        self.refresh_plot_btn.setEnabled(False)
                        self.save_plot_btn.setEnabled(False)
                        self.add_log(f"Cleared plot for {glycopeptide} - no fragments remaining")
                        
                except Exception as plot_error:
                    self.add_log(f"Error refreshing plot: {plot_error}")
                    self.plot_area.setText("Error refreshing plot after removal")
            else:
                # No selection - clear plot area
                self.plot_area.setText("Select a glycopeptide to view plots")
                self.refresh_plot_btn.setEnabled(False)
                self.save_plot_btn.setEnabled(False)
            
            # Step 5: Update export status
            if not self.current_matched_fragments.empty:
                num_fragments = len(self.current_matched_fragments)
                num_precursors = self.current_matched_fragments['Precursor_mz'].nunique()
                self.export_status_label.setText(f"Ready to export: {num_fragments} fragments from {num_precursors} precursors")
            else:
                self.export_status_label.setText("No fragments available for export")
            
            action_type = "restoration" if is_restoration else "removal"
            self.add_log(f"Display refresh completed after {action_type}")
            
        except Exception as e:
            self.add_log(f"Error refreshing displays: {e}")
            import traceback
            traceback.print_exc()
            
    def _reset_plot_displays(self):
        """Clear all plot displays"""
        try:
            # Clear EIC plot
            if hasattr(self, 'eic_canvas') and self.eic_canvas:
                self.eic_canvas.figure.clear()
                self.eic_canvas.draw()
            
            # Clear MS2 plot
            if hasattr(self, 'ms2_canvas') and self.ms2_canvas:
                self.ms2_canvas.figure.clear()
                self.ms2_canvas.draw()
                
            self.add_log("Cleared plot displays")
            
        except Exception as e:
            self.add_log(f"Error clearing plot displays: {e}")

    def restore_all_fragments(self):
            """Completely restore all fragments - ENHANCED VERSION"""
            try:
                self.add_log("Starting comprehensive fragment restoration...")
                
                # Store current selection before restoration if available
                current_selection = None
                if hasattr(self, 'selected_glycopeptide') and self.selected_glycopeptide:
                    current_selection = self.selected_glycopeptide.copy()
                    self.add_log(f"Saved current selection: {current_selection['name']}")
                
                # Step 1: Clear ALL removal states
                if self.global_removal_scope:
                    # Clear removal states for all files
                    self.fragment_removal_states.clear()
                    self.add_log("Cleared removal states for all files (global scope)")
                    
                    # Restore original data for all files
                    restored_files = 0
                    for file_key in list(self.all_analysis_results.keys()):
                        if self._restore_original_data_for_file(file_key):
                            restored_files += 1
                    
                    self.add_log(f"Restored original data for {restored_files} files")
                else:
                    # Clear removal state for current file only
                    if self.current_file_key in self.fragment_removal_states:
                        del self.fragment_removal_states[self.current_file_key]
                        self.add_log(f"Cleared removal state for {self.current_file_key}")
                    
                    # Restore original data for current file
                    self._restore_original_data_for_file(self.current_file_key)
                
                # CRITICAL FIX - Ensure current_matched_fragments is updated properly
                if self.current_file_key in self.all_analysis_results:
                    self.current_matched_fragments = self.all_analysis_results[self.current_file_key]['matched_fragments'].copy()
                    self.add_log(f"Updated current_matched_fragments with restored data: {len(self.current_matched_fragments)} fragments")
                
                # Call the combined refresh method for consistency
                self._refresh_all_displays_after_change(is_restoration=True)
                
                # Restore selection if available
                if current_selection and hasattr(self, 'show_eic_for_glycopeptide'):
                    try:
                        glycopeptide = current_selection['name']
                        precursor_mz = current_selection['precursor_mz']
                        precursor_rt = current_selection['precursor_rt']
                        row_id = current_selection.get('row_id')
                        
                        self.add_log(f"Restoring previous selection: {glycopeptide}")
                        self.show_eic_for_glycopeptide(glycopeptide, precursor_mz, precursor_rt, row_id)
                    except Exception as e:
                        self.add_log(f"Could not restore previous selection: {e}")
                
                # Update status
                total_fragments = len(self.current_matched_fragments)
                scope_text = "globally across all files" if self.global_removal_scope else "for current file"
                self.removal_status_label.setText(f"All fragments restored {scope_text}: {total_fragments} fragments available")
                
                self.add_log(f"Fragment restoration completed {scope_text}: {total_fragments} fragments restored")
                
            except Exception as e:
                error_msg = f"Error restoring fragments: {e}"
                self.add_log(error_msg)
                QMessageBox.critical(self, "Restoration Error", error_msg)
                import traceback
                traceback.print_exc()
        
    def apply_current_removals(self):
            """Apply the current removal state to the actual data - ENHANCED VERSION"""
            try:
                if not self.fragment_removal_states:
                    QMessageBox.warning(self, "No Removals", "No fragments are marked for removal.")
                    return
                
                # Backup data before applying removals (if not already backed up)
                if not hasattr(self, 'original_analysis_results') or not self.original_analysis_results:
                    if not self._backup_original_data():
                        QMessageBox.critical(self, "Backup Error", "Failed to backup original data. Cannot proceed with removals.")
                        return
                
                if self.global_removal_scope:
                    self._apply_removals_globally()
                else:
                    self._apply_removals_to_current_file()
                
                # Refresh displays after applying removals using the unified method
                self._refresh_all_displays_after_change(is_restoration=False)
                
                # Update status
                removed_count = self._count_total_removals()
                remaining_count = len(self.current_matched_fragments)
                scope_text = "globally to all files" if self.global_removal_scope else "to current file"
                self.removal_status_label.setText(f"Applied {removed_count} removals {scope_text}: {remaining_count} fragments remaining")
                
            except Exception as e:
                error_msg = f"Error applying removals: {e}"
                self.add_log(error_msg)
                QMessageBox.critical(self, "Removal Error", error_msg)
                import traceback
                traceback.print_exc()

    def _restore_original_data_for_file(self, file_key):
            """Restore original matched fragments data for a specific file - ENHANCED VERSION"""
            try:
                if file_key not in self.all_analysis_results:
                    self.add_log(f"Warning: File {file_key} not found in results")
                    return False
                
                # Check if we have backup data
                if hasattr(self, 'original_analysis_results') and file_key in self.original_analysis_results:
                    # Restore from backup
                    self.all_analysis_results[file_key]['matched_fragments'] = self.original_analysis_results[file_key]['matched_fragments'].copy()
                    self.add_log(f"Restored {file_key} from backup data ({len(self.original_analysis_results[file_key]['matched_fragments'])} fragments)")
                else:
                    # CRITICAL FIX: If no backup exists, we need to create one from current data
                    # This means no removals have been applied yet, so current data IS the original
                    if not hasattr(self, 'original_analysis_results'):
                        self.original_analysis_results = {}
                    
                    # Back up current data as original if it doesn't exist
                    if file_key not in self.original_analysis_results:
                        self.original_analysis_results[file_key] = {
                            'matched_fragments': self.all_analysis_results[file_key]['matched_fragments'].copy(),
                            'cached_data': self.all_analysis_results[file_key].get('cached_data', {}),
                            'analysis_params': self.all_analysis_results[file_key].get('analysis_params', {})
                        }
                        self.add_log(f"Created backup for {file_key} (no previous backup existed)")
                    
                    # Data is already original, no need to restore
                    self.add_log(f"No restoration needed for {file_key} - data already original")
                
                # If this is the current file, update the current_matched_fragments
                if file_key == self.current_file_key:
                    self.current_matched_fragments = self.all_analysis_results[file_key]['matched_fragments'].copy()
                    self.add_log(f"Updated current fragments: {len(self.current_matched_fragments)} fragments")
                
                return True
                
            except Exception as e:
                self.add_log(f"Error restoring data for {file_key}: {e}")
                return False

    def _backup_original_data(self):
            """Backup original data before any removals - ENHANCED VERSION"""
            try:
                if not hasattr(self, 'original_analysis_results'):
                    self.original_analysis_results = {}
                
                # Deep copy all matched fragments data for files that don't have backups yet
                backed_up_count = 0
                for file_key, file_data in self.all_analysis_results.items():
                    if file_key not in self.original_analysis_results:
                        self.original_analysis_results[file_key] = {
                            'matched_fragments': file_data['matched_fragments'].copy(),
                            'cached_data': file_data.get('cached_data', {}),
                            'analysis_params': file_data.get('analysis_params', {})
                        }
                        backed_up_count += 1
                
                if backed_up_count > 0:
                    self.add_log(f"Backed up original data for {backed_up_count} files")
                else:
                    self.add_log("Original data backup already exists")
                
                return True
                
            except Exception as e:
                self.add_log(f"Error backing up original data: {e}")
                return

    def update_removal_statistics(self):
            """Update removal statistics display"""
            total_fragments = 0
            removed_fragments = 0
            
            for i in range(self.fragment_tree.topLevelItemCount()):
                precursor_item = self.fragment_tree.topLevelItem(i)
                
                for j in range(precursor_item.childCount()):
                    fragment_item = precursor_item.child(j)
                    total_fragments += 1
                    
                    if fragment_item.checkState(0) == Qt.Checked:
                        removed_fragments += 1
            
            remaining_fragments = total_fragments - removed_fragments
            removal_percentage = (removed_fragments / total_fragments * 100) if total_fragments > 0 else 0
            
            stats_text = f"Total: {total_fragments} | Marked for Removal: {removed_fragments} | Remaining: {remaining_fragments} | Removal Rate: {removal_percentage:.1f}%"
            self.removal_stats_label.setText(stats_text)

    ##Reproducibility Summary##
    def setup_reproducibility_filter_buttons(self):
        """Add buttons to quickly filter by reproducibility"""
        repro_filter_layout = QHBoxLayout()
        
        # Add a frame for better visual grouping
        filter_frame = QFrame()
        filter_frame.setFrameStyle(QFrame.StyledPanel)
        filter_frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                margin: 2px;
                padding: 2px;
            }
        """)
        filter_frame_layout = QHBoxLayout(filter_frame)
        
        # Filter by reproducibility buttons
        self.show_all_btn = QPushButton("Show All")
        self.show_all_btn.clicked.connect(lambda: self.filter_by_reproducibility("all"))
        self.show_all_btn.setToolTip("Show all fragments")
        self.show_all_btn.setMinimumHeight(25)
        
        self.show_perfect_repro_btn = QPushButton("Perfect Reproducibility")
        self.show_perfect_repro_btn.clicked.connect(lambda: self.filter_by_reproducibility("perfect"))
        self.show_perfect_repro_btn.setToolTip("Show only fragments present in all files")
        self.show_perfect_repro_btn.setMinimumHeight(25)
        
        self.show_poor_repro_btn = QPushButton("Poor Reproducibility")
        self.show_poor_repro_btn.clicked.connect(lambda: self.filter_by_reproducibility("poor"))
        self.show_poor_repro_btn.setToolTip("Show only fragments present in <50% of files")
        self.show_poor_repro_btn.setMinimumHeight(25)
        
        filter_frame_layout.addWidget(QLabel("Quick Filters:"))
        filter_frame_layout.addWidget(self.show_all_btn)
        filter_frame_layout.addWidget(self.show_perfect_repro_btn)
        filter_frame_layout.addWidget(self.show_poor_repro_btn)
        filter_frame_layout.addStretch()
        
        repro_filter_layout.addWidget(filter_frame)
        
        return repro_filter_layout

    def filter_by_reproducibility(self, filter_type):
        """Filter fragment tree by reproducibility"""
        try:
            total_files = len(self.all_analysis_results) if hasattr(self, 'all_analysis_results') else 1
            shown_fragments = 0
            hidden_fragments = 0
            
            for i in range(self.fragment_tree.topLevelItemCount()):
                precursor_item = self.fragment_tree.topLevelItem(i)
                precursor_visible = False
                
                for j in range(precursor_item.childCount()):
                    fragment_item = precursor_item.child(j)
                    repro_text = fragment_item.text(7)  # Reproducibility column
                    
                    if '/' in repro_text:
                        try:
                            present, total = map(int, repro_text.split('/'))
                            
                            if filter_type == "all":
                                show_fragment = True
                            elif filter_type == "perfect":
                                show_fragment = (present == total)
                            elif filter_type == "poor":
                                show_fragment = (present < total * 0.5)
                            else:
                                show_fragment = True
                            
                            fragment_item.setHidden(not show_fragment)
                            if show_fragment:
                                precursor_visible = True
                                shown_fragments += 1
                            else:
                                hidden_fragments += 1
                                
                        except ValueError:
                            # If can't parse, show the fragment
                            fragment_item.setHidden(False)
                            precursor_visible = True
                            shown_fragments += 1
                    else:
                        # If no reproducibility data, show the fragment
                        fragment_item.setHidden(False)
                        precursor_visible = True
                        shown_fragments += 1
                
                precursor_item.setHidden(not precursor_visible)
            
            # Update status
            if filter_type == "all":
                status_msg = f"Showing all fragments: {shown_fragments} visible"
            elif filter_type == "perfect":
                status_msg = f"Perfect reproducibility filter: {shown_fragments} fragments shown, {hidden_fragments} hidden"
            elif filter_type == "poor":
                status_msg = f"Poor reproducibility filter: {shown_fragments} fragments shown, {hidden_fragments} hidden"
            
            self.removal_status_label.setText(status_msg)
            self.add_log(f"Applied reproducibility filter: {filter_type} - {shown_fragments} fragments shown")
            
        except Exception as e:
            self.add_log(f"Error applying reproducibility filter: {e}")
            import traceback
            traceback.print_exc()

    def _calculate_fragment_reproducibility(self):
        """Calculate fragment reproducibility correctly - PER GLYCOPEPTIDE across files"""
        try:
            # Create dictionary to store reproducibility counts
            fragment_reproducibility = {}
            
            # Exit if we don't have analysis results or only have one file
            if not hasattr(self, 'all_analysis_results') or len(self.all_analysis_results) <= 1:
                return fragment_reproducibility
            
            # First, create a mapping of glycopeptides across all files
            glycopeptide_map = {}
            
            for file_key, file_data in self.all_analysis_results.items():
                matched_fragments = file_data.get('matched_fragments')
                if matched_fragments is None or matched_fragments.empty:
                    continue
                    
                # Group by glycopeptide name and fragment type
                for idx, fragment in matched_fragments.iterrows():
                    try:
                        glycopeptide = fragment['Glycopeptides']
                        fragment_type = fragment['Type']
                        precursor_mz = fragment['Precursor_mz']
                        precursor_rt = fragment['precursor_rt']
                        theoretical_mz = fragment['Theoretical_mz']
                        
                        # FIXED: Use 4 decimal places consistently
                        fragment_key = f"{glycopeptide}_{fragment_type}_{precursor_mz}_{precursor_rt}_{theoretical_mz:.4f}"
                        
                        if fragment_key not in glycopeptide_map:
                            glycopeptide_map[fragment_key] = set()
                            
                        # Add this file to the set of files containing this glycopeptide+fragment
                        glycopeptide_map[fragment_key].add(file_key)
                        
                    except KeyError as ke:
                        continue
                    except Exception as fe:
                        continue
            
            # Now calculate reproducibility for each fragment in current file
            for idx, fragment in self.current_matched_fragments.iterrows():
                try:
                    glycopeptide = fragment['Glycopeptides']
                    fragment_type = fragment['Type']
                    precursor_mz = fragment['Precursor_mz']
                    precursor_rt = fragment['precursor_rt']
                    theoretical_mz = fragment['Theoretical_mz']
                    
                    # FIXED: Keys for reproducibility lookup and storage - 4 decimal places
                    lookup_key = f"{glycopeptide}_{fragment_type}_{precursor_mz}_{precursor_rt}_{theoretical_mz:.4f}"
                    storage_key = f"{glycopeptide}_{fragment_type}_{precursor_mz}_{precursor_rt}_{theoretical_mz:.4f}"
                    
                    # Get reproducibility count from our map
                    if lookup_key in glycopeptide_map:
                        file_count = len(glycopeptide_map[lookup_key])
                        fragment_reproducibility[storage_key] = file_count
                    else:
                        # If not found, it's only in the current file
                        fragment_reproducibility[storage_key] = 1
                        
                except KeyError as ke:
                    continue
                except Exception as fe:
                    continue
            
            return fragment_reproducibility
            
        except Exception as e:
            return {}
       
    def auto_remove_poor_reproducibility(self):
        """Automatically remove fragments with poor reproducibility across files"""
        try:
            if len(self.all_analysis_results) < 2:
                QMessageBox.warning(self, "Insufficient Files", 
                                "Need at least 2 files to assess reproducibility. Current files: 1")
                return
            
            # Get reproducibility threshold from user
            threshold, ok = QInputDialog.getInt(
                self, 
                "Set Reproducibility Threshold", 
                f"Remove fragments appearing in fewer than how many files?\n"
                f"(Total files: {len(self.all_analysis_results)})\n"
                f"Threshold (1-{len(self.all_analysis_results)}):", 
                value=2,  # Default to 2
                min=1, 
                max=len(self.all_analysis_results)
            )
            
            if not ok:
                return
            
            # Confirm removal action
            confirm = QMessageBox.question(
                self,
                "Confirm Auto-Removal",
                f"This will immediately remove all fragments appearing in fewer than {threshold} files.\n\n"
                f"This action will modify your data across all {len(self.all_analysis_results)} files.\n\n"
                f"Do you want to proceed?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if confirm != QMessageBox.Yes:
                return
            
            if not self.global_removal_scope:
                QMessageBox.information(self, "Scope Required", 
                                    "Reproducibility analysis requires GLOBAL scope. Please switch to 'All Files' mode.")
                return
            
            self.add_log(f"Starting reproducibility analysis across {len(self.all_analysis_results)} files...")
            self.add_log(f"Threshold: Remove fragments appearing in < {threshold} files")
            
            # Step 1: Collect all unique fragments across all files
            fragment_occurrence = {}
            
            try:
                for file_key in self.all_analysis_results.keys():
                    file_data = self.all_analysis_results[file_key]
                    
                    if 'matched_fragments' not in file_data:
                        self.add_log(f"Warning: No matched_fragments found for file {file_key}")
                        continue
                        
                    matched_fragments = file_data['matched_fragments']
                    
                    if matched_fragments is None or matched_fragments.empty:
                        self.add_log(f"File {file_key}: No fragments to analyze")
                        continue
                    
                    # Check required columns exist
                    required_cols = ['Glycopeptides', 'Type', 'Precursor_mz', 'precursor_rt']
                    missing_cols = [col for col in required_cols if col not in matched_fragments.columns]
                    if missing_cols:
                        self.add_log(f"Error: Missing columns in {file_key}: {missing_cols}")
                        continue
                    
                    # Track fragment occurrence
                    for idx, row in matched_fragments.iterrows():
                        try:
                            glycopeptide = str(row['Glycopeptides'])
                            fragment_type = str(row['Type'])
                            precursor_mz = float(row['Precursor_mz'])
                            precursor_rt = float(row['precursor_rt'])
                            theoretical_mz = float(row['Theoretical_mz'])
                            
                            # Create unique fragment identifier
                            fragment_id = f"{glycopeptide}_{fragment_type}_{precursor_mz}_{precursor_rt}_{theoretical_mz:.4f}"
                            
                            if fragment_id not in fragment_occurrence:
                                fragment_occurrence[fragment_id] = set()
                            
                            fragment_occurrence[fragment_id].add(file_key)
                            
                        except (ValueError, KeyError) as e:
                            self.add_log(f"Warning: Error processing row {idx} in {file_key}: {e}")
                            continue
                            
            except Exception as e:
                self.add_log(f"Error during fragment collection: {e}")
                QMessageBox.critical(self, "Error", f"Error during fragment analysis: {e}")
                return
            
            # Step 2: Identify poorly reproducible fragments
            poorly_reproducible = []
            for fragment_id, file_set in fragment_occurrence.items():
                if len(file_set) < threshold:
                    poorly_reproducible.append({
                        'fragment_id': fragment_id,
                        'occurrence_count': len(file_set),
                        'files': list(file_set)
                    })
            
            self.add_log(f"Found {len(poorly_reproducible)} poorly reproducible fragments")
            
            if not poorly_reproducible:
                QMessageBox.information(self, "No Removals", "No poorly reproducible fragments found.")
                return
            
            # Step 3: Remove fragments from all files
            total_removed_fragments = 0
            
            try:
                for file_key in list(self.all_analysis_results.keys()):  # Use list() to avoid iteration issues
                    file_data = self.all_analysis_results[file_key]
                    
                    if 'matched_fragments' not in file_data or file_data['matched_fragments'].empty:
                        continue
                    
                    matched_fragments = file_data['matched_fragments'].copy()
                    original_count = len(matched_fragments)
                    
                    # Create indices to keep
                    indices_to_keep = []
                    
                    for idx, row in matched_fragments.iterrows():
                        try:
                            glycopeptide = str(row['Glycopeptides'])
                            fragment_type = str(row['Type'])
                            precursor_mz = float(row['Precursor_mz'])
                            precursor_rt = float(row['precursor_rt'])
                            theoretical_mz = float(row['Theoretical_mz']) 
                            
                            fragment_id = f"{glycopeptide}_{fragment_type}_{precursor_mz}_{precursor_rt}_{theoretical_mz:.4f}"
                            
                            # Check if this fragment should be removed
                            should_remove = False
                            for poor_fragment in poorly_reproducible:
                                if poor_fragment['fragment_id'] == fragment_id:
                                    should_remove = True
                                    break
                            
                            if not should_remove:
                                indices_to_keep.append(idx)
                                
                        except Exception as e:
                            self.add_log(f"Warning: Error processing fragment in {file_key}: {e}")
                            indices_to_keep.append(idx)  # Keep fragment if there's an error
                    
                    # Create new dataframe with only kept fragments
                    if indices_to_keep:
                        filtered_fragments = matched_fragments.loc[indices_to_keep].reset_index(drop=True)
                    else:
                        # Create empty dataframe with same columns
                        filtered_fragments = matched_fragments.iloc[0:0].copy()
                    
                    # Update the data
                    self.all_analysis_results[file_key]['matched_fragments'] = filtered_fragments
                    
                    removed_in_file = original_count - len(filtered_fragments)
                    total_removed_fragments += removed_in_file
                    
                    if removed_in_file > 0:
                        self.add_log(f"File {file_key}: Removed {removed_in_file} fragments ({len(filtered_fragments)} remaining)")
                        
            except Exception as e:
                self.add_log(f"Error during fragment removal: {e}")
                QMessageBox.critical(self, "Error", f"Error during fragment removal: {e}")
                return
            
            # Step 4: Clear removal states and refresh display
            try:
                self.fragment_removal_states.clear()
                
                # Update current_matched_fragments to reflect the changes
                if hasattr(self, 'current_file_key') and self.current_file_key and self.current_file_key in self.all_analysis_results:
                    # Update the current displayed data
                    self.current_matched_fragments = self.all_analysis_results[self.current_file_key]['matched_fragments'].copy()
                    self.add_log(f"Updated current_matched_fragments: {len(self.current_matched_fragments)} fragments")
                    
                    # Use the unified refresh method for complete display update
                    self._refresh_all_displays_after_change(is_restoration=False)
                
            except Exception as e:
                self.add_log(f"Warning: Error refreshing display: {e}")
            
            # Step 5: Show results
            scope_text = f"globally across {len(self.all_analysis_results)} files (reproducibility < {threshold})"
            
            self.removal_status_label.setText(f"Removed {total_removed_fragments} poorly reproducible fragments {scope_text}")
            
            try:
                self.update_removal_statistics()
            except Exception as e:
                self.add_log(f"Warning: Error updating statistics: {e}")
            
            self.add_log(f"Successfully removed {total_removed_fragments} poorly reproducible fragments {scope_text}")
            
            # Show summary
            QMessageBox.information(self, "Removal Complete", 
                                f"Successfully removed {total_removed_fragments} poorly reproducible fragments.")
            
        except Exception as e:
            self.add_log(f"Critical error in auto_remove_poor_reproducibility: {e}")
            QMessageBox.critical(self, "Critical Error", f"An error occurred: {e}")
    
    def get_fragment_reproducibility_stats(self):
        """Get detailed reproducibility statistics for all fragments"""
        if len(self.all_analysis_results) < 2:
            return None
        
        fragment_stats = {}  # {fragment_id: {'files': set, 'glycopeptide': str, 'fragment_type': str}}
        
        # Create a mapping of file_key to file number (1-based)
        file_keys = list(self.all_analysis_results.keys())
        file_key_to_number = {file_key: idx + 1 for idx, file_key in enumerate(file_keys)}
        
        for file_key in self.all_analysis_results.keys():
            file_data = self.all_analysis_results[file_key]
            matched_fragments = file_data['matched_fragments']
            
            if matched_fragments.empty:
                continue
            
            for _, row in matched_fragments.iterrows():
                glycopeptide = row['Glycopeptides']
                fragment_type = row['Type']
                precursor_mz = row['Precursor_mz']
                precursor_rt = row['precursor_rt']
                theoretical_mz = row['Theoretical_mz']  
                
                # Include theoretical_mz in fragment_id to prevent false matches
                fragment_id = f"{glycopeptide}_{fragment_type}_{precursor_mz}_{precursor_rt}_{theoretical_mz:.4f}"
                
                if fragment_id not in fragment_stats:
                    fragment_stats[fragment_id] = {
                        'files': set(),
                        'file_numbers': set(),  # Track file numbers
                        'glycopeptide': glycopeptide,
                        'fragment_type': fragment_type,
                        'precursor_mz': precursor_mz,
                        'precursor_rt': precursor_rt,
                        'theoretical_mz': theoretical_mz  # ADD THIS LINE
                    }
                
                fragment_stats[fragment_id]['files'].add(file_key)
                fragment_stats[fragment_id]['file_numbers'].add(file_key_to_number[file_key])
        
        # Convert to summary format
        reproducibility_summary = []
        total_files = len(self.all_analysis_results)
        
        for fragment_id, stats in fragment_stats.items():
            occurrence_count = len(stats['files'])
            reproducibility_percent = (occurrence_count / total_files) * 100
            
            # Create file list for display
            if occurrence_count == total_files:
                files_display = "All"
            else:
                file_numbers = sorted(stats['file_numbers'])
                files_display = ", ".join(map(str, file_numbers))
            
            reproducibility_summary.append({
                'Fragment_ID': fragment_id,
                'Glycopeptide': stats['glycopeptide'],
                'Fragment_Type': stats['fragment_type'],
                'Precursor_mz': stats['precursor_mz'],
                'Precursor_RT': stats['precursor_rt'],
                'Theoretical_mz': stats['theoretical_mz'],  # ADD THIS LINE
                'Files_Present': occurrence_count,
                'Total_Files': total_files,
                'Reproducibility_Percent': reproducibility_percent,
                'Files_List': ', '.join(sorted(stats['files'])),  # Original file keys
                'Files_Display': files_display  # Simplified display format
            })
        
        # Sort by reproducibility (lowest first)
        reproducibility_summary.sort(key=lambda x: x['Reproducibility_Percent'])
        
        return reproducibility_summary

    def show_reproducibility_report(self):
        """Show detailed reproducibility report in a dialog"""
        if len(self.all_analysis_results) < 2:
            QMessageBox.warning(self, "Insufficient Files", 
                            "Need at least 2 files to generate reproducibility report.")
            return
        
        # Get reproducibility stats
        repro_stats = self.get_fragment_reproducibility_stats()
        
        if not repro_stats:
            QMessageBox.warning(self, "No Data", "No fragment data available for reproducibility analysis.")
            return
        
        # Create report dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Fragment Reproducibility Report")
        dialog.setModal(True)
        dialog.resize(1000, 600)  # Wider for additional column
        
        layout = QVBoxLayout(dialog)
        
        # Summary stats
        total_fragments = len(repro_stats)
        perfect_repro = len([f for f in repro_stats if f['Reproducibility_Percent'] == 100])
        poor_repro = len([f for f in repro_stats if f['Reproducibility_Percent'] < 50])
        
        summary_label = QLabel(f"""
        <h3>Reproducibility Summary</h3>
        <p><b>Total Unique Fragments:</b> {total_fragments}</p>
        <p><b>Perfect Reproducibility (100%):</b> {perfect_repro} fragments</p>
        <p><b>Poor Reproducibility (&lt;50%):</b> {poor_repro} fragments</p>
        <p><b>Total Files Analyzed:</b> {len(self.all_analysis_results)}</p>
        """)
        layout.addWidget(summary_label)
        
        # Create table widget with 8 columns (added Theoretical m/z)
        table = QTableWidget(dialog)
        table.setRowCount(len(repro_stats))
        table.setColumnCount(8)
        table.setHorizontalHeaderLabels([
            'Glycopeptide', 'Fragment Type', 'Precursor m/z', 'RT (min)', 
            'Theoretical m/z', 'Files Present', 'Total Files', 'Reproducibility %'
        ])
        
        # Populate table
        for row, stats in enumerate(repro_stats):
            table.setItem(row, 0, QTableWidgetItem(stats['Glycopeptide']))
            table.setItem(row, 1, QTableWidgetItem(stats['Fragment_Type']))
            table.setItem(row, 2, QTableWidgetItem(f"{stats['Precursor_mz']:.4f}"))
            table.setItem(row, 3, QTableWidgetItem(f"{stats['Precursor_RT']:.2f}"))
            table.setItem(row, 4, QTableWidgetItem(f"{stats['Theoretical_mz']:.5f}"))  # NEW COLUMN
            table.setItem(row, 5, QTableWidgetItem(str(stats['Files_Present'])))
            table.setItem(row, 6, QTableWidgetItem(str(stats['Total_Files'])))
            table.setItem(row, 7, QTableWidgetItem(f"{stats['Reproducibility_Percent']:.1f}%"))
            
            # Color code based on reproducibility
            if stats['Reproducibility_Percent'] < 30:
                color = QColor(255, 200, 200)  # Light red
            elif stats['Reproducibility_Percent'] < 70:
                color = QColor(255, 255, 200)  # Light yellow
            else:
                color = QColor(200, 255, 200)  # Light green
            
            for col in range(8):  # Updated to 8 columns
                table.item(row, col).setBackground(color)
        
        table.resizeColumnsToContents()
        layout.addWidget(table)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        export_btn = QPushButton("Export Report")
        export_btn.clicked.connect(lambda: self.export_reproducibility_report(repro_stats))
        button_layout.addWidget(export_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        dialog.exec_()

    def export_reproducibility_report(self, repro_stats):
            """Export reproducibility report to Excel"""
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Export Reproducibility Report", "fragment_reproducibility_report.xlsx", "Excel files (*.xlsx)")
            
            if file_path:
                try:
                    df = pd.DataFrame(repro_stats)
                    df.to_excel(file_path, index=False, sheet_name='Reproducibility_Report')
                    
                    QMessageBox.information(self, "Export Complete", 
                                        f"Reproducibility report exported to:\n{file_path}")
                    self.add_log(f"Exported reproducibility report: {os.path.basename(file_path)}")
                    
                except Exception as e:
                    QMessageBox.critical(self, "Export Error", f"Failed to export report:\n{str(e)}")
    
    def generate_summary_data(self, all_results, params):
            """Generate summary data from current results"""
            try:
                # Use the same logic as create_prm_quantification_summary but return data instead of saving
                metric_name = "Intensity" if params.get('use_intensity_instead_of_area', False) else "Area"
                metric_column = "Intensity" if params.get('use_intensity_instead_of_area', False) else "Area"
                
                # Initialize results
                summary1_rows = []
                summary2_rows = []
                
                # Get file mapping (for single file, use "Current_Analysis")
                file_mapping = {"Current_Analysis": "Current_Analysis"}
                base_filenames = ["Current_Analysis"]
                
                # Process for Summary 1 (Aggregated by precursor)
                unique_precursors = set()
                for file_path, df in all_results.items():
                    if 'Glycopeptides' in df.columns and 'Precursor_mz' in df.columns:
                        for _, row in df.iterrows():
                            glycopeptide = row['Glycopeptides']
                            if isinstance(glycopeptide, str) and '_row' in glycopeptide:
                                glycopeptide = glycopeptide.split('_row')[0]
                            key = (glycopeptide, row['Precursor_mz'], row['precursor_rt'])
                            unique_precursors.add(key)
                
                # Generate Summary 1 data
                for glycopeptide, precursor_mz, precursor_rt in sorted(unique_precursors):
                    row_data = {
                        'Glycopeptides': glycopeptide,
                        'Precursor_mz': precursor_mz,
                        'Precursor_rt': precursor_rt,
                        'Fragment_type': 'All'
                    }
                    
                    # Process data for this precursor
                    for base_filename in base_filenames:
                        full_filename = file_mapping[base_filename]
                        if full_filename in all_results:
                            df = all_results[full_filename]
                            precursor_df = df[
                                (df['Glycopeptides'].str.contains(str(glycopeptide), na=False, regex=False)) & 
                                (np.isclose(df['Precursor_mz'], precursor_mz, rtol=1e-4)) & 
                                (np.isclose(df['precursor_rt'], precursor_rt, rtol=1e-2))
                            ]
                            
                            if not precursor_df.empty:
                                row_data[f'No_of_Fragments_{base_filename}'] = len(precursor_df)
                                
                                if metric_column in precursor_df.columns:
                                    total_metric = float(precursor_df[metric_column].sum())
                                else:
                                    total_metric = 0.0
                                
                                row_data[f'Total_{metric_name.lower()}_{base_filename}'] = total_metric
                                
                                if 'Fragments_Score' in precursor_df.columns:
                                    avg_score = precursor_df['Fragments_Score'].mean()
                                    row_data[f'Fragments_Score_{base_filename}'] = round(float(avg_score), 2)
                                    
                                    if avg_score >= 75:
                                        rating = "High"
                                    elif avg_score >= 50:
                                        rating = "Medium"
                                    else:
                                        rating = "Low"
                                    row_data[f'Fragments_Rating_{base_filename}'] = rating
                            else:
                                # Initialize with zeros if no data
                                row_data[f'No_of_Fragments_{base_filename}'] = 0
                                row_data[f'Total_{metric_name.lower()}_{base_filename}'] = 0.0
                                row_data[f'Fragments_Score_{base_filename}'] = 0.0
                                row_data[f'Fragments_Rating_{base_filename}'] = "Low"
                    
                    summary1_rows.append(row_data)
                
                # Generate Summary 2 data (Individual fragments)
                unique_fragments_global = set()
                for file_path, df in all_results.items():
                    if 'Glycopeptides' in df.columns and 'Type' in df.columns:
                        for _, row in df.iterrows():
                            glycopeptide = row['Glycopeptides']
                            if isinstance(glycopeptide, str) and '_row' in glycopeptide:
                                glycopeptide = glycopeptide.split('_row')[0]
                            
                            fragment_key = (
                                glycopeptide,
                                row['Precursor_mz'],
                                row['precursor_rt'],
                                row['Type'],
                                row.get('FragmentType', 'unknown'),
                                row['Theoretical_mz']
                            )
                            unique_fragments_global.add(fragment_key)
                
                for fragment_key in sorted(unique_fragments_global):
                    glycopeptide, precursor_mz, precursor_rt, fragment_name, fragment_type, theoretical_mz = fragment_key
                    
                    row_data = {
                        'Glycopeptides': glycopeptide,
                        'Precursor_mz': precursor_mz,
                        'Precursor_rt': precursor_rt,
                        'Fragment': fragment_name,
                        'Fragment_type': fragment_type,
                        'Theoretical_mz': theoretical_mz
                    }
                    
                    # Initialize metric columns
                    for base_filename in base_filenames:
                        row_data[f'{metric_name}_{base_filename}'] = 0.0
                    
                    # Fill in actual values
                    for base_filename in base_filenames:
                        full_filename = file_mapping[base_filename]
                        if full_filename in all_results:
                            df = all_results[full_filename]
                            
                            matching_fragments = df[
                                (df['Glycopeptides'].str.contains(str(glycopeptide), na=False, regex=False)) &
                                (np.isclose(df['Precursor_mz'], precursor_mz, rtol=1e-4)) &
                                (np.isclose(df['precursor_rt'], precursor_rt, rtol=1e-2)) &
                                (df['Type'] == fragment_name) &
                                (np.isclose(df['Theoretical_mz'], theoretical_mz, rtol=1e-6))
                            ]
                            
                            if not matching_fragments.empty:
                                if metric_column in matching_fragments.columns:
                                    metric_value = float(matching_fragments.iloc[0][metric_column])
                                else:
                                    metric_value = 0.0
                                
                                row_data[f'{metric_name}_{base_filename}'] = metric_value
                    
                    # Calculate prevalence (always 100% for single file)
                    row_data['Fragment_Prevalence'] = 100.0
                    row_data['CV_Percent'] = 0.0  # No CV for single file
                    
                    summary2_rows.append(row_data)
                
                # Create DataFrames
                summary1_df = pd.DataFrame(summary1_rows)
                summary2_df = pd.DataFrame(summary2_rows)
                
                return {
                    'summary1': summary1_df,
                    'summary2': summary2_df
                }
                
            except Exception as e:
                self.add_log(f"Error generating summary data: {e}")
                return {
                    'summary1': pd.DataFrame(),
                    'summary2': pd.DataFrame()
                }
        
    def view_generated_plots(self):
            """Open the folder containing generated plots"""
            self.open_output_folder()

    def regenerate_plots(self):
            """Regenerate plots with current settings"""
            if self.current_cached_data and not self.current_matched_fragments.empty:
                try:
                    self.add_log("Regenerating plots...")
                    params = self.get_parameters()

                    # Log the parameters being used
                    self.add_log(f"Using max fragments displayed: {params.get('max_fragments_displayed', 'not set')}")
                    
                    # Get output directory
                    output_dir = params.get('output_directory', None)
                    if output_dir and not os.path.exists(output_dir):
                        os.makedirs(output_dir, exist_ok=True)
                    
                    # Create result dictionary to store generated figures
                    generated_figures = {}
                    
                    # Get unique glycopeptides for processing
                    unique_glycopeptides = self.current_matched_fragments['Glycopeptides'].unique()
                    self.add_log(f"Regenerating plots for {len(unique_glycopeptides)} unique glycopeptides...")
                    
                    # Call plot generation functions
                    if params.get('generate_eic_plots', False):
                        self.add_log("Generating EIC plots...")
                        eic_figures = plot_fragment_eics(
                            self.current_cached_data,
                            self.current_matched_fragments,
                            peptide=None, 
                            glycan_code=None,
                            output_dir=output_dir,
                            intensity_threshold=params.get('intensity_threshold', 1000),
                            rt_window=params.get('rt_window', 5.0),
                            #ms1_ppm_tolerance=params.get('ms1_ppm_tolerance', 10),
                            plot_style=params.get('plot_style', 'default'),
                            normalize_intensities=params.get('normalize_intensities', True),
                            figure_width=params.get('figure_width', 10),
                            figure_height=params.get('figure_height', 6),
                            dpi=params.get('dpi', 100),
                            show_titles=params.get('show_titles', True),
                            show_grid=params.get('show_grid', True),
                            save_plots=output_dir is not None,
                            max_fragments_displayed=params.get('max_fragments_displayed', 20)
                        )
                        
                        if eic_figures:
                            generated_figures['eic'] = eic_figures
                            self.add_log(f"Generated {len(eic_figures)} EIC plots")
                    
                    if params.get('generate_ms2_plots', False):
                        self.add_log("Generating MS2 plots...")
                        ms2_figures = plot_ms2_spectra(
                            self.current_cached_data,
                            self.current_matched_fragments,
                            glycan_code=None,  
                            peptide=None, 
                            output_dir=output_dir,
                            max_fragments_displayed=params.get('max_fragments_displayed', 30),
                            intensity_threshold=params.get('intensity_threshold', 1000),
                            plot_style=params.get('plot_style', 'default'),
                            figure_width=params.get('figure_width', 10),
                            figure_height=params.get('figure_height', 6),
                            dpi=params.get('dpi', 100),
                            label_fragments=params.get('label_fragments', True),
                            show_titles=params.get('show_titles', True),
                            normalize_intensities=params.get('normalize_intensities', True),
                            save_plots=output_dir is not None
                        )
                        
                        if ms2_figures:
                            generated_figures['ms2'] = ms2_figures
                            self.add_log(f"Generated {len(ms2_figures)} MS2 plots")
                    
                    # Store generated figures for later access
                    self.generated_figures = generated_figures
                    
                    self.add_log("Plot regeneration completed")
                    self.plots_status_label.setText("Plots regenerated successfully")
                    
                    # If we have a currently selected glycopeptide, refresh its display
                    if hasattr(self, 'selected_glycopeptide') and self.selected_glycopeptide:
                        glycopeptide = self.selected_glycopeptide['name']
                        precursor_mz = self.selected_glycopeptide['precursor_mz']
                        precursor_rt = self.selected_glycopeptide['precursor_rt']
                        row_id = self.selected_glycopeptide.get('row_id')
                        
                        self.add_log(f"Refreshing display for {glycopeptide}")
                        self.show_eic_for_glycopeptide(glycopeptide, precursor_mz, precursor_rt, row_id)
                    
                except Exception as e:
                    error_msg = f"Error regenerating plots: {e}"
                    self.add_log(error_msg)
                    traceback.print_exc()  # Print stack trace for debugging
                    QMessageBox.critical(self, "Plot Error", error_msg)
            else:
                QMessageBox.warning(self, "No Data", "No analysis data available for plot generation.")

    def export_current_results(self):
        """Export ALL analysis results to Excel with automatic PRM summary - ENHANCED with parameter-updated areas"""
        
        # Check if we have any results
        if not hasattr(self, 'all_analysis_results') or not self.all_analysis_results:
            QMessageBox.warning(self, "No Results", "No analysis results available for export.")
            return
        
        try:
            # Get save location
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Export All Results with Summary", "all_analysis_results_with_summary.xlsx", "Excel files (*.xlsx)")
            
            if file_path:
                self.export_status_label.setText("Generating comprehensive export with updated areas...")
                
                # CRITICAL FIX: Apply any custom EIC parameters before export
                self._apply_all_custom_parameters_before_export()
                
                # Prepare results for ALL files with updated areas
                all_results_for_summary = {}
                all_matched_fragments_combined = pd.DataFrame()
                
                # Collect data from ALL analyzed files
                for file_key, file_data in self.all_analysis_results.items():
                    matched_fragments = file_data.get('matched_fragments', pd.DataFrame())
                    
                    if not matched_fragments.empty:
                        # Add file identifier to each row
                        matched_fragments_with_file = matched_fragments.copy()
                        matched_fragments_with_file['Source_File'] = file_key
                        
                        # Add parameter information to track which parameters were used
                        matched_fragments_with_file['EIC_Parameters_Applied'] = self._get_parameter_info_for_fragments(matched_fragments_with_file)
                        
                        # Add to combined dataframe
                        all_matched_fragments_combined = pd.concat([all_matched_fragments_combined, matched_fragments_with_file], ignore_index=True)
                        
                        # Add to summary data (using filename as key)
                        all_results_for_summary[file_key] = matched_fragments
                        
                        self.add_log(f"Added {len(matched_fragments)} fragments from {file_key} to export (with updated areas)")
                    else:
                        self.add_log(f"No fragments found for {file_key}")
                
                if all_matched_fragments_combined.empty:
                    QMessageBox.warning(self, "No Data", "No fragment data available across all files for export.")
                    return
                
                # Get parameters for summary generation
                params = self.get_parameters()
                
                # Create comprehensive Excel file with multiple sheets
                with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                    
                    # Sheet 1: ALL matched fragments from all files combined (with updated areas)
                    prepared_all_fragments = prepare_matched_fragments_for_export(all_matched_fragments_combined)
                    prepared_all_fragments.to_excel(writer, sheet_name='All_Matched_Fragments', index=False)
                    self.add_log(f"Exported {len(prepared_all_fragments)} total fragments with updated areas to All_Matched_Fragments sheet")
                    
                    # Sheet 2 & 3: Generate comprehensive summary using ALL files with updated areas
                    if len(all_results_for_summary) > 0:
                        try:
                            # FIXED: Use updated results for summary generation
                            summary_path = create_prm_quantification_summary(
                                output_dir=os.path.dirname(file_path),
                                all_results=all_results_for_summary,  # This now contains updated areas
                                fdr_grade_cutoff=params.get('fdr_grade_cutoff'),
                                fragment_types="all",
                                use_intensity_instead_of_area=params.get('use_intensity_instead_of_area', False)
                            )
                            
                            # Read the generated summary file and copy sheets to our export file
                            if summary_path and os.path.exists(summary_path):
                                summary_workbook = pd.ExcelFile(summary_path)
                                
                                # Copy Summary_1 sheet
                                if 'Summary_1' in summary_workbook.sheet_names:
                                    summary1_df = pd.read_excel(summary_path, sheet_name='Summary_1')
                                    summary1_df.to_excel(writer, sheet_name='Summary_1_Precursors', index=False)
                                    self.add_log(f"Added Summary_1_Precursors sheet with {len(summary1_df)} entries (updated areas)")
                                
                                # Copy Summary_2 sheet  
                                if 'Summary_2' in summary_workbook.sheet_names:
                                    summary2_df = pd.read_excel(summary_path, sheet_name='Summary_2')
                                    summary2_df.to_excel(writer, sheet_name='Summary_2_Individual', index=False)
                                    self.add_log(f"Added Summary_2_Individual sheet with {len(summary2_df)} entries (updated areas)")
                                
                                # Clean up temporary summary file
                                try:
                                    os.remove(summary_path)
                                except:
                                    pass
                            else:
                                self.add_log("Warning: Could not generate summary data")
                            
                        except Exception as e:
                            self.add_log(f"Warning: Summary generation failed: {e}")
                            # Continue with export even if summary fails
                    
                    # Sheet 4: EIC Parameter Summary (NEW)
                    parameter_summary = self._generate_parameter_summary()
                    if not parameter_summary.empty:
                        parameter_summary.to_excel(writer, sheet_name='EIC_Parameters_Used', index=False)
                        self.add_log(f"Added EIC_Parameters_Used sheet with {len(parameter_summary)} parameter sets")
                    
                    # Sheet 5: Individual file breakdown (with area totals)
                    individual_breakdown = []
                    for file_key, file_data in self.all_analysis_results.items():
                        matched_fragments = file_data.get('matched_fragments', pd.DataFrame())
                        if not matched_fragments.empty:
                            total_area = matched_fragments['Area'].sum() if 'Area' in matched_fragments.columns else 0
                            avg_area = matched_fragments['Area'].mean() if 'Area' in matched_fragments.columns else 0
                            
                            breakdown_row = {
                                'File': file_key,
                                'Total_Fragments': len(matched_fragments),
                                'Unique_Precursors': matched_fragments['Precursor_mz'].nunique() if 'Precursor_mz' in matched_fragments.columns else 0,
                                'Unique_Glycopeptides': matched_fragments['Glycopeptides'].nunique() if 'Glycopeptides' in matched_fragments.columns else 0,
                                'Total_Area': round(total_area, 2),
                                'Average_Area': round(avg_area, 2),
                                'Avg_Fragment_Score': matched_fragments['Fragments_Score'].mean() if 'Fragments_Score' in matched_fragments.columns else 0,
                                'Grade_A_Count': len(matched_fragments[matched_fragments.get('FDR_Grade', '') == 'A']),
                                'Grade_B_Count': len(matched_fragments[matched_fragments.get('FDR_Grade', '') == 'B']),
                                'Grade_C_Count': len(matched_fragments[matched_fragments.get('FDR_Grade', '') == 'C']),
                                'Grade_D_Count': len(matched_fragments[matched_fragments.get('FDR_Grade', '') == 'D']),
                                'Grade_F_Count': len(matched_fragments[matched_fragments.get('FDR_Grade', '') == 'F']),
                                'Custom_Parameters_Applied': self._count_custom_parameters_in_file(file_key)
                            }
                            individual_breakdown.append(breakdown_row)
                    
                    if individual_breakdown:
                        breakdown_df = pd.DataFrame(individual_breakdown)
                        breakdown_df.to_excel(writer, sheet_name='File_Breakdown', index=False)
                        self.add_log(f"Added File_Breakdown sheet with {len(breakdown_df)} files")
                
                # Update status
                total_files = len(all_results_for_summary)
                total_fragments = len(all_matched_fragments_combined)
                custom_params_count = len(getattr(self, 'glycopeptide_specific_params', {}))
                
                self.export_status_label.setText(f"Export completed: {total_fragments} fragments from {total_files} files ({custom_params_count} custom parameters applied)")
                self.add_log(f"Comprehensive export completed with updated areas: {os.path.basename(file_path)}")
                
                # Show completion message
                QMessageBox.information(self, "Export Complete", 
                                    f"Comprehensive results exported successfully to:\n{file_path}\n\n"
                                    f"Data included:\n"
                                    f"• All_Matched_Fragments: {total_fragments} fragments with updated areas\n"
                                    f"• Summary_1_Precursors: Aggregated quantification (updated areas)\n"
                                    f"• Summary_2_Individual: Individual fragment quantification (updated areas)\n"
                                    f"• EIC_Parameters_Used: Custom parameters applied\n"
                                    f"• File_Breakdown: Per-file statistics with area totals\n\n"
                                    f"Custom EIC parameters applied: {custom_params_count}\n"
                                    f"Files processed: {', '.join(all_results_for_summary.keys())}")
                    
        except Exception as e:
            error_msg = f"Error exporting results: {e}"
            self.add_log(error_msg)
            self.export_status_label.setText("Export failed")
            QMessageBox.critical(self, "Export Error", error_msg)
            traceback.print_exc()

    def _apply_all_custom_parameters_before_export(self):
        """Apply all stored custom EIC parameters to their respective fragments before export"""
        if not hasattr(self, 'glycopeptide_specific_params') or not self.glycopeptide_specific_params:
            self.add_log("No custom EIC parameters to apply before export")
            return
        
        self.add_log(f"Applying {len(self.glycopeptide_specific_params)} custom parameter sets before export...")
        
        for glycopeptide, params in self.glycopeptide_specific_params.items():
            try:
                is_global = not params.get('file_scope', False)
                param_file_key = params.get('file_key') if not is_global else None
                
                if is_global:
                    # Apply to all files containing this glycopeptide
                    for file_key in self.all_analysis_results.keys():
                        self._apply_parameters_to_glycopeptide_in_file(glycopeptide, params, file_key)
                else:
                    # Apply only to specific file
                    if param_file_key and param_file_key in self.all_analysis_results:
                        self._apply_parameters_to_glycopeptide_in_file(glycopeptide, params, param_file_key)
                        
            except Exception as e:
                self.add_log(f"Error applying parameters for {glycopeptide}: {e}")
        
        self.add_log("Completed applying custom parameters before export")

    def _apply_parameters_to_glycopeptide_in_file(self, glycopeptide, params, file_key):
        """Apply specific parameters to a glycopeptide in a specific file"""
        try:
            if file_key not in self.all_analysis_results:
                return
                
            file_data = self.all_analysis_results[file_key]
            matched_fragments = file_data['matched_fragments']
            
            # Find all instances of this glycopeptide
            glycopeptide_mask = matched_fragments['Glycopeptides'] == glycopeptide
            if not glycopeptide_mask.any():
                return
            
            # Group by precursor to handle multiple RT instances
            glycopeptide_data = matched_fragments[glycopeptide_mask]
            updated_count = 0
            
            for (precursor_mz, precursor_rt), group in glycopeptide_data.groupby(['Precursor_mz', 'precursor_rt']):
                # Temporarily set context for this file
                original_file_key = self.current_file_key
                original_cached_data = getattr(self, 'current_cached_data', None)
                original_matched_fragments = self.current_matched_fragments.copy()
                
                try:
                    self.current_file_key = file_key
                    self.current_cached_data = file_data.get('cached_data', {})
                    self.current_matched_fragments = matched_fragments.copy()
                    
                    # Apply parameters to this precursor group
                    self._update_fragment_areas_with_new_params(
                        glycopeptide, precursor_mz, precursor_rt, params
                    )
                    
                    # Update stored data
                    file_data['matched_fragments'] = self.current_matched_fragments.copy()
                    updated_count += len(group)
                    
                finally:
                    # Restore context
                    self.current_file_key = original_file_key
                    if original_cached_data is not None:
                        self.current_cached_data = original_cached_data
                    self.current_matched_fragments = original_matched_fragments
            
            if updated_count > 0:
                scope = "global" if not params.get('file_scope', False) else "file-specific"
                self.add_log(f"  Applied {scope} parameters to {updated_count} fragments of {glycopeptide} in {file_key}")
                
        except Exception as e:
            self.add_log(f"Error applying parameters to {glycopeptide} in {file_key}: {e}")

    def _generate_parameter_summary(self):
        """Generate a summary of all custom EIC parameters used"""
        try:
            if not hasattr(self, 'glycopeptide_specific_params') or not self.glycopeptide_specific_params:
                return pd.DataFrame()
            
            parameter_rows = []
            for glycopeptide, params in self.glycopeptide_specific_params.items():
                row = {
                    'Glycopeptide': glycopeptide,
                    'Max_RT_Window': params.get('max_rt_window', 1.5),
                    'Back_Window_Ratio': params.get('back_window_ratio', 0.5),
                    'Display_Time_Extension': params.get('display_time_extension', 5.0),
                    'Scope': 'Global' if not params.get('file_scope', False) else 'File-Specific',
                    'Target_File': params.get('file_key', 'All Files'),
                    'Applied_At': 'Export Time'
                }
                parameter_rows.append(row)
            
            return pd.DataFrame(parameter_rows)
            
        except Exception as e:
            self.add_log(f"Error generating parameter summary: {e}")
            return pd.DataFrame()

    def _get_parameter_info_for_fragments(self, fragments_df):
        """Add parameter information to fragments dataframe"""
        try:
            if not hasattr(self, 'glycopeptide_specific_params'):
                return 'Default Parameters'
            
            parameter_info = []
            for _, row in fragments_df.iterrows():
                glycopeptide = row['Glycopeptides']
                if glycopeptide in self.glycopeptide_specific_params:
                    params = self.glycopeptide_specific_params[glycopeptide]
                    scope = 'Global' if not params.get('file_scope', False) else 'File-Specific'
                    info = f"Custom-{scope}"
                else:
                    info = 'Default'
                parameter_info.append(info)
            
            return parameter_info
            
        except Exception as e:
            self.add_log(f"Error getting parameter info: {e}")
            return ['Unknown'] * len(fragments_df)

    def _count_custom_parameters_in_file(self, file_key):
        """Count how many glycopeptides in a file have custom parameters"""
        if not hasattr(self, 'glycopeptide_specific_params'):
            return 0
        
        count = 0
        for glycopeptide, params in self.glycopeptide_specific_params.items():
            if not params.get('file_scope', False):  # Global parameters
                count += 1
            elif params.get('file_key') == file_key:  # File-specific parameters
                count += 1
        
        return count

    def analysis_finished(self, success, message):
        """Enhanced analysis completion with CLI-style logic - no Excel dependency"""
        try:
            print("DEBUG: analysis_finished called")
            self.timer.stop()
            
            if success:
                print("DEBUG: Analysis success = True")
                self.add_log("Analysis completed successfully!")
                self.status_label.setText("Analysis completed successfully")
                
                # CLI-STYLE: Check for results in memory (like CLI's all_results)
                has_results = False
                
                # Check worker's all_results (CLI equivalent)
                if hasattr(self.analysis_worker, 'all_results') and self.analysis_worker.all_results:
                    print(f"DEBUG: Found CLI-style results for {len(self.analysis_worker.all_results)} files")
                    self.all_summary_results = self.analysis_worker.all_results
                    has_results = True
                
                # Check worker's comprehensive file results (GUI enhancement)
                if hasattr(self.analysis_worker, 'all_file_results') and self.analysis_worker.all_file_results:
                    print(f"DEBUG: Found {len(self.analysis_worker.all_file_results)} file results")
                    self.all_analysis_results = self.analysis_worker.all_file_results
                    has_results = True
                    
                    # If we don't have CLI-style results, create them from file results
                    if not hasattr(self, 'all_summary_results') or not self.all_summary_results:
                        print("DEBUG: Creating CLI-style results from file results")
                        self.all_summary_results = {}
                        for file_key, file_data in self.all_analysis_results.items():
                            if (isinstance(file_data, dict) and 
                                'matched_fragments' in file_data and 
                                file_data['matched_fragments'] is not None and 
                                not file_data['matched_fragments'].empty):
                                self.all_summary_results[file_key] = file_data['matched_fragments']
                        print(f"DEBUG: Created CLI-style results for {len(self.all_summary_results)} files")
                
                # CLI-STYLE CHECK: Do we have any results at all?
                if has_results and (
                    (hasattr(self, 'all_summary_results') and self.all_summary_results) or
                    (hasattr(self, 'all_analysis_results') and self.all_analysis_results)
                ):
                    print("DEBUG: Results available - proceeding like CLI")
                    
                    # Log results summary (like CLI)
                    if hasattr(self, 'all_summary_results') and self.all_summary_results:
                        total_fragments = sum(len(df) for df in self.all_summary_results.values() if df is not None and not df.empty)
                        self.add_log(f"Results summary: {len(self.all_summary_results)} files, {total_fragments} total fragments")
                    
                    # CRITICAL FIX: Create backup immediately after loading results
                    self._backup_original_data()
                    print("DEBUG: Created backup of original data")
                    
                    # Set up file navigation
                    print("DEBUG: Setting up file navigation")
                    if hasattr(self, 'all_analysis_results') and self.all_analysis_results:
                        self.available_files = list(self.all_analysis_results.keys())
                    elif hasattr(self, 'all_summary_results') and self.all_summary_results:
                        self.available_files = list(self.all_summary_results.keys())
                    else:
                        self.available_files = []
                    
                    self.current_file_index = 0
                    
                    # Show/hide file navigation based on number of files
                    if len(self.available_files) > 1:
                        print("DEBUG: Multi-file navigation setup")
                        self.file_nav_group.setVisible(True)
                        self.file_selector.clear()
                        self.file_selector.addItems(self.available_files)
                        try:
                            self.update_file_navigation_state()
                            print("DEBUG: File navigation state updated")
                        except Exception as e:
                            print(f"DEBUG: Error in update_file_navigation_state: {e}")
                        self.add_log(f"Multi-file navigation enabled for {len(self.available_files)} files")
                    else:
                        print("DEBUG: Single file mode")
                        self.file_nav_group.setVisible(False)
                        self.add_log("Single file mode - navigation controls hidden")
                    
                    # Load data for the first file (CLI equivalent: use first result)
                    if self.available_files:
                        print("DEBUG: Loading first file data")
                        first_file = self.available_files[0]
                        self.current_file_key = first_file
                        
                        # Load first file's data
                        try:
                            # Try comprehensive file results first
                            if hasattr(self, 'all_analysis_results') and first_file in self.all_analysis_results:
                                file_data = self.all_analysis_results[first_file]
                                self.current_matched_fragments = file_data['matched_fragments'].copy()
                                self.current_cached_data = file_data.get('cached_data', {})
                                self.current_analysis_params = file_data.get('analysis_params', {})
                            # Fallback to CLI-style results
                            elif hasattr(self, 'all_summary_results') and first_file in self.all_summary_results:
                                self.current_matched_fragments = self.all_summary_results[first_file].copy()
                                self.current_cached_data = {}
                                self.current_analysis_params = {}
                            else:
                                raise Exception(f"No data found for {first_file}")
                            
                            print(f"DEBUG: Loaded {len(self.current_matched_fragments)} fragments from {first_file}")
                            self.add_log(f"Loaded {len(self.current_matched_fragments)} fragments from {first_file} into Output tab")
                            
                        except Exception as e:
                            print(f"DEBUG: Error loading first file data: {e}")
                            self.add_log(f"Error loading file data: {e}")
                            self.current_matched_fragments = pd.DataFrame()
                            self.current_cached_data = {}
                            self.current_analysis_params = {}
                    
                    # Get cached data from analysis worker
                    print("DEBUG: Getting cached data from worker")
                    if hasattr(self.analysis_worker, 'cached_mzml_data') and self.analysis_worker.cached_mzml_data:
                        # Store cached data from the last processed file for EIC display
                        if not self.current_cached_data:
                            self.current_cached_data = self.analysis_worker.cached_mzml_data
                        print(f"DEBUG: Loaded cached data: {len(self.current_cached_data)} precursors")
                        self.add_log(f"Loaded cached data: {len(self.current_cached_data)} precursors")
                    else:
                        print("DEBUG: No cached data available")
                        self.add_log("Warning: No cached data available")
                        if not self.current_cached_data:
                            self.current_cached_data = {}
                    
                    # Enable output tab features and auto-populate fragment tree
                    if not self.current_matched_fragments.empty:
                        print("DEBUG: Setting up output tab features")
                        try:
                            # Enable buttons - CHECK FOR EXISTENCE FIRST
                            buttons_to_enable = [
                                'auto_remove_repro_btn',
                                'auto_remove_df_btn',  # Old button name
                                'restore_all_btn',
                                'apply_removals_btn',
                                'export_results_btn',
                                'show_repro_report_btn'
                            ]
                            
                            for button_name in buttons_to_enable:
                                if hasattr(self, button_name):
                                    try:
                                        button = getattr(self, button_name)
                                        if button and (not hasattr(button, 'isWidgetType') or button.isWidgetType()) and hasattr(button, 'setEnabled'):
                                            button.setEnabled(True)
                                            print(f"DEBUG: Enabled {button_name}")
                                    except Exception as e:
                                        print(f"DEBUG: Could not enable {button_name}: {e}")
                            
                            print("DEBUG: Buttons enabled")
                            
                            # Update status labels
                            if hasattr(self, 'removal_status_label'):
                                self.removal_status_label.setText("Fragment curation interface ready")
                            
                            print("DEBUG: About to populate fragment tree")
                            # AUTO-POPULATE fragment tree immediately
                            self.populate_fragment_tree()
                            print("DEBUG: Fragment tree populated")
                            
                            self.update_removal_statistics()
                            print("DEBUG: Removal statistics updated")
                            
                            self.add_log("Fragment curation interface populated automatically")
                            
                            print("DEBUG: About to update results display")
                            # Update results display
                            self.update_results_display()
                            print("DEBUG: Results display updated")
                            
                            print("DEBUG: About to switch to Output tab")
                            # Switch to Output tab to show results
                            self.tab_widget.setCurrentIndex(2)  # Output tab
                            print("DEBUG: Switched to Output tab")
                            
                            if len(self.available_files) > 1:
                                self.add_log(f"Output tab ready with multi-file support: {len(self.available_files)} files loaded")
                            else:
                                self.add_log(f"Output tab ready with {len(self.current_matched_fragments)} fragments")
                                
                        except Exception as e:
                            print(f"DEBUG: Error in output tab setup: {e}")
                            self.add_log(f"Error setting up output tab: {e}")
                            import traceback
                            traceback.print_exc()
                            return  # Don't continue if there's an error
                    else:
                        print("DEBUG: No fragment data available")
                        self.add_log("No fragment data available for Output tab")
                else:
                    # CLI-STYLE: Like CLI's "No results to summarize"
                    print("DEBUG: No results available - like CLI's 'No results to summarize'")
                    self.add_log("No results to summarize - no matched fragments generated")
                    self.status_label.setText("Analysis completed but no results generated")
                    # Show informative message to user
                    try:
                        from PyQt5.QtWidgets import QMessageBox
                        QMessageBox.information(self, "Analysis Complete", 
                                            "Analysis completed but no matched fragments were generated.\n\n"
                                            "This could be due to:\n"
                                            "• No matching fragments found in the data\n"
                                            "• Incorrect analysis parameters\n"
                                            "• Data format issues\n\n"
                                            "Check the log for details.")
                    except:
                        print("Could not show info dialog")
                    
            else:
                print(f"DEBUG: Analysis failed: {message}")
                self.add_log(f"Analysis failed: {message}")
                self.status_label.setText(f"Analysis failed: {message}")
            
            print("DEBUG: Re-enabling UI controls")
            # Re-enable start button and hide progress bar
            try:
                self.start_button.setEnabled(True)
                self.cancel_button.setEnabled(False)
                self.progress_bar.setVisible(False)
            except Exception as e:
                print(f"DEBUG: Error updating UI controls: {e}")
                self.add_log(f"Warning: Could not update UI controls: {e}")
            
            print("DEBUG: Cleaning up worker")
            # Clean up worker
            try:
                if self.analysis_worker:
                    self.analysis_worker.deleteLater()
                    self.analysis_worker = None
            except Exception as e:
                print(f"DEBUG: Error cleaning up worker: {e}")
                self.add_log(f"Warning: Could not clean up worker: {e}")
            
            print("DEBUG: analysis_finished completed successfully")
            
        except Exception as e:
            print(f"DEBUG: CRITICAL ERROR in analysis_finished: {e}")
            self.add_log(f"CRITICAL ERROR in analysis_finished: {e}")
            import traceback
            traceback.print_exc()
            
            # Try to show error dialog
            try:
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.critical(self, "Analysis Completion Error", 
                                f"Error completing analysis:\n{str(e)}\n\nSee console for details.")
            except:
                print("Could not show error dialog")

class ProcessStage:
    def __init__(self, parent, stage_name):
        self.parent = parent
        self.stage_name = stage_name
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        self.parent.log_important_update(f"Starting: {self.stage_name}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = time.time() - self.start_time
        if exc_type is None:
            self.parent.log_important_update(f"Completed: {self.stage_name} ({elapsed:.1f}s)")
        else:
            self.parent.log_important_update(f"Failed: {self.stage_name} - {exc_val}", "ERROR")

def main_gui():
    """Enhanced GUI main function with proper multiple file support"""
    import sys
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("GlypPRM")
    app.setApplicationVersion("1.0")
    
    # Create and show the main window
    window = GlycanAnalysisGUI()
    window.show()
    
    # Run the application
    sys.exit(app.exec_())

def main_cli():
    """Main function that supports both .raw and .mzML file analysis with the specified options."""
    # ... (keep your existing main function code but rename it to main_cli)
    # Setup parameters
    output_dir = "glycan_analysis_output"
    input_excel = "glycan_list.xlsx"
    save_excel = True 
    use_intensity_instead_of_area = False
    modification_type = 3
    use_strict_rt_window = True
    enable_custom_peptide_fragments = True  
    glycan_type = "N"
    prefer_fisher_py = True  
    intensity_threshold=1000
    rt_window = 10.0
    max_rt_window = 1.5
    back_window_ratio = 0.5
    max_rt_difference = 1.0
    display_time_extension = 5.0
    fragment_types = "all"
    fdr_grade_cutoff = "D"
    generate_eic_plots = True  
    generate_ms2_plots = True
    max_fragments_displayed = 20
    generate_glycan_by_ions = True
    generate_peptide_by_ions = True
    generate_cz_peptide_fragment = False
    generate_cz_glycan_fragment = False
    use_excel_precursor = True 
    use_excel_rt_window = True 
    use_excel_pepmass = False
    use_excel_peptide_mod = False
    use_cam = False  
    fixed_mods = [""]  
    variable_mods = [""]  

    # Create a memory manager to track and clean up resources
    
    # Find all .mzML and .raw files in the current directory
    mzml_files = glob.glob("*.mzML")
    raw_files = glob.glob("*.raw")
    
    print(f"Found {len(mzml_files)} mzML files and {len(raw_files)} RAW files")
    
    # Combine all files for processing
    all_files = [(f, 'mzml') for f in mzml_files] + [(f, 'raw') for f in raw_files]
    
    if not all_files:
        print("No .mzML or .raw files found in the current directory")
        return
        
    print(f"Processing a total of {len(all_files)} files")
    
    # Ensure output directory exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Dictionary to store all results for summary
    all_results = {}
    
    # Process each file
    for file_path, file_type in all_files:
        print(f"\n{'='*60}")
        print(f"Processing {file_type.upper()} file: {file_path}")
        print(f"{'='*60}")

        # Generate appropriate output filename based on input file
        input_basename = os.path.splitext(os.path.basename(file_path))[0]
        excel_output_file = f"results_{input_basename}.xlsx"
        
        # Call analyze_and_export_all_glycans - NO EXCEL READING LOGIC HERE
        output_path, cached_data, matched_fragments = analyze_and_export_all_glycans(
            excel_input_file=input_excel,
            excel_output_file=excel_output_file,
            input_file=file_path,  
            save_excel=save_excel,
            use_intensity_instead_of_area=use_intensity_instead_of_area,
            modification_type=modification_type,
            use_excel_precursor=use_excel_precursor,
            glycan_type=glycan_type,  
            intensity_threshold=intensity_threshold,     
            max_rt_window=max_rt_window,
            rt_window=rt_window,
            use_strict_rt_window=use_strict_rt_window,  
            use_provided_rt=True,
            max_rt_difference=max_rt_difference,
            back_window_ratio=back_window_ratio,
            display_time_extension=display_time_extension,
            fragment_types=fragment_types,
            fdr_grade_cutoff=fdr_grade_cutoff,
            output_dir=output_dir,
            generate_eic_plots=generate_eic_plots,  
            generate_ms2_plots=generate_ms2_plots,
            max_fragments_displayed=max_fragments_displayed,
            use_cam=use_cam,
            fixed_mods=fixed_mods,
            variable_mods=variable_mods,
            generate_glycan_by_ions=generate_glycan_by_ions,
            generate_peptide_by_ions=generate_peptide_by_ions,
            generate_cz_peptide_fragment=generate_cz_peptide_fragment,
            enable_custom_peptide_fragments=enable_custom_peptide_fragments,  
            generate_cz_glycan_fragment=generate_cz_glycan_fragment,   
            use_excel_rt_window=use_excel_rt_window, 
            use_excel_pepmass=use_excel_pepmass,
            use_excel_peptide_mod=use_excel_peptide_mod,
            prefer_fisher_py=prefer_fisher_py  
        )
        
        # Store the results for summary - NO EXCEL READING
        if matched_fragments is not None and not matched_fragments.empty:
            all_results[file_path] = matched_fragments
            print(f"Added {len(matched_fragments)} matched fragments to summary")
        else:
            print(f"No matched fragments available for summary")
        
        print(f"Finished processing {file_path}" + (f" -> Output saved to: {output_path}" if save_excel and output_path else " -> Results processed in memory only"))
        # Clean up memory after each file
        import gc
        gc.collect()

    # Create the summary report if we have results
    if all_results:
        summary_path = create_prm_quantification_summary(
            output_dir, 
            all_results, 
            fragment_types=fragment_types,
            fdr_grade_cutoff=fdr_grade_cutoff,
            use_intensity_instead_of_area=use_intensity_instead_of_area  # NEW
        )
        if summary_path:
            print(f"PRM quantification summary saved to: {summary_path}")
    else:
        print("No results to summarize")

    print("\n=== Analysis Complete ===")

def main():
    """Main entry point - choose between GUI and CLI based on arguments"""
    if len(sys.argv) > 1 and sys.argv[1] == "--gui":
        main_gui()
    else:
        # Check if we're in an interactive environment
        try:
            # Try to import PyQt5 to see if GUI is available
            from PyQt5.QtWidgets import QApplication
            # If no command line args and GUI available, start GUI
            if len(sys.argv) == 1:
                print("Starting GUI mode... (Use --cli to force command line mode)")
                main_gui()
            else:
                main_cli()
        except ImportError:
            # PyQt5 not available, use CLI
            print("PyQt5 not available, using command line interface")
            main_cli()

if __name__ == "__main__":
    main()

