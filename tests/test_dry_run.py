"""ドライランのテスト。"""

from vibe_pdca.engine.dry_run import DryRunExecutor


class TestDryRun:
    def test_basic_execution(self):
        dr = DryRunExecutor()
        result = dr.execute(
            goal_purpose="テストシステム構築",
            acceptance_criteria=["条件1", "条件2", "条件3"],
        )
        assert result.estimated_tasks == 3
        assert result.estimated_cycles >= 1
        assert result.estimated_cost_usd > 0

    def test_warnings_without_constraints(self):
        dr = DryRunExecutor()
        result = dr.execute(
            goal_purpose="テスト",
            acceptance_criteria=["条件1"],
        )
        assert any("制約" in w for w in result.warnings)

    def test_blockers_for_large_scope(self):
        dr = DryRunExecutor()
        result = dr.execute(
            goal_purpose="大規模プロジェクト",
            acceptance_criteria=[f"条件{i}" for i in range(15)],
        )
        assert len(result.potential_blockers) > 0

    def test_to_markdown(self):
        dr = DryRunExecutor()
        result = dr.execute(
            goal_purpose="テスト",
            acceptance_criteria=["条件1"],
            constraints=["制約1"],
        )
        md = result.to_markdown()
        assert "ドライラン結果" in md

    def test_run_count(self):
        dr = DryRunExecutor()
        dr.execute("テスト1", ["条件1"])
        dr.execute("テスト2", ["条件1"])
        assert dr.run_count == 2


class TestDryRunMarkdownBlockersAndWarnings:
    """ブロッカーと警告の両方があるドライラン結果のMarkdownテスト。"""

    def test_markdown_with_blockers_and_warnings(self):
        dr = DryRunExecutor()
        # 受入条件15件でブロッカー発生、制約なしで警告発生
        result = dr.execute(
            goal_purpose="大規模テスト",
            acceptance_criteria=[f"条件{i}" for i in range(15)],
        )
        md = result.to_markdown()
        assert "潜在ブロッカー" in md
        assert "⚠️" in md
        assert "警告" in md
        assert "制約が未定義です" in md


class TestDryRunExecutorBarrierThreadSafety:
    """DryRunExecutorのスレッドセーフティテスト（Barrier同期）。"""

    def test_concurrent_execute(self):
        import threading

        executor = DryRunExecutor()
        n_threads = 10
        ops_per_thread = 10
        barrier = threading.Barrier(n_threads)

        def worker(tid: int) -> None:
            barrier.wait()
            for _ in range(ops_per_thread):
                executor.execute(
                    goal_purpose="test", acceptance_criteria=["ok"]
                )

        threads = [
            threading.Thread(target=worker, args=(t,)) for t in range(n_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert executor.run_count == n_threads * ops_per_thread
