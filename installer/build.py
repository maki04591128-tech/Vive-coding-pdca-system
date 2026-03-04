"""Vibe-PDCA インストーラー / アプリケーション EXE ビルドスクリプト。

使い方:
  # ダウンローダー EXE のビルド
  python installer/build.py downloader

  # メインアプリケーション EXE のビルド（ローカルソースから直接）
  python installer/build.py app

  # 両方ビルド
  python installer/build.py all
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def build_downloader_exe(output_dir: Path | None = None) -> Path:
    """ダウンローダー EXE をビルドする。

    Returns
    -------
    Path
        生成された EXE ファイルのパス
    """
    if output_dir is None:
        output_dir = PROJECT_ROOT / "dist"
    output_dir.mkdir(parents=True, exist_ok=True)

    downloader_script = PROJECT_ROOT / "installer" / "downloader.py"
    config_file = PROJECT_ROOT / "installer" / "installer_config.yml"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name",
        "VibePDCA-Setup",
        "--onefile",
        "--distpath",
        str(output_dir),
        "--workpath",
        str(output_dir / "build" / "downloader"),
        "--specpath",
        str(output_dir),
    ]

    # コンソールモード（進捗表示のため）
    cmd.append("--console")

    # installer_config.yml を同梱
    if config_file.exists():
        cmd.extend(["--add-data", f"{config_file}{os.pathsep}installer"])

    # 必要なパッケージ
    cmd.extend(["--hidden-import", "yaml"])

    cmd.append(str(downloader_script))

    logger.info("ダウンローダー EXE ビルド: %s", " ".join(cmd))
    subprocess.run(cmd, check=True, timeout=600)  # noqa: S603

    ext = ".exe" if sys.platform == "win32" else ""
    exe_path = output_dir / f"VibePDCA-Setup{ext}"
    logger.info("ダウンローダー EXE: %s", exe_path)
    return exe_path


def build_app_exe(output_dir: Path | None = None) -> Path:
    """メインアプリケーション EXE をローカルソースからビルドする。

    Returns
    -------
    Path
        生成された EXE ファイルのパス
    """
    from installer.downloader import _load_config, build_exe

    if output_dir is None:
        output_dir = PROJECT_ROOT / "dist"
    output_dir.mkdir(parents=True, exist_ok=True)

    config = _load_config()
    return build_exe(PROJECT_ROOT, output_dir, config=config)


def main() -> None:
    """CLI エントリポイント。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Vibe-PDCA EXE ビルドスクリプト",
    )
    parser.add_argument(
        "target",
        choices=["downloader", "app", "all"],
        help="ビルド対象: downloader=ダウンローダーEXE, app=メインアプリEXE, all=両方",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="出力ディレクトリ（デフォルト: dist/）",
    )
    args = parser.parse_args()

    results: list[tuple[str, Path]] = []
    if args.target in ("downloader", "all"):
        path = build_downloader_exe(args.output_dir)
        results.append(("ダウンローダー EXE", path))

    if args.target in ("app", "all"):
        path = build_app_exe(args.output_dir)
        results.append(("メインアプリ EXE", path))

    print("\n=== ビルド結果 ===")  # noqa: T201
    for label, path in results:
        exists = "✅" if path.exists() else "❌"
        print(f"  {exists} {label}: {path}")  # noqa: T201


if __name__ == "__main__":
    main()
