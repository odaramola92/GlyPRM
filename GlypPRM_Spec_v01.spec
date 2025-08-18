# -*- mode: python ; coding: utf-8 -*-

import sys
import os
import warnings
import subprocess
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

# Suppress SIP deprecation warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="sip")

block_cipher = None

# Version management
# ...existing code...
def get_version():
    """Get version from git tags or fallback to VERSION file or default."""
    import subprocess
    from pathlib import Path

    repo_root = Path(__file__).resolve().parent
    try:
        # Use --tags --always --dirty to get a sensible string even without annotated tags
        ver = subprocess.check_output(
            ['git', 'describe', '--tags', '--always', '--dirty'],
            cwd=str(repo_root),
            text=True,
            stderr=subprocess.DEVNULL
        ).strip()
        return ver
    except Exception:
        # Try reading a VERSION file if present (useful for source distributions)
        vfile = repo_root / "VERSION"
        if vfile.exists():
            return vfile.read_text().strip()
        # Final fallback
        return "1.0.1"

VERSION = get_version()
print(f"Building GlypPRM v{VERSION}")
# ...existing code...

# Safe data collection function
def safe_collect_data_files(package_name, include_py_files=False):
    """Safely collect data files with better error handling"""
    try:
        data_files = collect_data_files(package_name, include_py_files=include_py_files)
        print(f"✓ Collected {len(data_files)} data files from {package_name}")
        return data_files
    except ImportError:
        print(f"⚠ Package {package_name} not found, skipping data collection")
        return []
    except Exception as e:
        print(f"✗ Error collecting data from {package_name}: {e}")
        return []

def safe_collect_binaries(package_name):
    """Safely collect binary files"""
    try:
        binaries = collect_dynamic_libs(package_name)
        print(f"✓ Collected {len(binaries)} binaries from {package_name}")
        return binaries
    except ImportError:
        print(f"⚠ Package {package_name} not found, skipping binary collection")
        return []
    except Exception as e:
        print(f"✗ Error collecting binaries from {package_name}: {e}")
        return []

def safe_collect_submodules(package_name):
    """Safely collect submodules"""
    try:
        submodules = collect_submodules(package_name)
        print(f"✓ Collected {len(submodules)} submodules from {package_name}")
        return submodules
    except ImportError:
        print(f"⚠ Package {package_name} not found, skipping submodule collection")
        return []
    except Exception as e:
        print(f"✗ Error collecting submodules from {package_name}: {e}")
        return []

# Collect data files for all packages
print("Collecting package data files...")
fisher_py_datas = safe_collect_data_files('fisher_py')
fisher_py_binaries = safe_collect_binaries('fisher_py')
pyteomics_datas = safe_collect_data_files('pyteomics')
pandas_datas = safe_collect_data_files('pandas', include_py_files=True)
numpy_datas = safe_collect_data_files('numpy')
scipy_datas = safe_collect_data_files('scipy')
matplotlib_datas = safe_collect_data_files('matplotlib')

# Collect submodules for critical packages
print("Collecting submodules...")
additional_hidden_imports = []
critical_packages = ['numpy', 'pandas', 'scipy', 'matplotlib', 'pyteomics', 'networkx']
for package in critical_packages:
    submodules = safe_collect_submodules(package)
    additional_hidden_imports.extend(submodules)

# Combine all data files
all_datas = (
    fisher_py_datas + 
    pyteomics_datas + 
    pandas_datas + 
    numpy_datas + 
    scipy_datas + 
    matplotlib_datas
)

# Organized hidden imports
CORE_PYTHON_IMPORTS = [
    'warnings', 'multiprocessing', 'multiprocessing.pool', 'multiprocessing.spawn',
    'multiprocessing.util', 'multiprocessing.queues', 'multiprocessing.synchronize',
    'concurrent.futures', 'concurrent.futures._base', 'concurrent.futures.process',
    'concurrent.futures.thread', 'itertools', 'datetime', 'logging', 'traceback',
    'gc', 'os', 'sys', 're', 'glob', 'copy', 'time', 'functools', 'collections',
    'collections.abc', 'json', 'encodings', 'encodings.utf_8', 'encodings.cp1252',
    'encodings.latin_1'
]

XML_DATA_PROCESSING_IMPORTS = [
    'xml.etree.ElementTree', 'xml.parsers.expat', 'xml.dom.minidom',
    'lxml', 'lxml.etree', 'lxml.objectify'
]

NUMPY_IMPORTS = [
    'numpy', 'numpy.core', 'numpy.core._methods', 'numpy.core._multiarray_umath',
    'numpy.core.multiarray', 'numpy.core.umath', 'numpy.core._dtype_ctypes',
    'numpy.core._internal', 'numpy.lib', 'numpy.lib.format', 'numpy.lib.utils',
    'numpy.random', 'numpy.random._pickle', 'numpy.random.mtrand', 'numpy.random._mt19937',
    'numpy.random.bit_generator', 'numpy.linalg', 'numpy.linalg.lapack_lite',
    'numpy.linalg._umath_linalg', 'numpy.fft', 'numpy.polynomial', 'numpy.ma'
]

PANDAS_IMPORTS = [
    'pandas', 'pandas._libs', 'pandas._libs.tslibs', 'pandas._libs.tslibs.base',
    'pandas._libs.tslibs.ccalendar', 'pandas._libs.tslibs.conversion',
    'pandas._libs.tslibs.fields', 'pandas._libs.tslibs.nattype',
    'pandas._libs.tslibs.np_datetime', 'pandas._libs.tslibs.offsets',
    'pandas._libs.tslibs.parsing', 'pandas._libs.tslibs.period',
    'pandas._libs.tslibs.strptime', 'pandas._libs.tslibs.timedeltas',
    'pandas._libs.tslibs.timestamps', 'pandas._libs.tslibs.timezones',
    'pandas._libs.tslibs.tzconversion', 'pandas._libs.tslibs.vectorized',
    'pandas._libs.algos', 'pandas._libs.hashtable', 'pandas._libs.index',
    'pandas._libs.internals', 'pandas._libs.join', 'pandas._libs.lib',
    'pandas._libs.missing', 'pandas._libs.parsers', 'pandas._libs.reduction',
    'pandas._libs.reshape', 'pandas._libs.sparse', 'pandas._libs.testing',
    'pandas._libs.window', 'pandas._libs.writers', 'pandas.core',
    'pandas.core.dtypes', 'pandas.io', 'pandas.io.excel', 'pandas.io.common',
    'pandas.io.formats', 'pandas.io.parsers', 'pandas.plotting',
    'pandas.plotting._matplotlib', 'pandas.plotting._misc', 'pandas.io.excel._base',
    'pandas.io.excel._openpyxl', 'pandas.io.excel._xlsxwriter', 'pandas.util'
]

SCIPY_IMPORTS = [
    'scipy', 'scipy.signal', 'scipy.signal._bsplines', 'scipy.signal._savitzky_golay',
    'scipy.signal.windows', 'scipy.signal.filter_design', 'scipy.integrate',
    'scipy.integrate._ode', 'scipy.integrate._quadpack', 'scipy.integrate._odepack',
    'scipy.integrate.quadrature', 'scipy.interpolate', 'scipy.interpolate._bsplines',
    'scipy.interpolate._cubic', 'scipy.interpolate.interpnd', 'scipy.sparse',
    'scipy.sparse.linalg', 'scipy.sparse.csgraph', 'scipy.sparse.csgraph._validation',
    'scipy.sparse._matrix', 'scipy.sparse._base', 'scipy.linalg',
    'scipy.linalg.lapack', 'scipy.linalg.blas', 'scipy.linalg._flinalg',
    'scipy.special', 'scipy.special._ufuncs', 'scipy.special._ufuncs_cxx',
    'scipy.optimize', 'scipy.stats'
]

MATPLOTLIB_IMPORTS = [
    'matplotlib', 'matplotlib.backends', 'matplotlib.backends.backend_agg',
    'matplotlib.backends._backend_agg', 'matplotlib.backends.backend_svg',
    'matplotlib.backends.backend_qt5agg',     # Add this
    'matplotlib.backends._backend_qt5agg',    # Add this
    'matplotlib.backends.qt_compat',          # Add this for Qt compatibility
    'matplotlib.backends.qt_editor',          # Add this for Qt editor support
    'matplotlib.figure', 'matplotlib.pyplot', 'matplotlib.patches',
    'matplotlib.lines', 'matplotlib.text', 'matplotlib.font_manager',
    'matplotlib.colors', 'matplotlib.cm', 'matplotlib.gridspec',
    'matplotlib.ticker', 'matplotlib.transforms', 'matplotlib.path',
    'matplotlib.cbook', 'matplotlib.style', 'matplotlib._pylab_helpers',
    'matplotlib.backend_bases',               # Add this for backend base classes
    'matplotlib.backends._backend_pdf_ps',    # Add this for additional backend support
]

PYQT5_IMPORTS = [
    'PyQt5', 'PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.QtWidgets',
    'PyQt5.QtOpenGL', 'PyQt5.QtPrintSupport', 'PyQt5.Qt',
    'PyQt5.QtSvg', 'PyQt5.QtNetwork', 'sip', 'PyQt5.sip'
]

DOMAIN_SPECIFIC_IMPORTS = [
    'fisher_py', 'fisher_py._lib', 'fisher_py.raw_file_reader',
    'fisher_py.ms_file_reader', 'pythonnet', 'clr',
    'pyteomics', 'pyteomics.mzml', 'pyteomics.auxiliary', 'pyteomics.xml',
    'pyteomics.mass', 'pyteomics.parser', 'pyteomics.proforma',
    'networkx', 'networkx.algorithms', 'networkx.classes', 'networkx.convert',
    'networkx.generators', 'networkx.readwrite', 'networkx.utils'
]

EXCEL_HANDLING_IMPORTS = [
    'openpyxl', 'openpyxl.workbook', 'openpyxl.worksheet', 'openpyxl.styles',
    'openpyxl.utils', 'openpyxl.reader', 'openpyxl.writer',
    'xlsxwriter', 'xlsxwriter.workbook', 'xlsxwriter.worksheet',
    'xlrd', 'xlwt'
]

UTILITY_IMPORTS = [
    'pytz', 'dateutil', 'dateutil.parser', 'dateutil.tz', 'six',
    'packaging', 'packaging.version', 'packaging.specifiers', 'packaging.requirements'
]

# Combine all hidden imports
all_hidden_imports = (
    CORE_PYTHON_IMPORTS +
    XML_DATA_PROCESSING_IMPORTS +
    NUMPY_IMPORTS +
    PANDAS_IMPORTS +
    SCIPY_IMPORTS +
    MATPLOTLIB_IMPORTS +
    MATPLOTLIB_QT_IMPORTS + 
    PYQT5_IMPORTS +
    DOMAIN_SPECIFIC_IMPORTS +
    EXCEL_HANDLING_IMPORTS +
    UTILITY_IMPORTS +
    additional_hidden_imports
)

# Remove duplicates
all_hidden_imports = list(set(all_hidden_imports))
print(f"Total hidden imports: {len(all_hidden_imports)}")

# Analysis configuration
a = Analysis(
    ['GlypPRM_App_v01.py'],
    pathex=['.', os.getcwd()],
    binaries=fisher_py_binaries,
    datas=all_datas,
    hiddenimports=all_hidden_imports,
    hookspath=['hooks'],  # Custom hooks directory
    hooksconfig={
        "matplotlib": {
            "backends": ["Agg"]  # Only include Agg backend for headless operation
        }
    },
    runtime_hooks=['runtime_hook.py'],
    excludes=[
        # GUI frameworks not needed
        'tkinter', 'tkinter.filedialog', 'tkinter.messagebox',
        'IPython', 'jupyter', 'notebook',
        
        # Other Qt versions
        'PyQt4', 'PyQt6', 'PySide', 'PySide2', 'PySide6',
        
        # Matplotlib GUI backends (keep only Agg)
        'matplotlib.backends.backend_qt5agg',
        'matplotlib.backends.backend_qt4agg',
        'matplotlib.backends.backend_tkagg',
        'matplotlib.backends._backend_tk',
        'matplotlib.backends.backend_gtk3agg',
        'matplotlib.backends.backend_wxagg',
        'matplotlib.backends.backend_macosx',
        
        # Development and testing
        'pytest', 'nose', 'unittest2', 'sphinx', 'docutils',
        
        # Large optional packages
        'sympy', 'statsmodels', 'sklearn', 'scikit-learn', 'seaborn',
        
        # Unused modules
        'curses', 'readline'
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# PYZ configuration
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# EXE configuration
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='GlypPRM',
    debug=True,  # Set to True for debugging
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # Enable UPX compression
    upx_exclude=[
        'vcruntime140.dll',
        'msvcp140.dll',
        'api-ms-win-*.dll',
        'python*.dll'
    ],
    runtime_tmpdir=None,
    console=True,  # Windowed application
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
    version=None,
    uac_admin=False,
    uac_uiaccess=False,
)

print(f"Build configuration complete for GlypPRM v{VERSION}")
print(f"Console mode: {exe.console}")
print(f"Debug mode: {exe.debug}")
print(f"UPX compression: {exe.upx}")