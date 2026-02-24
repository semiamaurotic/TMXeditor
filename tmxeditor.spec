# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['src/tmxeditor/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('src/tmxeditor/default_shortcuts.json', 'tmxeditor'),
        ('src/tmxeditor/resources', 'tmxeditor/resources'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtQuick',
        'PySide6.QtQml',
        'PySide6.QtMultimedia',
        'PySide6.QtSql',
        'PySide6.QtTest',
        'PySide6.QtXml',
        'PySide6.QtBluetooth',
        'PySide6.QtNfc',
        'PySide6.QtPositioning',
        'PySide6.QtSensors',
        'PySide6.QtSerialPort',
        'PySide6.QtTextToSpeech',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TMXeditor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='src/tmxeditor/resources/app_icon.ico',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=True,
    upx=True,
    upx_exclude=[],
    name='TMXeditor',
)
app = BUNDLE(
    coll,
    name='TMXeditor.app',
    icon='src/tmxeditor/resources/app_icon.icns',
    bundle_identifier='com.semiamaurotic.tmxeditor',
)
