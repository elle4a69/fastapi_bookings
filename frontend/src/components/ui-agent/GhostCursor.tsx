import { motion, AnimatePresence } from "framer-motion";
import { MousePointer2 } from "lucide-react";

export interface CursorState {
  x: number;
  y: number;
  visible: boolean;
  pulse?: boolean;
}

export interface HighlightState {
  x: number;
  y: number;
  w: number;
  h: number;
  label?: string;
}

export interface GhostCursorProps {
  cursor?: CursorState;
  highlight?: HighlightState | null;
}

const spring = { type: "spring" as const, stiffness: 140, damping: 22 };

export const GhostCursor = ({
  cursor = { x: 0, y: 0, visible: false, pulse: false },
  highlight = null,
}: GhostCursorProps) => (
  <div data-agent-ignore className="pointer-events-none fixed inset-0 z-[9999]">
    <AnimatePresence>
      {highlight && (
        <motion.div
          data-testid="agent-highlight"
          key="hl"
          className="agent-highlight"
          initial={{ opacity: 0 }}
          animate={{
            opacity: 1,
            left: highlight.x - 4,
            top: highlight.y - 4,
            width: highlight.w + 8,
            height: highlight.h + 8,
          }}
          exit={{ opacity: 0 }}
          transition={spring}
        >
          {highlight.label && (
            <span className="agent-highlight-tag">Agent · {highlight.label}</span>
          )}
        </motion.div>
      )}
    </AnimatePresence>
    {cursor.visible && (
      <motion.div
        data-testid="agent-ghost-cursor"
        className="absolute left-0 top-0"
        initial={false}
        animate={{ x: cursor.x, y: cursor.y }}
        transition={spring}
      >
        <span className={`agent-cursor-glow ${cursor.pulse ? "agent-cursor-pulse" : ""}`} />
        <MousePointer2 className="relative h-6 w-6 fill-sky-400 text-sky-100 drop-shadow-[0_0_8px_rgba(56,189,248,0.9)]" />
      </motion.div>
    )}
  </div>
);
