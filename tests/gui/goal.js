/**
 * Vibe PDCA システム – ゴール入力画面 (JavaScript)
 *
 * ゴール入力、ギャップ検出、コスト見積もりのデモ操作を提供します。
 */

"use strict";

// $, addLog は common.js で定義

// ============================================================
// 受入基準の追加
// ============================================================

function addCriteria() {
  var container = $("criteriaContainer");
  var item = document.createElement("div");
  item.className = "criteria-item";
  var input = document.createElement("input");
  input.type = "text";
  input.className = "form-input";
  input.placeholder = "受入基準を入力...";
  item.appendChild(input);
  container.appendChild(item);
  input.focus();
  addLog("受入基準フィールドを追加しました", "DEBUG");
}

// ============================================================
// ギャップ検出デモ
// ============================================================

var gapTemplates = [
  { icon: "⚠️", text: "データベーススキーマが未定義です", severity: "high" },
  { icon: "⚠️", text: "エラーハンドリングの方針が未記載です", severity: "medium" },
  { icon: "💡", text: "パフォーマンス要件（レスポンスタイム等）の記載を推奨", severity: "low" },
  { icon: "⚠️", text: "認証方式（JWT/OAuth等）の詳細が不足しています", severity: "high" },
  { icon: "💡", text: "ログ出力の方針を追加することを推奨", severity: "low" },
  { icon: "⚠️", text: "デプロイ環境（Docker/K8s等）が未指定です", severity: "medium" },
  { icon: "⚠️", text: "テストカバレッジの目標値が未設定です", severity: "medium" },
  { icon: "💡", text: "CI/CDパイプラインの要件追加を推奨", severity: "low" },
];

function detectGaps() {
  var container = $("gapResults");
  var list = document.createElement("ul");
  list.className = "gap-list";

  // ランダムに3-5個選択
  var shuffled = gapTemplates.slice().sort(function () {
    return 0.5 - Math.random();
  });
  var count = 3 + Math.floor(Math.random() * 3);
  for (var i = 0; i < Math.min(count, shuffled.length); i++) {
    var gap = shuffled[i];
    var li = document.createElement("li");
    li.className = "gap-item";
    li.innerHTML =
      '<span class="gap-icon">' + gap.icon + "</span>" +
      '<span class="gap-text">' + gap.text + "</span>" +
      '<span class="gap-severity ' + gap.severity + '">' +
      gap.severity.toUpperCase() + "</span>";
    list.appendChild(li);
  }

  container.innerHTML = "";
  container.appendChild(list);
  updateEstimates();
  addLog("ギャップ検出完了: " + count + "件の指摘", "INFO");
}

// ============================================================
// コスト見積もりデモ
// ============================================================

function updateEstimates() {
  var milestones = 2 + Math.floor(Math.random() * 4);
  var cycles = milestones * 2 + Math.floor(Math.random() * 5);
  var cost = (cycles * 2.3 + Math.random() * 5).toFixed(2);
  var hours = (cycles * 0.3 + Math.random() * 1).toFixed(1);

  $("estMilestones").textContent = milestones;
  $("estCycles").textContent = cycles;
  $("estCost").textContent = "$" + cost;
  $("estTime").textContent = hours + "h";

  addLog(
    "コスト見積もり: MS=" + milestones + ", Cycles=" + cycles +
    ", Cost=$" + cost + ", Time=" + hours + "h",
    "DEBUG"
  );
}

// ============================================================
// PDCA 開始デモ
// ============================================================

function startPDCA() {
  var goal = $("goalPurpose").value.trim();
  if (!goal) {
    addLog("ゴールを入力してください", "WARNING");
    return;
  }

  var criteriaInputs = document.querySelectorAll("#criteriaContainer .form-input");
  var criteria = [];
  for (var i = 0; i < criteriaInputs.length; i++) {
    var val = criteriaInputs[i].value.trim();
    if (val) criteria.push(val);
  }

  if (criteria.length === 0) {
    addLog("受入基準を1つ以上入力してください", "WARNING");
    return;
  }

  addLog("ゴール登録: " + goal, "INFO");
  addLog("受入基準: " + criteria.length + "件", "INFO");
  addLog("🚀 PDCAサイクルを開始します...", "INFO");

  // ダッシュボードへ遷移
  setTimeout(function () {
    addLog("ダッシュボードへ遷移します", "INFO");
    window.location.href = "index.html";
  }, 1500);
}

function saveDraft() {
  addLog("💾 下書きを保存しました", "INFO");
}

// ============================================================
// 初期化
// ============================================================

function init() {
  $("btnAddCriteria").addEventListener("click", addCriteria);
  $("btnDetectGaps").addEventListener("click", detectGaps);
  $("btnStartPDCA").addEventListener("click", startPDCA);
  $("btnSaveDraft").addEventListener("click", saveDraft);

  addLog("ゴール入力画面を起動しました", "INFO");
}

document.addEventListener("DOMContentLoaded", init);
