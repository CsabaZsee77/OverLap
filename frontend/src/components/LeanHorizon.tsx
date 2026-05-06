interface Props {
  leanRight: number | null  // fok, pozitív
  leanLeft:  number | null  // fok, pozitív
  size?:     number
}

export default function LeanHorizon({ leanRight, leanLeft, size = 130 }: Props) {
  const cx = size / 2
  const cy = size / 2
  const r  = size * 0.40

  // Melyik oldal a nagyobb → arra dőlünk
  const right = leanRight ?? 0
  const left  = leanLeft  ?? 0
  const angle = right >= left ? right : -left   // + = jobb dőlés

  // A háttér (ég+föld) az angle negatívjával forog
  const bgRot = -angle

  // Szögjelölők: 10°, 20°, 30°, 45° mindkét oldalon
  const marks = [10, 20, 30, 45]

  const clipId = `horizClip-${size}`

  return (
    <svg width={size} height={size} style={{ display: 'block' }}>
      <defs>
        <clipPath id={clipId}>
          <circle cx={cx} cy={cy} r={r} />
        </clipPath>
      </defs>

      {/* Keretkarika */}
      <circle cx={cx} cy={cy} r={r + 3} fill="#0d0f18" />
      <circle cx={cx} cy={cy} r={r}     fill="#0d0f18" />

      {/* Forgó ég + föld */}
      <g transform={`rotate(${bgRot} ${cx} ${cy})`} clipPath={`url(#${clipId})`}>
        {/* Ég */}
        <rect x={cx - r} y={cy - r} width={2 * r} height={r}
              fill="#0e2d4a" />
        {/* Föld */}
        <rect x={cx - r} y={cy}     width={2 * r} height={r}
              fill="#3a2010" />
        {/* Horizont vonal */}
        <line x1={cx - r} y1={cy} x2={cx + r} y2={cy}
              stroke="#e0e0e0" strokeWidth={1.5} />

        {/* Dőlésjelölők az ég oldalán */}
        {marks.map(deg => {
          const rad    = (deg * Math.PI) / 180
          const tickX  = cx + r * Math.sin(rad)
          const tickY  = cy - r * Math.cos(rad)
          const tickX2 = cx + (r - (deg % 15 === 0 ? 8 : 5)) * Math.sin(rad)
          const tickY2 = cy - (r - (deg % 15 === 0 ? 8 : 5)) * Math.cos(rad)
          return (
            <g key={deg}>
              <line x1={tickX} y1={tickY} x2={tickX2} y2={tickY2}
                    stroke="#a0a8b0" strokeWidth={1} />
              <line x1={cx - r * Math.sin(rad)} y1={cy - r * -Math.cos(rad)}
                    x2={cx - (r - (deg % 15 === 0 ? 8 : 5)) * Math.sin(rad)}
                    y2={cy - (r - (deg % 15 === 0 ? 8 : 5)) * -Math.cos(rad)}
                    stroke="#a0a8b0" strokeWidth={1} />
            </g>
          )
        })}
      </g>

      {/* Fix referencia szárny (a pilóta nézetéből fix) */}
      <g>
        {/* Bal szárny */}
        <rect x={cx - r * 0.65} y={cy - 1} width={r * 0.3}  height={2.5}
              rx={1} fill="#e8e8e8" />
        {/* Jobb szárny */}
        <rect x={cx + r * 0.35} y={cy - 1} width={r * 0.3}  height={2.5}
              rx={1} fill="#e8e8e8" />
        {/* Középső pont */}
        <circle cx={cx} cy={cy} r={3} fill="#e8e8e8" />
        <circle cx={cx} cy={cy} r={1.5} fill="#0d0f18" />
      </g>

      {/* Külső szögskála (fix, a keret szélén) */}
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="#2a2d3a" strokeWidth={1.5} />

      {/* Csúcsérték felirat */}
      <text x={cx} y={size - 5} textAnchor="middle"
            fill={angle !== 0 ? '#22d3ee' : '#3a3f50'} fontSize={10} fontFamily="monospace">
        {angle !== 0
          ? `${Math.abs(angle).toFixed(1)}° ${right >= left ? 'R' : 'L'}`
          : '— °'}
      </text>
    </svg>
  )
}
