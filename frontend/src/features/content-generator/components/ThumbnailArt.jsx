import { useId } from "react";

import { splitHeadline } from "../lib/splitHeadline";
import { THUMBNAIL_PALETTES } from "../lib/thumbnailPalettes";

// A placeholder thumbnail drawn in SVG: a gradient, a few shapes and the
// headline. It stands in for the picture the image model will return later.
function ThumbnailArt({ headline, palette }) {
  const colors = THUMBNAIL_PALETTES[palette % THUMBNAIL_PALETTES.length];
  const lines = splitHeadline(headline);

  // Each drawing needs its own gradient id, or they would all share the first
  // one on the page. useId can contain characters that break url(#...).
  const gradientId = `${useId().replace(/[^a-zA-Z0-9_-]/g, "")}-bg`;

  return (
    <svg
      className="cg-art"
      viewBox="0 0 320 180"
      role="img"
      aria-label={`Thumbnail concept: ${headline}`}
    >
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor={colors.from} />
          <stop offset="1" stopColor={colors.to} />
        </linearGradient>
      </defs>
      <rect width="320" height="180" fill={`url(#${gradientId})`} />
      <circle cx="268" cy="62" r="74" fill="#ffffff" fillOpacity="0.09" />
      <circle cx="300" cy="150" r="52" fill="#000000" fillOpacity="0.14" />
      <rect x="220" y="60" width="84" height="56" rx="9" fill="#ffffff" fillOpacity="0.16" />
      <path d="M252 75v26l21-13z" fill="#ffffff" fillOpacity="0.85" />

      {lines.map((line, index) => (
        <text
          key={`${index}-${line}`}
          x="16"
          y={46 + index * 36}
          fontSize="28"
          fontWeight="900"
          fontStyle="italic"
          fill={index === 0 ? "#ffffff" : colors.accent}
        >
          {line}
        </text>
      ))}
    </svg>
  );
}

export default ThumbnailArt;
