import { useState } from 'react';
import { HelpCircle, X, CalendarClock, RotateCcw, CalendarOff, Lightbulb } from 'lucide-react';
import { Button } from '@/components/ui/button';

export function SpecialDaysInfoModal() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium text-muted-foreground bg-muted/30 border border-border/30 hover:bg-muted/60 hover:text-foreground transition-all duration-150"
        title="Learn about Special Days and Recurring schedules"
      >
        <HelpCircle className="h-3.5 w-3.5" />
        Special Days
      </button>
      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          onClick={(e) => { if (e.target === e.currentTarget) setOpen(false); }}
        >
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
          <div className="relative z-10 w-full max-w-md bg-card border border-border rounded-2xl shadow-2xl overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-border/60 bg-muted/20">
              <div className="flex items-center gap-2">
                <CalendarClock className="h-5 w-5 text-primary" />
                <h2 className="font-semibold text-foreground text-sm">Special Days and Recurring Schedules</h2>
              </div>
              <button type="button" onClick={() => setOpen(false)} className="h-7 w-7 flex items-center justify-center rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors">
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="p-5 space-y-4 text-sm text-muted-foreground">
              <div className="flex gap-3">
                <div className="mt-0.5 h-8 w-8 shrink-0 rounded-lg bg-primary/10 flex items-center justify-center">
                  <RotateCcw className="h-4 w-4 text-primary" />
                </div>
                <div>
                  <p className="font-semibold text-foreground mb-0.5">Recurring ON (default)</p>
                  <p>Changes to a day's time slots are saved as the <strong className="text-foreground">weekly repeating template</strong> for that day. Every future Monday (or whichever day) will use this schedule automatically.</p>
                </div>
              </div>
              <div className="flex gap-3">
                <div className="mt-0.5 h-8 w-8 shrink-0 rounded-lg bg-amber-500/10 flex items-center justify-center">
                  <CalendarOff className="h-4 w-4 text-amber-500" />
                </div>
                <div>
                  <p className="font-semibold text-foreground mb-0.5">Recurring OFF - Special Day</p>
                  <p>Turn <strong className="text-foreground">Recurring off</strong> before making changes, then save. Your changes apply <strong className="text-foreground">only to that specific date</strong>. The weekly template is untouched. Use this for public holidays, days off, or one-off extended hours.</p>
                </div>
              </div>
              <div className="flex gap-3">
                <div className="mt-0.5 h-8 w-8 shrink-0 rounded-lg bg-rose-500/10 flex items-center justify-center">
                  <HelpCircle className="h-4 w-4 text-rose-500" />
                </div>
                <div>
                  <p className="font-semibold text-foreground mb-0.5">Order matters</p>
                  <p>Switch Recurring <strong className="text-foreground">off first</strong>, then adjust slots. Turning Recurring back on afterward has <strong className="text-foreground">no retroactive effect</strong> on exceptions already saved.</p>
                </div>
              </div>
              <div className="rounded-xl bg-primary/5 border border-primary/20 p-3 flex gap-2.5">
                <Lightbulb className="h-4 w-4 text-primary mt-0.5 shrink-0" />
                <p className="text-xs text-foreground/80"><strong>Tip:</strong> Use <em>Scheduling - Workdays</em> to manage specific-date overrides week by week. Use the Providers page to set the default repeating weekly pattern.</p>
              </div>
            </div>
            <div className="px-5 pb-4 flex justify-end">
              <Button size="sm" onClick={() => setOpen(false)}>Got it</Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}