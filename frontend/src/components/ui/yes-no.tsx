// Yes/No field as two separate tick boxes. true = Yes, false = No, anything
// else = not answered. Ticking the already-ticked box clears the answer.
export function yesNoLabel(value: unknown): string {
  return value === true ? "Yes" : value === false ? "No" : "—"
}

export function YesNoBoxes({
  value,
  onChange,
  required,
  disabled,
  size = "w-4 h-4",
}: {
  value: unknown
  onChange?: (value: boolean | null) => void
  required?: boolean
  disabled?: boolean
  size?: string
}) {
  const unanswered = value !== true && value !== false
  const box = (label: string, v: boolean) => (
    <label className="inline-flex items-center gap-1.5 text-sm text-gray-700 cursor-pointer">
      <input
        type="checkbox"
        checked={value === v}
        disabled={disabled}
        // Native "please tick a box" only while neither is ticked.
        required={required && unanswered}
        onChange={() => onChange?.(value === v ? null : v)}
        className={`${size} text-blue-600 border-gray-300 rounded`}
      />
      {label}
    </label>
  )
  return (
    <div className="flex items-center gap-4">
      {box("Yes", true)}
      {box("No", false)}
    </div>
  )
}
