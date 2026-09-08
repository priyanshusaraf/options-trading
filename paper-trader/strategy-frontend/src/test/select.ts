import { fireEvent, screen, within } from '@testing-library/react'

export async function chooseSelect(label: string | RegExp, value: string) {
  fireEvent.keyDown(await screen.findByRole('combobox', { name: label }), { key: 'ArrowDown' })
  const menu = await screen.findByRole('listbox')
  const option = within(menu).getAllByRole('option').find((item) => item.getAttribute('data-value') === value)
  if (!option) throw new Error(`The requested option is unavailable in ${String(label)}`)
  fireEvent.click(option)
}
