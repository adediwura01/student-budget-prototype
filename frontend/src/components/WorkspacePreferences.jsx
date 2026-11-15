import { useRef, useState } from 'react'
import Modal from './Modal'
import AppearanceSelector from './AppearanceSelector'
import Button from './ui/Button'
import Input from './ui/Input'

export default function WorkspacePreferences({ name, appearance, onAppearanceChange, onSave, onClose }) {
  const [value, setValue] = useState(name)
  const [error, setError] = useState('')
  const inputRef = useRef(null)

  function submit(event) {
    event.preventDefault()
    const label = value.trim()
    if (!label || label.length > 40) {
      setError(!label ? 'Enter a workspace label.' : 'Keep your label to 40 characters or fewer.')
      inputRef.current.focus()
      return
    }
    onSave(label)
  }

  return <Modal title="Workspace preferences" description="Small details that make the interface your own." onClose={onClose}>
    <form className="preferences-form" onSubmit={submit} noValidate>
      <Input ref={inputRef} label="Workspace label" value={value} placeholder="My workspace" maxLength={40} required autoFocus
        onChange={(event) => { setValue(event.target.value); setError('') }} hint="A display label for this session only. This does not update an account." error={error} />
      <div><h3 className="field-section-title">Appearance</h3><AppearanceSelector appearance={appearance} onChange={onAppearanceChange} /></div>
      <p className="preferences-disclaimer">This is a frontend prototype. No personal or financial information is sent to a server.</p>
      <div className="modal-actions"><Button variant="secondary" onClick={onClose}>Cancel</Button><Button type="submit" icon="check">Save label</Button></div>
    </form>
  </Modal>
}
