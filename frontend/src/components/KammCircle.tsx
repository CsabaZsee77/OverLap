interface Props {
  peakG:     number | null
  peakAngle: number | null  // fok, 0=fékezés (felül), 90=jobb kanyar
  size?:     number
}

export default function KammCircle({ peakG, peakAngle, size = 130 }: Props) {
  const cx  = size / 2
  const cy  = size / 2
  const r1g = size * 0.37          // 1G referencia kör sugara

  // Csúcspont pozíciója
  let px = cx, py = cy
  if (peakG != null && peakAngle != null) {
    const rad = (peakAngle * Math.PI) / 180
    const d   = r1g * Math.min(peakG, 1.35)
    px = cx + d * Math.sin(rad)
    py = cy - d * Math.cos(rad)
  }

  const peakR = peakG != null ? r1g * Math.min(peakG, 1.35) : 0

  return (
    <svg width={size} height={size} style={{ display: 'block' }}>
      {/* Háttér */}
      <circle cx={cx} cy={cy} r={size * 0.46} fill="#0d0f18" />

      {/* Rács */}
      <line x1={cx - r1g * 1.1} y1={cy} x2={cx + r1g * 1.1} y2={cy}
            stroke="#2a2d3a" strokeWidth={0.8} />
      <line x1={cx} y1={cy - r1g * 1.1} x2={cx} y2={cy + r1g * 1.1}
            stroke="#2a2d3a" strokeWidth={0.8} />

      {/* 0.5G segédkör */}
      <circle cx={cx} cy={cy} r={r1g * 0.5}
              fill="none" stroke="#2a2d3a" strokeWidth={0.8} />

      {/* 1G határkör (szaggatott) */}
      <circle cx={cx} cy={cy} r={r1g}
              fill="none" stroke="#4a4f60" strokeWidth={1.2} strokeDasharray="5,3" />

      {/* Mért csúcs-G kör */}
      {peakG != null && peakG > 0.02 && (
        <circle cx={cx} cy={cy} r={peakR}
                fill="none" stroke="#f97316" strokeWidth={1.8} opacity={0.7} />
      )}

      {/* Csúcspont */}
      {peakG != null && peakAngle != null && (
        <>
          <line x1={cx} y1={cy} x2={px} y2={py}
                stroke="#f97316" strokeWidth={0.8} opacity={0.4} />
          <circle cx={px} cy={py} r={4.5} fill="#f97316" />
        </>
      )}

      {/* Középpont */}
      <circle cx={cx} cy={cy} r={2.5} fill="#555" />

      {/* Feliratok */}
      <text x={cx}        y={cy - r1g * 1.05 - 3} textAnchor="middle" fill="#3a3f50" fontSize={7}>+LON</text>
      <text x={cx}        y={cy + r1g * 1.05 + 9} textAnchor="middle" fill="#3a3f50" fontSize={7}>−LON</text>
      <text x={cx - r1g * 1.1 - 2} y={cy + 3}    textAnchor="end"    fill="#3a3f50" fontSize={7}>L</text>
      <text x={cx + r1g * 1.1 + 2} y={cy + 3}    textAnchor="start"  fill="#3a3f50" fontSize={7}>R</text>

      {/* Értékcímke */}
      <text x={cx} y={size - 5} textAnchor="middle"
            fill={peakG != null ? '#f97316' : '#3a3f50'} fontSize={10} fontFamily="monospace">
        {peakG != null ? `${peakG.toFixed(2)} G` : '— G'}
      </text>
    </svg>
  )
}
