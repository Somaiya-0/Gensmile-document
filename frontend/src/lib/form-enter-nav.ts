import type { KeyboardEvent, RefObject } from "react"

export type EnterNavField = {
  ref: RefObject<HTMLInputElement | null>
  value: string
}

// Pressing Enter in any tracked field jumps to the first still-empty field
// in order, instead of submitting. Only calls onSubmit once every tracked
// field has a non-empty value.
export function handleEnterFieldNav(
  event: KeyboardEvent<HTMLInputElement>,
  fields: EnterNavField[],
  onSubmit: () => void
) {
  if (event.key !== "Enter") return
  event.preventDefault()
  const firstEmpty = fields.find((f) => !f.value.trim())
  if (firstEmpty) {
    firstEmpty.ref.current?.focus()
  } else {
    onSubmit()
  }
}
