import { createContext, useContext, useEffect, useState, type ComponentProps } from "react";
import { ThemeProvider as NextThemesProvider } from "next-themes";

export type ColorTheme = "crimson" | "midnight" | "emerald";

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
];

interface ColorThemeContextType {
  colorTheme: ColorTheme;
  setColorTheme: (theme: ColorTheme) => void;
  availableThemes: ColorThemeOption[];
}

const ColorThemeContext = createContext<ColorThemeContextType | undefined>(undefined);

const COLOR_THEME_STORAGE_KEY = "bookme_color_theme";

export function ThemeProvider({ children, ...props }: ComponentProps<typeof NextThemesProvider>) {
  const [colorTheme, setColorThemeState] = useState<ColorTheme>(() => {
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem(COLOR_THEME_STORAGE_KEY);
      if (stored === "midnight" || stored === "emerald" || stored === "crimson") {
        return stored;
      }
    }
    return "crimson";
  });

  const setColorTheme = (theme: ColorTheme) => {
    setColorThemeState(theme);
    if (typeof window !== "undefined") {
      localStorage.setItem(COLOR_THEME_STORAGE_KEY, theme);
    }
  };

  useEffect(() => {
    if (typeof document === "undefined") return;
    const root = document.documentElement;
    // Clear existing color theme classes
    root.classList.remove(
      "theme-crimson",
      "theme-midnight",
      "theme-emerald",
      "crimson",
      "midnight",
      "emerald"
    );
    // Apply selected theme class and data-theme
    root.classList.add(`theme-${colorTheme}`, colorTheme);
    root.setAttribute("data-theme", colorTheme);
  }, [colorTheme]);

  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
      {...props}
    >
      <ColorThemeContext.Provider value={{ colorTheme, setColorTheme, availableThemes: COLOR_THEMES }}>
        {children}
      </ColorThemeContext.Provider>
    </NextThemesProvider>
  );
}

export function useColorTheme() {
  const context = useContext(ColorThemeContext);
  if (!context) {
    throw new Error("useColorTheme must be used within a ThemeProvider");
  }
  return context;
}
