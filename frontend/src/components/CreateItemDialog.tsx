// =============================================================================
// Copyright (c) 2026 ZombieTech LLC. All rights reserved.
//
// SPDX-License-Identifier: PolyForm-Strict-1.0.0
// See LICENSE in the project root for the full terms.
//
// Licensing inquiries: license@zombietech.biz
// =============================================================================
// ai: gpt-5 | 2026-11-03
import { useState } from 'react'
import axios from 'axios'
import { X } from 'lucide-react'
import toast from 'react-hot-toast'
import { createItem } from '../api/client'
import type { Item } from '../types'

interface Props {
  onClose: () => void
  onCreated: (item: Item) => void
}

export default function CreateItemDialog({ onClose, onCreated }: Props) {
  const [itemCode, setItemCode] = useState('')
  const [description, setDescription] = useState('')
  const [friendlyName, setFriendlyName] = useState('')
  const [taxType, setTaxType] = useState('')
  const [isByWeight, setIsByWeight] = useState(false)
  const [saving, setSaving] = useState(false)

  async function handleSave() {
    const trimmedCode = itemCode.trim()
    const trimmedDescription = description.trim()
    if (!trimmedCode || !trimmedDescription) {
      toast.error('Item code and receipt description are required')
      return
    }

    setSaving(true)
    try {
      const item = await createItem({
        item_code: trimmedCode,
        description: trimmedDescription,
        friendly_name: friendlyName.trim() || null,
        tax_type: taxType || null,
        is_by_weight: isByWeight,
      })
      onCreated(item)
      toast.success('Item added')
      onClose()
    } catch (error) {
      const detail = axios.isAxiosError(error) ? error.response?.data?.detail : null
      toast.error(typeof detail === 'string' ? detail : 'Failed to add item')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="card w-full max-w-md p-6 space-y-4" role="dialog" aria-modal="true" aria-labelledby="create-item-title">
        <div className="flex items-center justify-between">
          <h2 id="create-item-title" className="text-costco-blue">Add Item</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600" aria-label="Close">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1" htmlFor="new-item-code">Item code</label>
            <input id="new-item-code" className="input" value={itemCode} onChange={(event) => setItemCode(event.target.value)} maxLength={20} autoFocus />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1" htmlFor="new-item-description">Receipt description</label>
            <input id="new-item-description" className="input" value={description} onChange={(event) => setDescription(event.target.value)} maxLength={200} />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1" htmlFor="new-item-friendly-name">Friendly name</label>
            <input id="new-item-friendly-name" className="input" placeholder="Optional display name" value={friendlyName} onChange={(event) => setFriendlyName(event.target.value)} maxLength={200} />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1" htmlFor="new-item-tax-type">Tax type</label>
            <select id="new-item-tax-type" className="input" value={taxType} onChange={(event) => setTaxType(event.target.value)}>
              <option value="">Unknown</option>
              <option value="3">3 — Grocery / food</option>
              <option value="Y">Y — Prepared food</option>
              <option value="A">A — Non-food</option>
            </select>
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
            <input type="checkbox" checked={isByWeight} onChange={(event) => setIsByWeight(event.target.checked)} className="w-4 h-4 accent-costco-red" />
            Priced by weight (meat / fish)
          </label>
        </div>

        <div className="flex gap-2 pt-2">
          <button className="btn-ghost flex-1" onClick={onClose}>Cancel</button>
          <button className="btn-primary flex-1" onClick={handleSave} disabled={saving}>
            {saving ? 'Adding…' : 'Add Item'}
          </button>
        </div>
      </div>
    </div>
  )
}
