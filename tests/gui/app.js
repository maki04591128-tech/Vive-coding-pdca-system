/**
 * Vibe PDCA システム – GUI モック (JavaScript)
 *
 * Flet ベースの実際の GUI コンポーネント (DashboardView, StatusCard,
 * CostCard, PDCAStatusCard) の動作をブラウザ上で再現するモックです。
 *
 * デモ操作ボタンにより、以下のインタラクションを確認できます:
 *   - モード切替 (cloud ↔ local)
 *   - PDCAフェーズ遷移 (plan → do → check → act)
 *   - コスト加算と閾値別カラー変化
 *   - サーキットブレーカー状態変化
 *   - 停止/リセット
 */

"use strict";

// ============================================================
// 状態管理
// ============================================================

/** @type {object} アプリケーション全体の状態 */
const state = {
  mode: "cloud",
  currentPhaseIndex: -1,
  phases: ["plan", "do", "check", "act"],
  cycleNumber: 0,
  isStopped: false,
  stopReason: null,
  milestoneId: "ms-001",
  milestoneStatus: "open",
  cost: {
    dailyCostUsd: 0.0,
    dailyLimitUsd: 30.0,
    dailyCalls: 0,
    maxCallsPerDay: 500,
  },
  cloudProviders: {
    "openai-gpt5.1": {
      circuitState: "closed",
      consecutiveFailures: 0,
      totalFallbacks: 0,
    },
    "anthropic-opus4": {
      circuitState: "closed",
      consecutiveFailures: 0,
      totalFallbacks: 0,
    },
  },
  localProviders: {
    "ollama-pm": {
      model: "qwen3:72b",
      baseUrl: "http://localhost:11434/v1",
      status: "unknown",
    },
    "ollama-programmer": {
      model: "codestral:22b",
      baseUrl: "http://localhost:11434/v1",
      status: "unknown",
    },
  },
};

// $, addLog は common.js で定義

// ============================================================
// プロバイダ表示
// ============================================================

/**
 * サーキットブレーカー状態に対応するアイコンと CSS クラスを返す。
 * @param {string} status
 * @returns {{icon: string, className: string}}
 */
function getStatusStyle(status) {
  var mapping = {
    closed:    { icon: "✅", className: "status-green" },
    healthy:   { icon: "✅", className: "status-green" },
    open:      { icon: "❌", className: "status-red" },
    unhealthy: { icon: "❌", className: "status-red" },
    half_open: { icon: "⚠️", className: "status-orange" },
    degraded:  { icon: "⚠️", className: "status-orange" },
  };
  return mapping[status] || { icon: "❓", className: "status-grey" };
}

/**
 * クラウドプロバイダ一覧を描画する。
 */
function renderCloudProviders() {
  var container = $("cloudProviders");
  container.innerHTML = "";
  var providers = state.cloudProviders;
  var keys = Object.keys(providers);
  for (var i = 0; i < keys.length; i++) {
    var name = keys[i];
    var info = providers[name];
    var style = getStatusStyle(info.circuitState);

    var row = document.createElement("div");
    row.className = "provider-row";

    var icon = document.createElement("span");
    icon.className = "provider-icon " + style.className;
    icon.textContent = style.icon;

    var details = document.createElement("div");
    var nameEl = document.createElement("div");
    nameEl.className = "provider-name";
    nameEl.textContent = name;

    var detailEl = document.createElement("div");
    detailEl.className = "provider-detail";
    var parts = ["CB: " + info.circuitState];
    if (info.totalFallbacks > 0) {
      parts.push("FB: " + info.totalFallbacks);
    }
    detailEl.textContent = parts.join("  |  ");

    details.appendChild(nameEl);
    details.appendChild(detailEl);
    row.appendChild(icon);
    row.appendChild(details);
    container.appendChild(row);
  }
}

/**
 * ローカルプロバイダ一覧を描画する。
 */
function renderLocalProviders() {
  var container = $("localProviders");
  container.innerHTML = "";
  var providers = state.localProviders;
  var keys = Object.keys(providers);
  for (var i = 0; i < keys.length; i++) {
    var name = keys[i];
    var info = providers[name];
    var style = getStatusStyle(info.status);

    var row = document.createElement("div");
    row.className = "provider-row";

    var icon = document.createElement("span");
    icon.className = "provider-icon " + style.className;
    icon.textContent = style.icon;

    var details = document.createElement("div");
    var nameEl = document.createElement("div");
    nameEl.className = "provider-name";
    nameEl.textContent = name;

    var detailEl = document.createElement("div");
    detailEl.className = "provider-detail";
    detailEl.textContent = info.model + "  |  " + info.baseUrl;

    details.appendChild(nameEl);
    details.appendChild(detailEl);
    row.appendChild(icon);
    row.appendChild(details);
    container.appendChild(row);
  }
}

// ============================================================
// コスト表示
// ============================================================

/**
 * コストカードを更新する。
 */
function renderCost() {
  var c = state.cost;
  $("costValue").textContent =
    "$" + c.dailyCostUsd.toFixed(2) + " / $" + c.dailyLimitUsd.toFixed(2);
  $("costCalls").textContent =
    c.dailyCalls + " / " + c.maxCallsPerDay + " calls";

  var ratio = c.dailyLimitUsd > 0 ? c.dailyCostUsd / c.dailyLimitUsd : 0;
  var pct = Math.min(ratio * 100, 100);
  var bar = $("costBar");
  bar.style.width = pct + "%";

  if (ratio >= 0.9) {
    bar.style.background = "#F44336";
  } else if (ratio >= 0.7) {
    bar.style.background = "#FF9800";
  } else {
    bar.style.background = "#2196F3";
  }
}

// ============================================================
// PDCA フェーズ表示
// ============================================================

/** フェーズ名から表示ラベルへのマッピング */
var phaseLabels = {
  plan:  "📋 PLAN",
  do:    "🔧 DO",
  check: "🔍 CHECK",
  act:   "✅ ACT",
};

/** フェーズ名からカラーへのマッピング */
var phaseColors = {
  plan:  "#1565C0",
  do:    "#2E7D32",
  check: "#E65100",
  act:   "#6A1B9A",
};

/**
 * PDCA カードを更新する。
 */
function renderPDCA() {
  var phase = state.currentPhaseIndex >= 0
    ? state.phases[state.currentPhaseIndex]
    : null;

  // フェーズテキスト
  var phaseEl = $("pdcaPhase");
  if (phase) {
    phaseEl.textContent = "フェーズ: " + phaseLabels[phase];
    phaseEl.style.color = phaseColors[phase];
  } else {
    phaseEl.textContent = "フェーズ: 未開始";
    phaseEl.style.color = "#9E9E9E";
  }

  // サイクル
  var cycleEl = $("pdcaCycle");
  if (state.cycleNumber > 0) {
    cycleEl.textContent =
      "サイクル: #" + state.cycleNumber + " (running)";
  } else {
    cycleEl.textContent = "サイクル: 未開始";
  }

  // マイルストーン
  $("pdcaMilestone").textContent =
    "MS: " + state.milestoneId + " (" + state.milestoneStatus + ")";

  // 停止状態
  var statusEl = $("pdcaStatus");
  if (state.isStopped && state.stopReason) {
    statusEl.textContent = "⛔ 停止中: " + state.stopReason;
    statusEl.style.color = "#F44336";
  } else if (state.currentPhaseIndex >= 0) {
    statusEl.textContent = "状態: 正常稼働";
    statusEl.style.color = "#4CAF50";
  } else {
    statusEl.textContent = "状態: --";
    statusEl.style.color = "#757575";
  }

  // フェーズチップ
  var chips = document.querySelectorAll("#phaseIndicators .phase-chip");
  for (var i = 0; i < chips.length; i++) {
    var chipPhase = chips[i].getAttribute("data-phase");
    // 全クラスリセット
    chips[i].className = "phase-chip";
    if (phase && chipPhase === phase) {
      chips[i].classList.add("active-" + phase);
    }
  }
}

// ============================================================
// モード切替
// ============================================================

/**
 * モード切替ハンドラ。
 */
function handleModeToggle() {
  var toggle = $("modeToggle");
  state.mode = toggle.checked ? "local" : "cloud";
  $("modeLabel").textContent = "現在のモード: " + state.mode;
  addLog("モード切替: " + state.mode, "INFO");
}

// ============================================================
// デモ操作
// ============================================================

/**
 * 次のフェーズへ遷移する。
 */
function advancePhase() {
  if (state.isStopped) {
    addLog("停止中のためフェーズ遷移できません", "WARNING");
    return;
  }
  state.currentPhaseIndex++;
  if (state.currentPhaseIndex >= state.phases.length) {
    // 1サイクル完了 → 次のサイクルへ
    state.currentPhaseIndex = 0;
    state.cycleNumber++;
    state.milestoneStatus = "in_progress";
    addLog(
      "サイクル #" + state.cycleNumber + " 開始 – PLAN フェーズ",
      "INFO"
    );
  } else {
    if (state.cycleNumber === 0) {
      state.cycleNumber = 1;
      state.milestoneStatus = "in_progress";
    }
    var phase = state.phases[state.currentPhaseIndex];
    addLog(
      "フェーズ遷移: " + phaseLabels[phase],
      "INFO"
    );
  }
  renderPDCA();
}

/**
 * コストを加算するデモ操作。
 */
function addCost() {
  var amount = 2.5 + Math.random() * 2.5;
  var calls = Math.floor(10 + Math.random() * 20);
  state.cost.dailyCostUsd += amount;
  state.cost.dailyCalls += calls;
  addLog(
    "API呼び出し +" + calls + " 回, コスト +$" + amount.toFixed(2),
    "INFO"
  );

  // 閾値チェック
  var ratio = state.cost.dailyCostUsd / state.cost.dailyLimitUsd;
  if (ratio >= 0.9) {
    addLog("⚠️ コスト上限 90% 超過！", "ERROR");
  } else if (ratio >= 0.7) {
    addLog("⚠️ コスト警告: 70% 超過", "WARNING");
  }
  renderCost();
}

/**
 * サーキットブレーカーを開放するデモ操作。
 */
function simulateCircuitOpen() {
  var names = Object.keys(state.cloudProviders);
  var target = names[Math.floor(Math.random() * names.length)];
  var provider = state.cloudProviders[target];

  if (provider.circuitState === "closed") {
    provider.circuitState = "open";
    provider.consecutiveFailures = 3;
    provider.totalFallbacks++;
    addLog(target + " サーキットブレーカー開放 (連続失敗: 3)", "ERROR");
  } else if (provider.circuitState === "open") {
    provider.circuitState = "half_open";
    addLog(target + " サーキットブレーカー半開放 (回復試行中)", "WARNING");
  } else {
    provider.circuitState = "closed";
    provider.consecutiveFailures = 0;
    addLog(target + " サーキットブレーカー回復 ✅", "INFO");
  }
  renderCloudProviders();
}

/**
 * 停止をシミュレーションするデモ操作。
 */
function simulateStop() {
  if (state.isStopped) {
    addLog("すでに停止中です", "WARNING");
    return;
  }
  state.isStopped = true;
  state.stopReason = "ci_consecutive_failure";
  addLog("⛔ システム停止: ci_consecutive_failure", "ERROR");
  renderPDCA();
}

/**
 * 状態をリセットするデモ操作。
 */
function resetState() {
  state.mode = "cloud";
  state.currentPhaseIndex = -1;
  state.cycleNumber = 0;
  state.isStopped = false;
  state.stopReason = null;
  state.milestoneStatus = "open";
  state.cost.dailyCostUsd = 0;
  state.cost.dailyCalls = 0;

  // プロバイダリセット
  var cloudKeys = Object.keys(state.cloudProviders);
  for (var i = 0; i < cloudKeys.length; i++) {
    state.cloudProviders[cloudKeys[i]].circuitState = "closed";
    state.cloudProviders[cloudKeys[i]].consecutiveFailures = 0;
    state.cloudProviders[cloudKeys[i]].totalFallbacks = 0;
  }

  // UI リセット
  $("modeToggle").checked = false;
  $("modeLabel").textContent = "現在のモード: cloud";
  $("logContainer").innerHTML = "";

  renderAll();
  addLog("システムリセット完了", "INFO");
}

// ============================================================
// 全体描画
// ============================================================

/**
 * 全コンポーネントを再描画する。
 */
function renderAll() {
  renderCloudProviders();
  renderLocalProviders();
  renderCost();
  renderPDCA();
}

// ============================================================
// 初期化
// ============================================================

/**
 * アプリケーション初期化。
 */
function init() {
  // イベントリスナー登録
  $("modeToggle").addEventListener("change", handleModeToggle);
  $("btnNextPhase").addEventListener("click", advancePhase);
  $("btnAddCost").addEventListener("click", addCost);
  $("btnCircuitOpen").addEventListener("click", simulateCircuitOpen);
  $("btnStop").addEventListener("click", simulateStop);
  $("btnReset").addEventListener("click", resetState);

  // 初回描画
  renderAll();

  // 初期ログ
  addLog("ゲートウェイ未初期化（デモモードで表示中）", "WARNING");
  addLog("GUI モック起動完了 – ボタンで操作をお試しください", "INFO");
}

// DOM 読み込み完了後に初期化
document.addEventListener("DOMContentLoaded", init);
