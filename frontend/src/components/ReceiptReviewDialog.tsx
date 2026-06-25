// ai: claude-sonnet-4-6 | 2026-06-18
import { useState } from 'react'
import { CheckCircle, Trash2, X } from 'lucide-react'
import toast from 'react-hot-toast'
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { confirmReceipt } from '../api/client'
import type { OcrResponse, ParsedLine } from '../types'

interface Props {
  ocr: OcrResponse
  onClose: () => void
  onSaved?: () => void
}

export default function ReceiptReviewDialog({ ocr, onClose, onSaved }: Props) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [lines, setLines] = useState<ParsedLine[]>(ocr.lines)
  // Pre-fill from OCR extraction; user can override
  const [shoppingDate, setShoppingDate] = useState(
    ocr.detected_date ?? new Date().toISOString().slice(0, 10),
  )
  const [storeLocation, setStoreLocation] = useState(ocr.detected_store ?? '')
  const [saving, setSaving] = useState(false)

  function removeLine(idx: number) {
    setLines((prev) => prev.filter((_, i) => i !== idx))
  }

  function updateLine(idx: number, field: keyof ParsedLine, value: string | boolean | null) {
    setLines((prev) => prev.map((l, i) => (i === idx ? { ...l, [field]: value } : l)))
  }

  async function handleConfirm() {
    if (lines.length === 0) {
      toast.error('Add at least one line item')
      return
    }
    if (!shoppingDate) {
      toast.error('Shopping date is required')
      return
    }

    setSaving(true)
    try {
      const report = await confirmReceipt({
        shopping_date: shoppingDate,
        store_location: storeLocation.trim() || null,
        barcode: ocr.barcode || null,
        lines,
      })
      // Force immediate refetch — don't rely on staleTime expiring
      await Promise.all([
        queryClient.refetchQueries({ queryKey: ['receipts'] }),
        queryClient.refetchQueries({ queryKey: ['items'] }),
      ])
      onSaved?.()
      toast.success('Receipt saved!')
      onClose()
      navigate(`/reports/${report.receipt_id}`)
    } catch (err: unknown) {
      if (axios.isAxiosError(err) && err.response?.status === 409) {
        toast.error(
          `Duplicate receipt: ${err.response.data?.detail ?? 'already imported'}`,
          { duration: 8000 },
        )
      } else {
        toast.error('Failed to save receipt')
      }
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-start justify-center z-50 p-4 overflow-y-auto">
      <div className="card w-full max-w-4xl my-6 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-costco-border-gray">
          <div>
            <h2 className="text-costco-blue">Review Receipt Items</h2>
            {ocr.barcode && (
              <p className="text-xs text-gray-400 font-mono mt-0.5">
                Barcode: {ocr.barcode}
              </p>
            )}
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Date + location */}
        <div className="p-5 border-b border-costco-border-gray grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Shopping date <span className="text-costco-red">*</span>
            </label>
            <input
              type="date"
              className="input"
              value={shoppingDate}
              onChange={(e) => setShoppingDate(e.target.value)}
            />
            {ocr.detected_date && (
              <p className="text-xs text-gray-400 mt-1">Auto-filled from receipt</p>
            )}
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Store location (optional)
            </label>
            <input
              className="input"
              placeholder="e.g. Costco Warehouse #123"
              value={storeLocation}
              onChange={(e) => setStoreLocation(e.target.value)}
            />
            {ocr.detected_store && (
              <p className="text-xs text-gray-400 mt-1">Auto-filled from receipt</p>
            )}
          </div>
        </div>

        {/* Line items table */}
        <div className="overflow-y-auto max-h-[50vh]">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-gray-50 border-b border-costco-border-gray">
              <tr>
                <th className="text-left px-4 py-2 font-semibold text-gray-600 w-24">Code</th>
                <th className="text-left px-4 py-2 font-semibold text-gray-600">Description</th>
                <th className="text-right px-4 py-2 font-semibold text-gray-600 w-24">Price</th>
                <th className="text-center px-4 py-2 font-semibold text-gray-600 w-20">Tax</th>
                <th className="text-center px-4 py-2 font-semibold text-gray-600 w-20">Coupon</th>
                <th className="w-10"></th>
              </tr>
            </thead>
            <tbody>
              {lines.map((line, idx) => (
                <tr
                  key={idx}
                  className={`border-b border-gray-50 ${line.is_coupon ? 'bg-yellow-50' : ''}`}
                >
                  <td className="px-4 py-1.5 font-mono text-xs text-gray-500">{line.item_code}</td>
                  <td className="px-4 py-1.5">
                    <input
                      className="w-full text-sm border-0 bg-transparent focus:outline-none focus:ring-1 focus:ring-costco-red rounded px-1"
                      value={line.description}
                      onChange={(e) => updateLine(idx, 'description', e.target.value)}
                    />
                  </td>
                  <td className="px-4 py-1.5 text-right">
                    <input
                      className="w-20 text-sm text-right border-0 bg-transparent focus:outline-none focus:ring-1 focus:ring-costco-red rounded px-1 font-mono"
                      value={line.price}
                      onChange={(e) => updateLine(idx, 'price', e.target.value)}
                    />
                  </td>
                  <td className="px-4 py-1.5 text-center text-xs text-gray-500">
                    {line.tax_type ?? '—'}
                  </td>
                  <td className="px-4 py-1.5 text-center">
                    {line.is_coupon && <span className="badge-coupon">coupon</span>}
                  </td>
                  <td className="px-2 py-1.5">
                    <button
                      onClick={() => removeLine(idx)}
                      className="text-gray-300 hover:text-red-500 transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Summary + actions */}
        <div className="p-5 border-t border-costco-border-gray flex items-center justify-between gap-4">
          <p className="text-sm text-gray-600">
            <span className="font-semibold">{lines.filter((l) => !l.is_coupon).length}</span> items
            {lines.some((l) => l.is_coupon) && (
              <>
                ,{' '}
                <span className="font-semibold">{lines.filter((l) => l.is_coupon).length}</span>{' '}
                coupons
              </>
            )}
          </p>
          <div className="flex gap-2">
            <button className="btn-ghost" onClick={onClose}>
              Cancel
            </button>
            <button
              className="btn-primary flex items-center gap-2"
              onClick={handleConfirm}
              disabled={saving}
            >
              <CheckCircle className="w-4 h-4" />
              {saving ? 'Saving…' : 'Confirm & Save'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
