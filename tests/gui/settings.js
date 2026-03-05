/**
 * Vibe PDCA システム – 設定画面 (JavaScript)
 *
 * 実行モード、コスト管理、LLMプロバイダ、ガバナンスの
 * 設定操作デモを提供します。
 */

"use strict";

// $, addLog, setupRadioGroup は common.js で定義

// ============================================================
// 状態管理
// ============================================================

var defaultSettings = {
  mode: "full",
  costLimit: 30,
  callLimit: 500,
  warnThreshold: 70,
  provider: "cloud",
  approvalChannel: "#vibe-pdca-approval",
  approvalTimeout: 15,
  failureLimit: 3,
  stallLimit: 6,
};

var settings = JSON.parse(JSON.stringify(defaultSettings));

// ============================================================
// モード説明
// ============================================================

var modeDescriptions = {
  manual: {
    label: "🖐️ 手動モード",
    desc: "各フェーズ（PLAN/DO/CHECK/ACT）ごとに手動承認が必要です。学習・検証時に推奨。",
  },
  semi: {
    label: "⚡ 半自動モード",
    desc: "DO→CHECK は自動実行。PLAN・ACTフェーズで人間の確認が入ります。通常運用に推奨。",
  },
  full: {
    label: "🤖 全自動モード",
    desc: "PLAN→DO→CHECK→ACTを自動で繰り返します。A-ops操作のみDiscord承認が必要です。",
  },
};

// setupRadioGroup は common.js で定義

// ============================================================
// レンジスライダー制御
// ============================================================

function setupRange(inputId, displayId, settingKey, format) {
  var input = $(inputId);
  var display = $(displayId);

  input.addEventListener("input", function () {
    var value = parseInt(input.value);
    settings[settingKey] = value;
    display.textContent = format(value);
  });

  input.addEventListener("change", function () {
    addLog(settingKey + " を " + settings[settingKey] + " に変更", "INFO");
  });
}

// ============================================================
// プロバイダ設定描画
// ============================================================

var providerConfigs = {
  cloud: [
    { name: "OpenAI GPT-5.1", model: "gpt-5.1", status: "active" },
    { name: "Anthropic Opus 4", model: "claude-opus-4", status: "active" },
    { name: "Google Gemini", model: "gemini-2.5-pro", status: "standby" },
  ],
  local: [
    { name: "Ollama PM", model: "qwen3:72b", status: "active" },
    { name: "Ollama Programmer", model: "codestral:22b", status: "active" },
    { name: "Ollama General", model: "llama3.3:70b", status: "standby" },
  ],
  hybrid: [
    { name: "Primary: Cloud", model: "gpt-5.1 / claude-opus-4", status: "active" },
    { name: "Fallback: Local", model: "qwen3:72b / codestral:22b", status: "standby" },
    { name: "Cost Overflow: Local", model: "ollama auto-switch", status: "standby" },
  ],
};

function renderProviderConfig() {
  var container = $("providerConfig");
  container.innerHTML = "";

  var configs = providerConfigs[settings.provider] || [];
  for (var i = 0; i < configs.length; i++) {
    var config = configs[i];
    var div = document.createElement("div");
    div.className = "provider-config-item";

    var badgeClass = config.status === "active" ? "badge-green" :
                     config.status === "standby" ? "badge-orange" : "badge-grey";

    div.innerHTML =
      '<div class="provider-config-name">' + config.name +
      ' <span class="badge ' + badgeClass + '">' + config.status + "</span></div>" +
      '<div class="provider-config-detail">Model: ' + config.model + "</div>";

    container.appendChild(div);
  }
}

// ============================================================
// モード説明更新
// ============================================================

function updateModeDescription(mode) {
  var desc = modeDescriptions[mode];
  var container = $("modeDescription");
  container.innerHTML =
    "<div>" +
    '<div class="setting-label">' + desc.label + "</div>" +
    '<div class="setting-desc">' + desc.desc + "</div>" +
    "</div>";
}

// ============================================================
// 設定保存/リセット
// ============================================================

function saveSettings() {
  addLog("💾 設定を保存しました", "INFO");
  addLog(
    "モード=" + settings.mode +
    ", コスト上限=$" + settings.costLimit +
    ", API上限=" + settings.callLimit +
    ", プロバイダ=" + settings.provider,
    "DEBUG"
  );
}

function resetSettings() {
  settings = JSON.parse(JSON.stringify(defaultSettings));

  // UI をリセット
  $("costLimit").value = settings.costLimit;
  $("costLimitValue").textContent = "$" + settings.costLimit;
  $("callLimit").value = settings.callLimit;
  $("callLimitValue").textContent = settings.callLimit;
  $("warnThreshold").value = settings.warnThreshold;
  $("warnThresholdValue").textContent = settings.warnThreshold + "%";
  $("approvalTimeout").value = settings.approvalTimeout;
  $("approvalTimeoutValue").textContent = settings.approvalTimeout + "分";
  $("failureLimit").value = settings.failureLimit;
  $("failureLimitValue").textContent = settings.failureLimit + "回";
  $("stallLimit").value = settings.stallLimit;
  $("stallLimitValue").textContent = settings.stallLimit + "時間";
  $("approvalChannel").value = settings.approvalChannel;

  // ラジオグループリセット
  resetRadioGroup("modeSelector", settings.mode);
  resetRadioGroup("providerSelector", settings.provider);

  updateModeDescription(settings.mode);
  renderProviderConfig();
  addLog("🔄 設定をデフォルトに戻しました", "INFO");
}

function resetRadioGroup(groupId, value) {
  var options = $(groupId).querySelectorAll(".radio-option");
  for (var i = 0; i < options.length; i++) {
    options[i].classList.remove("selected");
    if (options[i].getAttribute("data-value") === value) {
      options[i].classList.add("selected");
      var radio = options[i].querySelector("input[type='radio']");
      if (radio) radio.checked = true;
    }
  }
}

// ============================================================
// 初期化
// ============================================================

function init() {
  // ラジオグループ
  setupRadioGroup("modeSelector", "mode", function (value) {
    updateModeDescription(value);
  });
  setupRadioGroup("providerSelector", "provider", function () {
    renderProviderConfig();
  });

  // レンジスライダー
  setupRange("costLimit", "costLimitValue", "costLimit", function (v) {
    return "$" + v;
  });
  setupRange("callLimit", "callLimitValue", "callLimit", function (v) {
    return v;
  });
  setupRange("warnThreshold", "warnThresholdValue", "warnThreshold", function (v) {
    return v + "%";
  });
  setupRange("approvalTimeout", "approvalTimeoutValue", "approvalTimeout", function (v) {
    return v + "分";
  });
  setupRange("failureLimit", "failureLimitValue", "failureLimit", function (v) {
    return v + "回";
  });
  setupRange("stallLimit", "stallLimitValue", "stallLimit", function (v) {
    return v + "時間";
  });

  // ボタン
  $("btnSaveSettings").addEventListener("click", saveSettings);
  $("btnResetSettings").addEventListener("click", resetSettings);

  // 初期描画
  renderProviderConfig();
  addLog("設定画面を起動しました", "INFO");
}

document.addEventListener("DOMContentLoaded", init);
