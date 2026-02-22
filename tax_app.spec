# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Tax App standalone .exe."""

import os

block_cipher = None

# Collect all .py files under form_parsers/ so PyInstaller bundles them.
_form_parser_files = []
for f in os.listdir('form_parsers'):
    if f.endswith('.py'):
        _form_parser_files.append(
            (os.path.join('form_parsers', f), 'form_parsers')
        )

a = Analysis(
    ['build_exe.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),
    ] + _form_parser_files,
    hiddenimports=[
        # --- app modules ---
        'web_app',
        'tax_app',
        'tax_calculator',
        'form_scanner',
        'form_parsers',
        'form_parsers.w2_parser',
        'form_parsers.f1099b_parser',
        'form_parsers.f1099int_parser',
        'form_parsers.f1098_parser',
        # --- third-party ---
        'flask',
        'jinja2',
        'jinja2.ext',
        'pdfplumber',
        'pdfminer',
        'pdfminer.high_level',
        'pdfminer.six',
        'pandas',
        'numpy',
        'yfinance',
        'requests',
        'certifi',
        'charset_normalizer',
        'urllib3',
        'bs4',
        'xlrd',
        'PIL',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='tax_app',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    # Use console=True so the user can see startup messages and errors.
    # Switch to console=False once the app is stable for a cleaner UX.
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
