import type { CSSProperties } from "react";

const paths = {
  compose:
    "M12 5H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-7M16 3a2.12 2.12 0 0 1 3 3l-9 9-4 1 1-4Z",
  inbox: "m3 12 4-8h10l4 8v7a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1Zm0 0h5l2 3h4l2-3h5",
  activity: "M3 12h4l3-8 4 16 3-8h4",
  chart: "M4 3v17h17M8 15v-4m5 4V7m5 8v-6",
  arrow: "M5 12h14m-5-5 5 5-5 5",
  check: "m5 12 4 4L19 6",
  shield: "m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6Zm-4 9 3 3 5-6",
  mail: "M3 5h18v14H3Zm0 0 9 8 9-8",
  layers: "m12 3 10 5-10 5L2 8Zm-9 9 9 5 9-5M3 16l9 5 9-5",
  sun: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Zm0-6v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5",
} as const;

export function Icon({
  name,
  size = 20,
  style,
}: {
  name: keyof typeof paths;
  size?: number;
  style?: CSSProperties;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      style={style}
    >
      <path d={paths[name]} />
    </svg>
  );
}
