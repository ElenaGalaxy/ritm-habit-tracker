// Набор линейных иконок. Все SVG статичны и не содержат пользовательских данных.
const P = {
  today: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.42 1.42M17.66 17.66l1.42 1.42M2 12h2M20 12h2M4.93 19.07l1.42-1.42M17.66 6.34l1.42-1.42"/>',
  habits: '<path d="M9 6h11M9 12h11M9 18h11"/><path d="M4 6l1.2 1.2L7.5 4.5M4 12l1.2 1.2L7.5 10.5M4 18l1.2 1.2L7.5 16.5"/>',
  check: '<path d="M20 6L9 17l-5-5"/>',
  checkCircle: '<circle cx="12" cy="12" r="9"/><path d="M8.5 12.2l2.3 2.3 4.7-5"/>',
  calendar: '<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M8 3v4M16 3v4M3 10h18"/><path d="M8 14h.01M12 14h.01M16 14h.01M8 18h.01M12 18h.01"/>',
  stats: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
  ai: '<path d="M12 3l1.7 4.3L18 9l-4.3 1.7L12 15l-1.7-4.3L6 9l4.3-1.7L12 3z"/><path d="M19 14l.9 2.1L22 17l-2.1.9L19 20l-.9-2.1L16 17l2.1-.9L19 14z"/><path d="M5 14l.7 1.6L7.5 16l-1.8.7L5 18.5l-.7-1.8L2.5 16l1.8-.4L5 14z"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 00.34 1.87l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.7 1.7 0 00-1.87-.34 1.7 1.7 0 00-1 1.55V21a2 2 0 11-4 0v-.09a1.7 1.7 0 00-1.1-1.55 1.7 1.7 0 00-1.88.34l-.06.06a2 2 0 11-2.82-2.83l.06-.06A1.7 1.7 0 004.6 15a1.7 1.7 0 00-1.55-1H3a2 2 0 110-4h.09A1.7 1.7 0 004.6 9a1.7 1.7 0 00-.34-1.87l-.06-.06a2 2 0 112.83-2.83l.06.06A1.7 1.7 0 009 4.6a1.7 1.7 0 001-1.55V3a2 2 0 114 0v.09a1.7 1.7 0 001 1.55 1.7 1.7 0 001.87-.34l.06-.06a2 2 0 112.83 2.83l-.06.06A1.7 1.7 0 0019.4 9c.14.6.68 1.02 1.3 1.02H21a2 2 0 110 4h-.09a1.7 1.7 0 00-1.51.98z"/>',
  docs: '<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><path d="M14 2v6h6M8 13h8M8 17h5"/>',
  admin: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="M9 12l2 2 4-4"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  minus: '<path d="M5 12h14"/>',
  edit: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z"/>',
  pause: '<path d="M9 4v16M15 4v16"/>',
  play: '<path d="M7 4l13 8-13 8z"/>',
  archive: '<rect x="3" y="4" width="18" height="4" rx="1"/><path d="M5 8v11a2 2 0 002 2h10a2 2 0 002-2V8M10 12h4"/>',
  trash: '<path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14M10 10v6M14 10v6"/>',
  more: '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
  close: '<path d="M18 6L6 18M6 6l12 12"/>',
  chevronLeft: '<path d="M15 18l-6-6 6-6"/>',
  chevronRight: '<path d="M9 6l6 6-6 6"/>',
  chevronDown: '<path d="M6 9l6 6 6-6"/>',
  flame: '<path d="M12 22c4.4 0 7-2.9 7-6.7 0-3.2-1.9-5.8-4.1-8.3-.5-.6-1.4-.2-1.4.6 0 1.1-.3 2.2-1 3.1-.6-2.7-2.3-5.2-4.6-6.5-.7-.4-1.5.2-1.4 1 .3 3-1.5 5-2.9 7.1-1 1.5-1.6 3-1.6 4.7C2 19 5.5 22 12 22z"/>',
  snow: '<path d="M12 2v20M4.5 6.5l15 11M19.5 6.5l-15 11"/><path d="M9 4l3 3 3-3M9 20l3-3 3 3M4.2 10L8 11l-.8-4M19.8 14L16 13l.8 4M4.2 14L8 13l-.8 4M19.8 10L16 11l.8-4"/>',
  trophy: '<path d="M8 3h8v5a4 4 0 11-8 0z"/><path d="M8 5H4v2a4 4 0 004 4M16 5h4v2a4 4 0 01-4 4M12 12v5M8 21h8M9 17h6v4H9z"/>',
  target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.5"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  bell: '<path d="M18 8a6 6 0 10-12 0c0 7-3 8-3 8h18s-3-1-3-8"/><path d="M10 21h4"/>',
  telegram: '<path d="M21.5 4.5L2.5 12l5.5 2 2 6 3-4 5 3.5z"/><path d="M8 14l9-7-6 9"/>',
  download: '<path d="M12 3v12M7 10l5 5 5-5M4 21h16"/>',
  upload: '<path d="M12 21V9M7 14l5-5 5 5M4 3h16"/>',
  file: '<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><path d="M14 2v6h6"/>',
  table: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M9 4v16"/>',
  sparkles: '<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z"/><path d="M19 16l1 2.5 2.5 1-2.5 1-1 2.5-1-2.5-2.5-1 2.5-1z"/>',
  alert: '<path d="M10.3 3.6L1.8 18a2 2 0 001.7 3h17a2 2 0 001.7-3L13.7 3.6a2 2 0 00-3.4 0z"/><path d="M12 9v4M12 17h.01"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
  undo: '<path d="M3 7v6h6"/><path d="M3.5 13a9 9 0 101.6-6.4L3 9"/>',
  refresh: '<path d="M21 12a9 9 0 11-2.6-6.4"/><path d="M21 3v6h-6"/>',
  arrowRight: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  external: '<path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><path d="M15 3h6v6M10 14L21 3"/>',
  logout: '<path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/><path d="M16 17l5-5-5-5M21 12H9"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path d="M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0116 0"/>',
  lock: '<rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 018 0v3"/>',
  mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/>',
  eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/>',
  eyeOff: '<path d="M3 3l18 18"/><path d="M10.6 6.3A10 10 0 0112 6c6.5 0 10 6 10 6a17 17 0 01-3 3.7M6.3 6.3A17 17 0 002 12s3.5 7 10 7a9.7 9.7 0 004.2-.9"/><path d="M9.9 9.9a3 3 0 004.2 4.2"/>',
  camera: '<path d="M3 8h3l2-3h8l2 3h3v12H3z"/><circle cx="12" cy="13" r="4"/>',
  pen: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z"/>',
  walk: '<circle cx="13" cy="4" r="2"/><path d="M11 21l2-6 3 3 3-2M13 10l-1 5-3 1-2 5M13 10l4 3 3-1M9 8l3 2 2-1"/>',
  water: '<path d="M12 2.7S5.5 10.4 5.5 15a6.5 6.5 0 0013 0c0-4.6-6.5-12.3-6.5-12.3z"/><path d="M9 16a3 3 0 003 3"/>',
  phone: '<rect x="6" y="2" width="12" height="20" rx="3"/><path d="M10 5h4M11 19h2"/>',
  book: '<path d="M4 19.5A2.5 2.5 0 016.5 17H20V4a2 2 0 00-2-2H6.5A2.5 2.5 0 004 4.5z"/><path d="M4 19.5A2.5 2.5 0 006.5 22H20v-5"/>',
  run: '<circle cx="15" cy="4" r="2"/><path d="M9 21l3-6 3 2 4-3M6 12l3-3 4 2 3 1M12 15l-2 6M9 9l3-2"/>',
  heart: '<path d="M20.8 5.6a5.5 5.5 0 00-7.8 0L12 6.6l-1-1a5.5 5.5 0 00-7.8 7.8l1 1L12 22l7.8-7.6 1-1a5.5 5.5 0 000-7.8z"/>',
  leaf: '<path d="M4 20c8 1 16-5 16-16-8 0-16 5-16 16z"/><path d="M4 20c2-6 6-10 12-12"/>',
  coffee: '<path d="M4 8h13v6a5 5 0 01-5 5H9a5 5 0 01-5-5z"/><path d="M17 9h2a3 3 0 010 6h-2M6 2v3M10 2v3M14 2v3"/>',
  dumbbell: '<path d="M6 7v10M3 10v4M18 7v10M21 10v4M6 12h12"/>',
  meditate: '<circle cx="12" cy="5" r="2"/><path d="M8 21l4-5 4 5M12 16V9M6 12l6-2 6 2M4 17c2 1 5 1 8-1 3 2 6 2 8 1"/>',
  spark: '<path d="M12 2l2.4 6.5L21 11l-6.6 2.5L12 20l-2.4-6.5L3 11l6.6-2.5z"/>',
  list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
  filter: '<path d="M3 5h18l-7 8v6l-4 2v-8z"/>',
  shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
  zap: '<path d="M13 2L3 14h7l-1 8 11-13h-7z"/>',
  lockSmall: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 018 0v4"/>',
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3.5 3 14 0 18M12 3c-3 3.5-3 14 0 18"/>',
};

export function icon(name, cls = "") {
  const path = P[name] || P.spark;
  const classes = cls ? ` class="${cls}"` : "";
  return `<svg${classes} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${path}</svg>`;
}

export function habitIcon(name) {
  return icon(P[name] ? name : "spark");
}

export const ICON_CHOICES = [
  "spark", "camera", "pen", "walk", "water", "moon", "phone", "book",
  "run", "sun", "leaf", "heart", "target", "coffee", "dumbbell", "meditate",
];

export const COLOR_CHOICES = [
  "#2E685F", "#4F7D70", "#5E8794", "#7A8F6C", "#AD8557",
  "#6D7F8A", "#7D6F7A", "#3F6E6B", "#97705D", "#5A6E7A",
];
