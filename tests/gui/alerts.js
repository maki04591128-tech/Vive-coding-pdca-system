/**
 * Vibe PDCA システム – アラート通知パネル (JavaScript)
 *
 * §3.5 アラート通知パネルの機能をデモする:
 *   - レベル別フィルタリング (CRITICAL / ERROR / WARNING / INFO)
 *   - カテゴリ別フィルタリング
 *   - アラートサマリーカウント
 *   - アラート一覧表示
 */

"use strict";

// ============================================================
// DOM ヘルパー
// ============================================================

function $(id) {
  return document.getElementById(id);
}

// ============================================================
// ログ管理
// ============================================================

function addLog(message, level) {
  level = level || "INFO";
  var container = $("logContainer");
  var entry = document.createElement("div");
  entry.className = "log-entry";
  var classMap = {
    INFO: "log-info",
    WARNING: "log-warning",
    ERROR: "log-error",
    DEBUG: "log-debug",
  };
  entry.classList.add(classMap[level] || "log-info");
  var now = new Date();
  var ts = now.toLocaleTimeString("ja-JP");
  entry.textContent = "[" + ts + "] [" + level + "] " + message;
  container.appendChild(entry);
  container.scrollTop = container.scrollHeight;
}

// ============================================================
// 状態管理
// ============================================================

var state = {
  alerts: [],
  activeFilter: "all",
  categoryFilter: "all",
};

// 初期アラートデータ
var initialAlerts = [
  { id: 1, level: "critical", category: "cost", message: "日次コスト上限の90%に到達しました ($27.00 / $30.00)", timestamp: new Date(Date.now() - 300000) },
  { id: 2, level: "error", category: "circuit", message: "openai-gpt5.1 サーキットブレーカー開放 (連続失敗: 3回)", timestamp: new Date(Date.now() - 600000) },
  { id: 3, level: "warning", category: "ci", message: "CI テスト失敗: test_auth_middleware (2回目)", timestamp: new Date(Date.now() - 900000) },
  { id: 4, level: "info", category: "governance", message: "A-ops 承認リクエスト送信: DB スキーマ変更", timestamp: new Date(Date.now() - 1200000) },
  { id: 5, level: "warning", category: "cost", message: "日次コスト警告閾値 (70%) を超過しました", timestamp: new Date(Date.now() - 1800000) },
  { id: 6, level: "error", category: "ci", message: "CI テスト失敗: test_user_crud (連続失敗)", timestamp: new Date(Date.now() - 2400000) },
  { id: 7, level: "info", category: "governance", message: "サイクル #2 CHECK フェーズ完了: 5ペルソナレビュー実施済み", timestamp: new Date(Date.now() - 3600000) },
  { id: 8, level: "warning", category: "security", message: "セキュリティスキャン: 中程度の脆弱性 1件検出 (npm audit)", timestamp: new Date(Date.now() - 5400000) },
];

// ============================================================
// アラートテンプレート (デモ追加用)
// ============================================================

var alertTemplates = [
  { level: "critical", category: "circuit", message: "全クラウドプロバイダのサーキットブレーカーが開放されました" },
  { level: "critical", category: "cost", message: "日次コスト上限に到達しました – API呼び出しを停止" },
  { level: "error", category: "ci", message: "CI パイプライン異常終了: タイムアウト (300s)" },
  { level: "error", category: "security", message: "セキュリティスキャン: 重大脆弱性検出 (CVE-2026-XXXX)" },
  { level: "warning", category: "governance", message: "A-ops 承認タイムアウト: 15分以内に応答がありません" },
  { level: "warning", category: "cost", message: "API呼び出し回数が上限の80%に到達しました" },
  { level: "info", category: "ci", message: "CI テスト全件パス: 42/42 テスト成功" },
  { level: "info", category: "governance", message: "サイクル #3 ACT フェーズ: ACCEPT 判定" },
];

// ============================================================
// フィルタリング
// ============================================================

function getFilteredAlerts() {
  return state.alerts.filter(function (a) {
    var levelOk = state.activeFilter === "all" || a.level === state.activeFilter;
    var catOk = state.categoryFilter === "all" || a.category === state.categoryFilter;
    return levelOk && catOk;
  });
}

// ============================================================
// 描画
// ============================================================

function renderSummary() {
  var counts = { critical: 0, error: 0, warning: 0, info: 0 };
  for (var i = 0; i < state.alerts.length; i++) {
    var level = state.alerts[i].level;
    if (counts[level] !== undefined) counts[level]++;
  }
  $("criticalCount").textContent = counts.critical;
  $("errorCount").textContent = counts.error;
  $("warningCount").textContent = counts.warning;
  $("infoCount").textContent = counts.info;
  $("alertCounter").textContent = "合計: " + state.alerts.length + "件";
}

function renderAlerts() {
  var container = $("alertList");
  var filtered = getFilteredAlerts();

  if (filtered.length === 0) {
    container.innerHTML = '<div class="placeholder-text">該当するアラートはありません</div>';
    return;
  }

  var html = "";
  for (var i = 0; i < filtered.length; i++) {
    var a = filtered[i];
    var levelIcon = { critical: "🔴", error: "🟠", warning: "🟡", info: "🔵" };
    var categoryIcon = { cost: "💰", circuit: "⚡", ci: "🔧", security: "🛡️", governance: "📜" };
    var ts = a.timestamp.toLocaleTimeString("ja-JP");

    html +=
      '<div class="alert-row alert-level-' + a.level + '">' +
      '  <span class="alert-level-icon">' + (levelIcon[a.level] || "⚪") + '</span>' +
      '  <span class="alert-category-icon">' + (categoryIcon[a.category] || "📋") + '</span>' +
      '  <span class="alert-message">' + a.message + '</span>' +
      '  <span class="alert-time">' + ts + '</span>' +
      '</div>';
  }
  container.innerHTML = html;
}

function renderAll() {
  renderSummary();
  renderAlerts();
}

// ============================================================
// フィルターイベント
// ============================================================

function setupFilters() {
  // レベルフィルター
  var chips = document.querySelectorAll(".filter-chip[data-level]");
  for (var i = 0; i < chips.length; i++) {
    (function (chip) {
      chip.addEventListener("click", function (e) {
        e.preventDefault();
        // 全チップのactiveを解除
        for (var j = 0; j < chips.length; j++) {
          chips[j].classList.remove("active");
        }
        chip.classList.add("active");
        state.activeFilter = chip.getAttribute("data-level");
        renderAlerts();
        addLog("フィルター変更: " + state.activeFilter, "DEBUG");
      });
    })(chips[i]);
  }

  // カテゴリフィルター
  $("categoryFilter").addEventListener("change", function () {
    state.categoryFilter = this.value;
    renderAlerts();
    addLog("カテゴリフィルター: " + state.categoryFilter, "DEBUG");
  });
}

// ============================================================
// デモ操作
// ============================================================

function addRandomAlert() {
  var template = alertTemplates[Math.floor(Math.random() * alertTemplates.length)];
  var alert = {
    id: state.alerts.length + 1,
    level: template.level,
    category: template.category,
    message: template.message,
    timestamp: new Date(),
  };
  state.alerts.unshift(alert);
  renderAll();
  addLog("🔔 アラート追加: [" + alert.level.toUpperCase() + "] " + alert.message, "INFO");
}

function addCriticalAlert() {
  var alert = {
    id: state.alerts.length + 1,
    level: "critical",
    category: "circuit",
    message: "⚠️ 全LLMプロバイダが応答不能 – 即時対応が必要です",
    timestamp: new Date(),
  };
  state.alerts.unshift(alert);
  renderAll();
  addLog("🔴 CRITICALアラート追加", "ERROR");
}

function clearAlerts() {
  state.alerts = [];
  renderAll();
  addLog("🗑️ アラートをクリアしました", "INFO");
}

// ============================================================
// 初期化
// ============================================================

function init() {
  // 初期データ読み込み
  state.alerts = initialAlerts.slice();

  setupFilters();

  $("btnAddAlert").addEventListener("click", addRandomAlert);
  $("btnAddCritical").addEventListener("click", addCriticalAlert);
  $("btnClearAlerts").addEventListener("click", clearAlerts);

  renderAll();
  addLog("アラート通知パネルを起動しました", "INFO");
}

document.addEventListener("DOMContentLoaded", init);
