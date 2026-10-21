// Visit dates are calendar days. The API stores them as midnight UTC
// ("2026-10-21T00:00:00Z"), so `new Date(value)` shows the day before for
// anyone west of UTC. Read only the YYYY-MM-DD part and build a local date.

/** Today's date in the user's own time zone, as YYYY-MM-DD (for date inputs). */
export function todayISO(): string {
  const d = new Date()
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

/** "2026-10-21" or "2026-10-21T00:00:00Z" -> "Oct 21, 2026"; "" when empty. */
export function formatVisitDate(value: string | null | undefined): string {
  const match = value?.match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (!match) return ""
  const [, y, m, d] = match
  return new Date(Number(y), Number(m) - 1, Number(d)).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" })
}
