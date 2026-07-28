import React from 'react';
import { AddOn } from '../../types';

interface AddOnSelectorProps {
  addOns: AddOn[];
  selectedIds: number[];
  onToggle: (id: number) => void;
}

export const AddOnSelector: React.FC<AddOnSelectorProps> = ({ addOns, selectedIds, onToggle }) => {
  if (addOns.length === 0) return null;

  const formatPrice = (minor: number) => `$${(minor / 100).toFixed(2)}`;

  return (
    <div className="space-y-3">
      {addOns.map(addon => {
        const isSelected = selectedIds.includes(addon.id);
        return (
          <label 
            key={addon.id}
            className={`
              flex items-center justify-between p-4 rounded-xl border cursor-pointer transition-colors
              ${isSelected ? 'border-indigo-600 bg-indigo-50 ring-1 ring-indigo-600' : 'border-slate-200 bg-white hover:border-indigo-300'}
            `}
          >
            <div className="flex items-center">
              <input 
                type="checkbox" 
                className="h-5 w-5 text-indigo-600 border-slate-300 rounded focus:ring-indigo-500"
                checked={isSelected}
                onChange={() => onToggle(addon.id)}
              />
              <div className="ml-3">
                <span className={`block font-medium ${isSelected ? 'text-indigo-900' : 'text-slate-900'}`}>
                  {addon.name}
                </span>
                {addon.duration_minutes > 0 && (
                  <span className="block text-xs text-slate-500 mt-0.5">
                    + {addon.duration_minutes} mins
                  </span>
                )}
              </div>
            </div>
            <span className={`font-medium ${isSelected ? 'text-indigo-700' : 'text-slate-700'}`}>
              +{formatPrice(addon.price_minor)}
            </span>
          </label>
        );
      })}
    </div>
  );
};
