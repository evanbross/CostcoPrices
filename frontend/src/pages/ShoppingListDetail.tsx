// ai: claude-sonnet-4-6 | 2026-06-20
import { useRef, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Pencil, Plus, Scale, X } from 'lucide-react'
import toast from 'react-hot-toast'
import {
  addShoppingListItem,
  getItems,
  getShoppingList,
  removeShoppingListItem,
  renameShoppingList,
  updateShoppingListItem,
} from '../api/client'
import type { Item, ShoppingList, ShoppingListItem } from '../types'

function fmt(v: string | number | null | undefined) {
  if (v == null) return null
  return `$${parseFloat(String(v)).toFixed(2)}`
}

// ── Quantity cell with inline editing ────────────────────────────────────────

interface QtyProps {
  entry: ShoppingListItem
  listId: number
  onUpdated: (e: ShoppingListItem) => void
}

function QtyCell({ entry, listId, onUpdated }: QtyProps) {
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState(String(parseFloat(entry.quantity)))
  const inputRef = useRef<HTMLInputElement>(null)

  function start() {
    setValue(String(parseFloat(entry.quantity)))
    setEditing(true)
    setTimeout(() => inputRef.current?.select(), 0)
  }

  async function save() {
    const parsed = parseFloat(value)
    if (isNaN(parsed) || parsed <= 0) { setEditing(false); return }
    if (parsed === parseFloat(entry.quantity)) { setEditing(false); return }
    try {
      const updated = await updateShoppingListItem(listId, entry.id, parsed)
      onUpdated(updated)
    } catch {
      toast.error('Failed to update quantity')
    }
    setEditing(false)
  }

  if (editing) {
    return (
      <input
        ref={inputRef}
        className="w-16 text-right border border-costco-border-gray rounded px-1 py-0.5 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-costco-red"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onBlur={save}
        onKeyDown={(e) => { if (e.key === 'Enter') save(); if (e.key === 'Escape') setEditing(false) }}
      />
    )
  }
  return (
    <button
      onClick={start}
      className="font-mono text-sm hover:text-costco-blue transition-colors min-w-[3rem] text-right"
      title="Click to edit quantity"
    >
      {parseFloat(entry.quantity) % 1 === 0
        ? parseInt(entry.quantity).toString()
        : parseFloat(entry.quantity).toFixed(2)}
    </button>
  )
}

// ── Add-item combobox ─────────────────────────────────────────────────────────

interface AddItemProps {
  listId: number
  existingItemIds: Set<number>
  onAdded: (entry: ShoppingListItem) => void
}

function AddItemRow({ listId, existingItemIds, onAdded }: AddItemProps) {
  const { data: allItems = [] } = useQuery({ queryKey: ['items'], queryFn: getItems })
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [adding, setAdding] = useState(false)

  const eligible = allItems.filter((item) => {
    if (existingItemIds.has(item.id)) return false
    // Exclude coupon items (their description starts with / or friendly_name starts with "Coupon for")
    if (item.friendly_name?.startsWith('Coupon for')) return false
    const q = query.toLowerCase()
    return (
      !q ||
      item.item_code.includes(q) ||
      item.description.toLowerCase().includes(q) ||
      (item.friendly_name?.toLowerCase().includes(q) ?? false)
    )
  })

  function displayName(item: Item) {
    return item.friendly_name ?? item.description
  }

  async function pick(item: Item) {
    setAdding(true)
    setOpen(false)
    setQuery('')
    try {
      const entry = await addShoppingListItem(listId, item.id, 1)
      onAdded(entry)
    } catch {
      toast.error('Failed to add item')
    }
    setAdding(false)
  }

  return (
    <tr className="border-t-2 border-costco-border-gray">
      <td colSpan={5} className="px-4 py-3">
        <div className="relative">
          <div className="flex items-center gap-2">
            <Plus className="w-4 h-4 text-gray-400 shrink-0" />
            <input
              className="input flex-1 text-sm"
              placeholder="Search items to add…"
              value={query}
              onChange={(e) => { setQuery(e.target.value); setOpen(true) }}
              onFocus={() => setOpen(true)}
              onBlur={() => setTimeout(() => setOpen(false), 150)}
              disabled={adding}
            />
          </div>
          {open && eligible.length > 0 && (
            <ul className="absolute left-6 right-0 top-full mt-1 z-20 bg-white border border-costco-border-gray rounded-lg shadow-lg max-h-60 overflow-y-auto">
              {eligible.slice(0, 30).map((item) => (
                <li key={item.id}>
                  <button
                    className="w-full text-left px-4 py-2.5 hover:bg-gray-50 transition-colors flex items-center justify-between gap-3"
                    onMouseDown={() => pick(item)}
                  >
                    <span className="font-medium text-gray-800 text-sm">{displayName(item)}</span>
                    <span className="text-xs text-gray-400 shrink-0 flex items-center gap-1">
                      {item.is_by_weight && <Scale className="w-3 h-3" />}
                      {item.latest_price ? fmt(item.latest_price) : '—'}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </td>
    </tr>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ShoppingListDetail() {
  const { id } = useParams<{ id: string }>()
  const listId = Number(id)
  const queryClient = useQueryClient()

  const { data: list, isLoading, error } = useQuery({
    queryKey: ['shopping-list', listId],
    queryFn: () => getShoppingList(listId),
    enabled: Number.isFinite(listId),
  })

  const [editingName, setEditingName] = useState(false)
  const [nameValue, setNameValue] = useState('')

  if (isLoading) return <div className="text-sm text-gray-400 py-8 text-center">Loading…</div>
  if (error || !list) return <div className="text-sm text-red-600 py-8 text-center">List not found.</div>

  function updateCache(updater: (old: ShoppingList) => ShoppingList) {
    queryClient.setQueryData<ShoppingList>(['shopping-list', listId], (old) =>
      old ? updater(old) : old,
    )
  }

  function handleEntryUpdated(updated: ShoppingListItem) {
    updateCache((old) => ({
      ...old,
      items: old.items.map((e) => (e.id === updated.id ? updated : e)),
      total_estimate: recomputeTotal(old.items.map((e) => (e.id === updated.id ? updated : e))),
    }))
  }

  function handleAdded(entry: ShoppingListItem) {
    updateCache((old) => {
      const items = [...old.items, entry]
      return { ...old, items, total_estimate: recomputeTotal(items) }
    })
  }

  async function handleRemove(entryId: number) {
    try {
      await removeShoppingListItem(listId, entryId)
      updateCache((old) => {
        const items = old.items.filter((e) => e.id !== entryId)
        return { ...old, items, total_estimate: recomputeTotal(items) }
      })
    } catch {
      toast.error('Failed to remove item')
    }
  }

  async function handleRename() {
    const name = nameValue.trim()
    if (!name || name === list!.name) { setEditingName(false); return }
    try {
      const updated = await renameShoppingList(listId, name)
      updateCache((old) => ({ ...old, name: updated.name }))
      queryClient.invalidateQueries({ queryKey: ['shopping-lists'] })
    } catch {
      toast.error('Failed to rename list')
    }
    setEditingName(false)
  }

  const existingItemIds = new Set(list.items.map((e) => e.item_id))
  const nonCouponItems = list.items.filter(
    (e) => !e.friendly_name?.startsWith('Coupon for'),
  )
  const estimableCount = nonCouponItems.filter((e) => e.estimated_cost !== null).length
  const unknownCount = nonCouponItems.filter((e) => e.estimated_cost === null).length

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Link to="/shopping-lists" className="text-gray-400 hover:text-costco-blue transition-colors">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div className="flex-1 min-w-0">
          {editingName ? (
            <div className="flex items-center gap-2">
              <input
                className="input text-xl font-bold text-costco-blue flex-1"
                value={nameValue}
                onChange={(e) => setNameValue(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') handleRename(); if (e.key === 'Escape') setEditingName(false) }}
                autoFocus
              />
              <button className="btn-primary text-sm" onClick={handleRename}>Save</button>
              <button className="btn-ghost text-sm" onClick={() => setEditingName(false)}>Cancel</button>
            </div>
          ) : (
            <button
              className="group flex items-center gap-2 text-left"
              onClick={() => { setNameValue(list.name); setEditingName(true) }}
            >
              <h1 className="text-costco-blue">{list.name}</h1>
              <Pencil className="w-4 h-4 text-gray-300 group-hover:text-costco-blue opacity-0 group-hover:opacity-100 transition-opacity" />
            </button>
          )}
        </div>
      </div>

      {/* Estimate summary */}
      <div className="card p-5 flex items-center gap-6 border-l-4 border-costco-blue">
        <div>
          <p className="text-xs text-gray-500">Estimated total</p>
          <p className="text-3xl font-bold text-costco-blue font-mono">
            {list.total_estimate ? fmt(list.total_estimate) : '—'}
          </p>
        </div>
        {unknownCount > 0 && (
          <p className="text-sm text-gray-400">
            {estimableCount} of {nonCouponItems.length} items have prices
            {unknownCount > 0 && ` · ${unknownCount} unknown`}
          </p>
        )}
      </div>

      {/* Items table */}
      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-costco-border-gray">
            <tr>
              <th className="text-left px-4 py-3 font-semibold text-gray-600">Item</th>
              <th className="text-center px-4 py-3 font-semibold text-gray-600 w-28">Qty / unit</th>
              <th className="text-right px-4 py-3 font-semibold text-gray-600 w-28">Unit price</th>
              <th className="text-right px-4 py-3 font-semibold text-gray-600 w-28">Est. cost</th>
              <th className="w-10"></th>
            </tr>
          </thead>
          <tbody>
            {list.items.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-10 text-center text-gray-400 text-sm">
                  No items yet — search below to add some.
                </td>
              </tr>
            ) : (
              list.items.map((entry) => {
                const unitLabel = entry.is_by_weight ? 'lb' : 'ea'
                const unitPrice = entry.is_by_weight
                  ? (entry.latest_price_per_lb ? `${fmt(entry.latest_price_per_lb)}/lb` : '—')
                  : (entry.latest_price ? fmt(entry.latest_price) : '—')

                return (
                  <tr key={entry.id} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3">
                      <p className="font-medium text-gray-800">
                        {entry.friendly_name ?? entry.description}
                      </p>
                      {entry.friendly_name && (
                        <p className="text-xs text-gray-400">{entry.description}</p>
                      )}
                      {entry.is_by_weight && (
                        <span className="inline-flex items-center gap-0.5 text-xs text-gray-400 mt-0.5">
                          <Scale className="w-3 h-3" /> by weight
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <div className="flex items-center justify-center gap-1">
                        <QtyCell entry={entry} listId={listId} onUpdated={handleEntryUpdated} />
                        <span className="text-xs text-gray-400">{unitLabel}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-gray-700">
                      {unitPrice}
                    </td>
                    <td className="px-4 py-3 text-right font-mono font-semibold text-gray-800">
                      {entry.estimated_cost ? fmt(entry.estimated_cost) : (
                        <span className="text-gray-300 font-normal text-xs">
                          {entry.is_by_weight ? 'set $/lb' : 'no price'}
                        </span>
                      )}
                    </td>
                    <td className="px-2 py-3">
                      <button
                        onClick={() => handleRemove(entry.id)}
                        className="text-gray-300 hover:text-red-500 transition-colors"
                        title="Remove from list"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                )
              })
            )}
            <AddItemRow
              listId={listId}
              existingItemIds={existingItemIds}
              onAdded={handleAdded}
            />
          </tbody>
        </table>
      </div>
    </div>
  )
}

function recomputeTotal(items: ShoppingListItem[]): string | null {
  const costs = items.map((e) => e.estimated_cost).filter((c): c is string => c !== null)
  if (costs.length === 0) return null
  const total = costs.reduce((sum, c) => sum + parseFloat(c), 0)
  return total.toFixed(2)
}
