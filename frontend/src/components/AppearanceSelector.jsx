import Icon from './Icon'

const modes = [{ value: 'light', name: 'Light', icon: 'sun' }, { value: 'dark', name: 'Dark', icon: 'moon' }, { value: 'system', name: 'System', icon: 'system' }]

export default function AppearanceSelector({ appearance, onChange }) {
  return <fieldset className="appearance-selector">
    <legend className="sr-only">Workspace appearance</legend>
    {modes.map((mode) => <label key={mode.value} className={appearance === mode.value ? 'is-selected' : ''}>
      <input type="radio" name="appearance" value={mode.value} checked={appearance === mode.value} onChange={() => onChange(mode.value)} />
      <span className={`appearance-swatch appearance-swatch--${mode.value}`} aria-hidden="true"><i /><span><b /><b /></span></span>
      <span className="appearance-choice-name"><Icon name={mode.icon} size={15} />{mode.name}</span>
    </label>)}
  </fieldset>
}
