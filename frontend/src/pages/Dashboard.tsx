// ai: claude-sonnet-4-6 | 2026-06-19
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Package, Receipt, TrendingUp } from 'lucide-react'
import { getItems, getReceipts } from '../api/client'
import ReceiptUploadZone from '../components/ReceiptUploadZone'
import ReceiptReviewDialog from '../components/ReceiptReviewDialog'
import type { OcrResponse } from '../types'

export default function Dashboard() {
  const { data: items = [] } = useQuery({ queryKey: ['items'], queryFn: getItems })
  const { data: receipts = [] } = useQuery({ queryKey: ['receipts'], queryFn: getReceipts })
  const [ocr, setOcr] = useState<OcrResponse | null>(null)
  const [uploadKey, setUploadKey] = useState(0)

  const recentReceipts = receipts.slice(0, 5)

  // Count items that have had a price increase vs. decrease across all history
  const itemsWithPrices = items.filter((i) => i.latest_price !== null)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-costco-blue">Dashboard</h1>
        <p className="text-gray-500 text-sm mt-1">Your Costco price tracking summary</p>
      </div>

      {/* Stats */}
      {/* ai: claude-sonnet-5 | 2026-07-20 */}
      <div className="grid grid-cols-3 gap-4">
        <Link to="/items" className="card p-5 flex items-center gap-4 hover:shadow-md transition-shadow">
          <div className="w-12 h-12 rounded-full bg-costco-red/10 flex items-center justify-center shrink-0">
            <Package className="w-6 h-6 text-costco-red" />
          </div>
          <div>
            <p className="text-3xl font-bold text-costco-blue">{items.length}</p>
            <p className="text-sm text-gray-500">Tracked items</p>
          </div>
        </Link>
        <Link to="/receipts" className="card p-5 flex items-center gap-4 hover:shadow-md transition-shadow">
          <div className="w-12 h-12 rounded-full bg-costco-blue/10 flex items-center justify-center shrink-0">
            <Receipt className="w-6 h-6 text-costco-blue" />
          </div>
          <div>
            <p className="text-3xl font-bold text-costco-blue">{receipts.length}</p>
            <p className="text-sm text-gray-500">Receipts imported</p>
          </div>
        </Link>
        <div className="card p-5 flex items-center gap-4">
          <div className="w-12 h-12 rounded-full bg-costco-gold/10 flex items-center justify-center shrink-0">
            <TrendingUp className="w-6 h-6 text-costco-gold" />
          </div>
          <div>
            <p className="text-3xl font-bold text-costco-blue">{itemsWithPrices.length}</p>
            <p className="text-sm text-gray-500">Items with prices</p>
          </div>
        </div>
      </div>

      {/* Upload zone */}
      <div className="card p-5">
        <h2 className="text-costco-blue text-base mb-3">Import Receipt</h2>
        <ReceiptUploadZone key={uploadKey} onParsed={(result) => setOcr(result)} />
      </div>

      {/* Recent receipts */}
      <div className="card">
        <div className="flex items-center justify-between px-5 py-4 border-b border-costco-border-gray">
          <h2 className="text-costco-blue">Recent Receipts</h2>
          <Link to="/receipts" className="text-sm text-costco-red hover:underline font-medium">
            View all →
          </Link>
        </div>
        {recentReceipts.length === 0 ? (
          <div className="p-8 text-center text-gray-400">
            <Receipt className="w-10 h-10 mx-auto mb-3 opacity-30" />
            <p className="text-sm">No receipts yet.</p>
            <Link to="/receipts" className="text-sm text-costco-red hover:underline mt-1 inline-block">
              View all receipts →
            </Link>
          </div>
        ) : (
          <ul className="divide-y divide-gray-50">
            {recentReceipts.map((r) => (
              <li key={r.id}>
                <Link
                  to={`/reports/${r.id}`}
                  className="flex items-center justify-between px-5 py-3 hover:bg-gray-50 transition-colors"
                >
                  <div>
                    <p className="font-medium text-gray-800">{r.shopping_date}</p>
                    <p className="text-xs text-gray-500">{r.store_location ?? 'Unknown store'}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-semibold text-costco-blue">{r.line_count} items</p>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>

      {ocr && (
        <ReceiptReviewDialog
          ocr={ocr}
          onClose={() => setOcr(null)}
          onSaved={() => setUploadKey((k) => k + 1)}
        />
      )}
    </div>
  )
}
