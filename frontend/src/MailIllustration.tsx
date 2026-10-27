/** Decorative, original vector artwork; the process is described in adjacent text. */
export function MailIllustration() {
  return (
    <div className="mail-art" aria-hidden="true">
      <svg viewBox="0 0 540 340" fill="none">
        <defs>
          <pattern
            id="iso-grid"
            width="48"
            height="28"
            patternUnits="userSpaceOnUse"
            patternTransform="matrix(1 .5 -1 .5 250 -80)"
          >
            <path d="M48 0H0V28" stroke="currentColor" strokeWidth=".7" />
          </pattern>
          <linearGradient
            id="tray-top"
            x1="200"
            y1="125"
            x2="350"
            y2="260"
            gradientUnits="userSpaceOnUse"
          >
            <stop stopColor="#fbfcf7" />
            <stop offset="1" stopColor="#cbd5c3" />
          </linearGradient>
          <linearGradient
            id="paper-top"
            x1="195"
            y1="44"
            x2="300"
            y2="203"
            gradientUnits="userSpaceOnUse"
          >
            <stop stopColor="#fff" />
            <stop offset="1" stopColor="#e8ede1" />
          </linearGradient>
          <filter id="art-shadow" x="-60%" y="-60%" width="240%" height="260%">
            <feGaussianBlur stdDeviation="12" />
          </filter>
        </defs>
        <path d="M0 0H540V340H0Z" fill="url(#iso-grid)" opacity=".22" />
        <ellipse
          cx="288"
          cy="275"
          rx="126"
          ry="28"
          fill="#425d43"
          opacity=".12"
          filter="url(#art-shadow)"
        />
        <path
          d="m83 221 72-41 50 28m164-32 65-37 53 30"
          stroke="#8aa385"
          strokeDasharray="4 5"
        />
        <g className="art-tray">
          <path
            d="m158 192 141-81 141 81-141 83Z"
            fill="url(#tray-top)"
            stroke="#8da085"
          />
          <path
            d="m158 192 141 82v26l-141-82Z"
            fill="#c1cfb8"
            stroke="#8da085"
          />
          <path
            d="m299 274 141-82v26l-141 82Z"
            fill="#8da482"
            stroke="#7d9573"
          />
          <path
            d="m177 189 122-70 122 70-122 72Z"
            fill="#b2c2a7"
            stroke="#8da085"
          />
          <path d="m179 189 120 70 120-70" stroke="#f6f8ef" strokeWidth="2" />
          <path d="m270 270 22 12v8l-22-12Z" fill="#f2f4e9" opacity=".8" />
        </g>
        <g className="art-letter">
          <path
            d="m183 152 114-65 107 62v10l-114 66-107-62Z"
            fill="#ced8c4"
            stroke="#9baa90"
          />
          <path
            d="m183 152 114-65 107 62-114 66Z"
            fill="url(#paper-top)"
            stroke="#9baa90"
          />
          <path
            d="m183 152 112 12 109-15m-109 15-5 51m-107-63 104-9 117 6"
            stroke="#c0cbb6"
          />
        </g>
        <g className="art-document">
          <path
            d="m191 102 100-58 105 61v9l-100 58-105-61Z"
            fill="#d8dfce"
            stroke="#a8b59c"
          />
          <path
            d="m191 102 100-58 105 61-100 58Z"
            fill="url(#paper-top)"
            stroke="#a8b59c"
          />
          <path d="m219 101 32-19 19 11-32 19Z" fill="#668664" />
          <path
            d="m251 119 66-38m-53 46 66-38m-53 46 44-26"
            stroke="#bac8b0"
            strokeWidth="4"
            strokeLinecap="round"
          />
          <path d="m329 129 26-15 15 9-26 15Z" fill="#e8cfa4" />
        </g>
        <g className="art-seal">
          <path d="m369 68 26-15 26 15v29l-26 15-26-15Z" fill="#2e624b" />
          <path d="m369 68 26 15 26-15m-26 15v29" stroke="#64967c" />
          <path
            d="m382 66 8 5 15-9"
            stroke="#fff"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </g>
        <g>
          <path d="m79 202 23-13 23 13v25l-23 14-23-14Z" fill="#d8b77c" />
          <path d="m79 202 23 14 23-14m-23 14v25" stroke="#ecd8b1" />
          <path d="m91 201 11 7 11-7-11-6Z" stroke="#fff9eb" />
        </g>
        <circle cx="151" cy="90" r="3" fill="#8ca582" />
        <path
          d="M433 246h10m-5-5v10M119 144h8m-4-4v8"
          stroke="#94a98a"
          strokeWidth="1.5"
        />
      </svg>
      <div className="art-label art-label-source">
        <span className="art-label-dot" />
        Policy evidence attached
      </div>
      <div className="art-label art-label-review">
        <span>✓</span> Ready for your review
      </div>
      <span className="art-caption">
        A THOUGHTFUL PATH FROM INBOX TO ANSWER
      </span>
    </div>
  );
}
