// ai: claude-sonnet-4-6 | 2026-06-18
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { PlusCircle, Receipt as ReceiptIcon } from 'lucide-react'
import { getReceipts } from '../api/client'
import ReceiptUploadZone from '../components/ReceiptUploadZone'
import ReceiptReviewDialog from '../components/ReceiptReviewDialog'
import type { OcrResponse } from '../types'

export default function Receipts() {
  const { data: receipts = [], isLoading } = useQuery({
    queryKey: ['receipts'],
    queryFn: getReceipts,
  })
  const [ocr, setOcr] = useState<OcrResponse | null>(null)
  const [showUpload, setShowUpload] = useState(false)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-costco-blue">Receipts</h1>
          <p className="text-sm text-gray-500">{receipts.length} imported</p>
        </div>
        <button
          className="btn-primary flex items-center gap-2"
          onClick={() => setShowUpload(!showUpload)}
        >
          <PlusCircle className="w-4 h-4" />
          Import Receipt
        </button>
      </div>

      {/* Upload zone */}
      {showUpload && (
        <div className="card p-5 space-y-3">
          <h2 className="text-costco-blue text-base">Upload Receipt Screenshot</h2>
          <p className="text-xs text-gray-500">
            Screenshot your Costco receipt page (from costco.com) and drop it below.
            Claude will extract the line items for your review.
          </p>
          <ReceiptUploadZone onParsed={(result) => { setOcr(result); setShowUpload(false) }} />
        </div>
      )}

      {/* Receipt list */}
      <div className="card overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-gray-400 text-sm">Loading…</div>
        ) : receipts.length === 0 ? (
          <div className="p-10 text-center space-y-3">
            <ReceiptIcon className="w-12 h-12 mx-auto text-gray-200" />
            <p className="text-gray-500">No receipts yet.</p>
            <button
              className="btn-primary"
              onClick={() => setShowUpload(true)}
            >
              Import your first receipt
            </button>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-costco-border-gray">
              <tr>
                <th className="text-left px-4 py-3 font-semibold text-gray-600">Date</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600">Store</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600">Barcode</th>
                <th className="text-right px-4 py-3 font-semibold text-gray-600">Items</th>
                <th className="text-right px-4 py-3 font-semibold text-gray-600">Report</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {receipts.map((r) => (
                <tr key={r.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 font-medium text-gray-800">{r.shopping_date}</td>
                  <td className="px-4 py-3 text-gray-500">{r.store_location ?? '—'}</td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-400">{r.barcode ?? '—'}</td>
                  <td className="px-4 py-3 text-right font-semibold text-costco-blue">
                    {r.line_count}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Link
                      to={`/reports/${r.id}`}
                      className="text-costco-red hover:underline text-sm font-medium"
                    >
                      View report →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {ocr && (
        <ReceiptReviewDialog
          ocr={ocr}
          onClose={() => setOcr(null)}
        />
      )}
    </div>
  )
}
