"""Vibe-PDCA ダウンローダー/インストーラー。

実行時に以下を行う:
1. GitHub Releases から最新リリースのソースアーカイブをダウンロード
2. Python 依存パッケージをインストール
3. 設定ファイル・リソースを展開
4. PyInstaller でメインアプリケーション EXE をビルド
5. デスクトップショートカットを作成（オプション）

ダウンローダー自体を EXE 化する場合:
  pyinstaller installer/downloader.spec
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import yaml

logger = logging.getLogger(__name__)

# ── 定数 ──────────────────────────────────────────────
APP_NAME = "VibePDCA"
VERSION = "0.2.0"
GITHUB_OWNER = "maki04591128-tech"
GITHUB_REPO = "Vive-coding-pdca-system"
GITHUB_API_BASE = "https://api.github.com"
MIN_PYTHON_VERSION = (3, 12)
CHUNK_SIZE = 8192


class InstallerError(Exception):
    """インストーラー固有のエラー。"""


class DownloadError(InstallerError):
    """ダウンロード失敗エラー。"""


class SetupError(InstallerError):
    """セットアップ失敗エラー。"""


# ── ユーティリティ ──────────────────────────────────────


def _load_config(config_path: Path | None = None) -> dict[str, Any]:
    """インストーラー設定を読み込む。"""
    if config_path is None:
        config_path = Path(__file__).parent / "installer_config.yml"
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}  # type: ignore[no-any-return]
    return {}


def _get_platform() -> str:
    """実行プラットフォームを判定する。"""
    system = platform.system().lower()
    if system == "windows":
        return "windows"
    if system == "darwin":
        return "macos"
    return "linux"


def _get_default_install_dir(config: dict[str, Any]) -> Path:
    """デフォルトのインストール先を取得する。"""
    plat = _get_platform()
    installer_cfg = config.get("installer", {}).get("install", {})

    if plat == "windows":
        raw = installer_cfg.get("default_dir_windows", "%LOCALAPPDATA%\\VibePDCA")
        return Path(os.path.expandvars(raw))
    if plat == "macos":
        raw = installer_cfg.get("default_dir_macos", "~/Applications/VibePDCA")
        return Path(raw).expanduser()

    raw = installer_cfg.get("default_dir_linux", "~/.local/share/VibePDCA")
    return Path(raw).expanduser()


def _sha256_file(path: Path) -> str:
    """ファイルの SHA-256 ハッシュを計算する。"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


# ── GitHub API ──────────────────────────────────────────


def _github_api_get(endpoint: str) -> Any:
    """GitHub API に GET リクエストを送信する。"""
    url = f"{GITHUB_API_BASE}{endpoint}"
    req = Request(url, headers={"Accept": "application/vnd.github.v3+json"})
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (HTTPError, URLError) as e:
        raise DownloadError(f"GitHub API リクエスト失敗: {url} — {e}") from e


def get_latest_release_info(
    owner: str = GITHUB_OWNER, repo: str = GITHUB_REPO
) -> dict[str, Any]:
    """最新リリース情報を取得する。"""
    return _github_api_get(f"/repos/{owner}/{repo}/releases/latest")  # type: ignore[no-any-return]


def get_release_info_by_tag(
    tag: str, owner: str = GITHUB_OWNER, repo: str = GITHUB_REPO
) -> dict[str, Any]:
    """タグ指定でリリース情報を取得する。"""
    return _github_api_get(f"/repos/{owner}/{repo}/releases/tags/{tag}")  # type: ignore[no-any-return]


def get_source_tarball_url(
    owner: str = GITHUB_OWNER,
    repo: str = GITHUB_REPO,
    tag: str = "latest",
) -> str:
    """ソースコードの tarball URL を取得する。"""
    if tag == "latest":
        info = get_latest_release_info(owner, repo)
        return str(info["tarball_url"])
    return f"{GITHUB_API_BASE}/repos/{owner}/{repo}/tarball/{tag}"


# ── ダウンロード ──────────────────────────────────────────


def download_file(
    url: str,
    dest: Path,
    *,
    progress_callback: Any | None = None,
) -> Path:
    """URL からファイルをダウンロードする。

    Parameters
    ----------
    url : str
        ダウンロード元 URL
    dest : Path
        保存先パス
    progress_callback : callable, optional
        進捗コールバック (downloaded_bytes, total_bytes)

    Returns
    -------
    Path
        ダウンロードされたファイルのパス
    """
    req = Request(url, headers={"Accept": "application/octet-stream"})
    try:
        with urlopen(req, timeout=120) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            dest.parent.mkdir(parents=True, exist_ok=True)
            downloaded = 0
            with open(dest, "wb") as f:
                while True:
                    chunk = resp.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total)
    except (HTTPError, URLError) as e:
        raise DownloadError(f"ダウンロード失敗: {url} — {e}") from e

    logger.info("ダウンロード完了: %s → %s", url, dest)
    return dest


# ── アーカイブ展開 ──────────────────────────────────────


def extract_archive(archive_path: Path, dest_dir: Path) -> Path:
    """アーカイブを展開する。

    Parameters
    ----------
    archive_path : Path
        アーカイブファイルのパス
    dest_dir : Path
        展開先ディレクトリ

    Returns
    -------
    Path
        展開されたトップレベルディレクトリのパス
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = archive_path.name.lower()

    if name.endswith(".tar.gz") or name.endswith(".tgz"):
        with tarfile.open(archive_path, "r:gz") as tar:
            # セキュリティチェック: パストラバーサル防止
            for member in tar.getmembers():
                member_path = Path(dest_dir / member.name)
                if not member_path.resolve().is_relative_to(dest_dir.resolve()):
                    raise InstallerError(
                        f"不正なパスを検出（パストラバーサル）: {member.name}"
                    )
            tar.extractall(dest_dir, filter="data")  # noqa: S202
    elif name.endswith(".zip"):
        with zipfile.ZipFile(archive_path, "r") as zf:
            for info in zf.infolist():
                member_path = Path(dest_dir / info.filename)
                if not member_path.resolve().is_relative_to(dest_dir.resolve()):
                    raise InstallerError(
                        f"不正なパスを検出（パストラバーサル）: {info.filename}"
                    )
            zf.extractall(dest_dir)
    else:
        raise InstallerError(f"未対応のアーカイブ形式: {archive_path}")

    # 展開されたディレクトリを検出
    extracted = [p for p in dest_dir.iterdir() if p.is_dir()]
    if extracted:
        return extracted[0]
    return dest_dir


# ── Python 環境チェック ──────────────────────────────────


def check_python_version() -> bool:
    """Python バージョンが要件を満たしているか確認する。"""
    return sys.version_info >= MIN_PYTHON_VERSION


def get_python_info() -> dict[str, str]:
    """Python の情報を返す。"""
    return {
        "version": platform.python_version(),
        "executable": sys.executable,
        "platform": _get_platform(),
        "arch": platform.machine(),
    }


# ── 依存パッケージインストール ──────────────────────────


def install_dependencies(
    project_dir: Path,
    *,
    extras: list[str] | None = None,
    progress_callback: Any | None = None,
) -> bool:
    """pip で依存パッケージをインストールする。

    Parameters
    ----------
    project_dir : Path
        プロジェクトのルートディレクトリ
    extras : list[str], optional
        追加でインストールするオプション依存（例: ["gui", "google"]）
    progress_callback : callable, optional
        進捗コールバック

    Returns
    -------
    bool
        成功した場合 True
    """
    if progress_callback:
        progress_callback("依存パッケージのインストール中...")

    extras_str = ",".join(extras) if extras else "gui"
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--upgrade",
        f"{project_dir}[{extras_str}]",
    ]
    logger.info("実行: %s", " ".join(cmd))
    try:
        subprocess.run(  # noqa: S603
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=600,
        )
    except subprocess.CalledProcessError as e:
        logger.error("pip install 失敗:\nstdout: %s\nstderr: %s", e.stdout, e.stderr)
        raise SetupError(f"依存パッケージのインストールに失敗: {e.stderr}") from e
    except subprocess.TimeoutExpired as e:
        raise SetupError("依存パッケージのインストールがタイムアウト") from e

    if progress_callback:
        progress_callback("依存パッケージのインストール完了")
    return True


# ── PyInstaller ビルド ──────────────────────────────────


def build_exe(
    project_dir: Path,
    output_dir: Path,
    *,
    config: dict[str, Any] | None = None,
    progress_callback: Any | None = None,
) -> Path:
    """PyInstaller でメインアプリケーション EXE をビルドする。

    Parameters
    ----------
    project_dir : Path
        プロジェクトのルートディレクトリ
    output_dir : Path
        EXE の出力先ディレクトリ
    config : dict, optional
        インストーラー設定
    progress_callback : callable, optional
        進捗コールバック

    Returns
    -------
    Path
        生成された EXE ファイルのパス
    """
    if progress_callback:
        progress_callback("アプリケーション EXE のビルド中...")

    # PyInstaller がインストールされているか確認
    try:
        subprocess.run(  # noqa: S603
            [sys.executable, "-m", "PyInstaller", "--version"],
            check=True,
            capture_output=True,
            timeout=30,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.info("PyInstaller をインストール中...")
        subprocess.run(  # noqa: S603
            [sys.executable, "-m", "pip", "install", "pyinstaller>=6.0"],
            check=True,
            capture_output=True,
            timeout=300,
        )
        logger.info("PyInstaller のインストール完了")

    pi_cfg = (config or {}).get("installer", {}).get("pyinstaller", {})
    app_name = pi_cfg.get("app_name", APP_NAME)
    main_script = project_dir / pi_cfg.get("main_script", "src/vibe_pdca/gui/app.py")
    onefile = pi_cfg.get("onefile", True)
    console = pi_cfg.get("console", False)
    hidden_imports = pi_cfg.get("hidden_imports", [])
    additional_data = pi_cfg.get("additional_data", [])
    icon = pi_cfg.get("icon")

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name",
        app_name,
        "--distpath",
        str(output_dir),
        "--workpath",
        str(output_dir / "build"),
        "--specpath",
        str(output_dir),
    ]

    if onefile:
        cmd.append("--onefile")
    if not console:
        cmd.append("--noconsole")
    if icon:
        cmd.extend(["--icon", str(project_dir / icon)])

    for imp in hidden_imports:
        cmd.extend(["--hidden-import", imp])

    for data in additional_data:
        src_part, dst_part = data.split(":")
        src_path = project_dir / src_part
        if src_path.exists():
            cmd.extend(["--add-data", f"{src_path}{os.pathsep}{dst_part}"])

    # src をパスに追加
    cmd.extend(["--paths", str(project_dir / "src")])
    cmd.append(str(main_script))

    logger.info("PyInstaller 実行: %s", " ".join(cmd))
    try:
        subprocess.run(  # noqa: S603
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=600,
            cwd=str(project_dir),
        )
    except subprocess.CalledProcessError as e:
        logger.error("PyInstaller 失敗:\nstdout: %s\nstderr: %s", e.stdout, e.stderr)
        raise SetupError(f"EXE ビルドに失敗: {e.stderr}") from e

    # 出力ファイルのパスを決定
    ext = ".exe" if _get_platform() == "windows" else ""
    exe_path = output_dir / f"{app_name}{ext}"
    if not exe_path.exists():
        # onefile モードでない場合はディレクトリ内を確認
        alt_path = output_dir / app_name / f"{app_name}{ext}"
        if alt_path.exists():
            exe_path = alt_path

    if progress_callback:
        progress_callback(f"EXE ビルド完了: {exe_path}")

    logger.info("EXE ビルド完了: %s", exe_path)
    return exe_path


# ── 設定ファイル展開 ──────────────────────────────────────


def deploy_config(project_dir: Path, install_dir: Path) -> None:
    """設定ファイルをインストール先に展開する。"""
    config_src = project_dir / "config"
    config_dst = install_dir / "config"
    if config_src.exists():
        if config_dst.exists():
            shutil.rmtree(config_dst)
        shutil.copytree(config_src, config_dst)
        logger.info("設定ファイル展開: %s → %s", config_src, config_dst)

    # .env.example をコピー
    env_example = project_dir / ".env.example"
    if env_example.exists():
        env_dst = install_dir / ".env.example"
        shutil.copy2(env_example, env_dst)
        logger.info(".env.example コピー: %s", env_dst)

    # Docker 設定
    docker_src = project_dir / "docker"
    docker_dst = install_dir / "docker"
    if docker_src.exists():
        if docker_dst.exists():
            shutil.rmtree(docker_dst)
        shutil.copytree(docker_src, docker_dst)
        logger.info("Docker 設定展開: %s → %s", docker_src, docker_dst)


# ── メインインストールフロー ──────────────────────────────


class Installer:
    """ダウンロード → セットアップ → ビルドを統括するクラス。"""

    def __init__(
        self,
        install_dir: Path | None = None,
        config: dict[str, Any] | None = None,
        progress_callback: Any | None = None,
    ) -> None:
        self._config = config or _load_config()
        self._progress = progress_callback
        self._install_dir = install_dir or _get_default_install_dir(self._config)
        self._temp_dir: Path | None = None

    @property
    def install_dir(self) -> Path:
        """インストール先ディレクトリ。"""
        return self._install_dir

    def _report(self, message: str) -> None:
        """進捗を報告する。"""
        logger.info(message)
        if self._progress:
            self._progress(message)

    def run(self) -> Path:
        """インストールを実行し、生成された EXE パスを返す。

        Returns
        -------
        Path
            メインアプリケーション EXE のパス
        """
        self._report("=== Vibe-PDCA インストーラー開始 ===")

        # Step 1: Python バージョンチェック
        self._report("Step 1/6: Python 環境を確認中...")
        if not check_python_version():
            raise SetupError(
                f"Python {MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]} 以上が必要です。"
                f"現在: {platform.python_version()}"
            )
        info = get_python_info()
        self._report(f"  Python {info['version']} ({info['platform']}/{info['arch']})")

        # Step 2: インストールディレクトリの準備
        self._report(f"Step 2/6: インストール先を準備中: {self._install_dir}")
        self._install_dir.mkdir(parents=True, exist_ok=True)

        # Step 3: ソースコードの取得
        self._report("Step 3/6: ソースコードをダウンロード中...")
        project_dir = self._download_source()

        # Step 4: 依存パッケージのインストール
        self._report("Step 4/6: 依存パッケージをインストール中...")
        install_dependencies(project_dir, extras=["gui"], progress_callback=self._report)

        # Step 5: 設定ファイルの展開
        self._report("Step 5/6: 設定ファイルを展開中...")
        deploy_config(project_dir, self._install_dir)

        # Step 6: EXE ビルド
        self._report("Step 6/6: アプリケーション EXE をビルド中...")
        exe_path = build_exe(
            project_dir,
            self._install_dir,
            config=self._config,
            progress_callback=self._report,
        )

        self._report(f"=== インストール完了: {exe_path} ===")
        return exe_path

    def _download_source(self) -> Path:
        """GitHub からソースコードをダウンロード・展開する。"""
        installer_cfg = self._config.get("installer", {})
        github_cfg = installer_cfg.get("github", {})
        owner = github_cfg.get("owner", GITHUB_OWNER)
        repo = github_cfg.get("repo", GITHUB_REPO)
        tag = github_cfg.get("release_tag", "latest")

        tarball_url = get_source_tarball_url(owner, repo, tag)
        self._report(f"  ダウンロード元: {tarball_url}")

        # 一時ディレクトリにダウンロード
        self._temp_dir = Path(tempfile.mkdtemp(prefix="vibe-pdca-install-"))
        archive_path = self._temp_dir / "source.tar.gz"

        download_file(tarball_url, archive_path, progress_callback=self._report)

        # 展開
        self._report("  アーカイブを展開中...")
        project_dir = extract_archive(archive_path, self._temp_dir / "source")
        self._report(f"  展開完了: {project_dir}")
        return project_dir

    def cleanup(self) -> None:
        """一時ファイルを削除する。"""
        if self._temp_dir and self._temp_dir.exists():
            shutil.rmtree(self._temp_dir, ignore_errors=True)
            logger.info("一時ファイル削除: %s", self._temp_dir)


# ── CLI エントリポイント ──────────────────────────────────


def main() -> None:
    """CLI からインストーラーを実行する。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    import argparse

    parser = argparse.ArgumentParser(
        description="Vibe-PDCA ダウンローダー/インストーラー",
    )
    parser.add_argument(
        "--install-dir",
        type=Path,
        default=None,
        help="インストール先ディレクトリ（デフォルト: プラットフォーム依存）",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="インストーラー設定ファイルのパス",
    )
    parser.add_argument(
        "--tag",
        type=str,
        default=None,
        help="GitHubリリースタグ（例: v0.2.0）。省略時は latest",
    )
    args = parser.parse_args()

    config = _load_config(args.config)
    if args.tag:
        config.setdefault("installer", {}).setdefault("github", {})["release_tag"] = args.tag

    def cli_progress(msg: Any) -> None:
        if isinstance(msg, str):
            print(msg)  # noqa: T201
        elif isinstance(msg, tuple) and len(msg) == 2:
            downloaded, total = msg
            if total > 0:
                pct = downloaded / total * 100
                bar_len = 40
                filled = int(bar_len * downloaded // total)
                bar = "█" * filled + "░" * (bar_len - filled)
                print(  # noqa: T201
                    f"\r  [{bar}] {pct:5.1f}% ({downloaded}/{total} bytes)",
                    end="",
                    flush=True,
                )
                if downloaded >= total:
                    print()  # noqa: T201

    installer = Installer(
        install_dir=args.install_dir,
        config=config,
        progress_callback=cli_progress,
    )
    try:
        exe_path = installer.run()
        print(f"\n✅ インストール完了: {exe_path}")  # noqa: T201
    except InstallerError as e:
        print(f"\n❌ エラー: {e}", file=sys.stderr)  # noqa: T201
        sys.exit(1)
    finally:
        installer.cleanup()


if __name__ == "__main__":
    main()
