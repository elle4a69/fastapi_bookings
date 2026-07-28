import React, { useMemo } from 'react';

interface TimeSelectorProps {
  validTimes: string[];
  selectedTime?: string;
  onSelect: (time: string) => void;
}

export const TimeSelector: React.FC<TimeSelectorProps> = ({ validTimes, selectedTime, onSelect }) => {
  // Group times by date
  const groupedTimes = useMemo(() => {
    const groups: Record<string, string[]> = {};
    validTimes.forEach(timeStr => {
      const date = new Date(timeStr);
      const dateKey = date.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
      if (!groups[dateKey]) groups[dateKey] = [];
      groups[dateKey].push(timeStr);
    });
    return groups;
  }, [validTimes]);

  if (validTimes.length === 0) {
    return (
      <div className="p-6 text-center bg-slate-50 rounded-xl border border-slate-200">
        <p className="text-slate-600">No available times match these choices. Try changing a selection.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {Object.entries(groupedTimes).map(([dateKey, times]) => (
        <div key={dateKey}>
          <h4 className="text-sm font-semibold text-slate-700 mb-3 uppercase tracking-wider">{dateKey}</h4>
          <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
            {(times as string[]).map(timeStr => {
              const date = new Date(timeStr);
              const timeLabel = date.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
              const isSelected = selectedTime === timeStr;
              
              return (
                <button
                  key={timeStr}
                  onClick={() => onSelect(timeStr)}
                  aria-pressed={isSelected}
                  className={`
                    py-2 px-1 text-sm font-medium rounded-lg border transition-colors
                    ${isSelected 
                      ? 'bg-indigo-600 border-indigo-600 text-white shadow-sm' 
                      : 'bg-white border-slate-200 text-slate-700 hover:border-indigo-300 hover:bg-indigo-50'}
                  `}
                >
                  {timeLabel}
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
};
