"""サンドボックスのリソース制限と監視の強化。

提案19: 要件定義書 §12, ADR-007 準拠。

- コンテナリソース制限（メモリ・CPU・PID・ストレージ）
- リソース使用量の監視とアラート生成
- OOMキル検知とレポート生成
- Docker実行引数の生成
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# デフォルト閾値
DEFAULT_WARNING_THRESHOLD = 0.8
DEFAULT_CRITICAL_THRESHOLD = 0.95

# OOMキルの終了コード
OOM_EXIT_CODE = 137


@dataclass
class ResourceLimit:
    """コンテナリソース制限。"""

    memory_mb: int = 512
    cpus: float = 1.0
    pids_limit: int = 256
    storage_mb: int = 1024
    network_bandwidth_mbps: int | None = None
    timeout_seconds: int = 3600


@dataclass
class ResourceUsage:
    """現在のリソース使用量。"""

    memory_mb: float
    cpu_percent: float
    disk_mb: float
    pid_count: int
    timestamp: float = field(default_factory=time.time)


@dataclass
class ResourceAlert:
    """リソース制限に近づいた場合のアラート。"""

    resource_type: str
    current_value: float
    limit_value: float
    threshold_percent: float
    severity: str


class DockerResourceConfig:
    """ResourceLimitからDocker実行引数を生成する。"""

    def __init__(self, limit: ResourceLimit) -> None:
        self._limit = limit

    def to_docker_args(self) -> list[str]:
        """Docker runコマンド用の引数リストを返す。

        Note:
            --storage-opt はdevicemapper/btrfs/overlay2等の対応ドライバが必要。
            network_bandwidth_mbps はDocker標準外の拡張引数（tc等での制御を想定）。
        """
        args = [
            f"--memory={self._limit.memory_mb}m",
            f"--cpus={self._limit.cpus}",
            f"--pids-limit={self._limit.pids_limit}",
            f"--stop-timeout={self._limit.timeout_seconds}",
        ]
        if self._limit.storage_mb:
            args.append(f"--storage-opt=size={self._limit.storage_mb}m")
        if self._limit.network_bandwidth_mbps is not None:
            # Docker標準外: 外部ツール(tc等)でのネットワーク帯域制限用の設定値
            args.append(
                f"--network-bandwidth={self._limit.network_bandwidth_mbps}mbps"
            )
        return args

    def to_docker_compose_dict(self) -> dict:
        """Docker Compose用のresourcesセクション辞書を返す。"""
        limits: dict = {
            "cpus": str(self._limit.cpus),
            "memory": f"{self._limit.memory_mb}M",
            "pids": self._limit.pids_limit,
        }
        reservations: dict = {
            "cpus": str(self._limit.cpus / 2),
            "memory": f"{self._limit.memory_mb // 2}M",
        }
        return {
            "resources": {
                "limits": limits,
                "reservations": reservations,
            },
        }


class ResourceMonitor:
    """コンテナリソース使用量を監視し、アラートを生成する。"""

    def __init__(
        self,
        limit: ResourceLimit,
        *,
        warning_threshold: float = DEFAULT_WARNING_THRESHOLD,
        critical_threshold: float = DEFAULT_CRITICAL_THRESHOLD,
    ) -> None:
        self._limit = limit
        self._warning_threshold = warning_threshold
        self._critical_threshold = critical_threshold
        self._samples: list[ResourceUsage] = []

    def check_usage(self, usage: ResourceUsage) -> list[ResourceAlert]:
        """使用量を制限と照合し、アラートリストを返す。"""
        self._samples.append(usage)
        alerts: list[ResourceAlert] = []

        checks: list[tuple[str, float, float]] = [
            ("memory", usage.memory_mb, float(self._limit.memory_mb)),
            ("cpu", usage.cpu_percent, 100.0 * self._limit.cpus),
            ("disk", usage.disk_mb, float(self._limit.storage_mb)),
            ("pid", float(usage.pid_count), float(self._limit.pids_limit)),
        ]

        for resource_type, current, limit_val in checks:
            if limit_val <= 0:
                continue
            ratio = current / limit_val
            if ratio >= self._critical_threshold:
                alerts.append(
                    ResourceAlert(
                        resource_type=resource_type,
                        current_value=current,
                        limit_value=limit_val,
                        threshold_percent=self._critical_threshold * 100,
                        severity="critical",
                    )
                )
                logger.warning(
                    "リソース危険: %s %.1f/%.1f (%.0f%%)",
                    resource_type,
                    current,
                    limit_val,
                    ratio * 100,
                )
            elif ratio >= self._warning_threshold:
                alerts.append(
                    ResourceAlert(
                        resource_type=resource_type,
                        current_value=current,
                        limit_value=limit_val,
                        threshold_percent=self._warning_threshold * 100,
                        severity="warning",
                    )
                )
                logger.info(
                    "リソース警告: %s %.1f/%.1f (%.0f%%)",
                    resource_type,
                    current,
                    limit_val,
                    ratio * 100,
                )

        return alerts

    def get_summary(self) -> dict:
        """収集したサンプルの統計サマリを返す。"""
        if not self._samples:
            return {"sample_count": 0}

        return {
            "sample_count": len(self._samples),
            "memory_mb_max": max(s.memory_mb for s in self._samples),
            "memory_mb_avg": sum(s.memory_mb for s in self._samples)
            / len(self._samples),
            "cpu_percent_max": max(s.cpu_percent for s in self._samples),
            "cpu_percent_avg": sum(s.cpu_percent for s in self._samples)
            / len(self._samples),
            "disk_mb_max": max(s.disk_mb for s in self._samples),
            "pid_count_max": max(s.pid_count for s in self._samples),
        }


class OOMHandler:
    """Out-of-Memoryキルの検知とレポート生成。"""

    def detect_oom(self, container_exit_code: int) -> bool:
        """終了コードからOOMキルを検知する。"""
        return container_exit_code == OOM_EXIT_CODE

    def generate_report(self, container_id: str, exit_code: int) -> dict:
        """OOMイベントのレポートを生成する。"""
        is_oom = self.detect_oom(exit_code)
        return {
            "container_id": container_id,
            "exit_code": exit_code,
            "oom_detected": is_oom,
            "timestamp": time.time(),
            "recommendation": "メモリ制限の引き上げを検討してください。"
            if is_oom
            else "",
        }
