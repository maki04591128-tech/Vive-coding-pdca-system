/**
 * Vibe PDCA システム – 介入コントロールパネル (JavaScript)
 *
 * §10.4 介入パネルの機能をデモする:
 *   - 緊急停止 / 再開
 *   - 根本原因レポート (自動生成)
 *   - 再開条件チェック
 *   - ロールバック候補表示
 *   - 判定オーバーライド
 *   - タスク優先度変更
 *   - マイルストーン再構築
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
  isStopped: false,
  stopReason: null,
  stopTime: null,
};

// ============================================================
// 緊急停止 / 再開
// ============================================================

function emergencyStop() {
  if (state.isStopped) {
    addLog("すでに停止中です", "WARNING");
    return;
  }

  state.isStopped = true;
  state.stopReason = "manual_intervention";
  state.stopTime = new Date();

  // UI更新
  $("systemStatusBadge").textContent = "🔴 停止中";
  $("systemStatusBadge").className = "system-status-badge stopped";
  $("emergencyStatus").textContent = "⛔ システムは手動介入により停止されました (" + state.stopTime.toLocaleTimeString("ja-JP") + ")";
  $("emergencyStatus").className = "emergency-status stopped";
  $("btnEmergencyStop").disabled = true;
  $("btnRestart").disabled = false;
  $("emergencyCard").classList.add("stopped-state");

  // 根本原因レポート生成
  renderRootCause();
  renderRestartConditions();
  renderRollbackCandidates();

  addLog("⛔ 緊急停止が実行されました", "ERROR");
}

function restartSystem() {
  if (!state.isStopped) {
    addLog("システムは稼働中です", "WARNING");
    return;
  }

  // 再開条件チェック
  var checks = document.querySelectorAll("#restartCondContent .restart-check input");
  var allChecked = true;
  for (var i = 0; i < checks.length; i++) {
    if (!checks[i].checked) {
      allChecked = false;
      break;
    }
  }

  if (!allChecked) {
    addLog("再開条件が満たされていません。すべての条件をチェックしてください。", "WARNING");
    return;
  }

  state.isStopped = false;
  state.stopReason = null;
  state.stopTime = null;

  $("systemStatusBadge").textContent = "🟢 正常稼働";
  $("systemStatusBadge").className = "system-status-badge";
  $("emergencyStatus").textContent = "システムは正常に稼働しています。";
  $("emergencyStatus").className = "emergency-status";
  $("btnEmergencyStop").disabled = false;
  $("btnRestart").disabled = true;
  $("emergencyCard").classList.remove("stopped-state");

  $("rootCauseContent").innerHTML = '<span class="placeholder-text">停止時に自動生成されます</span>';
  $("restartCondContent").innerHTML = '<span class="placeholder-text">停止時に自動表示されます</span>';
  $("rollbackList").innerHTML = '<span class="placeholder-text">停止時にロールバック候補を表示します</span>';

  addLog("▶️ システムを再開しました", "INFO");
}

// ============================================================
// 根本原因レポート
// ============================================================

function renderRootCause() {
  var container = $("rootCauseContent");
  container.innerHTML =
    '<div class="root-cause-report">' +
    '  <div class="report-row"><span class="report-label">停止理由:</span><span class="report-value">手動介入 (manual_intervention)</span></div>' +
    '  <div class="report-row"><span class="report-label">停止時刻:</span><span class="report-value">' + state.stopTime.toLocaleString("ja-JP") + '</span></div>' +
    '  <div class="report-row"><span class="report-label">最終フェーズ:</span><span class="report-value">DO (サイクル #2)</span></div>' +
    '  <div class="report-row"><span class="report-label">直前エラー:</span><span class="report-value error-text">CI テスト失敗 (3回連続)</span></div>' +
    '  <div class="report-row"><span class="report-label">影響範囲:</span><span class="report-value">MS-002: CRUD API実装 – Task 3/4</span></div>' +
    '  <div class="report-row"><span class="report-label">推奨対応:</span><span class="report-value">エラーハンドリングのテストケース修正後に再開</span></div>' +
    '</div>';
}

// ============================================================
// 再開条件
// ============================================================

function renderRestartConditions() {
  var container = $("restartCondContent");
  var conditions = [
    "CI テストが全件パスすること",
    "根本原因が特定・対処済みであること",
    "コスト上限に余裕があること (現在: 65%)",
    "サーキットブレーカーが全てCLOSEDであること",
  ];

  var html = "";
  for (var i = 0; i < conditions.length; i++) {
    html +=
      '<label class="restart-check">' +
      '<input type="checkbox"> ' +
      '<span>' + conditions[i] + '</span>' +
      '</label>';
  }
  container.innerHTML = html;
}

// ============================================================
// ロールバック候補
// ============================================================

function renderRollbackCandidates() {
  var container = $("rollbackList");
  var candidates = [
    { commit: "a3f2c1d", desc: "MS-002 Task2完了時点", time: "10:35", status: "CI ✅" },
    { commit: "b7e4a8f", desc: "MS-001 完了時点", time: "10:45", status: "CI ✅" },
    { commit: "c1d9e3b", desc: "MS-002 Task3 途中 (テスト失敗)", time: "11:02", status: "CI ❌" },
  ];

  var html = "";
  for (var i = 0; i < candidates.length; i++) {
    var c = candidates[i];
    var statusClass = c.status.indexOf("✅") >= 0 ? "badge-green" : "badge-orange";
    html +=
      '<div class="rollback-item">' +
      '  <div class="rollback-commit"><code>' + c.commit + '</code></div>' +
      '  <div class="rollback-desc">' + c.desc + '</div>' +
      '  <div class="rollback-time">' + c.time + '</div>' +
      '  <span class="badge ' + statusClass + '">' + c.status + '</span>' +
      '  <button class="btn-sm btn-secondary rollback-btn" data-commit="' + c.commit + '">ロールバック</button>' +
      '</div>';
  }
  container.innerHTML = html;

  // ロールバックボタンにイベント追加
  var btns = container.querySelectorAll(".rollback-btn");
  for (var j = 0; j < btns.length; j++) {
    btns[j].addEventListener("click", function () {
      addLog("⏪ ロールバック実行: " + this.getAttribute("data-commit"), "INFO");
    });
  }
}

// ============================================================
// 判定オーバーライド
// ============================================================

function handleOverride() {
  var cycle = $("overrideCycle").value;
  var reason = $("overrideReason").value.trim();

  if (!cycle) {
    addLog("対象サイクルを選択してください", "WARNING");
    return;
  }

  var selected = document.querySelector('#overrideDecision .radio-option.selected');
  if (!selected) {
    addLog("新しい判定を選択してください", "WARNING");
    return;
  }

  var decision = selected.getAttribute("data-value");
  addLog("🔄 判定オーバーライド: " + cycle + " → " + decision.toUpperCase() +
    (reason ? " (理由: " + reason + ")" : ""), "INFO");
}

// ============================================================
// タスク優先度
// ============================================================

function applyPriority() {
  var selects = document.querySelectorAll("#taskPriorityList select");
  var changes = [];
  for (var i = 0; i < selects.length; i++) {
    var taskId = selects[i].getAttribute("data-task");
    var priority = selects[i].value;
    changes.push(taskId + "=" + priority);
  }
  addLog("📊 優先度更新: " + changes.join(", "), "INFO");
}

// ============================================================
// マイルストーン編集
// ============================================================

function toggleEditArea(id) {
  var area = $(id);
  if (area.style.display === "none") {
    area.style.display = "block";
  } else {
    area.style.display = "none";
  }
}

// ============================================================
// ラジオグループ制御
// ============================================================

function setupRadioGroup(groupId) {
  var group = $(groupId);
  if (!group) return;
  var options = group.querySelectorAll(".radio-option");
  for (var i = 0; i < options.length; i++) {
    (function (option) {
      option.addEventListener("click", function () {
        for (var j = 0; j < options.length; j++) {
          options[j].classList.remove("selected");
        }
        option.classList.add("selected");
        var radio = option.querySelector("input[type='radio']");
        if (radio) radio.checked = true;
      });
    })(options[i]);
  }
}

// ============================================================
// 初期化
// ============================================================

function init() {
  $("btnEmergencyStop").addEventListener("click", emergencyStop);
  $("btnRestart").addEventListener("click", restartSystem);
  $("btnOverride").addEventListener("click", handleOverride);
  $("btnApplyPriority").addEventListener("click", applyPriority);

  // マイルストーン編集トグル
  var editMs2 = $("btnEditMs2");
  if (editMs2) {
    editMs2.addEventListener("click", function () {
      toggleEditArea("editAreaMs2");
    });
  }
  var saveMs2 = $("btnSaveMs2");
  if (saveMs2) {
    saveMs2.addEventListener("click", function () {
      toggleEditArea("editAreaMs2");
      addLog("🏗️ MS-002 再定義を保存しました", "INFO");
    });
  }
  var cancelMs2 = $("btnCancelMs2");
  if (cancelMs2) {
    cancelMs2.addEventListener("click", function () {
      toggleEditArea("editAreaMs2");
    });
  }

  var addMs = $("btnAddMilestone");
  if (addMs) {
    addMs.addEventListener("click", function () {
      addLog("🏗️ 新しいマイルストーンを追加しました (デモ)", "INFO");
    });
  }

  setupRadioGroup("overrideDecision");

  addLog("介入コントロールパネルを起動しました", "INFO");
}

document.addEventListener("DOMContentLoaded", init);
