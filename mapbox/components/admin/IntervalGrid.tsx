import React from 'react';
import { TimeInterval } from '../../types';

interface IntervalGridProps {
  intervals: TimeInterval[];
  onChange: (intervals: TimeInterval[]) => void;
  disabled?: boolean;
}

export const IntervalGrid: React.FC<IntervalGridProps> = ({ intervals, onChange, disabled = false }) => {
  
  const handleAdd = () => {
    onChange([...intervals, { start_time: '09:00', end_time: '17:00' }]);
  };

  const handleRemove = (index: number) => {
    const newIntervals = [...intervals];
    newIntervals.splice(index, 1);
    onChange(newIntervals);
  };

  const handleChange = (index: number, field: keyof TimeInterval, value: string) => {
    const newIntervals = [...intervals];
    newIntervals[index] = { ...newIntervals[index], [field]: value };
    onChange(newIntervals);
  };

  // Basic overlap check for visual feedback
  const hasOverlap = (index: number) => {
    const current = intervals[index];
    if (!current.start_time || !current.end_time) return false;
    
    for (let i = 0; i < intervals.length; i++) {
      if (i === index) continue;
      const other = intervals[i];
      if (!other.start_time || !other.end_time) continue;

      // Check if current overlaps with other
      if (current.start_time < other.end_time && current.end_time > other.start_time) {
        return true;
      }
    }
    return false;
  };

  const isInvalidTime = (interval: TimeInterval) => {
    return interval.start_time >= interval.end_time;
  };

  return (
    <div className="space-y-3">
      {intervals.length === 0 ? (
        <div className="text-sm text-slate-500 italic p-4 bg-slate-50 rounded-lg border border-slate-200 text-center">
          No hours configured.
        </div>
      ) : (
        intervals.map((interval, index) => {
          const overlap = hasOverlap(index);
          const invalid = isInvalidTime(interval);
          
          return (
            <div key={index} className={`flex items-center space-x-3 p-3 rounded-lg border ${overlap || invalid ? 'border-red-300 bg-red-50' : 'border-slate-200 bg-white'}`}>
              <div className="flex-1 flex items-center space-x-2">
                <input
                  type="time"
                  disabled={disabled}
                  value={interval.start_time}
                  onChange={(e) => handleChange(index, 'start_time', e.target.value)}
                  className="block w-full rounded-md border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border disabled:bg-slate-50 disabled:text-slate-500"
                />
                <span className="text-slate-500 text-sm">to</span>
                <input
                  type="time"
                  disabled={disabled}
                  value={interval.end_time}
                  onChange={(e) => handleChange(index, 'end_time', e.target.value)}
                  className="block w-full rounded-md border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border disabled:bg-slate-50 disabled:text-slate-500"
                />
              </div>
              {!disabled && (
                <button
                  type="button"
                  onClick={() => handleRemove(index)}
                  className="text-slate-400 hover:text-red-600 p-2 rounded-md hover:bg-red-50 transition-colors"
                  title="Remove interval"
                >
                  <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              )}
            </div>
          );
        })
      )}
      
      {!disabled && (
        <button
          type="button"
          onClick={handleAdd}
          className="inline-flex items-center px-3 py-2 border border-slate-300 shadow-sm text-sm font-medium rounded-md text-slate-700 bg-white hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
        >
          <svg className="-ml-1 mr-2 h-5 w-5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
          </svg>
          Add Interval
        </button>
      )}
    </div>
  );
};
