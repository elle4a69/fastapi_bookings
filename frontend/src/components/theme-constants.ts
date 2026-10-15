export type ColorTheme = "crimson" | "midnight" | "emerald" | "logto";

export interface ColorThemeOption {
  id: ColorTheme;
  name: string;
  description: string;
  previewColor: string;
}

export const COLOR_THEMES: ColorThemeOption[] = [
  {
    id: "midnight",
    name: "Midnight Slate",
    description: "Deep Navy & Electric Blue",
    previewColor: "#3b82f6",
  },
  {
    id: "emerald",
    name: "Emerald Luxe",
    description: "Obsidian Base & Vibrant Emerald",
    previewColor: "#10b981",
  },
  {
    id: "crimson",
    name: "BookMe Crimson",
    description: "Velvet Magenta & Modern Crimson",
    previewColor: "#c2185b",
  },
  {
    id: "logto",
    name: "Logto Violet",
    description: "Electric Purple & Obsidian Dark",
    previewColor: "#6c47ff",
  },
];

export const COLOR_THEME_STORAGE_KEY = "bookme_color_theme";

export const VALID_COLOR_THEMES = new Set<ColorTheme>(["midnight", "emerald", "crimson", "logto"]);

export function isValidColorTheme(theme: string | null): theme is ColorTheme {
  return theme !== null && VALID_COLOR_THEMES.has(theme as ColorTheme);
}
