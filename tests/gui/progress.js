/**
 * Vibe PDCA システム – 進捗画面 (JavaScript)
 *
 * マイルストーン進捗、5ペルソナレビュー、DoDチェックリスト、
 * サイクルタイムラインのデモ表示を提供します。
 */

"use strict";

// $, addLog は common.js で定義

// ============================================================
// 状態管理
// ============================================================

var state = {
  milestones: [
    {
      id: "ms-001",
      title: "認証モジュール",
      status: "completed",
      progress: 100,
      dodItems: [
        { text: "JWT認証の実装", done: true },
        { text: "ログイン/ログアウトAPI", done: true },
        { text: "ユニットテスト完了", done: true },
      ],
    },
    {
      id: "ms-002",
      title: "CRUD API実装",
      status: "in_progress",
      progress: 65,
      dodItems: [
        { text: "ユーザーCRUD API", done: true },
        { text: "バリデーション実装", done: true },
        { text: "エラーハンドリング", done: false },
        { text: "統合テスト完了", done: false },
      ],
    },
    {
      id: "ms-003",
      title: "デプロイ & ドキュメント",
      status: "pending",
      progress: 0,
      dodItems: [
        { text: "Docker構成", done: false },
        { text: "CI/CDパイプライン", done: false },
        { text: "APIドキュメント", done: false },
      ],
    },
  ],
  personas: [
    { name: "PM", icon: "📋", score: 85 },
    { name: "Architect", icon: "🏗️", score: 78 },
    { name: "Security", icon: "🛡️", score: 92 },
    { name: "QA", icon: "🧪", score: 70 },
    { name: "UX", icon: "🎨", score: 88 },
  ],
  timeline: [
    {
      phase: "PLAN",
      status: "completed",
      title: "サイクル #1 – PLAN",
      body: "Goal分解完了: 3 Milestones, 12 Tasks",
      time: "10:00",
    },
    {
      phase: "DO",
      status: "completed",
      title: "サイクル #1 – DO",
      body: "Task 4/4完了、PR #1-#4 マージ済み",
      time: "10:35",
    },
    {
      phase: "CHECK",
      status: "completed",
      title: "サイクル #1 – CHECK",
      body: "CI ✅ | 5ペルソナレビュー: 2 MINOR指摘",
      time: "10:42",
    },
    {
      phase: "ACT",
      status: "completed",
      title: "サイクル #1 – ACT",
      body: "ACCEPT – MS-001完了、MS-002へ進行",
      time: "10:45",
    },
    {
      phase: "PLAN",
      status: "completed",
      title: "サイクル #2 – PLAN",
      body: "MS-002タスク再計画: 4 Tasks",
      time: "10:48",
    },
    {
      phase: "DO",
      status: "in-progress",
      title: "サイクル #2 – DO",
      body: "Task 2/4実行中...",
      time: "11:05",
    },
  ],
  currentMilestoneIndex: 1,
};

// ============================================================
// マイルストーン描画
// ============================================================

function renderMilestones() {
  var container = $("milestoneList");
  container.innerHTML = "";

  for (var i = 0; i < state.milestones.length; i++) {
    var ms = state.milestones[i];
    var card = document.createElement("div");
    card.className = "milestone-card";

    // プログレスサークル (SVG)
    var progressDiv = document.createElement("div");
    progressDiv.className = "milestone-progress";
    var circumference = 2 * Math.PI * 24;
    var offset = circumference - (ms.progress / 100) * circumference;
    var color = ms.status === "completed" ? "#4CAF50" :
                ms.status === "in_progress" ? "#2196F3" : "#e0e0e0";
    progressDiv.innerHTML =
      '<svg width="60" height="60">' +
      '<circle cx="30" cy="30" r="24" fill="none" stroke="#e0e0e0" stroke-width="4"/>' +
      '<circle cx="30" cy="30" r="24" fill="none" stroke="' + color + '" stroke-width="4" ' +
      'stroke-dasharray="' + circumference + '" stroke-dashoffset="' + offset + '" stroke-linecap="round"/>' +
      "</svg>" +
      '<div class="milestone-progress-text">' + ms.progress + "%</div>";

    // 情報部分
    var info = document.createElement("div");
    info.className = "milestone-info";

    var statusBadge = ms.status === "completed" ? '<span class="badge badge-green">完了</span>' :
                      ms.status === "in_progress" ? '<span class="badge badge-blue">進行中</span>' :
                      '<span class="badge badge-grey">未着手</span>';

    info.innerHTML =
      '<div class="milestone-title">' + ms.id.toUpperCase() + ": " + ms.title + " " + statusBadge + "</div>" +
      '<div class="milestone-detail">DoD: ' + ms.dodItems.filter(function (d) { return d.done; }).length +
      "/" + ms.dodItems.length + " 完了</div>";

    card.appendChild(progressDiv);
    card.appendChild(info);
    container.appendChild(card);
  }
}

// ============================================================
// 5ペルソナレビュー描画
// ============================================================

function renderReviewSummary() {
  var container = $("reviewSummary");
  container.innerHTML = "";

  for (var i = 0; i < state.personas.length; i++) {
    var p = state.personas[i];
    var div = document.createElement("div");
    div.className = "review-persona";

    var scoreClass = p.score >= 80 ? "score-good" :
                     p.score >= 60 ? "score-warning" : "score-danger";

    div.innerHTML =
      '<div class="review-persona-icon">' + p.icon + "</div>" +
      '<div class="review-persona-name">' + p.name + "</div>" +
      '<div class="review-persona-score ' + scoreClass + '">' + p.score + "</div>";

    container.appendChild(div);
  }
}

// ============================================================
// DoD チェックリスト描画
// ============================================================

function renderDoDChecklist() {
  var container = $("dodChecklist");
  container.innerHTML = "";

  var ms = state.milestones[state.currentMilestoneIndex];
  for (var i = 0; i < ms.dodItems.length; i++) {
    var item = ms.dodItems[i];
    var li = document.createElement("li");
    li.className = "dod-item";
    li.setAttribute("data-index", i);

    var icon = item.done ? "✅" : "⬜";
    var iconClass = item.done ? "check" : "uncheck";
    li.innerHTML =
      '<span class="' + iconClass + '">' + icon + "</span>" +
      "<span>" + item.text + "</span>";

    container.appendChild(li);
  }
}

// ============================================================
// タイムライン描画
// ============================================================

function renderTimeline() {
  var container = $("timeline");
  container.innerHTML = "";

  for (var i = state.timeline.length - 1; i >= 0; i--) {
    var entry = state.timeline[i];
    var div = document.createElement("div");
    div.className = "timeline-item " + entry.status;

    div.innerHTML =
      '<div class="timeline-header">' +
      '<span class="timeline-title">' + entry.title + "</span>" +
      '<span class="timeline-time">' + entry.time + "</span>" +
      "</div>" +
      '<div class="timeline-body">' + entry.body + "</div>";

    container.appendChild(div);
  }
}

// ============================================================
// デモ操作
// ============================================================

var phaseOrder = ["PLAN", "DO", "CHECK", "ACT"];
var phaseIcons = { PLAN: "📋", DO: "🔧", CHECK: "🔍", ACT: "✅" };

function simulateCycle() {
  var lastEntry = state.timeline[state.timeline.length - 1];

  // 現在のフェーズを完了してから次へ
  if (lastEntry.status === "in-progress") {
    lastEntry.status = "completed";
    lastEntry.body = lastEntry.body.replace("実行中...", "完了");

    // 次のフェーズを決定
    var currentPhaseIdx = phaseOrder.indexOf(lastEntry.phase);
    var nextPhaseIdx = (currentPhaseIdx + 1) % phaseOrder.length;
    var cycleNum = lastEntry.title.match(/#(\d+)/);
    var num = cycleNum ? parseInt(cycleNum[1]) : 1;
    if (nextPhaseIdx === 0) num++;

    var nextPhase = phaseOrder[nextPhaseIdx];
    var bodies = {
      PLAN: "タスク再計画中...",
      DO: "タスク実行中...",
      CHECK: "CI & レビュー実行中...",
      ACT: "判定処理実行中...",
    };

    var now = new Date();
    state.timeline.push({
      phase: nextPhase,
      status: "in-progress",
      title: "サイクル #" + num + " – " + nextPhase,
      body: bodies[nextPhase],
      time: now.toLocaleTimeString("ja-JP", { hour: "2-digit", minute: "2-digit" }),
    });

    addLog(phaseIcons[nextPhase] + " サイクル #" + num + " " + nextPhase + " フェーズ開始", "INFO");
  } else {
    addLog("前のフェーズが未完了です", "WARNING");
  }

  // マイルストーン進捗を少し進める
  var ms = state.milestones[state.currentMilestoneIndex];
  if (ms.status !== "completed") {
    ms.progress = Math.min(ms.progress + 10, 100);
    if (ms.progress === 100) ms.status = "completed";
  }

  // ペルソナスコアを少し変動
  for (var i = 0; i < state.personas.length; i++) {
    state.personas[i].score = Math.max(50, Math.min(100,
      state.personas[i].score + Math.floor(Math.random() * 11 - 5)));
  }

  renderAll();
}

function completeMilestone() {
  var ms = state.milestones[state.currentMilestoneIndex];
  if (ms.status === "completed") {
    if (state.currentMilestoneIndex < state.milestones.length - 1) {
      state.currentMilestoneIndex++;
      state.milestones[state.currentMilestoneIndex].status = "in_progress";
      addLog("🏁 次のマイルストーンへ: " + state.milestones[state.currentMilestoneIndex].title, "INFO");
    } else {
      addLog("全マイルストーン完了！ 🎉", "INFO");
    }
  } else {
    ms.progress = 100;
    ms.status = "completed";
    for (var i = 0; i < ms.dodItems.length; i++) {
      ms.dodItems[i].done = true;
    }
    addLog("🏁 マイルストーン完了: " + ms.title, "INFO");
  }
  renderAll();
}

function toggleDod() {
  var ms = state.milestones[state.currentMilestoneIndex];
  // 未完了の最初のアイテムを完了にする
  for (var i = 0; i < ms.dodItems.length; i++) {
    if (!ms.dodItems[i].done) {
      ms.dodItems[i].done = true;
      addLog("✅ DoD達成: " + ms.dodItems[i].text, "INFO");
      // 進捗を更新
      var doneCount = ms.dodItems.filter(function (d) { return d.done; }).length;
      ms.progress = Math.round((doneCount / ms.dodItems.length) * 100);
      renderAll();
      return;
    }
  }
  addLog("全DoD項目が達成済みです", "DEBUG");
}

// ============================================================
// 全体描画
// ============================================================

function renderAll() {
  renderMilestones();
  renderReviewSummary();
  renderDoDChecklist();
  renderTimeline();
}

// ============================================================
// 初期化
// ============================================================

function init() {
  $("btnSimulateCycle").addEventListener("click", simulateCycle);
  $("btnCompleteMilestone").addEventListener("click", completeMilestone);
  $("btnToggleDod").addEventListener("click", toggleDod);

  renderAll();
  addLog("進捗画面を起動しました", "INFO");
}

document.addEventListener("DOMContentLoaded", init);
