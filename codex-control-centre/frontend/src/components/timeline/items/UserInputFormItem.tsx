import React, { useState } from 'react'
import { HelpCircle, Send, CheckCircle2 } from 'lucide-react'
import type { UserInputRequestItem as UserInputRequestItemType } from '../../../types/workbench'
import { Button } from '../../ui/button'
import { Input } from '../../ui/input'
import { Badge } from '../../ui/badge'

interface Props {
  item: UserInputRequestItemType
}

export const UserInputFormItem: React.FC<Props> = ({ item }) => {
  const [formData, setFormData] = useState<Record<string, any>>({})
  const [isSubmitted, setIsSubmitted] = useState(item.status === 'submitted')

  const handleChange = (fieldId: string, val: any) => {
    setFormData(prev => ({ ...prev, [fieldId]: val }))
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setIsSubmitted(true)
  }

  return (
    <div className="my-3 max-w-4xl mx-auto border border-[var(--border)] rounded-lg bg-[var(--surface-primary)] p-4 shadow-xs text-xs">
      <div className="flex items-center justify-between gap-2 pb-2.5 mb-2.5 border-b border-[var(--border)]">
        <div className="flex items-center gap-2">
          <HelpCircle className="w-4 h-4 text-[var(--accent)]" aria-hidden="true" />
          <h3 className="font-semibold text-xs text-[var(--text-primary)] m-0">
            Input Required: {item.question}
          </h3>
        </div>
        <Badge variant={isSubmitted ? 'success' : 'warning'}>
          {isSubmitted ? 'Submitted' : 'Awaiting Response'}
        </Badge>
      </div>

      {!isSubmitted ? (
        <form onSubmit={handleSubmit} className="space-y-3">
          {item.schema.map((field) => (
            <div key={field.id}>
              <label 
                htmlFor={`user-input-${field.id}`}
                className="block text-xs font-medium text-[var(--text-secondary)] mb-1"
              >
                {field.label} {field.required && <span className="text-[var(--danger)]">*</span>}
              </label>
              {field.type === 'select' ? (
                <select
                  id={`user-input-${field.id}`}
                  aria-describedby={field.description ? `desc-${field.id}` : undefined}
                  value={formData[field.id] || ''}
                  onChange={(e) => handleChange(field.id, e.target.value)}
                  className="w-full h-8 rounded border border-[var(--border)] bg-[var(--surface-secondary)] px-2.5 text-xs text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
                >
                  <option value="">Select an option...</option>
                  {field.options?.map((opt, i) => (
                    <option key={i} value={opt}>{opt}</option>
                  ))}
                </select>
              ) : (
                <Input
                  id={`user-input-${field.id}`}
                  aria-describedby={field.description ? `desc-${field.id}` : undefined}
                  value={formData[field.id] || ''}
                  onChange={(e) => handleChange(field.id, e.target.value)}
                  placeholder={field.description || `Enter ${field.label}`}
                  className="h-8 text-xs"
                />
              )}
              {field.description && (
                <div id={`desc-${field.id}`} className="text-[10px] text-[var(--text-subtle)] mt-1">
                  {field.description}
                </div>
              )}
            </div>
          ))}

          <div className="flex justify-end pt-2">
            <Button size="sm" type="submit" className="text-xs">
              <Send className="w-3.5 h-3.5 mr-1" />
              Submit Response
            </Button>
          </div>
        </form>
      ) : (
        <div className="flex items-center gap-2 text-xs text-[var(--success)] font-medium">
          <CheckCircle2 className="w-4 h-4" />
          Response provided to Codex turn.
        </div>
      )}
    </div>
  )
}
