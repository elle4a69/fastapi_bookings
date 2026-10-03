import { Moon, Sun, Laptop, Check, Palette } from "lucide-react";
import { useTheme } from "next-themes";
import { useColorTheme } from "./theme-provider";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const { colorTheme, setColorTheme, availableThemes } = useColorTheme();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Select theme and appearance"
          className="relative h-8 w-8 hover:bg-accent cursor-pointer"
        >
          <Sun className="h-4 w-4 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
          <Moon className="absolute h-4 w-4 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
          {/* Subtle color theme indicator pip */}
          <span
            className="absolute bottom-1 right-1 h-1.5 w-1.5 rounded-full ring-1 ring-background"
            style={{
              backgroundColor:
                availableThemes.find((t) => t.id === colorTheme)?.previewColor || "currentColor",
            }}
          />
          <span className="sr-only">Toggle theme and appearance</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56 p-1.5">
        <DropdownMenuLabel className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-muted-foreground px-2 py-1">
          <Palette className="h-3 w-3" />
          <span>Luxury Palette</span>
        </DropdownMenuLabel>

        {availableThemes.map((t) => {
          const isActive = colorTheme === t.id;
          return (
            <DropdownMenuItem
              key={t.id}
              onClick={() => setColorTheme(t.id)}
              className={`flex items-center justify-between gap-2 px-2 py-1.5 text-xs rounded-md cursor-pointer transition-colors ${
                isActive ? "bg-accent/80 font-semibold text-foreground" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <div className="flex items-center gap-2">
                <span
                  className="h-3 w-3 rounded-full shrink-0 shadow-xs border border-white/20"
                  style={{ backgroundColor: t.previewColor }}
                />
                <div className="flex flex-col">
                  <span>{t.name}</span>
                  <span className="text-[10px] text-muted-foreground/80 font-normal">
                    {t.description}
                  </span>
                </div>
              </div>
              {isActive && <Check className="h-3.5 w-3.5 text-primary shrink-0" />}
            </DropdownMenuItem>
          );
        })}

        <DropdownMenuSeparator className="my-1.5" />

        <DropdownMenuLabel className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground px-2 py-1">
          Display Mode
        </DropdownMenuLabel>

        <DropdownMenuItem
          onClick={() => setTheme("light")}
          className={`flex items-center justify-between px-2 py-1.5 text-xs rounded-md cursor-pointer ${
            theme === "light" ? "bg-accent/80 font-semibold text-foreground" : "text-muted-foreground hover:text-foreground"
          }`}
        >
          <div className="flex items-center gap-2">
            <Sun className="h-3.5 w-3.5" />
            <span>Light</span>
          </div>
          {theme === "light" && <Check className="h-3.5 w-3.5 text-primary shrink-0" />}
        </DropdownMenuItem>

        <DropdownMenuItem
          onClick={() => setTheme("dark")}
          className={`flex items-center justify-between px-2 py-1.5 text-xs rounded-md cursor-pointer ${
            theme === "dark" ? "bg-accent/80 font-semibold text-foreground" : "text-muted-foreground hover:text-foreground"
          }`}
        >
          <div className="flex items-center gap-2">
            <Moon className="h-3.5 w-3.5" />
            <span>Dark</span>
          </div>
          {theme === "dark" && <Check className="h-3.5 w-3.5 text-primary shrink-0" />}
        </DropdownMenuItem>

        <DropdownMenuItem
          onClick={() => setTheme("system")}
          className={`flex items-center justify-between px-2 py-1.5 text-xs rounded-md cursor-pointer ${
            theme === "system" ? "bg-accent/80 font-semibold text-foreground" : "text-muted-foreground hover:text-foreground"
          }`}
        >
          <div className="flex items-center gap-2">
            <Laptop className="h-3.5 w-3.5" />
            <span>System</span>
          </div>
          {theme === "system" && <Check className="h-3.5 w-3.5 text-primary shrink-0" />}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
