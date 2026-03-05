/**
 * Vibe PDCA システム – 共通ユーティリティ (JavaScript)
 *
 * 全画面で共有される DOM ヘルパー、ログ管理、ラジオグループ制御を提供します。
 * 各 HTML で page-specific スクリプトより先に読み込んでください。
 */

"use strict";

// ============================================================
// DOM ヘルパー
// ============================================================

/**
 * 指定 ID の要素を取得する。
 * @param {string} id
 * @returns {HTMLElement}
 */
function $(id) {
  return document.getElementById(id);
}

// ============================================================
// ログ管理
// ============================================================

/**
 * ログメッセージを追加する。
 * @param {string} message - ログ本文
 * @param {"INFO"|"WARNING"|"ERROR"|"DEBUG"} level - ログレベル
 */
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
// ラジオグループ制御 (キーボードナビゲーション対応)
// ============================================================

/**
 * 簡易デバウンス関数。連続呼び出しを抑制し、最後の呼び出しから
 * delay ミリ秒後に fn を実行する。
 * @param {Function} fn
 * @param {number} delay - ミリ秒
 * @returns {Function}
 */
function debounce(fn, delay) {
  var timer;
  return function () {
    clearTimeout(timer);
    timer = setTimeout(fn, delay);
  };
}

/**
 * カスタムラジオグループにクリック＆キーボード操作を設定する。
 *
 * @param {string} groupId - ラジオグループのコンテナ要素 ID
 * @param {string} [settingKey] - グローバル settings オブジェクトのキー (settings.js 用)
 * @param {Function} [onChange] - 値変更時のコールバック
 */
function setupRadioGroup(groupId, settingKey, onChange) {
  var group = $(groupId);
  if (!group) return;
  var options = group.querySelectorAll(".radio-option");

  // tabindex を付与してキーボードフォーカス可能にする
  for (var k = 0; k < options.length; k++) {
    if (!options[k].getAttribute("tabindex")) {
      options[k].setAttribute("tabindex", "0");
    }
    options[k].setAttribute("role", "radio");
    options[k].setAttribute(
      "aria-checked",
      options[k].classList.contains("selected") ? "true" : "false"
    );
  }
  group.setAttribute("role", "radiogroup");

  function selectOption(option) {
    for (var j = 0; j < options.length; j++) {
      options[j].classList.remove("selected");
      options[j].setAttribute("aria-checked", "false");
    }
    option.classList.add("selected");
    option.setAttribute("aria-checked", "true");

    var value = option.getAttribute("data-value");
    var radio = option.querySelector("input[type='radio']");
    if (radio) radio.checked = true;

    if (settingKey && typeof settings !== "undefined") {
      settings[settingKey] = value;
    }
    if (onChange) onChange(value);
    if (settingKey) {
      addLog(settingKey + " を " + value + " に変更", "INFO");
    }
  }

  for (var i = 0; i < options.length; i++) {
    (function (option) {
      option.addEventListener("click", function () {
        selectOption(option);
      });

      option.addEventListener("keydown", function (e) {
        var idx = Array.prototype.indexOf.call(options, option);
        var next;
        if (e.key === "ArrowRight" || e.key === "ArrowDown") {
          e.preventDefault();
          next = options[(idx + 1) % options.length];
          next.focus();
          selectOption(next);
        } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
          e.preventDefault();
          next = options[(idx - 1 + options.length) % options.length];
          next.focus();
          selectOption(next);
        } else if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          selectOption(option);
        }
      });
    })(options[i]);
  }
}
