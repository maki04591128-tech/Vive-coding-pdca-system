"""installer/downloader.py のテスト。"""

from __future__ import annotations

import json
import platform
import tarfile
import zipfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from installer.downloader import (
    APP_NAME,
    GITHUB_OWNER,
    GITHUB_REPO,
    DownloadError,
    Installer,
    InstallerError,
    SetupError,
    _get_default_install_dir,
    _get_platform,
    _load_config,
    _sha256_file,
    check_python_version,
    deploy_config,
    download_file,
    extract_archive,
    get_python_info,
    get_source_tarball_url,
)

# ── 定数テスト ──


class TestConstants:
    """定数の基本検証。"""

    def test_app_name(self) -> None:
        assert APP_NAME == "VibePDCA"

    def test_github_owner(self) -> None:
        assert GITHUB_OWNER == "maki04591128-tech"

    def test_github_repo(self) -> None:
        assert GITHUB_REPO == "Vive-coding-pdca-system"


# ── ユーティリティ関数テスト ──


class TestGetPlatform:
    """_get_platform のテスト。"""

    @patch("installer.downloader.platform")
    def test_windows(self, mock_platform: MagicMock) -> None:
        mock_platform.system.return_value = "Windows"
        assert _get_platform() == "windows"

    @patch("installer.downloader.platform")
    def test_macos(self, mock_platform: MagicMock) -> None:
        mock_platform.system.return_value = "Darwin"
        assert _get_platform() == "macos"

    @patch("installer.downloader.platform")
    def test_linux(self, mock_platform: MagicMock) -> None:
        mock_platform.system.return_value = "Linux"
        assert _get_platform() == "linux"


class TestLoadConfig:
    """_load_config のテスト。"""

    def test_load_existing_config(self) -> None:
        config_path = Path(__file__).parent.parent / "installer" / "installer_config.yml"
        if config_path.exists():
            config = _load_config(config_path)
            assert isinstance(config, dict)
            assert "installer" in config

    def test_load_nonexistent_returns_empty(self, tmp_path: Path) -> None:
        config = _load_config(tmp_path / "nonexistent.yml")
        assert config == {}


class TestGetDefaultInstallDir:
    """_get_default_install_dir のテスト。"""

    def test_returns_path(self) -> None:
        config: dict[str, Any] = {}
        result = _get_default_install_dir(config)
        assert isinstance(result, Path)

    @patch("installer.downloader._get_platform", return_value="linux")
    def test_linux_default(self, _mock: MagicMock) -> None:
        config: dict[str, Any] = {}
        result = _get_default_install_dir(config)
        assert "VibePDCA" in str(result)

    @patch("installer.downloader._get_platform", return_value="macos")
    def test_macos_default(self, _mock: MagicMock) -> None:
        config: dict[str, Any] = {}
        result = _get_default_install_dir(config)
        assert "VibePDCA" in str(result)


class TestSha256File:
    """_sha256_file のテスト。"""

    def test_hash_known_content(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")
        h = _sha256_file(test_file)
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 は64文字の16進数

    def test_same_content_same_hash(self, tmp_path: Path) -> None:
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("test content")
        f2.write_text("test content")
        assert _sha256_file(f1) == _sha256_file(f2)

    def test_different_content_different_hash(self, tmp_path: Path) -> None:
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("content a")
        f2.write_text("content b")
        assert _sha256_file(f1) != _sha256_file(f2)


# ── Python 環境チェック ──


class TestCheckPythonVersion:
    """check_python_version のテスト。"""

    @pytest.mark.skipif(
        __import__("sys").version_info < (3, 12),
        reason="Python 3.12+ が必要なテスト",
    )
    def test_current_version_ok(self) -> None:
        assert check_python_version() is True

    def test_get_python_info(self) -> None:
        info = get_python_info()
        assert "version" in info
        assert "executable" in info
        assert "platform" in info
        assert "arch" in info
        assert info["version"] == platform.python_version()


# ── GitHub API テスト（モック） ──


class TestGitHubApi:
    """GitHub API 関連のテスト。"""

    @patch("installer.downloader.urlopen")
    def test_get_source_tarball_url_latest(self, mock_urlopen: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {"tarball_url": "https://api.github.com/repos/owner/repo/tarball/v1.0"}
        ).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        url = get_source_tarball_url("owner", "repo", "latest")
        assert "tarball" in url

    def test_get_source_tarball_url_specific_tag(self) -> None:
        url = get_source_tarball_url("owner", "repo", "v0.1.0")
        assert "v0.1.0" in url
        assert "tarball" in url


# ── ダウンロードテスト（モック） ──


class TestDownloadFile:
    """download_file のテスト。"""

    @patch("installer.downloader.urlopen")
    def test_download_success(self, mock_urlopen: MagicMock, tmp_path: Path) -> None:
        content = b"test file content"
        mock_resp = MagicMock()
        mock_resp.headers = {"Content-Length": str(len(content))}
        mock_resp.read = MagicMock(side_effect=[content, b""])
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        dest = tmp_path / "downloaded.txt"
        result = download_file("https://example.com/file", dest)

        assert result == dest
        assert dest.exists()
        assert dest.read_bytes() == content

    @patch("installer.downloader.urlopen")
    def test_download_with_progress(self, mock_urlopen: MagicMock, tmp_path: Path) -> None:
        content = b"test"
        mock_resp = MagicMock()
        mock_resp.headers = {"Content-Length": str(len(content))}
        mock_resp.read = MagicMock(side_effect=[content, b""])
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        progress_calls: list[tuple[int, int]] = []

        def progress(downloaded: int, total: int) -> None:
            progress_calls.append((downloaded, total))

        dest = tmp_path / "downloaded.txt"
        download_file("https://example.com/file", dest, progress_callback=progress)

        assert len(progress_calls) > 0
        assert progress_calls[-1][0] == len(content)


# ── アーカイブ展開テスト ──


class TestExtractArchive:
    """extract_archive のテスト。"""

    def test_extract_tar_gz(self, tmp_path: Path) -> None:
        # テスト用の tar.gz を作成
        archive_path = tmp_path / "test.tar.gz"
        content_dir = tmp_path / "content"
        content_dir.mkdir()
        (content_dir / "hello.txt").write_text("hello world")

        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(content_dir, arcname="project")

        dest = tmp_path / "extracted"
        result = extract_archive(archive_path, dest)

        assert result.exists()
        assert (result / "hello.txt").exists()
        assert (result / "hello.txt").read_text() == "hello world"

    def test_extract_zip(self, tmp_path: Path) -> None:
        # テスト用の zip を作成
        archive_path = tmp_path / "test.zip"
        with zipfile.ZipFile(archive_path, "w") as zf:
            zf.writestr("project/hello.txt", "hello from zip")

        dest = tmp_path / "extracted"
        result = extract_archive(archive_path, dest)

        assert result.exists()

    def test_unsupported_format(self, tmp_path: Path) -> None:
        archive_path = tmp_path / "test.rar"
        archive_path.write_bytes(b"not a real archive")

        with pytest.raises(InstallerError, match="未対応のアーカイブ形式"):
            extract_archive(archive_path, tmp_path / "out")

    def test_path_traversal_prevention_tar(self, tmp_path: Path) -> None:
        """パストラバーサル攻撃の防止を確認。"""
        archive_path = tmp_path / "malicious.tar.gz"
        with tarfile.open(archive_path, "w:gz") as tar:
            info = tarfile.TarInfo(name="../../../etc/passwd")
            info.size = 5
            import io

            tar.addfile(info, io.BytesIO(b"pwned"))

        dest = tmp_path / "extracted"
        with pytest.raises(InstallerError, match="パストラバーサル"):
            extract_archive(archive_path, dest)

    def test_path_traversal_prevention_zip(self, tmp_path: Path) -> None:
        """ZIP のパストラバーサル攻撃の防止を確認。"""
        archive_path = tmp_path / "malicious.zip"
        with zipfile.ZipFile(archive_path, "w") as zf:
            zf.writestr("../../../etc/passwd", "pwned")

        dest = tmp_path / "extracted"
        with pytest.raises(InstallerError, match="パストラバーサル"):
            extract_archive(archive_path, dest)


# ── 設定ファイル展開テスト ──


class TestDeployConfig:
    """deploy_config のテスト。"""

    def test_deploy_config_copies_files(self, tmp_path: Path) -> None:
        # プロジェクトディレクトリをシミュレート
        project = tmp_path / "project"
        project.mkdir()
        (project / "config").mkdir()
        (project / "config" / "default.yml").write_text("test: true")
        (project / ".env.example").write_text("KEY=value")
        (project / "docker").mkdir()
        (project / "docker" / "Dockerfile").write_text("FROM python:3.12")

        install_dir = tmp_path / "install"
        install_dir.mkdir()

        deploy_config(project, install_dir)

        assert (install_dir / "config" / "default.yml").exists()
        assert (install_dir / ".env.example").exists()
        assert (install_dir / "docker" / "Dockerfile").exists()

    def test_deploy_config_overwrites_existing(self, tmp_path: Path) -> None:
        project = tmp_path / "project"
        project.mkdir()
        (project / "config").mkdir()
        (project / "config" / "default.yml").write_text("version: 2")

        install_dir = tmp_path / "install"
        (install_dir / "config").mkdir(parents=True)
        (install_dir / "config" / "default.yml").write_text("version: 1")

        deploy_config(project, install_dir)

        assert (install_dir / "config" / "default.yml").read_text() == "version: 2"


# ── Installer クラステスト ──


class TestInstaller:
    """Installer クラスのテスト。"""

    def test_init_default(self) -> None:
        installer = Installer(config={})
        assert isinstance(installer.install_dir, Path)

    def test_init_custom_dir(self, tmp_path: Path) -> None:
        installer = Installer(install_dir=tmp_path / "custom", config={})
        assert installer.install_dir == tmp_path / "custom"

    def test_cleanup_removes_temp(self, tmp_path: Path) -> None:
        installer = Installer(install_dir=tmp_path, config={})
        # _temp_dir を手動設定
        temp = tmp_path / "temp"
        temp.mkdir()
        (temp / "file.txt").write_text("temp")
        installer._temp_dir = temp

        installer.cleanup()
        assert not temp.exists()

    def test_cleanup_no_temp(self) -> None:
        """_temp_dir が None でもエラーにならない。"""
        installer = Installer(config={})
        installer.cleanup()  # エラーなしで完了すること

    @patch("installer.downloader.install_dependencies")
    @patch("installer.downloader.build_exe")
    @patch("installer.downloader.deploy_config")
    @patch("installer.downloader.download_file")
    @patch("installer.downloader.extract_archive")
    @patch("installer.downloader.get_source_tarball_url")
    def test_run_full_flow(
        self,
        mock_tarball_url: MagicMock,
        mock_extract: MagicMock,
        mock_download: MagicMock,
        mock_deploy: MagicMock,
        mock_build_exe: MagicMock,
        mock_install_deps: MagicMock,
        tmp_path: Path,
    ) -> None:
        """run() の完全フロー（全外部操作をモック化）。"""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        exe_path = tmp_path / "VibePDCA.exe"
        exe_path.touch()

        mock_tarball_url.return_value = "https://example.com/tarball"
        mock_download.return_value = tmp_path / "source.tar.gz"
        mock_extract.return_value = project_dir
        mock_install_deps.return_value = True
        mock_build_exe.return_value = exe_path

        progress_messages: list[str] = []

        installer = Installer(
            install_dir=tmp_path / "install",
            config={},
            progress_callback=lambda msg: progress_messages.append(str(msg)),
        )
        result = installer.run()

        assert result == exe_path
        assert any("インストーラー開始" in m for m in progress_messages)
        assert any("インストール完了" in m for m in progress_messages)

    def test_run_fails_python_version(self, tmp_path: Path) -> None:
        """Python バージョンが不足している場合のエラー。"""
        with patch("installer.downloader.check_python_version", return_value=False):
            installer = Installer(install_dir=tmp_path, config={})
            with pytest.raises(SetupError, match="Python"):
                installer.run()


# ── エラークラステスト ──


class TestErrorClasses:
    """エラークラスの継承関係テスト。"""

    def test_installer_error_is_exception(self) -> None:
        assert issubclass(InstallerError, Exception)

    def test_download_error_is_installer_error(self) -> None:
        assert issubclass(DownloadError, InstallerError)

    def test_setup_error_is_installer_error(self) -> None:
        assert issubclass(SetupError, InstallerError)
