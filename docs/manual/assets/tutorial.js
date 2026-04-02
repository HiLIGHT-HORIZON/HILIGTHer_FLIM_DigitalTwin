(function () {
  const IRF_OFFSET_NS = 1.0;
  const ABS_FISHER_DENSITY_MAX = 1000;
  const ABS_FISHER_DENSITY_LOG_FLOOR = 1e-3;
  const GATE_PERIOD_NS = 25.0;
  let lastTutorialInput = null;

  function byId(id) {
    return document.getElementById(id);
  }

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }

  function linspace(start, stop, count) {
    if (count <= 1) return [start];
    const step = (stop - start) / (count - 1);
    return Array.from({ length: count }, (_, idx) => start + idx * step);
  }

  function trapz(x, y) {
    let area = 0;
    for (let i = 1; i < x.length; i += 1) {
      area += 0.5 * (y[i] + y[i - 1]) * (x[i] - x[i - 1]);
    }
    return area;
  }

  function cumsum(values, dt) {
    const out = [];
    let total = 0;
    values.forEach((value) => {
      total += value * dt;
      out.push(total);
    });
    return out;
  }

  function formatNumber(value, decimals) {
    return Number(value).toLocaleString(undefined, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  }

  function normalisePeak(values) {
    const maxValue = Math.max(...values, 1e-12);
    return values.map((value) => value / maxValue);
  }

  function controlConfig(id) {
    return document.querySelector("[data-control-id='" + id + "']");
  }

  function readControl(id) {
    const node = controlConfig(id);
    const input = byId(id);
    if (!node || !input) return 0;
    const min = Number(node.dataset.min);
    const max = Number(node.dataset.max);
    const decimals = Number(node.dataset.decimals || "0");
    const fraction = Number(input.value) / Number(input.max || 1);
    let value;
    if (node.dataset.scale === "log") {
      const lo = Math.log10(Math.max(min, 1e-12));
      const hi = Math.log10(Math.max(max, 1e-12));
      value = Math.pow(10, lo + fraction * (hi - lo));
    } else {
      value = min + fraction * (max - min);
    }
    return Number(value.toFixed(decimals));
  }

  function setControlValue(id, value) {
    const node = controlConfig(id);
    const input = byId(id);
    if (!node || !input) return;
    const min = Number(node.dataset.min);
    const max = Number(node.dataset.max);
    const clamped = clamp(value, min, max);
    let fraction;
    if (node.dataset.scale === "log") {
      const lo = Math.log10(Math.max(min, 1e-12));
      const hi = Math.log10(Math.max(max, 1e-12));
      fraction = (Math.log10(Math.max(clamped, 1e-12)) - lo) / Math.max(hi - lo, 1e-12);
    } else {
      fraction = (clamped - min) / Math.max(max - min, 1e-12);
    }
    input.value = String(Math.round(clamp(fraction, 0, 1) * Number(input.max || 500)));
  }

  function updateControlLabels() {
    document.querySelectorAll("[data-control-id]").forEach((node) => {
      const id = node.dataset.controlId;
      const value = readControl(id);
      const decimals = Number(node.dataset.decimals || "0");
      const suffix = node.dataset.suffix || "";
      const label = byId(id + "Value");
      if (label) {
        label.textContent = formatNumber(value, decimals) + suffix;
      }
    });
  }

  function gaussianBlur(signal, t, sigmaNs) {
    if (sigmaNs <= 1e-9) return signal.slice();
    const dt = t[1] - t[0];
    const halfWidth = Math.max(Math.ceil((4 * sigmaNs) / Math.max(dt, 1e-12)), 1);
    const kernel = [];
    for (let i = -halfWidth; i <= halfWidth; i += 1) {
      const x = i * dt;
      kernel.push(Math.exp(-0.5 * Math.pow(x / sigmaNs, 2)));
    }
    const norm = kernel.reduce((acc, value) => acc + value, 0);
    const normKernel = kernel.map((value) => value / Math.max(norm, 1e-12));
    const out = new Array(signal.length).fill(0);
    for (let i = 0; i < signal.length; i += 1) {
      let sum = 0;
      for (let j = -halfWidth; j <= halfWidth; j += 1) {
        const idx = clamp(i + j, 0, signal.length - 1);
        sum += signal[idx] * normKernel[j + halfWidth];
      }
      out[i] = sum;
    }
    return out;
  }

  function gaussianProfile(t, centre, sigmaNs) {
    const sigma = Math.max(sigmaNs, 1e-9);
    return t.map((time) => Math.exp(-0.5 * Math.pow((time - centre) / sigma, 2)));
  }

  function diracProfile(t, centre) {
    const out = new Array(t.length).fill(0);
    let bestIndex = 0;
    let bestDistance = Infinity;
    t.forEach((time, idx) => {
      const distance = Math.abs(time - centre);
      if (distance < bestDistance) {
        bestDistance = distance;
        bestIndex = idx;
      }
    });
    out[bestIndex] = 1;
    return out;
  }

  function irfProfile(t, centre, sigmaNs) {
    if (sigmaNs <= 1e-9) {
      return diracProfile(t, centre);
    }
    return normalisePeak(gaussianProfile(t, centre, sigmaNs));
  }

  function normalisedDecay(t, tau, blurSigmaNs, offsetNs) {
    const offset = Number.isFinite(offsetNs) ? offsetNs : 0;
    const decay = t.map((time) => {
      if (time < offset) return 0;
      return Math.exp(-(time - offset) / Math.max(tau, 1e-6));
    });
    const blurred = blurSigmaNs > 1e-9 ? gaussianBlur(decay, t, blurSigmaNs) : decay.slice();
    const area = trapz(t, blurred);
    return blurred.map((value) => value / Math.max(area, 1e-12));
  }

  function fisherDensity(t, tau, blurSigmaNs, offsetNs) {
    const base = normalisedDecay(t, tau, blurSigmaNs, offsetNs);
    const eps = Math.max(0.01, 0.02 * tau);
    const plus = normalisedDecay(t, tau + eps, blurSigmaNs, offsetNs);
    const minus = normalisedDecay(t, Math.max(tau - eps, 0.02), blurSigmaNs, offsetNs);
    const density = base.map((value, idx) => {
      const dlog = (Math.log(Math.max(plus[idx], 1e-12)) - Math.log(Math.max(minus[idx], 1e-12))) / (2 * eps);
      return value * dlog * dlog;
    });
    const irf = irfProfile(t, Number.isFinite(offsetNs) ? offsetNs : 0, blurSigmaNs);
    return { base: base, density: density, irf: irf };
  }

  function gateProfile(t, centre, width) {
    const left = centre - width / 2;
    const right = centre + width / 2;
    return t.map((time) => (time >= left && time <= right ? 1 : 0));
  }

  function niceLinearTicks(min, max, count) {
    const ticks = [];
    if (!Number.isFinite(min) || !Number.isFinite(max)) return ticks;
    if (Math.abs(max - min) < 1e-12) {
      return [min];
    }
    const step = (max - min) / Math.max(count - 1, 1);
    for (let i = 0; i < count; i += 1) {
      ticks.push(min + i * step);
    }
    return ticks;
  }

  function formatTick(value) {
    if (Math.abs(value) >= 1000) return Math.round(value).toLocaleString();
    if (Math.abs(value) >= 10) return value.toFixed(0);
    if (Math.abs(value) >= 1) return value.toFixed(1);
    return value.toFixed(2);
  }

  function niceLogTicks(min, max) {
    const ticks = [];
    if (!(min > 0) || !(max > 0)) return ticks;
    const start = Math.ceil(Math.log10(min));
    const stop = Math.floor(Math.log10(max));
    for (let exponent = start; exponent <= stop; exponent += 1) {
      const value = Math.pow(10, exponent);
      ticks.push({ value: value, label: "1e" + exponent });
    }
    if (!ticks.length) {
      ticks.push({ value: min, label: min.toExponential(0) });
      ticks.push({ value: max, label: max.toExponential(0) });
    }
    return ticks;
  }

  function svgEl(name, attrs) {
    const node = document.createElementNS("http://www.w3.org/2000/svg", name);
    Object.entries(attrs || {}).forEach(([key, value]) => {
      node.setAttribute(key, String(value));
    });
    return node;
  }

  function buildLegend(containerId, items) {
    const container = byId(containerId);
    if (!container) return;
    container.innerHTML = "";
    (items || []).forEach((item) => {
      const entry = document.createElement("span");
      entry.className = "chart-legend-item";
      const swatch = document.createElement("span");
      swatch.className = "chart-legend-swatch";
      if (item.style === "dot") swatch.classList.add("dot");
      if (item.dash) swatch.classList.add("dashed");
      swatch.style.setProperty("--accent", item.color);
      swatch.style.borderTopColor = item.color;
      swatch.style.background = item.style === "dot" ? item.color : swatch.style.background;
      const text = document.createElement("span");
      text.textContent = item.label;
      entry.appendChild(swatch);
      entry.appendChild(text);
      container.appendChild(entry);
    });
  }

  function drawChart(svgId, legendId, config) {
    const svg = byId(svgId);
    if (!svg) return;
    svg.innerHTML = "";

    const width = 820;
    const height = 320;
    const hasRightAxis = Boolean(config.yRightLabel);
    const margin = { left: 68, right: hasRightAxis ? 68 : 18, top: 18, bottom: 46 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const xMin = config.xMin;
    const xMax = config.xMax;
    let yMin = config.yMin;
    let yMax = config.yMax;
    let yRightMin = config.yRightMin;
    let yRightMax = config.yRightMax;
    const yScale = config.yScale || "linear";
    const yRightScale = config.yRightScale || "linear";
    if (Math.abs(yMax - yMin) < 1e-12) {
      yMin -= 0.5;
      yMax += 0.5;
    }
    if (hasRightAxis && Math.abs(yRightMax - yRightMin) < 1e-12) {
      yRightMin -= 0.5;
      yRightMax += 0.5;
    }

    const xScale = config.xScale || "linear";
    const mapX = (value) => {
      if (xScale === "log") {
        const lo = Math.log10(Math.max(xMin, 1e-12));
        const hi = Math.log10(Math.max(xMax, 1e-12));
        const pos = (Math.log10(Math.max(value, 1e-12)) - lo) / Math.max(hi - lo, 1e-12);
        return margin.left + pos * innerWidth;
      }
      return margin.left + ((value - xMin) / Math.max(xMax - xMin, 1e-12)) * innerWidth;
    };
    const mapY = (value) => {
      if (yScale === "log") {
        const lo = Math.log10(Math.max(yMin, 1e-12));
        const hi = Math.log10(Math.max(yMax, 1e-12));
        const pos = (Math.log10(Math.max(value, 1e-12)) - lo) / Math.max(hi - lo, 1e-12);
        return margin.top + innerHeight - pos * innerHeight;
      }
      return margin.top + innerHeight - ((value - yMin) / Math.max(yMax - yMin, 1e-12)) * innerHeight;
    };
    const mapYRight = (value) => {
      if (yRightScale === "log") {
        const lo = Math.log10(Math.max(yRightMin, 1e-12));
        const hi = Math.log10(Math.max(yRightMax, 1e-12));
        const pos = (Math.log10(Math.max(value, 1e-12)) - lo) / Math.max(hi - lo, 1e-12);
        return margin.top + innerHeight - pos * innerHeight;
      }
      return margin.top + innerHeight - ((value - yRightMin) / Math.max(yRightMax - yRightMin, 1e-12)) * innerHeight;
    };

    svg.appendChild(svgEl("rect", { x: 0, y: 0, width: width, height: height, fill: "#09121d" }));

    const xTicks = config.xTicks || niceLinearTicks(xMin, xMax, 5).map((value) => ({ value: value, label: formatTick(value) }));
    const yTicks = config.yTicks || (
      yScale === "log"
        ? niceLogTicks(yMin, yMax)
        : niceLinearTicks(yMin, yMax, 5).map((value) => ({ value: value, label: formatTick(value) }))
    );
    const yRightTicks = hasRightAxis
      ? (config.yRightTicks || (
        yRightScale === "log"
          ? niceLogTicks(yRightMin, yRightMax)
          : niceLinearTicks(yRightMin, yRightMax, 5).map((value) => ({ value: value, label: formatTick(value) }))
      ))
      : [];

    xTicks.forEach((tick) => {
      const x = mapX(tick.value);
      svg.appendChild(svgEl("line", { x1: x, y1: margin.top, x2: x, y2: margin.top + innerHeight, stroke: "#203245", "stroke-width": 1 }));
      const label = svgEl("text", { x: x, y: height - 16, fill: "#9eb2c8", "font-size": 11, "text-anchor": "middle" });
      label.textContent = tick.label;
      svg.appendChild(label);
    });

    yTicks.forEach((tick) => {
      const y = mapY(tick.value);
      svg.appendChild(svgEl("line", { x1: margin.left, y1: y, x2: width - margin.right, y2: y, stroke: "#203245", "stroke-width": 1 }));
      const label = svgEl("text", { x: margin.left - 10, y: y + 4, fill: "#9eb2c8", "font-size": 11, "text-anchor": "end" });
      label.textContent = tick.label;
      svg.appendChild(label);
    });

    svg.appendChild(svgEl("line", { x1: margin.left, y1: margin.top, x2: margin.left, y2: margin.top + innerHeight, stroke: "#dbeafe", "stroke-width": 1.5 }));
    svg.appendChild(svgEl("line", { x1: margin.left, y1: margin.top + innerHeight, x2: width - margin.right, y2: margin.top + innerHeight, stroke: "#dbeafe", "stroke-width": 1.5 }));
    if (hasRightAxis) {
      svg.appendChild(svgEl("line", { x1: width - margin.right, y1: margin.top, x2: width - margin.right, y2: margin.top + innerHeight, stroke: "#dbeafe", "stroke-width": 1.5 }));
      yRightTicks.forEach((tick) => {
        const y = mapYRight(tick.value);
        const label = svgEl("text", { x: width - margin.right + 10, y: y + 4, fill: "#9eb2c8", "font-size": 11, "text-anchor": "start" });
        label.textContent = tick.label;
        svg.appendChild(label);
      });
    }

    (config.vLines || []).forEach((line) => {
      const x = mapX(line.value);
      svg.appendChild(svgEl("line", {
        x1: x,
        y1: margin.top,
        x2: x,
        y2: margin.top + innerHeight,
        stroke: line.color || "#fbbf24",
        "stroke-width": 1.5,
        "stroke-dasharray": line.dash ? "6 5" : "",
      }));
    });

    (config.series || []).forEach((series) => {
      const points = [];
      const yMapper = series.yAxis === "right" ? mapYRight : mapY;
      for (let i = 0; i < series.x.length; i += 1) {
        const x = series.x[i];
        const y = series.y[i];
        if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
        points.push(mapX(x).toFixed(2) + "," + yMapper(y).toFixed(2));
      }
      if (!points.length) return;
      svg.appendChild(svgEl("polyline", {
        points: points.join(" "),
        fill: "none",
        stroke: series.color,
        "stroke-width": series.width || 2.5,
        "stroke-dasharray": series.dash ? "8 6" : "",
        "stroke-linejoin": "round",
        "stroke-linecap": "round",
      }));
    });

    (config.points || []).forEach((point) => {
      svg.appendChild(svgEl("circle", {
        cx: mapX(point.x),
        cy: mapY(point.y),
        r: point.radius || 5,
        fill: point.color || "#f43f5e",
        stroke: point.stroke || "#ffffff",
        "stroke-width": 1.5,
      }));
    });

    const xLabel = svgEl("text", {
      x: margin.left + innerWidth / 2,
      y: height - 4,
      fill: "#dbeafe",
      "font-size": 12,
      "text-anchor": "middle",
    });
    xLabel.textContent = config.xLabel;
    svg.appendChild(xLabel);

    const yLabel = svgEl("text", {
      x: 18,
      y: margin.top + innerHeight / 2,
      fill: "#dbeafe",
      "font-size": 12,
      transform: "rotate(-90 18 " + (margin.top + innerHeight / 2) + ")",
      "text-anchor": "middle",
    });
    yLabel.textContent = config.yLabel;
    svg.appendChild(yLabel);

    if (hasRightAxis) {
      const yRightLabel = svgEl("text", {
        x: width - 18,
        y: margin.top + innerHeight / 2,
        fill: "#dbeafe",
        "font-size": 12,
        transform: "rotate(90 " + (width - 18) + " " + (margin.top + innerHeight / 2) + ")",
        "text-anchor": "middle",
      });
      yRightLabel.textContent = config.yRightLabel;
      svg.appendChild(yRightLabel);
    }

    buildLegend(legendId, config.legend || []);
  }

  function drawBarChart(svgId, legendId, config) {
    const svg = byId(svgId);
    if (!svg) return;
    svg.innerHTML = "";

    const width = 820;
    const height = 320;
    const hasRightAxis = Boolean(config.yRightLabel);
    const margin = { left: 68, right: hasRightAxis ? 68 : 24, top: 18, bottom: 56 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;
    const yMin = 0;
    const yMax = Math.max(config.yMax, 1e-12);
    const yRightMin = Number.isFinite(config.yRightMin) ? config.yRightMin : 0;
    const yRightMax = Number.isFinite(config.yRightMax) ? Math.max(config.yRightMax, 1e-12) : 1;
    const labels = config.labels || [];
    const values = config.values || [];
    const colors = config.colors || [];
    const rightValues = config.rightValues || [];
    const rightColor = config.rightColor || "#ef4444";
    const rightMarkerOnAxis = Boolean(config.rightMarkerOnAxis);

    const mapY = (value) => margin.top + innerHeight - ((value - yMin) / Math.max(yMax - yMin, 1e-12)) * innerHeight;
    const mapYRight = (value) => margin.top + innerHeight - ((value - yRightMin) / Math.max(yRightMax - yRightMin, 1e-12)) * innerHeight;

    svg.appendChild(svgEl("rect", { x: 0, y: 0, width: width, height: height, fill: "#09121d" }));

    niceLinearTicks(yMin, yMax, 5).forEach((tickValue) => {
      const y = mapY(tickValue);
      svg.appendChild(svgEl("line", { x1: margin.left, y1: y, x2: width - margin.right, y2: y, stroke: "#203245", "stroke-width": 1 }));
      const label = svgEl("text", { x: margin.left - 10, y: y + 4, fill: "#9eb2c8", "font-size": 11, "text-anchor": "end" });
      label.textContent = formatTick(tickValue);
      svg.appendChild(label);
    });

    svg.appendChild(svgEl("line", { x1: margin.left, y1: margin.top, x2: margin.left, y2: margin.top + innerHeight, stroke: "#dbeafe", "stroke-width": 1.5 }));
    svg.appendChild(svgEl("line", { x1: margin.left, y1: margin.top + innerHeight, x2: width - margin.right, y2: margin.top + innerHeight, stroke: "#dbeafe", "stroke-width": 1.5 }));
    if (hasRightAxis) {
      svg.appendChild(svgEl("line", { x1: width - margin.right, y1: margin.top, x2: width - margin.right, y2: margin.top + innerHeight, stroke: "#dbeafe", "stroke-width": 1.5 }));
      niceLinearTicks(yRightMin, yRightMax, 5).forEach((tickValue) => {
        const y = mapYRight(tickValue);
        const label = svgEl("text", { x: width - margin.right + 10, y: y + 4, fill: "#9eb2c8", "font-size": 11, "text-anchor": "start" });
        label.textContent = formatTick(tickValue);
        svg.appendChild(label);
      });
    }

    const slotWidth = innerWidth / Math.max(values.length, 1);
    const barWidth = Math.min(110, slotWidth * 0.58);
    const centers = [];
    values.forEach((value, idx) => {
      const x = margin.left + idx * slotWidth + (slotWidth - barWidth) / 2;
      centers.push(x + barWidth / 2);
      const y = mapY(value);
      const barHeight = margin.top + innerHeight - y;
      svg.appendChild(svgEl("rect", {
        x: x,
        y: y,
        width: barWidth,
        height: Math.max(barHeight, 0),
        fill: colors[idx] || "#38bdf8",
        rx: 8,
      }));
      const valueLabel = svgEl("text", {
        x: x + barWidth / 2,
        y: Math.max(y - 8, margin.top + 12),
        fill: "#dbeafe",
        "font-size": 11,
        "text-anchor": "middle",
      });
      valueLabel.textContent = formatTick(value);
      svg.appendChild(valueLabel);

      const xLabel = svgEl("text", {
        x: x + barWidth / 2,
        y: height - 20,
        fill: "#9eb2c8",
        "font-size": 11,
        "text-anchor": "middle",
      });
      xLabel.textContent = labels[idx] || ("Bar " + (idx + 1));
      svg.appendChild(xLabel);
    });

    if (rightValues.length) {
      const points = [];
      rightValues.forEach((value, idx) => {
        if (!Number.isFinite(value) || !Number.isFinite(centers[idx])) return;
        const cx = rightMarkerOnAxis ? width - margin.right : centers[idx];
        const cy = mapYRight(value);
        points.push(cx.toFixed(2) + "," + cy.toFixed(2));
        const triangle = svgEl("polygon", {
          points: [
            (cx - 7).toFixed(2) + "," + (cy - 6).toFixed(2),
            (cx - 7).toFixed(2) + "," + (cy + 6).toFixed(2),
            (cx + 6).toFixed(2) + "," + cy.toFixed(2),
          ].join(" "),
          fill: rightColor,
          stroke: "#ffffff",
          "stroke-width": 1.5,
        });
        svg.appendChild(triangle);
      });
      if (points.length > 1) {
        svg.appendChild(svgEl("polyline", {
          points: points.join(" "),
          fill: "none",
          stroke: rightColor,
          "stroke-width": 2.5,
          "stroke-dasharray": "8 6",
          "stroke-linejoin": "round",
          "stroke-linecap": "round",
        }));
      }
    }

    const yLabel = svgEl("text", {
      x: 18,
      y: margin.top + innerHeight / 2,
      fill: "#dbeafe",
      "font-size": 12,
      transform: "rotate(-90 18 " + (margin.top + innerHeight / 2) + ")",
      "text-anchor": "middle",
    });
    yLabel.textContent = config.yLabel;
    svg.appendChild(yLabel);

    const xLabel = svgEl("text", {
      x: margin.left + innerWidth / 2,
      y: height - 4,
      fill: "#dbeafe",
      "font-size": 12,
      "text-anchor": "middle",
    });
    xLabel.textContent = config.xLabel;
    svg.appendChild(xLabel);

    if (hasRightAxis) {
      const yRightLabel = svgEl("text", {
        x: width - 18,
        y: margin.top + innerHeight / 2,
        fill: "#dbeafe",
        "font-size": 12,
        transform: "rotate(90 " + (width - 18) + " " + (margin.top + innerHeight / 2) + ")",
        "text-anchor": "middle",
      });
      yRightLabel.textContent = config.yRightLabel;
      svg.appendChild(yRightLabel);
    }

    const legend = (config.labels || []).map((label, idx) => ({ label: label, color: colors[idx] || "#38bdf8" }));
    if (rightValues.length) {
      legend.push({ label: config.rightLegendLabel || "Secondary axis", color: rightColor, dash: true });
    }
    buildLegend(legendId, legend);
  }

  function setBar(fillId, labelId, fraction, tone) {
    const pct = clamp(fraction, 0, 1);
    const fill = byId(fillId);
    const label = byId(labelId);
    if (fill) {
      fill.style.width = (pct * 100).toFixed(1) + "%";
      if (tone === "resolved") {
        fill.style.background = "linear-gradient(90deg, #10b981, #22c55e)";
      } else if (tone === "unresolved") {
        fill.style.background = "linear-gradient(90deg, #e11d48, #d946ef)";
      } else {
        fill.style.background = "linear-gradient(90deg, #10b981, #38bdf8)";
      }
    }
    if (label) label.textContent = Math.round(pct * 100) + "%";
  }

  function combinedGateProfile(gateA, gateB) {
    return gateA.map((value, idx) => Math.max(value, gateB[idx]));
  }

  function safeContribution(derivative, probability) {
    return (derivative * derivative) / Math.max(probability, 1e-12);
  }

  function gaussianCurve(x, mean, sigma) {
    const safeSigma = Math.max(sigma, 1e-6);
    const norm = 1 / (safeSigma * Math.sqrt(2 * Math.PI));
    return x.map((value) => norm * Math.exp(-0.5 * Math.pow((value - mean) / safeSigma, 2)));
  }

  function titleFromCard(node) {
    if (!node) return "";
    const heading = node.querySelector("h3");
    const paragraph = node.querySelector("p, li");
    const parts = [];
    if (heading && heading.textContent.trim()) parts.push(heading.textContent.trim());
    if (paragraph && paragraph.textContent.trim()) parts.push(paragraph.textContent.trim());
    return parts.join(": ");
  }

  function applyTutorialTooltips() {
    const tooltipMap = {
      fiTau: "Set the lifetime being analysed in the Fisher-information example.",
      fiDelta: "Choose a nearby comparison lifetime so you can see how much the timing curve changes.",
      fiPeriod: "Set the laser repetition period used in the Fisher-information example.",
      fiBlur: "Set the timing blur of the instrument response in picoseconds.",
      fiYScale: "Choose whether the absolute Fisher-density axis on the right is shown on a linear or logarithmic scale.",
      mtF: "Set the F-value. It cannot go below 1 because 1 is the ideal limit.",
      mtPhotons: "Set the number of collected photons used to evaluate precision and resolvability.",
      rpTau: "Set the fluorescence lifetime you want to measure. This remains an independent input.",
      rpF: "Set the F-value of the system. This remains an independent input and only changes the lifetime precision.",
      rpPhotons: "Set the number of measured photons. Photon count and lifetime standard deviation are always linked through F.",
      rpSigma: "Set the lifetime standard deviation. The photon count updates automatically to keep sigma, F, and lifetime consistent.",
      rpDelta: "Set the lifetime separation delta tau between the two mean lifetime estimates.",
      rpR: "Set the resolving power R, defined as delta tau divided by the lifetime standard deviation.",
      rpLockR: "When enabled, the resolving power is fixed at R = 3 to show the Rayleigh-style criterion.",
      gtTau: "Set the lifetime used in the gate-comparison example.",
      gtStart1: "Move the first edge of gate 1. Gate starts cannot move before the IRF at 1 ns.",
      gtWidth1: "Set how wide gate 1 is in nanoseconds.",
      gtStart2: "Move the first edge of gate 2. In sequential mode it can overlap gate 1. In parallel mode it is shifted right if overlap would occur.",
      gtWidth2: "Set how wide gate 2 is in nanoseconds.",
      gtLockStart: "When enabled, gate 2 tries to start at the same time as gate 1. Parallel mode may still shift it to avoid overlap.",
      gtParallel: "Choose parallel acquisition for one shared photon stream, or clear this for two sequential acquisitions with half the photons in each.",
      gtUseAcquired: "When enabled, F is computed from photons that fall inside the two gates. When disabled, F includes photon losses outside the gates.",
    };

    Object.entries(tooltipMap).forEach(([id, text]) => {
      const node = byId(id);
      if (node) node.title = text;
      const label = node ? node.closest(".tutorial-control") : null;
      if (label) {
        label.title = text;
        label.querySelectorAll("span, input, select").forEach((child) => {
          child.title = text;
        });
      }
    });

    document.querySelectorAll(".tutorial-tab").forEach((node) => {
      if (node.dataset.tabTarget === "panel-fisher") node.title = "Open the Fisher-information basics section.";
      if (node.dataset.tabTarget === "panel-gates") node.title = "Open the gate-comparison section.";
      if (node.dataset.tabTarget === "panel-metrics") node.title = "Open the F-value, photon-efficiency and lifetime-resolution section.";
      if (node.dataset.tabTarget === "panel-resolving") node.title = "Open the FLIM resolving-power section.";
    });

    document.querySelectorAll(".tutorial-note, .chart-card, .sidebar-card").forEach((node) => {
      if (!node.title) node.title = titleFromCard(node);
    });

    document.querySelectorAll(".hero-stat").forEach((node) => {
      if (!node.title) node.title = node.textContent.trim();
    });

    document.querySelectorAll("svg").forEach((node) => {
      if (!node.title) node.title = (node.getAttribute("aria-label") || "Tutorial chart") + ". Move the controls to update this plot.";
    });
  }

  function updateFisher() {
    const tau = readControl("fiTau");
    const delta = readControl("fiDelta");
    const period = Math.max(readControl("fiPeriod"), IRF_OFFSET_NS + tau + delta + 0.8);
    const blurSigmaNs = readControl("fiBlur") / 1000;
    const absScaleMode = byId("fiYScale") ? byId("fiYScale").value : "linear";

    const t = linspace(0, period, 900);
    const fisher = fisherDensity(t, tau, blurSigmaNs, IRF_OFFSET_NS);
    const shifted = normalisedDecay(t, tau + delta, blurSigmaNs, IRF_OFFSET_NS);
    const densityMax = Math.max(...fisher.density, 1e-12);
    const absDensityPlot = absScaleMode === "log"
      ? fisher.density.map((value) => Math.max(value, ABS_FISHER_DENSITY_LOG_FLOOR))
      : fisher.density.slice();
    const densityRel = fisher.density.map((value) => value / densityMax);
    const cumulative = cumsum(fisher.density, t[1] - t[0]);
    const cumulativeMax = Math.max(cumulative[cumulative.length - 1], 1e-12);
    const cumulativeNorm = cumulative.map((value) => value / cumulativeMax);
    const halfIndex = cumulativeNorm.findIndex((value) => value >= 0.5);
    const halfTime = t[Math.max(halfIndex, 0)];
    const fisherInfo = trapz(t, fisher.density);
    const fValue = 1 / Math.max(tau * Math.sqrt(Math.max(fisherInfo, 1e-12)), 1e-12);
    const distanceCurve = t.map((time, idx) => Math.abs(shifted[idx] - fisher.base[idx]));
    const curveDistance = 0.5 * trapz(t, distanceCurve);
    const distanceMax = Math.max(...distanceCurve, 1e-12);
    const distanceNorm = distanceCurve.map((value) => value / distanceMax);
    const signalPeak = Math.max(...fisher.base, ...shifted, 1e-12);
    const irfDisplay = fisher.irf.map((value) => value * signalPeak);

    drawChart("fiDecayPlot", "fiDecayLegend", {
      xMin: 0,
      xMax: period,
      yMin: 0,
      yMax: Math.max(...fisher.base, ...shifted, ...irfDisplay) * 1.08,
      xLabel: "Time (ns)",
      yLabel: "Relative signal",
      series: [
        { x: t, y: irfDisplay, color: "#94a3b8", dash: true },
        { x: t, y: fisher.base, color: "#38bdf8" },
        { x: t, y: shifted, color: "#f59e0b", dash: true },
      ],
      legend: [
        { label: "IRF (offset 1 ns)", color: "#94a3b8", dash: true },
        { label: "Current lifetime", color: "#38bdf8" },
        { label: "Shifted lifetime", color: "#f59e0b", dash: true },
      ],
    });

    drawChart("fiInfoPlot", "fiInfoLegend", {
      xMin: 0,
      xMax: period,
      yMin: 0,
      yMax: 1.05,
      yRightMin: absScaleMode === "log" ? ABS_FISHER_DENSITY_LOG_FLOOR : 0,
      yRightMax: ABS_FISHER_DENSITY_MAX,
      xLabel: "Time (ns)",
      yLabel: "Relative information",
      yRightLabel: "Absolute Fisher density (ns^-3)",
      yRightScale: absScaleMode,
      series: [
        { x: t, y: densityRel, color: "#34d399" },
        { x: t, y: absDensityPlot, color: "#06b6d4", dash: true, yAxis: "right" },
        { x: t, y: cumulativeNorm, color: "#f97316" },
        { x: t, y: distanceNorm, color: "#ec4899", dash: true },
      ],
      vLines: [{ value: halfTime, color: "#fbbf24", dash: true }],
      legend: [
        { label: "Relative information density", color: "#34d399" },
        { label: "Absolute Fisher density (right axis, ns^-3)", color: "#06b6d4", dash: true },
        { label: "Cumulative information", color: "#f97316" },
        { label: "Absolute difference between curves", color: "#ec4899", dash: true },
        { label: "50% information time", color: "#fbbf24", dash: true },
      ],
    });

    byId("fiSummary").textContent =
      "Fisher information is large when nearby lifetimes produce visibly different timing curves. " +
      "Here the IRF is centred at 1.00 ns, so the signal starts after an initial offset rather than at time zero. " +
      "If timing blur is set to 0 ps, the IRF becomes a spike-like Dirac pulse at 1.00 ns. " +
      "The comparison shift = " + delta.toFixed(2) + " ns is only a visual probe: it sets the second lifetime hypothesis. " +
      "The magenta trace is the absolute point-by-point difference between the blue and orange curves. " +
      "The cyan dashed trace uses the right-hand axis and shows the absolute Fisher density in ns^-3. " +
      "That axis is locked to 0-" + ABS_FISHER_DENSITY_MAX.toFixed(0) + " ns^-3 so the scale does not jump between settings. " +
      "The current total Fisher information is " + fisherInfo.toFixed(3) + " ns^-2. " +
      "For the current settings the integrated curve difference is " + curveDistance.toFixed(3) + ", and half of the available information arrives by about " +
      halfTime.toFixed(2) + " ns.";

    byId("fiMath").innerHTML =
      "<p><b>Live interpretation</b></p>" +
      "<p>Approximate conditional <i>F</i> in this toy model: <b>" + fValue.toFixed(2) + "</b>.</p>" +
      "<p>Smaller <i>F</i> means better precision for the same number of collected photons.</p>" +
      "<div class='equation'><i>i</i>(t; &tau;) = p(t | &tau;) [&part; ln p(t | &tau;) / &part;&tau;]<sup>2</sup></div>" +
      "<div class='equation'><i>F</i> &asymp; 1 / [&tau; sqrt(&int; <i>i</i>(t; &tau;) dt)]</div>" +
      "<div class='equation'>difference(t) = |p(t | &tau; + shift) - p(t | &tau;)|</div>" +
      "<p>The comparison shift does not enter the Fisher information definition. It only chooses the nearby lifetime used for the orange comparison curve.</p>";
  }

  function updateMetrics() {
    const fValue = readControl("mtF");
    const photons = Math.max(readControl("mtPhotons"), 1);
    const efficiency = 1 / Math.max(fValue * fValue, 1e-12);
    const penalty = fValue * fValue;
    const effectivePhotons = efficiency * photons;
    const relativeErrorPct = 100 * fValue / Math.sqrt(photons);
    const resolvability = Math.sqrt(photons / Math.max(8 * penalty, 1e-12));
    const resolutionTone = resolvability >= 3 ? "resolved" : "unresolved";

    setBar("fBar", "fLabel", fValue / 10);
    if (byId("fLabel")) byId("fLabel").textContent = fValue.toFixed(2);
    setBar("efficiencyBar", "efficiencyLabel", Math.min(efficiency, 1));
    if (byId("efficiencyLabel")) byId("efficiencyLabel").textContent = efficiency.toFixed(3);
    setBar("resolvabilityBar", "resolvabilityLabel", Math.min(resolvability / 10, 1), resolutionTone);
    if (byId("resolvabilityLabel")) byId("resolvabilityLabel").textContent = resolvability.toFixed(2);

    byId("metricSummary").textContent =
      "With F = " + fValue.toFixed(2) + " and " + Math.round(photons).toLocaleString() +
      " collected photons, the relative lifetime precision is about " + relativeErrorPct.toFixed(2) +
      "%. The experiment behaves as if only " + Math.round(effectivePhotons).toLocaleString() +
      " of those photons were ideal. The resolvability bar turns green when R is above 3, meaning the lifetime is conventionally considered resolved, and red/magenta when R is below 3, meaning it is not yet cleanly resolved.";

    byId("metricMath").innerHTML =
      "<p><b>Compact explainer</b></p>" +
      "<div class='equation'>&sigma;<sub>&tau;</sub> / &tau; = F / sqrt(N<sub>c</sub>)</div>" +
      "<div class='equation'>F = sqrt(N<sub>c</sub>) [&sigma;<sub>&tau;</sub> / &tau;] = " + fValue.toFixed(2) + "</div>" +
      "<div class='equation'>F = 1 / [&tau; sqrt(I&#771;)]</div>" +
      "<div class='equation'>p = F<sup>-2</sup> = &tau;<sup>2</sup> I&#771; = " + efficiency.toFixed(3) + "</div>" +
      "<div class='equation'>N<sub>eff</sub> = p N<sub>c</sub> = N<sub>c</sub> / F<sup>2</sup> = " + Math.round(effectivePhotons) + "</div>" +
      "<div class='equation'>R = sqrt[N<sub>c</sub> / (8F<sup>2</sup>)] = " + resolvability.toFixed(2) + "</div>" +
      "<p><b>Interpretation</b>: F tells you how much worse the precision is than the ideal case. Photon efficiency F^-2 tells you what fraction of your photons behave like ideal photons. F^2 is the photon penalty factor.</p>";
  }

  function updateResolvingPower() {
    const tau0 = readControl("rpTau");
    const fValue = readControl("rpF");
    let photons = Math.max(readControl("rpPhotons"), 1);
    const lockR = !(byId("rpLockR")) || byId("rpLockR").checked;
    let sigma = (fValue * tau0) / Math.sqrt(photons);

    if (lastTutorialInput === "rpSigma") {
      sigma = readControl("rpSigma");
      photons = Math.max(Math.pow((fValue * tau0) / Math.max(sigma, 1e-9), 2), 1);
      setControlValue("rpPhotons", photons);
    } else {
      sigma = (fValue * tau0) / Math.sqrt(photons);
      setControlValue("rpSigma", sigma);
    }

    let rValue = lockR ? 3 : readControl("rpR");
    let deltaTau;
    if (lockR) {
      deltaTau = 3 * sigma;
      setControlValue("rpR", 3);
      setControlValue("rpDelta", deltaTau);
    } else if (lastTutorialInput === "rpR") {
      rValue = readControl("rpR");
      deltaTau = rValue * sigma;
      setControlValue("rpDelta", deltaTau);
    } else {
      deltaTau = readControl("rpDelta");
      rValue = deltaTau / Math.max(sigma, 1e-12);
      setControlValue("rpR", rValue);
    }

    const tau1 = Math.max(tau0 - deltaTau / 2, 0.02);
    const tau2 = tau0 + deltaTau / 2;
    const xMin = 0;
    const xMax = 10;
    const x = linspace(xMin, xMax, 800);
    const g1 = gaussianCurve(x, tau1, sigma);
    const g2 = gaussianCurve(x, tau2, sigma);
    const yMax = Math.max(...g1, ...g2) * 1.08;
    const sigmaInput = byId("rpSigma");
    const sigmaValue = byId("rpSigmaValue");
    const photonsValue = byId("rpPhotonsValue");
    const rInput = byId("rpR");
    const rValueNode = byId("rpRValue");
    const deltaValue = byId("rpDeltaValue");
    const badge = byId("rpBadge");

    if (sigmaValue) {
      sigmaValue.textContent = formatNumber(sigma, 3) + " ns";
    }
    if (photonsValue) {
      photonsValue.textContent = Math.round(photons).toLocaleString();
    }
    if (rInput) rInput.disabled = lockR;
    if (rValueNode) {
      let label = formatNumber(rValue, 2);
      if (lockR) label += " (Rayleigh)";
      rValueNode.textContent = label;
    }
    if (deltaValue) {
      deltaValue.textContent = formatNumber(deltaTau, 3) + " ns";
    }
    if (badge) {
      badge.classList.remove("resolved", "unresolved");
      if (rValue >= 3) {
        badge.classList.add("resolved");
        badge.textContent = "Fluorescence lifetime resolved";
      } else {
        badge.classList.add("unresolved");
        badge.textContent = "Fluorescence lifetime not resolved";
      }
    }

    drawChart("rpPlot", "rpLegend", {
      xMin: xMin,
      xMax: xMax,
      yMin: 0,
      yMax: yMax,
      xLabel: "Estimated lifetime (ns)",
      yLabel: "Probability density",
      series: [
        { x: x, y: g1, color: "#38bdf8" },
        { x: x, y: g2, color: "#f59e0b" },
      ],
      vLines: [
        { value: tau1, color: "#38bdf8", dash: true },
        { value: tau2, color: "#f59e0b", dash: true },
      ],
      legend: [
        { label: "Lifetime 1 estimate PDF", color: "#38bdf8" },
        { label: "Lifetime 2 estimate PDF", color: "#f59e0b" },
        { label: "Mean lifetime 1", color: "#38bdf8", dash: true },
        { label: "Mean lifetime 2", color: "#f59e0b", dash: true },
      ],
    });

    byId("rpSummary").textContent =
      "For a single-exponential decay, the lifetime standard deviation follows sigma_tau = F tau / sqrt(N). " +
      "Here F and the fluorescence lifetime are independent inputs. The current sigma is " + sigma.toFixed(3) + " ns, " +
      "so the two lifetime means are at " + tau1.toFixed(3) + " ns and " + tau2.toFixed(3) + " ns. Their separation is " +
      deltaTau.toFixed(3) + " ns, corresponding to resolving power R = " + rValue.toFixed(2) + ". " +
      "With R unlocked, delta tau stays fixed and R updates when sigma changes. Changing sigma changes N accordingly, and changing N changes sigma accordingly.";

    byId("rpMath").innerHTML =
      "<p><b>Compact explainer</b></p>" +
      "<div class='equation'>&sigma;<sub>&tau;</sub> = F &tau; / sqrt(N<sub>c</sub>) = " + sigma.toFixed(3) + " ns</div>" +
      "<div class='equation'>R = |&tau;<sub>2</sub> - &tau;<sub>1</sub>| / &sigma;<sub>&tau;</sub> = " + rValue.toFixed(2) + "</div>" +
      "<div class='equation'>&tau;<sub>1</sub> = &tau;<sub>0</sub> - (R &sigma;<sub>&tau;</sub>) / 2 = " + tau1.toFixed(3) + " ns</div>" +
      "<div class='equation'>&tau;<sub>2</sub> = &tau;<sub>0</sub> + (R &sigma;<sub>&tau;</sub>) / 2 = " + tau2.toFixed(3) + " ns</div>" +
      "<div class='equation'>p(t | &tau;) = (1 / &tau;) exp(-t / &tau;), &nbsp; t &ge; 0</div>" +
      "<p>The underlying photon-arrival PDF is a single exponential decay. The Gaussian curves shown here are the sampling distributions of the fitted lifetime estimates, not the photon-arrival PDF itself. F and fluorescence lifetime are treated as independent controls; sigma and photon count stay linked, and delta tau stays fixed unless R is locked or changed directly.</p>";
  }

  function updateGates() {
    const period = GATE_PERIOD_NS;
    const tau = readControl("gtTau");
    const lockStart = Boolean(byId("gtLockStart") && byId("gtLockStart").checked);
    const parallel = !(byId("gtParallel")) || byId("gtParallel").checked;
    const useAcquiredPhotons = !(byId("gtUseAcquired")) || byId("gtUseAcquired").checked;

    const start1 = clamp(readControl("gtStart1"), IRF_OFFSET_NS, period - 0.1);
    const width1 = clamp(readControl("gtWidth1"), 0.1, period - start1);
    const end1 = clamp(start1 + width1, IRF_OFFSET_NS + 0.1, period);

    let start2Requested = lockStart ? start1 : readControl("gtStart2");
    start2Requested = clamp(start2Requested, IRF_OFFSET_NS, period - 0.1);
    const width2Requested = clamp(readControl("gtWidth2"), 0.1, period - start2Requested);

    let start2 = start2Requested;
    if (parallel && start2 < end1) {
      start2 = end1;
    }
    start2 = clamp(start2, IRF_OFFSET_NS, period - 0.1);
    const width2 = clamp(width2Requested, 0.1, period - start2);
    const end2 = clamp(start2 + width2, IRF_OFFSET_NS + 0.1, period);

    const t = linspace(0, period, 900);
    const fisher = fisherDensity(t, tau, 0, IRF_OFFSET_NS);
    const gate1 = gateProfile(t, start1 + (end1 - start1) / 2, end1 - start1);
    const gate2 = gateProfile(t, start2 + (end2 - start2) / 2, end2 - start2);
    const combinedGate = combinedGateProfile(gate1, gate2);

    const epsTau = Math.max(0.005, 0.01 * tau);
    const pdfPlus = normalisedDecay(t, tau + epsTau, 0, IRF_OFFSET_NS);
    const pdfMinus = normalisedDecay(t, Math.max(tau - epsTau, 0.02), 0, IRF_OFFSET_NS);

    const eta1 = trapz(t, fisher.base.map((value, idx) => value * gate1[idx]));
    const eta2 = trapz(t, fisher.base.map((value, idx) => value * gate2[idx]));
    const totalInfo = trapz(t, fisher.density);
    const unionEta = trapz(t, fisher.base.map((value, idx) => value * combinedGate[idx]));
    const eta1Plus = trapz(t, pdfPlus.map((value, idx) => value * gate1[idx]));
    const eta1Minus = trapz(t, pdfMinus.map((value, idx) => value * gate1[idx]));
    const eta2Plus = trapz(t, pdfPlus.map((value, idx) => value * gate2[idx]));
    const eta2Minus = trapz(t, pdfMinus.map((value, idx) => value * gate2[idx]));
    const dEta1 = (eta1Plus - eta1Minus) / (2 * epsTau);
    const dEta2 = (eta2Plus - eta2Minus) / (2 * epsTau);

    let info1;
    let info2;
    let displayedSum;
    let effectiveAbsInfo;
    let effectivePhotonFraction;

    if (useAcquiredPhotons) {
      const accepted = Math.max(eta1 + eta2, 1e-12);
      const dAccepted = dEta1 + dEta2;
      const q1 = eta1 / accepted;
      const q2 = eta2 / accepted;
      const dq1 = (dEta1 * accepted - eta1 * dAccepted) / Math.max(accepted * accepted, 1e-12);
      const dq2 = (dEta2 * accepted - eta2 * dAccepted) / Math.max(accepted * accepted, 1e-12);
      const seqFactor = parallel ? 1 : 0.5;
      info1 = seqFactor * safeContribution(dq1, q1);
      info2 = seqFactor * safeContribution(dq2, q2);
      displayedSum = info1 + info2;
      effectiveAbsInfo = displayedSum;
      effectivePhotonFraction = parallel ? unionEta : 0.5 * (eta1 + eta2);
    } else if (parallel) {
      const etaOutside = Math.max(1 - eta1 - eta2, 1e-12);
      const dEtaOutside = -(dEta1 + dEta2);
      info1 = safeContribution(dEta1, eta1);
      info2 = safeContribution(dEta2, eta2);
      const infoOutside = safeContribution(dEtaOutside, etaOutside);
      displayedSum = info1 + info2;
      effectiveAbsInfo = displayedSum + infoOutside;
      effectivePhotonFraction = unionEta;
    } else {
      info1 = 0.5 * (dEta1 * dEta1) / Math.max(eta1 * (1 - eta1), 1e-12);
      info2 = 0.5 * (dEta2 * dEta2) / Math.max(eta2 * (1 - eta2), 1e-12);
      displayedSum = info1 + info2;
      effectiveAbsInfo = displayedSum;
      effectivePhotonFraction = 0.5 * (eta1 + eta2);
    }

    const informationForF = useAcquiredPhotons
      ? effectiveAbsInfo
      : effectiveAbsInfo;
    const fValue = 1 / Math.max(tau * Math.sqrt(Math.max(informationForF, 1e-12)), 1e-12);

    const gateScale = Math.max(...fisher.base, 1e-12);
    const irfDisplay = fisher.irf.map((value) => value * gateScale);
    const gate1Overlay = gate1.map((value) => value * gateScale);
    const gate2Overlay = gate2.map((value) => value * gateScale * 0.9);
    const overlapPrevented = parallel && start2 !== start2Requested;
    const gate2Input = byId("gtStart2");
    const gate2Value = byId("gtStart2Value");
    if (gate2Input) gate2Input.disabled = lockStart;
    if (gate2Value) {
      let label = formatNumber(start2, 2) + " ns";
      if (lockStart) label += " (locked)";
      else if (overlapPrevented) label += " (shifted)";
      gate2Value.textContent = label;
    }

    drawChart("gatePlot", "gateLegend", {
      xMin: 0,
      xMax: period,
      yMin: 0,
      yMax: Math.max(...fisher.base, ...irfDisplay, ...gate1Overlay, ...gate2Overlay) * 1.12,
      yRightMin: 0,
      yRightMax: Math.max(...fisher.density) * 1.05,
      xLabel: "Time (ns)",
      yLabel: "Relative height",
      yRightLabel: "Absolute Fisher density (ns^-3)",
      series: [
        { x: t, y: irfDisplay, color: "#94a3b8", dash: true },
        { x: t, y: fisher.base, color: "#38bdf8" },
        { x: t, y: fisher.density, color: "#22c55e", dash: true, yAxis: "right" },
        { x: t, y: gate1Overlay, color: "#f59e0b" },
        { x: t, y: gate2Overlay, color: "#a855f7" },
      ],
      legend: [
        { label: "Dirac IRF at 1 ns", color: "#94a3b8", dash: true },
        { label: "Decay curve", color: "#38bdf8" },
        { label: "Fisher density (right axis)", color: "#22c55e", dash: true },
        { label: "Gate 1 window", color: "#f59e0b" },
        { label: "Gate 2 window", color: "#a855f7" },
      ],
    });

    const maxRawSum = Math.max(2 * totalInfo, displayedSum) * 1.02;
    drawBarChart("tradeoffPlot", "tradeoffLegend", {
      labels: ["Gate 1 FI", "Gate 2 FI", "Sum"],
      values: [info1, info2, displayedSum],
      colors: ["#f59e0b", "#a855f7", "#22c55e"],
      yMax: maxRawSum,
      rightValues: [null, null, fValue],
      rightColor: "#ef4444",
      rightMarkerOnAxis: true,
      yRightMin: 0,
      yRightMax: Math.max(6, fValue * 1.4),
      yRightLabel: "F-value",
      rightLegendLabel: "Resulting F (right axis)",
      xLabel: "Fisher information contributions",
      yLabel: "Absolute Fisher information (ns^-2)",
    });

    let modeText;
    if (parallel) {
      modeText = "Parallel mode uses one shared photon stream, so overlapping gates are not allowed.";
    } else {
      modeText = "Sequential mode uses two separate acquisitions, so the two gates may overlap, but each gate only receives half of the total photons.";
    }

    if (overlapPrevented) {
      modeText += " Gate 2 was shifted right to avoid overlap in parallel mode.";
    }

    byId("gateSummary").textContent =
      modeText + " Gate 1 contributes " + info1.toFixed(3) + " ns^-2 of gated Fisher information, gate 2 contributes " +
      info2.toFixed(3) + " ns^-2, and the displayed sum is " + displayedSum.toFixed(3) + " ns^-2. " +
      "The FI bar-chart axis is locked to " + maxRawSum.toFixed(3) + " ns^-2 for the current lifetime. " +
      "The effective information used for the F-value is " + effectiveAbsInfo.toFixed(3) + " ns^-2, and the current F-value is " +
      fValue.toFixed(2) + ".";

    byId("gateMath").innerHTML =
      "<p><b>Live interpretation</b></p>" +
      "<div class='equation'>p<sub>k</sub>(&tau;) = &int; g<sub>k</sub>(t) p(t | &tau;) dt</div>" +
      "<div class='equation'>I<sub>gate k</sub> = [&part;p<sub>k</sub>(&tau;) / &part;&tau;]<sup>2</sup> / p<sub>k</sub>(&tau;)</div>" +
      "<div class='equation'>I<sub>gate 1</sub> = " + info1.toFixed(3) + " ns<sup>-2</sup>,&nbsp;&nbsp; I<sub>gate 2</sub> = " + info2.toFixed(3) + " ns<sup>-2</sup></div>" +
      "<div class='equation'>F = 1 / [&tau; sqrt(I<sub>used</sub>)] = " + fValue.toFixed(2) + "</div>" +
      "<p>This panel now uses derivatives of the integrated gate probabilities, which is the correct discrete-bin Fisher-information model for gated counting. Integrating the continuous-time Fisher-density curve inside a gate is only an approximation.</p>";
  }

  function updateAll() {
    updateControlLabels();
    updateFisher();
    updateMetrics();
    updateResolvingPower();
    updateGates();
  }

  function wireTabs() {
    const buttons = document.querySelectorAll(".tutorial-tab");
    const panels = document.querySelectorAll(".tutorial-panel");
    buttons.forEach((button) => {
      button.addEventListener("click", () => {
        buttons.forEach((node) => node.classList.remove("active"));
        panels.forEach((node) => node.classList.remove("active"));
        button.classList.add("active");
        const panel = byId(button.dataset.tabTarget);
        if (panel) panel.classList.add("active");
      });
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-control-id] input[type='range']").forEach((input) => {
      input.addEventListener("input", (event) => {
        lastTutorialInput = event.target.id;
        updateAll();
      });
    });
    document.querySelectorAll("select").forEach((input) => {
      input.addEventListener("change", (event) => {
        lastTutorialInput = event.target.id;
        updateAll();
      });
    });
    document.querySelectorAll("input[type='checkbox']").forEach((input) => {
      input.addEventListener("change", (event) => {
        lastTutorialInput = event.target.id;
        updateAll();
      });
    });
    wireTabs();
    applyTutorialTooltips();
    updateAll();
  });
})();
