"""サンドボックスリソース制限と監視のテスト。"""

import time

from vibe_pdca.engine.sandbox_resource import (
    DockerResourceConfig,
    OOMHandler,
    ResourceAlert,
    ResourceLimit,
    ResourceMonitor,
    ResourceUsage,
)


class TestResourceLimit:
    def test_default_values(self):
        limit = ResourceLimit()
        assert limit.memory_mb == 512
        assert limit.cpus == 1.0
        assert limit.pids_limit == 256
        assert limit.storage_mb == 1024
        assert limit.network_bandwidth_mbps is None
        assert limit.timeout_seconds == 3600

    def test_custom_values(self):
        limit = ResourceLimit(memory_mb=1024, cpus=2.0, pids_limit=512)
        assert limit.memory_mb == 1024
        assert limit.cpus == 2.0
        assert limit.pids_limit == 512


class TestResourceUsage:
    def test_creation(self):
        usage = ResourceUsage(
            memory_mb=256.0, cpu_percent=50.0, disk_mb=100.0, pid_count=10
        )
        assert usage.memory_mb == 256.0
        assert usage.cpu_percent == 50.0
        assert usage.disk_mb == 100.0
        assert usage.pid_count == 10
        assert usage.timestamp > 0

    def test_custom_timestamp(self):
        ts = 1700000000.0
        usage = ResourceUsage(
            memory_mb=0, cpu_percent=0, disk_mb=0, pid_count=0, timestamp=ts
        )
        assert usage.timestamp == ts


class TestResourceAlert:
    def test_creation(self):
        alert = ResourceAlert(
            resource_type="memory",
            current_value=450.0,
            limit_value=512.0,
            threshold_percent=80.0,
            severity="warning",
        )
        assert alert.resource_type == "memory"
        assert alert.severity == "warning"


class TestDockerResourceConfig:
    def test_to_docker_args(self):
        limit = ResourceLimit()
        config = DockerResourceConfig(limit)
        args = config.to_docker_args()
        assert "--memory=512m" in args
        assert "--cpus=1.0" in args
        assert "--pids-limit=256" in args
        assert "--stop-timeout=3600" in args

    def test_to_docker_args_with_network(self):
        limit = ResourceLimit(network_bandwidth_mbps=100)
        config = DockerResourceConfig(limit)
        args = config.to_docker_args()
        assert "--network-bandwidth=100mbps" in args

    def test_to_docker_args_without_network(self):
        limit = ResourceLimit()
        config = DockerResourceConfig(limit)
        args = config.to_docker_args()
        network_args = [a for a in args if "network-bandwidth" in a]
        assert len(network_args) == 0

    def test_to_docker_compose_dict(self):
        limit = ResourceLimit(memory_mb=1024, cpus=2.0, pids_limit=128)
        config = DockerResourceConfig(limit)
        result = config.to_docker_compose_dict()
        assert "resources" in result
        limits = result["resources"]["limits"]
        assert limits["memory"] == "1024M"
        assert limits["cpus"] == "2.0"
        assert limits["pids"] == 128
        reservations = result["resources"]["reservations"]
        assert reservations["memory"] == "512M"
        assert reservations["cpus"] == "1.0"


class TestResourceMonitor:
    def test_no_alert_under_threshold(self):
        limit = ResourceLimit(memory_mb=512)
        monitor = ResourceMonitor(limit)
        usage = ResourceUsage(
            memory_mb=200.0, cpu_percent=30.0, disk_mb=100.0, pid_count=10
        )
        alerts = monitor.check_usage(usage)
        assert len(alerts) == 0

    def test_warning_alert(self):
        limit = ResourceLimit(memory_mb=512)
        monitor = ResourceMonitor(limit)
        usage = ResourceUsage(
            memory_mb=420.0, cpu_percent=30.0, disk_mb=100.0, pid_count=10
        )
        alerts = monitor.check_usage(usage)
        memory_alerts = [a for a in alerts if a.resource_type == "memory"]
        assert len(memory_alerts) == 1
        assert memory_alerts[0].severity == "warning"

    def test_critical_alert(self):
        limit = ResourceLimit(memory_mb=512)
        monitor = ResourceMonitor(limit)
        usage = ResourceUsage(
            memory_mb=500.0, cpu_percent=30.0, disk_mb=100.0, pid_count=10
        )
        alerts = monitor.check_usage(usage)
        memory_alerts = [a for a in alerts if a.resource_type == "memory"]
        assert len(memory_alerts) == 1
        assert memory_alerts[0].severity == "critical"

    def test_multiple_alerts(self):
        limit = ResourceLimit(memory_mb=512, pids_limit=256)
        monitor = ResourceMonitor(limit)
        usage = ResourceUsage(
            memory_mb=500.0, cpu_percent=30.0, disk_mb=100.0, pid_count=250
        )
        alerts = monitor.check_usage(usage)
        types = {a.resource_type for a in alerts}
        assert "memory" in types
        assert "pid" in types

    def test_custom_thresholds(self):
        limit = ResourceLimit(memory_mb=512)
        monitor = ResourceMonitor(
            limit, warning_threshold=0.5, critical_threshold=0.7
        )
        usage = ResourceUsage(
            memory_mb=300.0, cpu_percent=10.0, disk_mb=50.0, pid_count=5
        )
        alerts = monitor.check_usage(usage)
        memory_alerts = [a for a in alerts if a.resource_type == "memory"]
        assert len(memory_alerts) == 1
        assert memory_alerts[0].severity == "warning"

    def test_get_summary_empty(self):
        limit = ResourceLimit()
        monitor = ResourceMonitor(limit)
        summary = monitor.get_summary()
        assert summary["sample_count"] == 0

    def test_get_summary_with_samples(self):
        limit = ResourceLimit()
        monitor = ResourceMonitor(limit)
        monitor.check_usage(
            ResourceUsage(
                memory_mb=100.0, cpu_percent=20.0, disk_mb=50.0, pid_count=5
            )
        )
        monitor.check_usage(
            ResourceUsage(
                memory_mb=200.0, cpu_percent=40.0, disk_mb=80.0, pid_count=10
            )
        )
        summary = monitor.get_summary()
        assert summary["sample_count"] == 2
        assert summary["memory_mb_max"] == 200.0
        assert summary["memory_mb_avg"] == 150.0
        assert summary["cpu_percent_max"] == 40.0
        assert summary["pid_count_max"] == 10


class TestOOMHandler:
    def test_detect_oom_true(self):
        handler = OOMHandler()
        assert handler.detect_oom(137) is True

    def test_detect_oom_false(self):
        handler = OOMHandler()
        assert handler.detect_oom(0) is False
        assert handler.detect_oom(1) is False

    def test_generate_report_oom(self):
        handler = OOMHandler()
        report = handler.generate_report("container-abc", 137)
        assert report["container_id"] == "container-abc"
        assert report["exit_code"] == 137
        assert report["oom_detected"] is True
        assert report["recommendation"] != ""
        assert report["timestamp"] > 0

    def test_generate_report_normal_exit(self):
        handler = OOMHandler()
        report = handler.generate_report("container-xyz", 0)
        assert report["oom_detected"] is False
        assert report["recommendation"] == ""
