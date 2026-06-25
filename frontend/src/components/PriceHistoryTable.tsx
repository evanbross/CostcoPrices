// ai: claude-sonnet-4-6 | 2026-06-20
import { useRef, useState } from 'react'
import toast from 'react-hot-toast'
import { Check, X } from 'lucide-react'
import { updatePriceHistoryEntry } from '../api/client'
import type { PriceHistoryEntry } from '../types'

interface Props {
  history: PriceHistoryEntry[]
  isWeightItem?: boolean
  onEntryUpdated?: (updated: PriceHistoryEntry) => void
}

function fmt(price: string | number) {
  return `$${parseFloat(String(price)).toFixed(2)}`
}

interface PerLbCellProps {
  entry: PriceHistoryEntry
  onSaved: (updated: PriceHistoryEntry) => void
}

function PerLbCell({ entry, onSaved }: PerLbCellProps) {
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState(entry.price_per_lb ?? '')
  const [saving, setSaving] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  function startEdit() {
    setValue(entry.price_per_lb ?? '')
    setEditing(true)
    setTimeout(() => inputRef.current?.focus(), 0)
  }

  function cancel() {
    setEditing(false)
    setValue(entry.price_per_lb ?? '')
  }

  async function save() {
    const trimmed = value.trim()
    const parsed = trimmed === '' ? null : parseFloat(trimmed)
    if (parsed !== null && isNaN(parsed)) {
      toast.error('Enter a valid price per lb')
      return
    }
    const next = parsed === null ? null : parsed.toFixed(4)
    if (next === (entry.price_per_lb ? parseFloat(entry.price_per_lb).toFixed(4) : null)) {
      setEditing(false)
      return
    }
    setSaving(true)
    try {
      const updated = await updatePriceHistoryEntry(entry.id, next)
      onSaved(updated)
      toast.success('Price per lb saved')
      setEditing(false)
    } catch {
      toast.error('Failed to save')
    } finally {
      setSaving(false)
    }
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter') save()
    if (e.key === 'Escape') cancel()
  }

  if (editing) {
    return (
      <div className="flex items-center justify-end gap-1">
        <span className="text-gray-400 text-xs">$</span>
        <input
          ref={inputRef}
          className="w-20 text-right border border-costco-border-gray rounded px-1 py-0.5 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-costco-red"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onKeyDown}
          disabled={saving}
          placeholder="0.00"
        />
        <span className="text-gray-400 text-xs">/lb</span>
        <button onClick={save} disabled={saving} className="text-green-500 hover:text-green-700" title="Save">
          <Check className="w-3.5 h-3.5" />
        </button>
        <button onClick={cancel} disabled={saving} className="text-gray-400 hover:text-gray-600" title="Cancel">
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
    )
  }

  return (
    <button
      onClick={startEdit}
      className="group flex items-center justify-end gap-1 w-full font-mono text-sm hover:text-costco-blue transition-colors"
      title="Click to set price per lb"
    >
      {entry.price_per_lb ? (
        <span>{fmt(entry.price_per_lb)}/lb</span>
      ) : (
        <span className="text-gray-300 italic text-xs">click to add</span>
      )}
    </button>
  )
}

export default function PriceHistoryTable({ history, isWeightItem = false, onEntryUpdated }: Props) {
  const [entries, setEntries] = useState<PriceHistoryEntry[]>(history)

  // Sync if parent passes new history (e.g. after refetch)
  const prevHistory = useRef(history)
  if (prevHistory.current !== history) {
    prevHistory.current = history
    setEntries(history)
  }

  function handleEntryUpdated(updated: PriceHistoryEntry) {
    setEntries((prev) => prev.map((e) => (e.id === updated.id ? updated : e)))
    onEntryUpdated?.(updated)
  }

  if (entries.length === 0) {
    return <p className="text-gray-500 text-sm">No price history yet.</p>
  }

  const nonCoupon = entries.filter((h) => !h.is_coupon)

  // For by-weight items, use price_per_lb for the change column when available on both entries.
  function getComparablePrice(entry: PriceHistoryEntry): number | null {
    if (isWeightItem && entry.price_per_lb) return parseFloat(entry.price_per_lb)
    if (!isWeightItem) return parseFloat(entry.price)
    return null // weight item but no price_per_lb yet — can't compare
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-costco-border-gray">
            <th className="text-left py-2 px-3 font-semibold text-gray-600">Date</th>
            <th className="text-right py-2 px-3 font-semibold text-gray-600">Total paid</th>
            {isWeightItem && (
              <th className="text-right py-2 px-3 font-semibold text-gray-600">Per lb</th>
            )}
            <th className="text-right py-2 px-3 font-semibold text-gray-600">Change</th>
          </tr>
        </thead>
        <tbody>
          {nonCoupon.map((entry, idx) => {
            const prev = nonCoupon[idx - 1]
            const curVal = getComparablePrice(entry)
            const prevVal = prev ? getComparablePrice(prev) : null
            const change = curVal !== null && prevVal !== null ? curVal - prevVal : null
            const changeUnavailable = idx > 0 && (curVal === null || prevVal === null)

            return (
              <tr key={entry.id} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                <td className="py-2 px-3 text-gray-700">
                  {entry.shopping_date ?? entry.created_at.slice(0, 10)}
                </td>
                <td className="py-2 px-3 text-right font-mono font-semibold">
                  {fmt(entry.price)}
                </td>
                {isWeightItem && (
                  <td className="py-2 px-3 text-right">
                    <PerLbCell entry={entry} onSaved={handleEntryUpdated} />
                  </td>
                )}
                <td className="py-2 px-3 text-right">
                  {change === null ? (
                    changeUnavailable ? (
                      <span className="text-gray-300 text-xs" title="Set $/lb on both entries to compare">—</span>
                    ) : (
                      <span className="text-gray-400 text-xs">first</span>
                    )
                  ) : change === 0 ? (
                    <span className="text-gray-400 text-xs">—</span>
                  ) : change > 0 ? (
                    <span className="badge-up">+{fmt(String(change))}{isWeightItem ? '/lb' : ''}</span>
                  ) : (
                    <span className="badge-down">{fmt(String(change))}{isWeightItem ? '/lb' : ''}</span>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      {isWeightItem && (
        <p className="text-xs text-gray-400 mt-2 px-3">
          Click any "Per lb" cell to enter the price per pound. Changes are compared by $/lb.
        </p>
      )}
    </div>
  )
}
