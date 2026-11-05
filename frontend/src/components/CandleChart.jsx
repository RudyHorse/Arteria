import React, { useEffect, useRef, useState } from "react";

const fmt = (v) => String(Math.round(v * 100) / 100);

function CandleChart({ data }) {
  const wrapRef = useRef(null);
  const [width, setWidth] = useState(600);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const measure = () => setWidth(Math.max(el.clientWidth || 600, 300));
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, []);

  const nameW = 130;
  const leftPad = 44;
  const rightPad = 44;
  const rowH = 44;
  const topPad = 12;
  const bottomPad = 8;
  const plotW = Math.max(width - nameW - leftPad - rightPad, 120);
  const x0 = nameW + leftPad;
  const x1 = x0 + plotW;
  const height = topPad + data.length * rowH + bottomPad;

  return (
    <div ref={wrapRef}>
      <svg width="100%" height={height} style={{ display: "block" }}>
        {data.map((d, i) => {
          const cy = topPad + i * rowH + rowH / 2 - 7;
          const out =
            d.abnormal ||
            (d.refMin != null && d.result < d.refMin) ||
            (d.refMax != null && d.result > d.refMax);

          const vals = [d.refMin, d.refMax, d.result].filter((v) => v != null);
          let lo = Math.min(...vals);
          let hi = Math.max(...vals);
          if (hi - lo < 1e-9) {
            lo -= 0.5;
            hi += 0.5;
          }

          const px = (v) => x0 + ((v - lo) / (hi - lo)) * plotW;
          const xMin = d.refMin != null ? px(d.refMin) : null;
          const xMax = d.refMax != null ? px(d.refMax) : null;
          const xRes = px(d.result);
          const clampLabel = (x) => Math.min(Math.max(x, x0 + 20), x1 - 20);

          const oneSided = d.refMin == null || d.refMax == null;
          const barFrom = d.refMin != null ? xMin : x0;
          const barTo = d.refMax != null ? xMax : x1;

          return (
            <g key={i}>
              <line x1={x0} y1={cy + rowH / 2 + 9} x2={x1} y2={cy + rowH / 2 + 9} stroke="#f1f3f5" />

              <text x={nameW - 8} y={cy + 3} textAnchor="end" fontSize={12} fill="#495057">
                {d.name}
              </text>
              {d.unit && (
                <text x={nameW - 8} y={cy + 16} textAnchor="end" fontSize={10} fill="#adb5bd">
                  {d.unit}
                </text>
              )}

              <line x1={x0} y1={cy} x2={x1} y2={cy} stroke="#e9ecef" strokeWidth={1} />
              <line x1={barFrom} y1={cy} x2={barTo} y2={cy}
                stroke={oneSided ? "#b8c8da" : "#9db2c8"}
                strokeWidth={5}
                strokeLinecap="round"
                strokeDasharray={oneSided ? "6 4" : undefined} />

              {d.refMin != null && (
                <>
                  <line x1={xMin} y1={cy - 5} x2={xMin} y2={cy + 5} stroke="#6c8aa8" strokeWidth={1.5} />
                  <text x={clampLabel(xMin)} y={cy + 21} textAnchor="middle" fontSize={10} fill="#5a7188">
                    {fmt(d.refMin)}
                  </text>
                </>
              )}
              {d.refMax != null && (
                <>
                  <line x1={xMax} y1={cy - 5} x2={xMax} y2={cy + 5} stroke="#6c8aa8" strokeWidth={1.5} />
                  <text x={clampLabel(xMax)} y={cy + 21} textAnchor="middle" fontSize={10} fill="#5a7188">
                    {fmt(d.refMax)}
                  </text>
                </>
              )}

              <polygon
                points={`${xRes},${cy - 6} ${xRes + 6},${cy} ${xRes},${cy + 6} ${xRes - 6},${cy}`}
                fill={out ? "#dc3545" : "#198754"}
                stroke="#fff"
                strokeWidth={1}
              />
              <text x={clampLabel(xRes)} y={cy - 13} textAnchor="middle" fontSize={11} fontWeight={600}
                fill={out ? "#dc3545" : "#198754"}>
                {fmt(d.result)}
              </text>

              <title>
                {`${d.name}: ${d.result}${d.unit ? " " + d.unit : ""}` +
                  ` (ref ${d.refMin ?? "?"} – ${d.refMax ?? "?"}${d.unit ? " " + d.unit : ""})`}
              </title>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

export default CandleChart;
