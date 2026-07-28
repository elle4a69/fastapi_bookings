import React from 'react';
import { Provider } from '../../types';

interface ProviderCardProps {
  provider: Provider;
  isSelected: boolean;
  isValid: boolean;
  onSelect: () => void;
}

export const ProviderCard: React.FC<ProviderCardProps> = ({ provider, isSelected, isValid, onSelect }) => {
  return (
    <button
      onClick={onSelect}
      disabled={!isValid && !isSelected}
      aria-pressed={isSelected}
      className={`
        flex items-center p-3 rounded-xl border transition-all duration-200
        ${isSelected 
          ? 'border-indigo-600 ring-1 ring-indigo-600 bg-indigo-50' 
          : isValid 
            ? 'border-slate-200 hover:border-indigo-300 hover:shadow-sm bg-white' 
            : 'border-slate-100 bg-slate-50 opacity-50 cursor-not-allowed'}
      `}
    >
      <div className={`h-10 w-10 rounded-full flex items-center justify-center text-sm font-bold mr-3
        ${isSelected ? 'bg-indigo-200 text-indigo-800' : 'bg-slate-200 text-slate-600'}
      `}>
        {provider.name.charAt(0).toUpperCase()}
      </div>
      <span className={`font-medium ${isSelected ? 'text-indigo-900' : 'text-slate-800'}`}>
        {provider.name}
      </span>
    </button>
  );
};
