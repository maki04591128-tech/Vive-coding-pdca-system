/**
 * Vibe PDCA システム – ペルソナ別レーダーチャート (JavaScript)
 *
 * §3.4 ペルソナ別レーダーチャートの機能をデモする:
 *   - 5ペルソナ (PM / Architect / Security / QA / UX) のスコア比較
 *   - SVGベースのレーダー (スパイダー) チャート
 *   - サイクル間の比較表示
 *   - レビュー指摘サマリー
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

var personas = [
  { id: "pm", name: "PM", icon: "📋", fullName: "プロジェクトマネージャー" },
  { id: "architect", name: "Architect", icon: "🏗️", fullName: "アーキテクト" },
  { id: "security", name: "Security", icon: "🛡️", fullName: "セキュリティ" },
  { id: "qa", name: "QA", icon: "🧪", fullName: "品質保証" },
  { id: "ux", name: "UX", icon: "🎨", fullName: "UXデザイナー" },
];

var cycleScores = {
  "latest": [0.85, 0.78, 0.92, 0.70, 0.88],
  "3": [0.85, 0.78, 0.92, 0.70, 0.88],
  "2": [0.75, 0.82, 0.85, 0.65, 0.80],
  "1": [0.60, 0.70, 0.75, 0.55, 0.72],
};

var findings = [
  { persona: "pm", severity: "MINOR", text: "タスク粒度が大きすぎる (2件のタスクを分割推奨)", cycle: 3 },
  { persona: "architect", severity: "MAJOR", text: "エラーハンドリングの一貫性が不足", cycle: 3 },
  { persona: "security", severity: "MINOR", text: "入力バリデーションにサニタイズ処理を追加", cycle: 3 },
  { persona: "qa", severity: "MAJOR", text: "エッジケースのテストカバレッジ不足 (60%未満)", cycle: 3 },
  { persona: "ux", severity: "MINOR", text: "エラーメッセージのユーザーフレンドリー化を推奨", cycle: 3 },
  { persona: "security", severity: "BLOCKER", text: "SQLインジェクション脆弱性の修正が必要", cycle: 2 },
  { persona: "qa", severity: "MAJOR", text: "テストデータのハードコーディングを排除", cycle: 2 },
  { persona: "architect", severity: "MINOR", text: "モジュール間の依存関係を明示化", cycle: 1 },
];

var state = {
  selectedCycle: "latest",
  showComparison: false,
};

// ============================================================
// レーダーチャート描画
// ============================================================

var centerX = 200;
var centerY = 200;
var maxRadius = 150;

function polarToCartesian(angle, radius) {
  var rad = (angle - 90) * Math.PI / 180;
  return {
    x: centerX + radius * Math.cos(rad),
    y: centerY + radius * Math.sin(rad),
  };
}

function renderRadar() {
  var svg = $("radarChart");
  svg.innerHTML = "";
  var n = personas.length;
  var angleStep = 360 / n;

  // グリッドリング (5段階)
  for (var ring = 1; ring <= 5; ring++) {
    var r = (ring / 5) * maxRadius;
    var ringPoints = [];
    for (var ri = 0; ri < n; ri++) {
      var p = polarToCartesian(ri * angleStep, r);
      ringPoints.push(p.x + "," + p.y);
    }
    var polygon = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
    polygon.setAttribute("points", ringPoints.join(" "));
    polygon.setAttribute("fill", "none");
    polygon.setAttribute("stroke", "#e0e0e0");
    polygon.setAttribute("stroke-width", "1");
    svg.appendChild(polygon);
  }

  // 軸線 + ラベル
  for (var ai = 0; ai < n; ai++) {
    var angle = ai * angleStep;
    var endPoint = polarToCartesian(angle, maxRadius);
    var labelPoint = polarToCartesian(angle, maxRadius + 25);

    var line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", centerX);
    line.setAttribute("y1", centerY);
    line.setAttribute("x2", endPoint.x);
    line.setAttribute("y2", endPoint.y);
    line.setAttribute("stroke", "#e0e0e0");
    line.setAttribute("stroke-width", "1");
    svg.appendChild(line);

    var label = document.createElementNS("http://www.w3.org/2000/svg", "text");
    label.setAttribute("x", labelPoint.x);
    label.setAttribute("y", labelPoint.y + 4);
    label.setAttribute("text-anchor", "middle");
    label.setAttribute("font-size", "12");
    label.setAttribute("font-weight", "600");
    label.setAttribute("fill", "#333");
    label.textContent = personas[ai].icon + " " + personas[ai].name;
    svg.appendChild(label);
  }

  // 比較データ (前サイクル)
  if (state.showComparison) {
    var prevCycle = getPreviousCycle(state.selectedCycle);
    if (prevCycle && cycleScores[prevCycle]) {
      var prevScores = cycleScores[prevCycle];
      drawDataPolygon(svg, prevScores, "rgba(158,158,158,0.3)", "#9E9E9E", n, angleStep);
    }
  }

  // 現在のスコア
  var currentScores = cycleScores[state.selectedCycle] || cycleScores["latest"];
  drawDataPolygon(svg, currentScores, "rgba(25,118,210,0.2)", "#1976D2", n, angleStep);

  // レジェンド
  renderRadarLegend();
}

function drawDataPolygon(svg, scores, fillColor, strokeColor, n, angleStep) {
  var dataPoints = [];
  for (var i = 0; i < n; i++) {
    var angle = i * angleStep;
    var r = scores[i] * maxRadius;
    var p = polarToCartesian(angle, r);
    dataPoints.push(p.x + "," + p.y);

    // データポイント
    var circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("cx", p.x);
    circle.setAttribute("cy", p.y);
    circle.setAttribute("r", "5");
    circle.setAttribute("fill", strokeColor);
    svg.appendChild(circle);

    // スコアラベル
    var scoreLabel = document.createElementNS("http://www.w3.org/2000/svg", "text");
    var labelPos = polarToCartesian(angle, r + 15);
    scoreLabel.setAttribute("x", labelPos.x);
    scoreLabel.setAttribute("y", labelPos.y + 4);
    scoreLabel.setAttribute("text-anchor", "middle");
    scoreLabel.setAttribute("font-size", "11");
    scoreLabel.setAttribute("font-weight", "bold");
    scoreLabel.setAttribute("fill", strokeColor);
    scoreLabel.textContent = Math.round(scores[i] * 100);
    svg.appendChild(scoreLabel);
  }

  var polygon = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
  polygon.setAttribute("points", dataPoints.join(" "));
  polygon.setAttribute("fill", fillColor);
  polygon.setAttribute("stroke", strokeColor);
  polygon.setAttribute("stroke-width", "2");
  svg.appendChild(polygon);
}

function getPreviousCycle(current) {
  var cycleMap = { "latest": "2", "3": "2", "2": "1", "1": null };
  return cycleMap[current] || null;
}

function renderRadarLegend() {
  var container = $("radarLegend");
  container.innerHTML = "";

  var items = [{ color: "#1976D2", label: "サイクル #" + (state.selectedCycle === "latest" ? "3 (最新)" : state.selectedCycle) }];
  if (state.showComparison) {
    var prev = getPreviousCycle(state.selectedCycle);
    if (prev) {
      items.push({ color: "#9E9E9E", label: "サイクル #" + prev + " (前回)" });
    }
  }

  for (var i = 0; i < items.length; i++) {
    var span = document.createElement("span");
    span.className = "legend-item";
    span.innerHTML = '<span class="legend-color" style="background:' + items[i].color + '"></span>' + items[i].label;
    container.appendChild(span);
  }
}

// ============================================================
// ペルソナ詳細
// ============================================================

function renderPersonaDetails() {
  var container = $("personaDetails");
  container.innerHTML = "";

  var scores = cycleScores[state.selectedCycle] || cycleScores["latest"];
  var prevCycle = getPreviousCycle(state.selectedCycle);
  var prevScores = prevCycle && cycleScores[prevCycle] ? cycleScores[prevCycle] : null;

  for (var i = 0; i < personas.length; i++) {
    var p = personas[i];
    var score = Math.round(scores[i] * 100);
    var scoreClass = score >= 80 ? "score-good" : score >= 60 ? "score-warning" : "score-danger";

    var changeHtml = "";
    if (prevScores) {
      var prevScore = Math.round(prevScores[i] * 100);
      var diff = score - prevScore;
      var arrow = diff > 0 ? "↑" : diff < 0 ? "↓" : "→";
      var diffClass = diff > 0 ? "score-good" : diff < 0 ? "score-danger" : "";
      changeHtml = '<span class="persona-change ' + diffClass + '">' + arrow + Math.abs(diff) + '</span>';
    }

    // ペルソナ別の指摘数
    var personaFindings = findings.filter(function (f) {
      return f.persona === p.id;
    });
    var blockerCount = personaFindings.filter(function (f) { return f.severity === "BLOCKER"; }).length;
    var majorCount = personaFindings.filter(function (f) { return f.severity === "MAJOR"; }).length;
    var minorCount = personaFindings.filter(function (f) { return f.severity === "MINOR"; }).length;

    var div = document.createElement("div");
    div.className = "persona-detail-item";
    div.innerHTML =
      '<div class="persona-detail-header">' +
      '  <span class="persona-detail-icon">' + p.icon + '</span>' +
      '  <span class="persona-detail-name">' + p.fullName + '</span>' +
      '  <span class="persona-detail-score ' + scoreClass + '">' + score + '</span>' +
      changeHtml +
      '</div>' +
      '<div class="persona-detail-bar-container">' +
      '  <div class="persona-detail-bar" style="width:' + score + '%;background:' + (score >= 80 ? "#4CAF50" : score >= 60 ? "#FF9800" : "#F44336") + '"></div>' +
      '</div>' +
      '<div class="persona-detail-findings">' +
      (blockerCount > 0 ? '<span class="badge gap-severity high">BLOCKER: ' + blockerCount + '</span> ' : '') +
      (majorCount > 0 ? '<span class="badge gap-severity medium">MAJOR: ' + majorCount + '</span> ' : '') +
      (minorCount > 0 ? '<span class="badge gap-severity low">MINOR: ' + minorCount + '</span>' : '') +
      (blockerCount + majorCount + minorCount === 0 ? '<span class="badge badge-green">指摘なし</span>' : '') +
      '</div>';
    container.appendChild(div);
  }
}

// ============================================================
// 指摘サマリー
// ============================================================

function renderFindings() {
  var container = $("findingsSummary");
  container.innerHTML = "";

  // サイクルでフィルタ
  var cycleNum = state.selectedCycle === "latest" ? 3 : parseInt(state.selectedCycle);
  var filtered = findings.filter(function (f) {
    return f.cycle === cycleNum;
  });

  if (filtered.length === 0) {
    container.innerHTML = '<div class="placeholder-text">このサイクルの指摘はありません</div>';
    return;
  }

  for (var i = 0; i < filtered.length; i++) {
    var f = filtered[i];
    var persona = personas.filter(function (p) { return p.id === f.persona; })[0];
    var severityClass = f.severity === "BLOCKER" ? "high" : f.severity === "MAJOR" ? "medium" : "low";

    var div = document.createElement("div");
    div.className = "finding-item";
    div.innerHTML =
      '<span class="finding-persona">' + (persona ? persona.icon : "❓") + '</span>' +
      '<span class="gap-severity ' + severityClass + '">' + f.severity + '</span>' +
      '<span class="finding-text">' + f.text + '</span>';
    container.appendChild(div);
  }
}

// ============================================================
// 全体描画
// ============================================================

function renderAll() {
  renderRadar();
  renderPersonaDetails();
  renderFindings();
}

// ============================================================
// デモ操作
// ============================================================

function randomizeScores() {
  var key = state.selectedCycle;
  var scores = cycleScores[key] || cycleScores["latest"];
  for (var i = 0; i < scores.length; i++) {
    scores[i] = Math.max(0.3, Math.min(1.0, scores[i] + (Math.random() * 0.2 - 0.1)));
  }
  renderAll();
  addLog("🎲 スコアをランダム変更しました", "INFO");
}

function addFinding() {
  var cycleNum = state.selectedCycle === "latest" ? 3 : parseInt(state.selectedCycle);
  var randomPersona = personas[Math.floor(Math.random() * personas.length)];
  var severities = ["BLOCKER", "MAJOR", "MINOR"];
  var severity = severities[Math.floor(Math.random() * severities.length)];
  var texts = [
    "コード重複の排除が必要",
    "例外処理のテストケース追加を推奨",
    "ドキュメントの更新が必要",
    "パフォーマンス改善の余地あり",
    "アクセシビリティ対応が不足",
  ];
  var text = texts[Math.floor(Math.random() * texts.length)];

  findings.push({
    persona: randomPersona.id,
    severity: severity,
    text: text,
    cycle: cycleNum,
  });

  renderAll();
  addLog("📝 指摘追加: [" + randomPersona.name + "] " + severity + " - " + text, "INFO");
}

function resetRadar() {
  cycleScores["latest"] = [0.85, 0.78, 0.92, 0.70, 0.88];
  cycleScores["3"] = [0.85, 0.78, 0.92, 0.70, 0.88];
  cycleScores["2"] = [0.75, 0.82, 0.85, 0.65, 0.80];
  cycleScores["1"] = [0.60, 0.70, 0.75, 0.55, 0.72];
  state.selectedCycle = "latest";
  state.showComparison = false;
  $("cycleSelect").value = "latest";
  $("compareCheck").checked = false;
  renderAll();
  addLog("🔄 レーダーチャートをリセットしました", "INFO");
}

// ============================================================
// 初期化
// ============================================================

function init() {
  $("cycleSelect").addEventListener("change", function () {
    state.selectedCycle = this.value;
    renderAll();
    addLog("サイクル変更: " + state.selectedCycle, "DEBUG");
  });

  $("compareCheck").addEventListener("change", function () {
    state.showComparison = this.checked;
    renderAll();
    addLog("比較表示: " + (state.showComparison ? "ON" : "OFF"), "DEBUG");
  });

  $("btnRandomize").addEventListener("click", randomizeScores);
  $("btnAddFinding").addEventListener("click", addFinding);
  $("btnResetRadar").addEventListener("click", resetRadar);

  renderAll();
  addLog("ペルソナレーダーチャートを起動しました", "INFO");
}

document.addEventListener("DOMContentLoaded", init);
