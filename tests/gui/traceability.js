/**
 * Vibe PDCA システム – トレーサビリティマップ (JavaScript)
 *
 * §3.3 トレーサビリティマップの機能をデモする:
 *   - Goal → Milestone → Task → PR → Decision の関係グラフ
 *   - SVGベースのノード・エッジ描画
 *   - ノードクリックで詳細表示
 *   - リレーション一覧テーブル
 */

"use strict";

// $, addLog, debounce は common.js で定義

// ============================================================
// データモデル
// ============================================================

var nodes = [
  { id: "goal-1", type: "goal", label: "REST APIサーバー構築", x: 400, y: 40 },
  { id: "ms-001", type: "milestone", label: "認証モジュール", x: 200, y: 130 },
  { id: "ms-002", type: "milestone", label: "CRUD API実装", x: 400, y: 130 },
  { id: "ms-003", type: "milestone", label: "デプロイ & ドキュメント", x: 600, y: 130 },
  { id: "task-1", type: "task", label: "JWT認証実装", x: 120, y: 230 },
  { id: "task-2", type: "task", label: "ログインAPI", x: 280, y: 230 },
  { id: "task-3", type: "task", label: "ユーザーCRUD", x: 400, y: 230 },
  { id: "task-4", type: "task", label: "バリデーション", x: 520, y: 230 },
  { id: "task-5", type: "task", label: "Docker構成", x: 620, y: 230 },
  { id: "pr-1", type: "pr", label: "PR #1: JWT auth", x: 120, y: 330 },
  { id: "pr-2", type: "pr", label: "PR #2: Login API", x: 280, y: 330 },
  { id: "pr-3", type: "pr", label: "PR #3: User CRUD", x: 400, y: 330 },
  { id: "pr-4", type: "pr", label: "PR #4: Validation", x: 520, y: 330 },
  { id: "dec-1", type: "decision", label: "ACT: ACCEPT (C#1)", x: 200, y: 420 },
  { id: "dec-2", type: "decision", label: "ACT: 進行中 (C#2)", x: 460, y: 420 },
];

var edges = [
  { source: "goal-1", target: "ms-001" },
  { source: "goal-1", target: "ms-002" },
  { source: "goal-1", target: "ms-003" },
  { source: "ms-001", target: "task-1" },
  { source: "ms-001", target: "task-2" },
  { source: "ms-002", target: "task-3" },
  { source: "ms-002", target: "task-4" },
  { source: "ms-003", target: "task-5" },
  { source: "task-1", target: "pr-1" },
  { source: "task-2", target: "pr-2" },
  { source: "task-3", target: "pr-3" },
  { source: "task-4", target: "pr-4" },
  { source: "pr-1", target: "dec-1" },
  { source: "pr-2", target: "dec-1" },
  { source: "pr-3", target: "dec-2" },
  { source: "pr-4", target: "dec-2" },
];

var nodeDetails = {
  "goal-1": { title: "🎯 ゴール: REST APIサーバー構築", desc: "ユーザー認証・CRUD操作・テストを完備したREST APIサーバーを構築する", status: "進行中" },
  "ms-001": { title: "🏁 MS-001: 認証モジュール", desc: "JWT認証、ログイン/ログアウトAPI、ユニットテスト", status: "完了" },
  "ms-002": { title: "🏁 MS-002: CRUD API実装", desc: "ユーザーCRUD、バリデーション、エラーハンドリング", status: "進行中" },
  "ms-003": { title: "🏁 MS-003: デプロイ & ドキュメント", desc: "Docker構成、CI/CD、APIドキュメント", status: "未着手" },
  "task-1": { title: "📝 Task: JWT認証実装", desc: "JSONWebTokenによる認証ミドルウェア実装", status: "完了" },
  "task-2": { title: "📝 Task: ログインAPI", desc: "POST /api/auth/login エンドポイント実装", status: "完了" },
  "task-3": { title: "📝 Task: ユーザーCRUD", desc: "GET/POST/PUT/DELETE /api/users 実装", status: "完了" },
  "task-4": { title: "📝 Task: バリデーション", desc: "リクエストバリデーションミドルウェア", status: "進行中" },
  "task-5": { title: "📝 Task: Docker構成", desc: "Dockerfile + docker-compose.yml 作成", status: "未着手" },
  "pr-1": { title: "🔀 PR #1: JWT auth", desc: "JWT認証の実装 – マージ済み", status: "マージ済" },
  "pr-2": { title: "🔀 PR #2: Login API", desc: "ログインAPI実装 – マージ済み", status: "マージ済" },
  "pr-3": { title: "🔀 PR #3: User CRUD", desc: "ユーザーCRUD API – マージ済み", status: "マージ済" },
  "pr-4": { title: "🔀 PR #4: Validation", desc: "バリデーション – レビュー中", status: "レビュー中" },
  "dec-1": { title: "⚖️ ACT: ACCEPT (サイクル #1)", desc: "5ペルソナレビュー合格、MS-001完了", status: "確定" },
  "dec-2": { title: "⚖️ ACT: 進行中 (サイクル #2)", desc: "CHECK フェーズ実行中", status: "進行中" },
};

// ============================================================
// SVG 描画
// ============================================================

var typeColors = {
  goal: "#1976D2",
  milestone: "#4CAF50",
  task: "#FF9800",
  pr: "#9C27B0",
  decision: "#F44336",
};

var typeIcons = {
  goal: "🎯",
  milestone: "🏁",
  task: "📝",
  pr: "🔀",
  decision: "⚖️",
};

function findNode(id) {
  for (var i = 0; i < nodes.length; i++) {
    if (nodes[i].id === id) return nodes[i];
  }
  return null;
}

function renderGraph() {
  var svg = $("traceSvg");
  svg.innerHTML = "";

  // エッジ描画
  for (var i = 0; i < edges.length; i++) {
    var src = findNode(edges[i].source);
    var tgt = findNode(edges[i].target);
    if (!src || !tgt) continue;

    var line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", src.x);
    line.setAttribute("y1", src.y + 18);
    line.setAttribute("x2", tgt.x);
    line.setAttribute("y2", tgt.y - 8);
    line.setAttribute("stroke", "#BDBDBD");
    line.setAttribute("stroke-width", "2");
    svg.appendChild(line);
  }

  // ノード描画
  for (var j = 0; j < nodes.length; j++) {
    var n = nodes[j];
    var color = typeColors[n.type] || "#9E9E9E";

    var g = document.createElementNS("http://www.w3.org/2000/svg", "g");
    g.setAttribute("class", "trace-node");
    g.setAttribute("data-id", n.id);
    g.style.cursor = "pointer";

    // 背景矩形
    var rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    var labelWidth = Math.max(n.label.length * 7 + 30, 80);
    rect.setAttribute("x", n.x - labelWidth / 2);
    rect.setAttribute("y", n.y - 14);
    rect.setAttribute("width", labelWidth);
    rect.setAttribute("height", 28);
    rect.setAttribute("rx", "14");
    rect.setAttribute("fill", color);
    rect.setAttribute("opacity", "0.15");
    rect.setAttribute("stroke", color);
    rect.setAttribute("stroke-width", "2");

    // テキスト
    var text = document.createElementNS("http://www.w3.org/2000/svg", "text");
    text.setAttribute("x", n.x);
    text.setAttribute("y", n.y + 5);
    text.setAttribute("text-anchor", "middle");
    text.setAttribute("font-size", "12");
    text.setAttribute("font-weight", "600");
    text.setAttribute("fill", color);
    text.textContent = (typeIcons[n.type] || "") + " " + n.label;

    g.appendChild(rect);
    g.appendChild(text);
    svg.appendChild(g);

    // クリックイベント
    (function (nodeId) {
      g.addEventListener("click", function () {
        showNodeDetail(nodeId);
      });
    })(n.id);
  }
}

// ============================================================
// 詳細表示
// ============================================================

function showNodeDetail(nodeId) {
  var detail = nodeDetails[nodeId];
  if (!detail) return;

  var statusBadge = detail.status === "完了" || detail.status === "マージ済" || detail.status === "確定"
    ? "badge-green"
    : detail.status === "進行中" || detail.status === "レビュー中"
    ? "badge-blue"
    : "badge-grey";

  $("traceDetail").innerHTML =
    '<div class="trace-detail-content">' +
    '  <h3>' + detail.title + '</h3>' +
    '  <p>' + detail.desc + '</p>' +
    '  <span class="badge ' + statusBadge + '">' + detail.status + '</span>' +
    '</div>';

  addLog("ノード選択: " + nodeId, "DEBUG");
}

// ============================================================
// リレーションテーブル
// ============================================================

function renderTable() {
  var tbody = $("traceTableBody");
  tbody.innerHTML = "";

  for (var i = 0; i < edges.length; i++) {
    var src = findNode(edges[i].source);
    var tgt = findNode(edges[i].target);
    if (!src || !tgt) continue;

    var tr = document.createElement("tr");
    tr.innerHTML =
      '<td><span class="badge badge-' + getTypeBadge(src.type) + '">' + (typeIcons[src.type] || "") + " " + src.label + '</span></td>' +
      '<td>→</td>' +
      '<td><span class="badge badge-' + getTypeBadge(tgt.type) + '">' + (typeIcons[tgt.type] || "") + " " + tgt.label + '</span></td>' +
      '<td>' + src.type + ' → ' + tgt.type + '</td>';
    tbody.appendChild(tr);
  }
}

function getTypeBadge(type) {
  var map = { goal: "blue", milestone: "green", task: "orange", pr: "purple", decision: "red" };
  return map[type] || "grey";
}

// ============================================================
// デモ操作
// ============================================================

function addRelation() {
  var newTask = {
    id: "task-" + (nodes.length + 1),
    type: "task",
    label: "新タスク #" + (nodes.length - 14),
    x: 200 + Math.random() * 400,
    y: 230 + Math.random() * 40,
  };
  nodes.push(newTask);
  edges.push({ source: "ms-002", target: newTask.id });
  renderGraph();
  renderTable();
  addLog("🔗 リレーション追加: ms-002 → " + newTask.id, "INFO");
}

function resetGraph() {
  // 追加されたノード・エッジを削除（初期状態に戻す）
  while (nodes.length > 15) nodes.pop();
  while (edges.length > 16) edges.pop();
  renderGraph();
  renderTable();
  $("traceDetail").innerHTML = '<span class="placeholder-text">ノードをクリックして詳細を表示</span>';
  addLog("🔄 グラフをリセットしました", "INFO");
}

// ============================================================
// 初期化
// ============================================================

function init() {
  $("btnAddRelation").addEventListener("click", addRelation);
  $("btnResetGraph").addEventListener("click", resetGraph);

  // ウィンドウリサイズ時にグラフを再描画 (デバウンス)
  window.addEventListener("resize", debounce(function () { renderGraph(); }, 150));

  renderGraph();
  renderTable();
  addLog("トレーサビリティマップを起動しました", "INFO");
}

document.addEventListener("DOMContentLoaded", init);
