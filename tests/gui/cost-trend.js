/**
 * Vibe PDCA システム – コスト推移グラフ (JavaScript)
 *
 * §3.2 コスト推移グラフの機能をデモする:
 *   - 日次/サイクル別/モデル別の表示切替
 *   - SVGベースのラインチャート
 *   - コストサマリーカード
 *   - モデル別内訳表示
 */

"use strict";

// $, addLog, debounce は common.js で定義

// ============================================================
// 状態管理
// ============================================================

var state = {
  viewMode: "daily",
  dailyData: [],
  cycleData: [],
  modelData: {
    "gpt-5.1": [],
    "claude-opus-4": [],
    "qwen3:72b": [],
    "codestral:22b": [],
  },
  totalCost: 0,
  totalCalls: 0,
};

var chartColors = {
  daily: "#1976D2",
  "gpt-5.1": "#4CAF50",
  "claude-opus-4": "#FF9800",
  "qwen3:72b": "#9C27B0",
  "codestral:22b": "#F44336",
};

// ============================================================
// データ生成
// ============================================================

function generateWeekData() {
  state.dailyData = [];
  state.cycleData = [];
  state.totalCost = 0;
  state.totalCalls = 0;

  // モデルデータリセット
  var modelKeys = Object.keys(state.modelData);
  for (var m = 0; m < modelKeys.length; m++) {
    state.modelData[modelKeys[m]] = [];
  }

  var now = new Date();
  for (var d = 6; d >= 0; d--) {
    var date = new Date(now);
    date.setDate(date.getDate() - d);
    var dateStr = (date.getMonth() + 1) + "/" + date.getDate();

    var dayCost = 5 + Math.random() * 20;
    var dayCalls = Math.floor(50 + Math.random() * 200);
    state.totalCost += dayCost;
    state.totalCalls += dayCalls;

    state.dailyData.push({ label: dateStr, cost: dayCost, calls: dayCalls });

    // モデル別内訳
    var remaining = dayCost;
    for (var mi = 0; mi < modelKeys.length; mi++) {
      var share = mi < modelKeys.length - 1 ? remaining * (0.2 + Math.random() * 0.3) : remaining;
      remaining -= share;
      state.modelData[modelKeys[mi]].push({ label: dateStr, cost: Math.max(share, 0) });
    }
  }

  // サイクル別データ
  for (var c = 1; c <= 5; c++) {
    state.cycleData.push({
      label: "Cycle #" + c,
      cost: 8 + Math.random() * 15,
      calls: Math.floor(40 + Math.random() * 100),
    });
  }
}

function addDataPoint() {
  var now = new Date();
  var dateStr = (now.getMonth() + 1) + "/" + now.getDate() + " " + now.toLocaleTimeString("ja-JP", { hour: "2-digit", minute: "2-digit" });
  var cost = 2 + Math.random() * 5;
  var calls = Math.floor(10 + Math.random() * 30);

  state.dailyData.push({ label: dateStr, cost: cost, calls: calls });
  state.totalCost += cost;
  state.totalCalls += calls;

  // モデル別に分配
  var modelKeys = Object.keys(state.modelData);
  var remaining = cost;
  for (var i = 0; i < modelKeys.length; i++) {
    var share = i < modelKeys.length - 1 ? remaining * (0.2 + Math.random() * 0.3) : remaining;
    remaining -= share;
    state.modelData[modelKeys[i]].push({ label: dateStr, cost: Math.max(share, 0) });
  }

  renderAll();
  addLog("📊 データポイント追加: $" + cost.toFixed(2) + " (" + calls + " calls)", "INFO");
}

// ============================================================
// サマリー描画
// ============================================================

function renderSummary() {
  var todayCost = state.dailyData.length > 0 ? state.dailyData[state.dailyData.length - 1].cost : 0;
  var weekCost = 0;
  for (var i = 0; i < state.dailyData.length; i++) {
    weekCost += state.dailyData[i].cost;
  }
  var avgCost = state.totalCalls > 0 ? state.totalCost / state.totalCalls : 0;

  // ローカルLLM節約率 (概算)
  var localCost = 0;
  var localModels = ["qwen3:72b", "codestral:22b"];
  for (var lm = 0; lm < localModels.length; lm++) {
    var data = state.modelData[localModels[lm]] || [];
    for (var j = 0; j < data.length; j++) {
      localCost += data[j].cost;
    }
  }
  var savingsRate = state.totalCost > 0 ? Math.round((localCost / state.totalCost) * 100) : 0;

  $("todayCost").textContent = "$" + todayCost.toFixed(2);
  $("weekCost").textContent = "$" + weekCost.toFixed(2);
  $("totalCalls").textContent = state.totalCalls;
  $("avgCostCall").textContent = "平均 $" + avgCost.toFixed(4) + "/回";
  $("totalCostLabel").textContent = "累計コスト: $" + state.totalCost.toFixed(2);
  $("savingsRate").textContent = savingsRate + "%";
}

// ============================================================
// チャート描画
// ============================================================

function renderChart() {
  var svg = $("costChart");
  var width = svg.clientWidth || 760;
  var height = 300;
  svg.setAttribute("viewBox", "0 0 " + width + " " + height);
  svg.innerHTML = "";

  var padding = { top: 20, right: 20, bottom: 40, left: 60 };
  var chartW = width - padding.left - padding.right;
  var chartH = height - padding.top - padding.bottom;

  var data;
  var legendItems = [];

  if (state.viewMode === "daily") {
    data = [{ values: state.dailyData, color: chartColors.daily, label: "日次コスト" }];
    legendItems = [{ color: chartColors.daily, label: "日次コスト ($)" }];
  } else if (state.viewMode === "cycle") {
    data = [{ values: state.cycleData, color: "#4CAF50", label: "サイクル別コスト" }];
    legendItems = [{ color: "#4CAF50", label: "サイクル別コスト ($)" }];
  } else {
    // モデル別
    var modelKeys = Object.keys(state.modelData);
    data = [];
    for (var mk = 0; mk < modelKeys.length; mk++) {
      var key = modelKeys[mk];
      data.push({ values: state.modelData[key], color: chartColors[key] || "#9E9E9E", label: key });
      legendItems.push({ color: chartColors[key] || "#9E9E9E", label: key });
    }
  }

  // 最大値算出
  var maxVal = 1;
  for (var di = 0; di < data.length; di++) {
    for (var dj = 0; dj < data[di].values.length; dj++) {
      if (data[di].values[dj].cost > maxVal) maxVal = data[di].values[dj].cost;
    }
  }
  maxVal = Math.ceil(maxVal / 5) * 5 + 5;

  // グリッド線
  for (var g = 0; g <= 4; g++) {
    var gy = padding.top + chartH - (g / 4) * chartH;
    var gridLine = document.createElementNS("http://www.w3.org/2000/svg", "line");
    gridLine.setAttribute("x1", padding.left);
    gridLine.setAttribute("y1", gy);
    gridLine.setAttribute("x2", width - padding.right);
    gridLine.setAttribute("y2", gy);
    gridLine.setAttribute("stroke", "#e0e0e0");
    gridLine.setAttribute("stroke-width", "1");
    svg.appendChild(gridLine);

    var label = document.createElementNS("http://www.w3.org/2000/svg", "text");
    label.setAttribute("x", padding.left - 8);
    label.setAttribute("y", gy + 4);
    label.setAttribute("text-anchor", "end");
    label.setAttribute("font-size", "11");
    label.setAttribute("fill", "#757575");
    label.textContent = "$" + ((g / 4) * maxVal).toFixed(0);
    svg.appendChild(label);
  }

  // データ描画
  for (var si = 0; si < data.length; si++) {
    var series = data[si];
    var vals = series.values;
    if (vals.length === 0) continue;

    var points = [];
    for (var vi = 0; vi < vals.length; vi++) {
      var px = padding.left + (vi / Math.max(vals.length - 1, 1)) * chartW;
      var py = padding.top + chartH - (vals[vi].cost / maxVal) * chartH;
      points.push(px + "," + py);

      // データポイント (丸)
      var circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      circle.setAttribute("cx", px);
      circle.setAttribute("cy", py);
      circle.setAttribute("r", "4");
      circle.setAttribute("fill", series.color);
      svg.appendChild(circle);

      // X軸ラベル (最初のシリーズのみ)
      if (si === 0) {
        var xLabel = document.createElementNS("http://www.w3.org/2000/svg", "text");
        xLabel.setAttribute("x", px);
        xLabel.setAttribute("y", height - 8);
        xLabel.setAttribute("text-anchor", "middle");
        xLabel.setAttribute("font-size", "10");
        xLabel.setAttribute("fill", "#757575");
        xLabel.textContent = vals[vi].label;
        svg.appendChild(xLabel);
      }
    }

    // ライン描画
    var polyline = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
    polyline.setAttribute("points", points.join(" "));
    polyline.setAttribute("fill", "none");
    polyline.setAttribute("stroke", series.color);
    polyline.setAttribute("stroke-width", "2");
    svg.appendChild(polyline);
  }

  // limit ライン ($30)
  if (state.viewMode === "daily") {
    var limitY = padding.top + chartH - (30 / maxVal) * chartH;
    var limitLine = document.createElementNS("http://www.w3.org/2000/svg", "line");
    limitLine.setAttribute("x1", padding.left);
    limitLine.setAttribute("y1", limitY);
    limitLine.setAttribute("x2", width - padding.right);
    limitLine.setAttribute("y2", limitY);
    limitLine.setAttribute("stroke", "#F44336");
    limitLine.setAttribute("stroke-width", "1");
    limitLine.setAttribute("stroke-dasharray", "5,5");
    svg.appendChild(limitLine);

    var limitLabel = document.createElementNS("http://www.w3.org/2000/svg", "text");
    limitLabel.setAttribute("x", width - padding.right - 4);
    limitLabel.setAttribute("y", limitY - 4);
    limitLabel.setAttribute("text-anchor", "end");
    limitLabel.setAttribute("font-size", "10");
    limitLabel.setAttribute("fill", "#F44336");
    limitLabel.textContent = "上限 $30";
    svg.appendChild(limitLabel);

    legendItems.push({ color: "#F44336", label: "日次上限 ($30)" });
  }

  // 凡例
  renderLegend(legendItems);
}

function renderLegend(items) {
  var container = $("chartLegend");
  container.innerHTML = "";
  for (var i = 0; i < items.length; i++) {
    var span = document.createElement("span");
    span.className = "legend-item";
    span.innerHTML = '<span class="legend-color" style="background:' + items[i].color + '"></span>' + items[i].label;
    container.appendChild(span);
  }
}

// ============================================================
// モデル別内訳
// ============================================================

function renderModelBreakdown() {
  var container = $("modelBreakdown");
  container.innerHTML = "";

  var modelKeys = Object.keys(state.modelData);
  var totalByModel = {};
  for (var i = 0; i < modelKeys.length; i++) {
    var key = modelKeys[i];
    var total = 0;
    for (var j = 0; j < state.modelData[key].length; j++) {
      total += state.modelData[key][j].cost;
    }
    totalByModel[key] = total;
  }

  for (var k = 0; k < modelKeys.length; k++) {
    var mKey = modelKeys[k];
    var cost = totalByModel[mKey];
    var pct = state.totalCost > 0 ? (cost / state.totalCost * 100) : 0;
    var color = chartColors[mKey] || "#9E9E9E";
    var isLocal = mKey === "qwen3:72b" || mKey === "codestral:22b";

    var div = document.createElement("div");
    div.className = "model-breakdown-item";
    div.innerHTML =
      '<div class="model-breakdown-header">' +
      '  <span class="model-breakdown-name">' + (isLocal ? "🖥️ " : "☁️ ") + mKey + '</span>' +
      '  <span class="model-breakdown-cost">$' + cost.toFixed(2) + '</span>' +
      '</div>' +
      '<div class="model-breakdown-bar-container">' +
      '  <div class="model-breakdown-bar" style="width:' + pct + '%;background:' + color + '"></div>' +
      '</div>' +
      '<div class="model-breakdown-pct">' + pct.toFixed(1) + '%</div>';
    container.appendChild(div);
  }
}

// ============================================================
// 全体描画
// ============================================================

function renderAll() {
  renderSummary();
  renderChart();
  renderModelBreakdown();
}

// ============================================================
// ビューモード切替
// ============================================================

function setupViewMode() {
  var options = document.querySelectorAll("#viewMode .radio-option");
  for (var i = 0; i < options.length; i++) {
    (function (option) {
      option.addEventListener("click", function () {
        for (var j = 0; j < options.length; j++) {
          options[j].classList.remove("selected");
        }
        option.classList.add("selected");
        state.viewMode = option.getAttribute("data-value");
        var radio = option.querySelector("input[type='radio']");
        if (radio) radio.checked = true;
        renderChart();
        addLog("表示モード変更: " + state.viewMode, "DEBUG");
      });
    })(options[i]);
  }
}

// ============================================================
// 初期化
// ============================================================

function init() {
  setupViewMode();

  $("btnAddDataPoint").addEventListener("click", addDataPoint);
  $("btnSimulateWeek").addEventListener("click", function () {
    generateWeekData();
    renderAll();
    addLog("📅 1週間分のデータを生成しました", "INFO");
  });
  $("btnResetChart").addEventListener("click", function () {
    state.dailyData = [];
    state.cycleData = [];
    state.totalCost = 0;
    state.totalCalls = 0;
    var modelKeys = Object.keys(state.modelData);
    for (var m = 0; m < modelKeys.length; m++) {
      state.modelData[modelKeys[m]] = [];
    }
    renderAll();
    addLog("🔄 チャートをリセットしました", "INFO");
  });

  // ウィンドウリサイズ時にチャートを再描画 (デバウンス)
  window.addEventListener("resize", debounce(function () { renderChart(); }, 150));

  // 初期データ生成
  generateWeekData();
  renderAll();

  addLog("コスト推移グラフを起動しました", "INFO");
}

document.addEventListener("DOMContentLoaded", init);
