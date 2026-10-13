import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useAgent } from "./AgentProvider.tsx";

export interface AgentControlBannerProps {
  className?: string;
}

/**
 * AgentControlBanner
 *
 * Prominent visual takeover indicator displayed when the UI Agent is actively
 * automating the screen (navigating, typing, clicking, filling in forms via GhostCursor).
 * Features a soft, slowly pulsing red banner at the top of the viewport signaling:
 * "Agent in Control — Please wait while automated actions complete".
 * Automatically disappears when actions finish and the agent returns to idle.
 */
export const AgentControlBanner: React.FC<AgentControlBannerProps> = ({ className = "" }) => {
  const { busy, status } = useAgent();
  const isAutomating = busy || status === "RUNNING" || status === "THINKING";

  return (
    <AnimatePresence>
      {isAutomating && (
        <motion.div
          key="agent-control-banner"
          role="alert"
          aria-live="assertive"
          data-testid="agent-control-banner"
          initial={{ opacity: 0, y: -20, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -20, scale: 0.95 }}
          transition={{ duration: 0.25, ease: "easeOut" }}
          className={`pointer-events-none fixed top-4 left-1/2 -translate-x-1/2 z-[9999] flex select-none items-center gap-2.5 rounded-full border border-red-500/60 bg-red-950/90 px-4 py-2 text-xs font-semibold text-red-100 shadow-[0_0_24px_rgba(239,68,68,0.35)] backdrop-blur-md animate-pulse ${className}`}
        >
          <span className="relative flex h-2.5 w-2.5 shrink-0">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-400 opacity-75" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.9)]" />
          </span>
          <span className="tracking-wide">
            Agent in Control — Please wait while automated actions complete
          </span>
        </motion.div>
      )}
    </AnimatePresence>
  );
};
