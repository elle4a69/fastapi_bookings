import React, { useMemo, useState } from 'react'
import { CheckCircle2, ExternalLink, HelpCircle, Loader2, LockKeyhole, Send, ShieldCheck, XCircle } from 'lucide-react'
import type { FormFieldSchema, UserInputRequestItem as UserInputRequestItemType } from '../../../types/workbench'
import { useWorkbenchStore } from '../../../store/useWorkbenchStore'
import { Button } from '../../ui/button'
import { Input } from '../../ui/input'
import { Badge } from '../../ui/badge'

interface Props {
  item: UserInputRequestItemType
}

function fieldsFromJsonSchema(schema?: Record<string, any>): FormFieldSchema[] {
  const properties = schema?.properties
  if (!properties || typeof properties !== 'object') return []
  const required = new Set(Array.isArray(schema?.required) ? schema.required : [])
  return Object.entries(properties).map(([id, raw]) => {
    const field = raw && typeof raw === 'object' ? raw as Record<string, any> : {}
    const options = Array.isArray(field.enum) ? field.enum.map(String) : undefined
    const type: FormFieldSchema['type'] = options
      ? 'radio'
      : field.type === 'boolean'
        ? 'checkbox'
        : field.type === 'number' || field.type === 'integer'
          ? 'number'
          : 'text'
    return {
      id,
      label: String(field.title || id),
      description: typeof field.description === 'string' ? field.description : undefined,
      type,
      options,
      defaultValue: field.default,
      required: required.has(id),
    }
  })
}

export const UserInputFormItem: React.FC<Props> = ({ item }) => {
  const { resolveUserInputRequest } = useWorkbenchStore()
  const generatedFields = useMemo(() => fieldsFromJsonSchema(item.requestedSchema), [item.requestedSchema])
  const fields = item.schema.length > 0 ? item.schema : generatedFields
  const [formData, setFormData] = useState<Record<string, any>>(() =>
    Object.fromEntries(fields.filter(field => field.defaultValue !== undefined).map(field => [field.id, field.defaultValue]))
  )
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const isPending = item.status === 'pending'

  const submit = async (action: 'accept' | 'decline' | 'cancel', response: Record<string, any>) => {
    setSubmitting(true)
    setError(null)
    try {
      await resolveUserInputRequest(item.requestId, action, response)
      setFormData({})
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Codex could not receive this response')
    } finally {
      setSubmitting(false)
    }
  }

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    await submit('accept', item.kind === 'mcp_form' ? { content: formData } : { answers: formData })
  }

  const renderField = (field: FormFieldSchema) => {
    const descriptionId = field.description ? `desc-${item.requestId}-${field.id}` : undefined
    if (field.type === 'radio') {
      return (
        <div className="space-y-1.5" role="radiogroup" aria-describedby={descriptionId}>
          {field.options?.map(option => (
            <label key={option} className="flex items-start gap-2 rounded-md border border-border bg-muted/30 px-2.5 py-2 cursor-pointer hover:bg-muted/60">
              <input
                type="radio"
                name={`${item.requestId}-${field.id}`}
                value={option}
                checked={formData[field.id] === option}
                onChange={() => setFormData(previous => ({ ...previous, [field.id]: option }))}
                required={field.required}
                className="mt-0.5"
              />
              <span>
                <span className="block font-medium text-foreground">{option}</span>
                {field.optionDescriptions?.[option] && (
                  <span className="block text-[10px] text-muted-foreground mt-0.5">{field.optionDescriptions[option]}</span>
                )}
              </span>
            </label>
          ))}
          {field.allowOther && (
            <Input
              value={field.options?.includes(formData[field.id]) ? '' : formData[field.id] || ''}
              onChange={event => setFormData(previous => ({ ...previous, [field.id]: event.target.value }))}
              placeholder="Other response"
              className="h-9 text-xs"
            />
          )}
        </div>
      )
    }
    if (field.type === 'checkbox') {
      return (
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={Boolean(formData[field.id])}
            onChange={event => setFormData(previous => ({ ...previous, [field.id]: event.target.checked }))}
          />
          <span className="text-xs text-muted-foreground">Enabled</span>
        </label>
      )
    }
    return (
      <Input
        id={`user-input-${item.requestId}-${field.id}`}
        type={field.type === 'password' ? 'password' : field.type === 'number' ? 'number' : 'text'}
        aria-describedby={descriptionId}
        value={formData[field.id] ?? ''}
        onChange={event => setFormData(previous => ({
          ...previous,
          [field.id]: field.type === 'number' ? Number(event.target.value) : event.target.value,
        }))}
        placeholder={field.description || `Enter ${field.label}`}
        required={field.required}
        autoComplete={field.type === 'password' ? 'off' : undefined}
        className="h-9 text-xs"
      />
    )
  }

  return (
    <div className="my-2 sm:my-3 max-w-4xl mx-auto border border-amber-500/40 rounded-lg bg-amber-500/5 p-3 sm:p-4 shadow-xs text-xs w-full max-w-full overflow-hidden break-words">
      <div className="flex items-center justify-between gap-2 pb-2.5 mb-2.5 border-b border-border">
        <div className="flex items-center gap-2 min-w-0">
          {item.kind === 'permissions' ? (
            <ShieldCheck className="w-4 h-4 text-amber-500 flex-shrink-0" aria-hidden="true" />
          ) : item.kind.startsWith('mcp_') ? (
            <LockKeyhole className="w-4 h-4 text-amber-500 flex-shrink-0" aria-hidden="true" />
          ) : (
            <HelpCircle className="w-4 h-4 text-amber-500 flex-shrink-0" aria-hidden="true" />
          )}
          <div className="min-w-0">
            <h3 className="font-semibold text-xs text-foreground m-0">Authorization or input required</h3>
            {item.serverName && <p className="text-[10px] text-muted-foreground m-0">Requested by {item.serverName}</p>}
          </div>
        </div>
        <Badge variant={isPending ? 'warning' : item.status === 'submitted' ? 'success' : 'danger'} className="flex-shrink-0">
          {isPending ? 'Awaiting Response' : item.status === 'submitted' ? 'Submitted' : 'Declined'}
        </Badge>
      </div>

      <p className="text-sm text-foreground mb-3">{item.question}</p>

      {item.kind === 'mcp_url' && item.url && isPending && (
        <div className="space-y-3">
          <a href={item.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-2 text-xs font-semibold text-primary-foreground hover:opacity-90">
            Open authorization page <ExternalLink className="w-3.5 h-3.5" />
          </a>
          <p className="text-[11px] text-muted-foreground">Complete the provider flow in the new tab, then confirm here so the Codex turn can resume.</p>
          <div className="flex flex-wrap justify-end gap-2">
            <Button variant="outline" size="sm" disabled={submitting} onClick={() => submit('decline', {})}>Decline</Button>
            <Button size="sm" disabled={submitting} onClick={() => submit('accept', { content: null })}>
              {submitting ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5 mr-1" />}
              Authorization completed
            </Button>
          </div>
        </div>
      )}

      {item.kind === 'permissions' && isPending && (
        <div className="space-y-3">
          {item.workingDirectory && <p className="text-[11px] text-muted-foreground">Working directory: <span className="font-mono">{item.workingDirectory}</span></p>}
          <pre className="max-h-44 overflow-auto rounded-md border border-border bg-muted/50 p-2 text-[10px] text-foreground whitespace-pre-wrap">{JSON.stringify(item.permissions || {}, null, 2)}</pre>
          <div className="flex flex-wrap justify-end gap-2">
            <Button variant="outline" size="sm" disabled={submitting} onClick={() => submit('decline', { permissions: {} })}>
              <XCircle className="w-3.5 h-3.5 mr-1" /> Decline
            </Button>
            <Button variant="secondary" size="sm" disabled={submitting} onClick={() => submit('accept', { permissions: item.permissions || {}, scope: 'session' })}>Allow for session</Button>
            <Button size="sm" disabled={submitting} onClick={() => submit('accept', { permissions: item.permissions || {}, scope: 'turn' })}>Allow for turn</Button>
          </div>
        </div>
      )}

      {(item.kind === 'tool_user_input' || item.kind === 'mcp_form') && isPending && (
        <form onSubmit={handleSubmit} className="space-y-3">
          {fields.map(field => (
            <div key={field.id}>
              <label htmlFor={`user-input-${item.requestId}-${field.id}`} className="block text-xs font-medium text-foreground mb-1">
                {field.label} {field.required && <span className="text-rose-500">*</span>}
              </label>
              {field.question && field.question !== item.question && <p className="text-[11px] text-muted-foreground mb-1.5">{field.question}</p>}
              {renderField(field)}
              {field.description && <div id={`desc-${item.requestId}-${field.id}`} className="text-[10px] text-muted-foreground mt-1">{field.description}</div>}
            </div>
          ))}
          <div className="flex justify-end gap-2 pt-2">
            {item.kind === 'mcp_form' && <Button type="button" variant="outline" size="sm" disabled={submitting} onClick={() => submit('decline', {})}>Decline</Button>}
            <Button size="sm" type="submit" disabled={submitting || fields.length === 0}>
              {submitting ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> : <Send className="w-3.5 h-3.5 mr-1" />}
              Send response to Codex
            </Button>
          </div>
        </form>
      )}

      {!isPending && (
        <div className={`flex items-center gap-2 text-xs font-medium ${item.status === 'submitted' ? 'text-emerald-500' : 'text-rose-500'}`}>
          {item.status === 'submitted' ? <CheckCircle2 className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
          {item.status === 'submitted' ? 'Response delivered to the active Codex worker.' : 'Request declined.'}
        </div>
      )}

      {error && <div role="alert" className="mt-3 rounded-md border border-rose-500/40 bg-rose-500/10 p-2 text-xs text-rose-500">{error}</div>}
    </div>
  )
}
