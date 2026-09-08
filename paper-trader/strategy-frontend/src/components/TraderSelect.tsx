import * as Select from '@radix-ui/react-select'
import { Check, ChevronDown, ChevronUp } from 'lucide-react'
import type { ComponentProps } from 'react'
import './trader-select.css'

export type SelectOption = Readonly<{ value: string; label: string; disabled?: boolean }>
type Props = Pick<ComponentProps<typeof Select.Root>, 'value' | 'defaultValue' | 'onValueChange' | 'disabled' | 'required' | 'name' | 'form'> & {
  id?: string
  label: string
  options: readonly SelectOption[]
  placeholder?: string
  className?: string
  describedBy?: string
  invalid?: boolean
}

export function TraderSelect({ id, label, options, placeholder, className = '', describedBy, invalid, ...control }: Props) {
  const prompt = placeholder ?? options.find((option) => option.value === '')?.label ?? 'Choose an option'
  // State-managed fields do not need Radix's implicit native form input.
  const Root = control.name || control.required ? Select.Root : Select.unstable_Provider
  return <Root {...control}>
    <Select.Trigger id={id} aria-label={label} aria-describedby={describedBy} aria-invalid={invalid} className={`trader-select-trigger ${className}`}>
      <Select.Value placeholder={prompt} /><Select.Icon asChild><ChevronDown aria-hidden="true" /></Select.Icon>
    </Select.Trigger>
    <Select.Portal><Select.Content className="trader-select-menu" position="popper" sideOffset={4} collisionPadding={8}>
      <Select.ScrollUpButton className="trader-select-scroll"><ChevronUp aria-hidden="true" /></Select.ScrollUpButton>
      <Select.Viewport className="trader-select-options">
        {options.map((option) => <Select.Item key={option.value} value={option.value} data-value={option.value} disabled={option.disabled} textValue={option.label} className="trader-select-option">
          <Select.ItemText>{option.label}</Select.ItemText><Select.ItemIndicator className="trader-select-check"><Check aria-hidden="true" /></Select.ItemIndicator>
        </Select.Item>)}
      </Select.Viewport>
      <Select.ScrollDownButton className="trader-select-scroll"><ChevronDown aria-hidden="true" /></Select.ScrollDownButton>
    </Select.Content></Select.Portal>
  </Root>
}
