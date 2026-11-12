// ai: claude-sonnet-4-6 | 2026-06-18
import { useState } from 'react'
import { X } from 'lucide-react'
import toast from 'react-hot-toast'
import { updateItem } from '../api/client'
import type { Item } from '../types'

interface Props {
  item: Item
  onClose: () => void
  onSaved: (updated: Item) => void
}

export default function EditItemDialog({ item, onClose, onSaved }: Props) {
  const [friendlyName, setFriendlyName] = useState(item.friendly_name ?? '')
  const [taxType, setTaxType] = useState(item.tax_type ?? '')
  const [isByWeight, setIsByWeight] = useState(item.is_by_weight)
  const [latestPrice, setLatestPrice] = useState(item.latest_price ?? '')
  const [saving, setSaving] = useState(false)

  async function handleSave() {
    const parsedPrice = Number(latestPrice)
    if (latestPrice && (!Number.isFinite(parsedPrice) || parsedPrice <= 0)) {
      toast.error('Latest price must be greater than zero')
      return
    }

    setSaving(true)
    try {
      const updated = await updateItem(item.id, {
        friendly_name: friendlyName.trim() || null,
        tax_type: taxType.trim() || null,
        is_by_weight: isByWeight,
        ...(latestPrice ? { latest_price: parsedPrice.toFixed(2) } : {}),
      })
      onSaved(updated)
      toast.success('Item updated')
      onClose()
    } catch {
      toast.error('Failed to save item')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="card w-full max-w-md p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-costco-blue">Edit Item</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="space-y-1">
          <p className="text-xs text-gray-500 font-mono">{item.item_code}</p>
          <p className="text-sm text-gray-700">{item.description}</p>
        </div>

        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Friendly name
            </label>
            <input
              className="input"
              placeholder="e.g. Sensodyne Pronamel Toothpaste"
              value={friendlyName}
              onChange={(e) => setFriendlyName(e.target.value)}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Latest price
            </label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">$</span>
              <input
                className="input pl-7"
                type="number"
                min="0.01"
                step="0.01"
                value={latestPrice}
                onChange={(e) => setLatestPrice(e.target.value)}
                placeholder="Enter a price"
              />
            </div>
            {item.latest_price === null && (
              <p className="mt-1 text-xs text-gray-400">This will be saved as the item&rsquo;s manual price.</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Tax type
            </label>
            <select
              className="input"
              value={taxType}
              onChange={(e) => setTaxType(e.target.value)}
            >
              <option value="">Unknown</option>
              <option value="3">3 — Grocery / food</option>
              <option value="Y">Y — Prepared food</option>
              <option value="A">A — Non-food</option>
            </select>
          </div>

          <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
            <input
              type="checkbox"
              checked={isByWeight}
              onChange={(e) => setIsByWeight(e.target.checked)}
              className="w-4 h-4 accent-costco-red"
            />
            Priced by weight (meat / fish)
          </label>
        </div>

        <div className="flex gap-2 pt-2">
          <button className="btn-ghost flex-1" onClick={onClose}>
            Cancel
          </button>
          <button className="btn-primary flex-1" onClick={handleSave} disabled={saving}>
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}
