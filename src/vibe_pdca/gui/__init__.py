"""GUI モジュール – Flet ベースのクロスプラットフォーム GUI。

デスクトップ (.exe) / モバイル (.apk) / Web に対応する。
"""

import contextlib

__all__ = ["create_app", "main"]

with contextlib.suppress(ImportError):  # flet が未インストールの場合
    from vibe_pdca.gui.app import create_app, main
