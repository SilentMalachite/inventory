# -*- mode: python ; coding: utf-8 -*-

# PyInstaller spec for Inventory System
# 前提: フロントエンドは先に `frontend/` で `npm run build` 済み（出力先: src/app/public）

block_cipher = None

from PyInstaller.building.build_main import Analysis, PYZ, EXE
from PyInstaller.building.datastruct import Tree
import os


# 解析
a = Analysis(
    ['src/app/__main__.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('src/app/assets/seed.db', 'app/assets'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

# 追加データ（ディレクトリ）
a.datas += Tree('src/app/templates', prefix='app/templates')
a.datas += Tree('src/app/static', prefix='app/static')
a.datas += Tree('src/app/locales', prefix='app/locales')
# SPA ビルド（存在しない場合はスキップ）
if os.path.isdir('src/app/public'):
    a.datas += Tree('src/app/public', prefix='app/public')

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# onefile 相当: EXE に binaries/zipfiles/datas を与える
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='inventory-app',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)
