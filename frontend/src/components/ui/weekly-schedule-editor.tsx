import { useState } from 'react';
import { ChevronLeft, ChevronRight, Loader2 } from 'lucide-react';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { SpecialDaysInfoModal } from '@/components/ui/special-days-info-modal';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface DayScheduleEntry {
  is_working: boolean;
  recurring: boolean;
  active_slots: string[];
}

export type WeeklyScheduleMap = Record<string, DayScheduleEntry>;

export interface SpecialDayRecord {
  is_working: boolean;
  active_slots: string[];
  reason?: string | null;
}

export interface WeeklyScheduleEditorProps {
  schedule: WeeklyScheduleMap | null | undefined;
  specialDays?: Record<string, SpecialDayRecord>;
  onFieldChange: (dayKey: string, field: keyof DayScheduleEntry, value: boolean, dateStr: string) => void;
  onSlotToggle: (dayKey: string, slot: string, dateStr: string) => void;
  saveStatus?: 'idle' | 'saving' | 'saved';
  initialDay?: string;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const DAYS = [
  { key: 'monday',    label: 'Monday',    short: 'Mo', offset: 0 },
  { key: 'tuesday',   label: 'Tuesday',   short: 'Tu', offset: 1 },
  { key: 'wednesday', label: 'Wednesday', short: 'We', offset: 2 },
  { key: 'thursday',  label: 'Thursday',  short: 'Th', offset: 3 },
  { key: 'friday',    label: 'Friday',    short: 'Fr', offset: 4 },
  { key: 'saturday',  label: 'Saturday',  short: 'Sa', offset: 5 },
  { key: 'sunday',    label: 'Sunday',    short: 'Su', offset: 6 },
];

const SLOTS: string[] = [];
for (const period of ['AM', 'PM']) {
  for (const hour of [12, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]) {
    SLOTS.push(hour + ':00 ' + period);
    SLOTS.push(hour + ':30 ' + period);
  }
}

// ─── Date helpers ─────────────────────────────────────────────────────────────

function getWeekMonday(weekOffset: number): Date {
  const now = new Date();
  const dow = now.getDay();
  const toMonday = dow === 0 ? -6 : 1 - dow;
  const d = new Date(now);
  d.setDate(now.getDate() + toMonday + weekOffset * 7);
  d.setHours(0, 0, 0, 0);
  return d;
}

function getDayDate(dayOffset: number, weekOffset: number): Date {
  const monday = getWeekMonday(weekOffset);
  const d = new Date(monday);
  d.setDate(monday.getDate() + dayOffset);
  return d;
}

function toISODate(d: Date): string {
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
}

const SHORT_MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const LONG_MONTHS  = ['January','February','March','April','May','June','July','August','September','October','November','December'];

function fmtShort(d: Date): string {
  return 'Mon ' + d.getDate() + ' ' + SHORT_MONTHS[d.getMonth()];
}
function fmtLong(d: Date): string {
  const days = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
  return days[d.getDay()] + ', ' + d.getDate() + ' ' + LONG_MONTHS[d.getMonth()] + ' ' + d.getFullYear();
}

// ─── Component ────────────────────────────────────────────────────────────────

export function WeeklyScheduleEditor({
  schedule, specialDays, onFieldChange, onSlotToggle,
  saveStatus = 'idle', initialDay = 'monday',
}: WeeklyScheduleEditorProps) {
  const [activeDay,  setActiveDay]  = useState(initialDay);
  const [weekOffset, setWeekOffset] = useState(0);
  const [tappedSlot, setTappedSlot] = useState<string | null>(null);

  const day = DAYS.find((d) => d.key === activeDay) ?? DAYS[0];
  const selectedDate = getDayDate(day.offset, weekOffset);
  const dateStr      = toISODate(selectedDate);
  const monday       = getWeekMonday(weekOffset);

  // Determine active schedule entry: special day override vs. weekly template
  const specialOverride = specialDays?.[dateStr];
  const isSpecial = !!specialOverride;

  const baseWeekly = schedule?.[day.key] ?? { is_working: false, recurring: true, active_slots: [] };
  const sched: DayScheduleEntry = specialOverride
    ? {
        is_working: specialOverride.is_working,
        recurring: false,
        active_slots: specialOverride.active_slots ?? [],
      }
    : baseWeekly;

  const isActive  = sched.is_working;
  const isRecur   = sched.recurring;
  const slots     = sched.active_slots ?? [];

  const handleSlotClick = (slot: string) => {
    setTappedSlot(slot);
    onSlotToggle(day.key, slot, dateStr);
    setTimeout(() => setTappedSlot(null), 200);
  };

  return (
    <div className="flex flex-col">

      {/* ── Week navigation bar ─────────────────────────────────── */}
      <div className="flex items-center justify-between px-3 pt-3 pb-2 border-b border-border/20">
        <button
          type="button"
          onClick={() => setWeekOffset((w) => w - 1)}
          className="p-1.5 rounded-lg hover:bg-muted/60 transition-colors text-muted-foreground hover:text-foreground"
          title="Previous week"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>

        <span className="text-xs font-semibold text-foreground tracking-wide">
          {'Week of ' + fmtShort(monday)}
          {weekOffset === 0 && <span className="ml-1.5 text-[10px] text-primary font-bold">(this week)</span>}
        </span>

        <button
          type="button"
          onClick={() => setWeekOffset((w) => w + 1)}
          className="p-1.5 rounded-lg hover:bg-muted/60 transition-colors text-muted-foreground hover:text-foreground"
          title="Next week"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>

      {/* ── Day tabs ─────────────────────────────────────────────── */}
      <div className="flex items-end border-b border-border/30 gap-1 px-2 pt-2 pb-0 overflow-x-auto scrollbar-none">
        {DAYS.map((d) => {
          const isTab       = d.key === activeDay;
          const tabDate     = getDayDate(d.offset, weekOffset);
          const tabDateStr  = toISODate(tabDate);
          const tabSpecial  = specialDays?.[tabDateStr];
          const isTabSpecial= !!tabSpecial;
          const tabWorking  = isTabSpecial
            ? tabSpecial.is_working
            : (schedule?.[d.key]?.is_working ?? false);

          const base   = 'flex-1 min-w-[36px] flex flex-col items-center pb-2 pt-1.5 text-center text-xs font-semibold rounded-t-xl transition-all duration-200 relative border-b-2 ';
          const tabCls = isTab
            ? 'text-primary border-primary bg-primary/5'
            : 'text-muted-foreground border-transparent hover:text-foreground hover:bg-muted/30';
          const dotCls = 'absolute top-0.5 right-0.5 w-1.5 h-1.5 rounded-full ' + (isTab ? 'bg-primary' : 'bg-emerald-500');

          return (
            <button
              key={d.key}
              type="button"
              onClick={() => setActiveDay(d.key)}
              title={d.label + ' ' + fmtLong(tabDate) + (isTabSpecial ? ' — special day override' : '')}
              className={base + tabCls}
            >
              <span className="text-[11px] font-bold leading-none">{d.short}</span>
              <span className="text-[10px] font-normal leading-none mt-0.5 opacity-70">{tabDate.getDate()}</span>
              {tabWorking && !isTabSpecial && <span className={dotCls} />}
              {isTabSpecial && <span className="absolute top-0.5 right-0.5 w-1.5 h-1.5 rounded-full bg-amber-400" />}
            </button>
          );
        })}

        {/* Save status + help — pushed to right end */}
        <div className="ml-1 mb-1.5 flex items-center gap-1.5 shrink-0 self-center">
          {saveStatus === 'saving' && (
            <span className="flex items-center gap-1 text-xs text-muted-foreground animate-pulse">
              <Loader2 className="h-3 w-3 animate-spin text-primary" />
              <span className="hidden sm:inline">Saving...</span>
            </span>
          )}
          {saveStatus === 'saved' && <span className="text-xs text-emerald-500 font-medium hidden sm:inline">Saved</span>}
          <SpecialDaysInfoModal />
        </div>
      </div>

      {/* ── Day panel ────────────────────────────────────────────── */}
      <div className="flex flex-col gap-4 p-4">

        {/* Date heading */}
        <div className="flex flex-col gap-2">
          <h3 className="font-bold text-base text-foreground leading-tight">
            {fmtLong(selectedDate)}
            {isSpecial && <span className="ml-2 text-xs font-normal text-amber-500">(special day override)</span>}
          </h3>

          {/* Toggles — side by side */}
          <div className="flex flex-wrap gap-x-6 gap-y-2 items-center">
            <div className="flex items-center gap-2">
              <Switch
                id={'wse-' + day.key + '-working'}
                checked={isActive}
                onCheckedChange={(v) => onFieldChange(day.key, 'is_working', v, dateStr)}
              />
              <Label
                htmlFor={'wse-' + day.key + '-working'}
                className="text-xs font-semibold text-muted-foreground uppercase tracking-wider cursor-pointer select-none"
              >
                Working Day
              </Label>
            </div>
            <div className="flex items-center gap-2">
              <Switch
                id={'wse-' + day.key + '-recurring'}
                checked={isRecur}
                disabled={!isActive}
                onCheckedChange={(v) => onFieldChange(day.key, 'recurring', v, dateStr)}
              />
              <Label
                htmlFor={'wse-' + day.key + '-recurring'}
                className="text-xs font-semibold text-muted-foreground uppercase tracking-wider cursor-pointer select-none"
              >
                Recurring
              </Label>
            </div>
          </div>
        </div>

        {/* Slot grid */}
        <div className={'grid grid-cols-4 sm:grid-cols-6 gap-1.5 max-h-[380px] overflow-y-auto pr-1 select-none scrollbar-thin transition-opacity ' + (!isActive ? 'opacity-40 pointer-events-none' : '')}>
          {SLOTS.map((slot) => {
            const on      = slots.includes(slot);
            const tapping = tappedSlot === slot;
            const base    = 'py-1 px-0.5 rounded-md text-[10px] font-medium border text-center transition-all duration-150 ';
            const cls     = on && isActive
              ? 'bg-primary text-primary-foreground border-primary font-semibold shadow-sm'
              : 'bg-muted/10 text-muted-foreground border-border/20 hover:bg-muted/30 hover:text-foreground disabled:opacity-40 disabled:cursor-not-allowed';
            return (
              <button
                key={slot}
                type="button"
                disabled={!isActive}
                onClick={() => handleSlotClick(slot)}
                className={base + cls + (tapping ? ' scale-90 opacity-70' : '')}
              >
                {slot}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
