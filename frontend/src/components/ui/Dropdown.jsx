import { useEffect, useId, useRef, useState } from 'react'
import Icon from '../Icon'
import Button from './Button'
import './ui.css'

export default function Dropdown({
  label = 'Options',
  icon,
  items = [],
  triggerContent,
  align = 'right',
  className = '',
}) {
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const rootRef = useRef(null)
  const triggerRef = useRef(null)
  const menuRef = useRef(null)
  const tabDismissRef = useRef(false)
  const menuId = useId()
  const triggerId = `${menuId}-trigger`

  useEffect(() => {
    if (!open) return

    const menu = menuRef.current
    const focusTarget = menu.querySelector('[tabindex="0"]') ?? menu
    focusTarget.focus()

    const handleOutsidePointer = (event) => {
      if (!rootRef.current?.contains(event.target)) setOpen(false)
    }

    document.addEventListener('pointerdown', handleOutsidePointer, true)
    return () => document.removeEventListener('pointerdown', handleOutsidePointer, true)
  }, [open])

  const openMenu = (last = false) => {
    const index = last
      ? items.findLastIndex((item) => !item.disabled)
      : items.findIndex((item) => !item.disabled)
    tabDismissRef.current = false
    setActiveIndex(index)
    setOpen(true)
    if (open) {
      const focusTarget = menuRef.current.querySelectorAll('[role^="menuitem"]')[index] ?? menuRef.current
      focusTarget.focus()
    }
  }

  const handleMenuKeyDown = (event) => {
    if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return
    event.preventDefault()
    event.stopPropagation()

    const enabledItems = Array.from(event.currentTarget.querySelectorAll('[role^="menuitem"]:not(:disabled)'))
    if (!enabledItems.length) return

    const currentIndex = enabledItems.indexOf(document.activeElement)
    let nextIndex
    if (event.key === 'ArrowDown') nextIndex = (currentIndex + 1) % enabledItems.length
    else if (event.key === 'ArrowUp') nextIndex = currentIndex <= 0 ? enabledItems.length - 1 : currentIndex - 1
    else if (event.key === 'Home') nextIndex = 0
    else nextIndex = enabledItems.length - 1
    enabledItems[nextIndex].focus()
  }

  return (
    <div
      ref={rootRef}
      className={`ui-dropdown ui-dropdown--${align} ${className}`.trim()}
      onBlur={(event) => {
        if (tabDismissRef.current || !event.currentTarget.contains(event.relatedTarget)) {
          setOpen(false)
        }
        tabDismissRef.current = false
      }}
      onKeyDown={(event) => {
        if (event.key === 'Escape' && open) {
          event.preventDefault()
          event.stopPropagation()
          setOpen(false)
          triggerRef.current?.focus()
        } else if (event.key === 'Tab' && open) {
          // Let native Tab navigation move focus before the focused menu item unmounts.
          if (menuRef.current?.contains(event.target)) tabDismissRef.current = true
          else setOpen(false)
        }
      }}
    >
      <Button
        ref={triggerRef}
        id={triggerId}
        variant="secondary"
        icon={icon}
        className="ui-dropdown-trigger"
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        onClick={() => {
          if (open) setOpen(false)
          else openMenu()
        }}
        onKeyDown={(event) => {
          if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return
          event.preventDefault()
          event.stopPropagation()
          openMenu(event.key === 'ArrowUp')
        }}
      >
        {triggerContent ?? label}
        <Icon name="chevron" size={16} className="ui-dropdown-chevron" />
      </Button>
      {open && (
        <div
          ref={menuRef}
          id={menuId}
          className="ui-dropdown-menu"
          role="menu"
          aria-labelledby={triggerId}
          tabIndex={-1}
          onKeyDown={handleMenuKeyDown}
        >
          {items.length ? items.map((item, index) => {
            const itemId = `${menuId}-item-${index}`
            const radio = item.checked !== undefined

            return (
              <button
                key={item.id ?? index}
                type="button"
                role={radio ? 'menuitemradio' : 'menuitem'}
                aria-checked={radio ? Boolean(item.checked) : undefined}
                aria-labelledby={`${itemId}-label`}
                aria-describedby={item.description ? `${itemId}-description` : undefined}
                tabIndex={index === activeIndex && !item.disabled ? 0 : -1}
                disabled={item.disabled}
                className="ui-dropdown-item"
                onFocus={() => setActiveIndex(index)}
                onClick={() => {
                  setOpen(false)
                  triggerRef.current?.focus()
                  item.onSelect?.()
                }}
              >
                {item.icon && <Icon name={item.icon} size={18} />}
                <span className="ui-dropdown-item-copy">
                  <span id={`${itemId}-label`}>{item.label}</span>
                  {item.description && (
                    <span className="ui-dropdown-item-description" id={`${itemId}-description`}>{item.description}</span>
                  )}
                </span>
                {item.checked && <Icon name="check" size={16} className="ui-dropdown-check" />}
              </button>
            )
          }) : <p className="ui-dropdown-empty" role="none">No actions available</p>}
        </div>
      )}
    </div>
  )
}
