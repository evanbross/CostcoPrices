// ai: claude-sonnet-4-6 | 2026-06-18
// ai: claude-sonnet-4-6 | 2026-06-20
import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Pencil, Scale, Tag } from 'lucide-react'
import { getItem } from '../api/client'
import PriceHistoryTable from '../components/PriceHistoryTable'
import EditItemDialog from '../components/EditItemDialog'
import type { Item, ItemDetail, PriceHistoryEntry } from '../types'

const TAX_LABELS: Record<string, string> = {
  '3': 'Grocery / food',
  Y: 'Prepared food',
  A: 'Non-food',
}

export default function ItemDetail() {
  const { id } = useParams<{ id: string }>()
  const itemId = Number(id)
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)

  const { data: item, isLoading, error } = useQuery({
    queryKey: ['item', itemId],
    queryFn: () => getItem(itemId),
    enabled: Number.isFinite(itemId),
  })

  function handleSaved(updated: Item) {
    queryClient.setQueryData(['item', itemId], (old: typeof item) =>
      old ? { ...old, ...updated } : old,
    )
    queryClient.setQueryData<Item[]>(['items'], (old = []) =>
      old.map((i) => (i.id === updated.id ? updated : i)),
    )
  }

  function handleHistoryEntryUpdated(updated: PriceHistoryEntry) {
    queryClient.setQueryData<ItemDetail>(['item', itemId], (old) => {
      if (!old) return old
      return {
        ...old,
        price_history: old.price_history.map((e) => (e.id === updated.id ? updated : e)),
      }
    })
  }

  if (isLoading) return <div className="text-sm text-gray-400 py-8 text-center">Loading…</div>
  if (error || !item) return <div className="text-sm text-red-600 py-8 text-center">Item not found.</div>

  const nonCouponHistory = item.price_history.filter((h) => !h.is_coupon)
  const latestPrice = nonCouponHistory.at(-1)

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link to="/items" className="text-gray-400 hover:text-costco-blue transition-colors">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div className="flex-1">
          <h1 className="text-costco-blue">
            {item.friendly_name ?? item.description}
          </h1>
          {item.friendly_name && (
            <p className="text-sm text-gray-500">{item.description}</p>
          )}
        </div>
        <button
          onClick={() => setEditing(true)}
          className="btn-ghost flex items-center gap-2 text-sm"
        >
          <Pencil className="w-4 h-4" />
          Edit
        </button>
      </div>

      {/* Item metadata */}
      <div className="grid grid-cols-3 gap-4">
        <div className="card p-4">
          <p className="text-xs text-gray-500 mb-1">Item code</p>
          <p className="font-mono font-semibold text-gray-800">{item.item_code}</p>
        </div>
        <div className="card p-4 flex items-center gap-2">
          <Tag className="w-4 h-4 text-gray-400" />
          <div>
            <p className="text-xs text-gray-500 mb-0.5">Tax type</p>
            <p className="text-sm font-medium">
              {item.tax_type ? `${item.tax_type} — ${TAX_LABELS[item.tax_type] ?? 'Unknown'}` : '—'}
            </p>
          </div>
        </div>
        <div className="card p-4 flex items-center gap-2">
          <Scale className="w-4 h-4 text-gray-400" />
          <div>
            <p className="text-xs text-gray-500 mb-0.5">Pricing</p>
            <p className="text-sm font-medium">
              {item.is_by_weight ? 'By weight' : 'Unit price'}
            </p>
          </div>
        </div>
      </div>

      {/* Current price callout */}
      {latestPrice && (() => {
        const isWeight = item.is_by_weight
        // For weight items: prefer per-lb for the change badge; show total + per-lb if set
        const latestPerLb = isWeight ? latestPrice.price_per_lb : null
        const prevEntry = nonCouponHistory.length >= 2 ? nonCouponHistory[nonCouponHistory.length - 2] : null
        const prevPerLb = isWeight && prevEntry ? prevEntry.price_per_lb : null

        let diff: number | null = null
        let diffLabel = ''
        if (isWeight && latestPerLb && prevPerLb) {
          diff = parseFloat(latestPerLb) - parseFloat(prevPerLb)
          diffLabel = '/lb from last visit'
        } else if (!isWeight && prevEntry) {
          diff = parseFloat(latestPrice.price) - parseFloat(prevEntry.price)
          diffLabel = ' from last visit'
        }

        return (
          <div className="card p-5 flex items-center gap-4 border-l-4 border-costco-red">
            <div>
              <p className="text-xs text-gray-500">Latest price</p>
              <p className="text-3xl font-bold text-costco-blue font-mono">
                ${parseFloat(latestPrice.price).toFixed(2)}
              </p>
              {isWeight && latestPerLb && (
                <p className="text-sm text-gray-500 font-mono mt-0.5">
                  ${parseFloat(latestPerLb).toFixed(2)}/lb
                </p>
              )}
              {isWeight && !latestPerLb && (
                <p className="text-xs text-gray-400 mt-0.5 italic">no $/lb set — add in history below</p>
              )}
            </div>
            {diff !== null && diff !== 0 && (
              <span className={diff > 0 ? 'badge-up text-sm px-3 py-1' : 'badge-down text-sm px-3 py-1'}>
                {diff > 0 ? '+' : ''}${Math.abs(diff).toFixed(2)}{diffLabel}
              </span>
            )}
          </div>
        )
      })()}

      {/* Price history */}
      <div className="card">
        <div className="px-5 py-4 border-b border-costco-border-gray">
          <h2 className="text-costco-blue">Price History</h2>
        </div>
        <div className="p-4">
          <PriceHistoryTable
            history={item.price_history}
            isWeightItem={item.is_by_weight}
            onEntryUpdated={handleHistoryEntryUpdated}
          />
        </div>
      </div>

      {editing && (
        <EditItemDialog
          item={item}
          onClose={() => setEditing(false)}
          onSaved={handleSaved}
        />
      )}
    </div>
  )
}
