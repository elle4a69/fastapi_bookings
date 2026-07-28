import React from 'react';
import { Service } from '../../types';

interface ServiceCardProps {
  service: Service;
  isSelected: boolean;
  isValid: boolean;
  onSelect: () => void;
}

export const ServiceCard: React.FC<ServiceCardProps> = ({ service, isSelected, isValid, onSelect }) => {
  const formatPrice = (minor: number) => `$${(minor / 100).toFixed(2)}`;

  return (
    <button
      onClick={onSelect}
      disabled={!isValid && !isSelected}
      aria-pressed={isSelected}
      className={`
        w-full text-left p-4 rounded-xl border transition-all duration-200
        ${isSelected 
          ? 'border-indigo-600 ring-1 ring-indigo-600 bg-indigo-50' 
          : isValid 
            ? 'border-slate-200 hover:border-indigo-300 hover:shadow-sm bg-white' 
            : 'border-slate-100 bg-slate-50 opacity-50 cursor-not-allowed'}
      `}
    >
      <div className="flex justify-between items-start">
        <div>
          <h3 className={`font-semibold ${isSelected ? 'text-indigo-900' : 'text-slate-900'}`}>
            {service.name}
          </h3>
          <p className="text-sm text-slate-500 mt-1">{service.duration_minutes} minutes</p>
        </div>
        <div className="text-right">
          <span className={`font-medium ${isSelected ? 'text-indigo-700' : 'text-slate-700'}`}>
            {formatPrice(service.price_minor)}
          </span>
        </div>
      </div>
    </button>
  );
};
