import { useId } from 'react'
import './ui.css'

export default function Textarea({ label, id, hint, error, required, className = '', ...props }) {
  const generatedId = useId()
  const textareaId = id ?? generatedId
  const hintId = `${textareaId}-hint`
  const errorId = `${textareaId}-error`
  const describedBy = [
    props['aria-describedby'],
    hint ? hintId : null,
    error ? errorId : null,
  ].filter(Boolean).join(' ') || undefined

  return (
    <div className="ui-field">
      {label && (
        <label className="ui-field-label" htmlFor={textareaId}>
          {label}
          {required && <span className="ui-field-required" aria-hidden="true">*</span>}
        </label>
      )}
      <textarea
        {...props}
        id={textareaId}
        className={`ui-input ui-textarea ${className}`.trim()}
        required={required}
        aria-invalid={error ? true : props['aria-invalid']}
        aria-describedby={describedBy}
      />
      {hint && <p className="ui-field-hint" id={hintId}>{hint}</p>}
      {error && <p className="ui-field-error" id={errorId} role="alert">{error}</p>}
    </div>
  )
}