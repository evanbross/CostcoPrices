// ai: claude-sonnet-4-6 | 2026-06-18
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, CheckCircle, Tag, TrendingDown, TrendingUp } from 'lucide-react'
import { getReceiptReport } from '../api/client'

function fmt(price: string) {
  return `$${parseFloat(price).toFixed(2)}`
}

export default function Reports() {
  const { receiptId } = useParams<{ receiptId: string }>()
  const id = Number(receiptId)

  const { data: report, isLoading, error } = useQuery({
    queryKey: ['report', id],
    queryFn: () => getReceiptReport(id),
    enabled: Number.isFinite(id),
  })

  if (isLoading) return <div className="text-sm text-gray-400 py-8 text-center">Loading report…</div>
  if (error || !report) return <div className="text-sm text-red-600 py-8 text-center">Report not found.</div>

  const total =
    report.new_items.length + report.price_changes.length + report.unchanged.length

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link to="/receipts" className="text-gray-400 hover:text-costco-blue transition-colors">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div>
          <h1 className="text-costco-blue">Import Report — Receipt #{report.receipt_id}</h1>
          <p className="text-sm text-gray-500">{total} items processed</p>
        </div>
      </div>

      {/* Summary chips */}
      <div className="flex gap-3 flex-wrap">
        <div className="badge-new px-3 py-1.5 text-sm gap-1.5">
          <span className="font-bold">{report.new_items.length}</span> new items
        </div>
        <div className={`px-3 py-1.5 text-sm gap-1.5 rounded font-semibold inline-flex items-center ${
          report.price_changes.length > 0 ? 'badge-up' : 'bg-gray-100 text-gray-600'
        }`}>
          <span className="font-bold">{report.price_changes.length}</span> price changes
        </div>
        <div className="bg-gray-100 text-gray-600 px-3 py-1.5 text-sm gap-1.5 rounded font-semibold inline-flex items-center">
          <span className="font-bold">{report.unchanged.length}</span> unchanged
        </div>
        {report.coupons.length > 0 && (
          <div className="badge-coupon px-3 py-1.5 text-sm gap-1.5">
            <span className="font-bold">{report.coupons.length}</span> coupons
          </div>
        )}
      </div>

      {/* Price changes */}
      {report.price_changes.length > 0 && (
        <div className="card">
          <div className="px-5 py-4 border-b border-costco-border-gray flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-costco-red" />
            <h2 className="text-costco-blue">Price Changes</h2>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-costco-border-gray">
              <tr>
                <th className="text-left px-4 py-2 font-semibold text-gray-600">Item</th>
                <th className="text-right px-4 py-2 font-semibold text-gray-600">Old</th>
                <th className="text-right px-4 py-2 font-semibold text-gray-600">New</th>
                <th className="text-right px-4 py-2 font-semibold text-gray-600">Change</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {report.price_changes.map((c) => {
                const diff = parseFloat(c.change)
                return (
                  <tr key={c.item_id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <Link to={`/items/${c.item_id}`} className="font-medium text-costco-blue hover:underline">
                        {c.friendly_name ?? c.description}
                      </Link>
                      <p className="text-xs text-gray-400 font-mono">{c.item_code}</p>
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-gray-500 line-through">
                      {fmt(c.old_price)}
                    </td>
                    <td className="px-4 py-3 text-right font-mono font-semibold">
                      {fmt(c.new_price)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {diff > 0 ? (
                        <span className="badge-up flex items-center gap-1 justify-end">
                          <TrendingUp className="w-3 h-3" />+{fmt(c.change)}
                        </span>
                      ) : (
                        <span className="badge-down flex items-center gap-1 justify-end">
                          <TrendingDown className="w-3 h-3" />{fmt(c.change)}
                        </span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* New items */}
      {report.new_items.length > 0 && (
        <div className="card">
          <div className="px-5 py-4 border-b border-costco-border-gray flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-green-600" />
            <h2 className="text-costco-blue">New Items</h2>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-costco-border-gray">
              <tr>
                <th className="text-left px-4 py-2 font-semibold text-gray-600">Item</th>
                <th className="text-right px-4 py-2 font-semibold text-gray-600">Price</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {report.new_items.map((item) => (
                <tr key={item.item_id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <Link to={`/items/${item.item_id}`} className="font-medium text-costco-blue hover:underline">
                      {item.friendly_name ?? item.description}
                    </Link>
                    <p className="text-xs text-gray-400 font-mono">{item.item_code}</p>
                  </td>
                  <td className="px-4 py-3 text-right font-mono font-semibold">
                    {fmt(item.price)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Coupons */}
      {report.coupons.length > 0 && (
        <div className="card">
          <div className="px-5 py-4 border-b border-costco-border-gray flex items-center gap-2">
            <Tag className="w-4 h-4 text-yellow-600" />
            <h2 className="text-costco-blue">Coupons / Discounts</h2>
          </div>
          <table className="w-full text-sm">
            <tbody className="divide-y divide-gray-50">
              {report.coupons.map((c) => (
                <tr key={c.item_id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-gray-700">{c.description}</td>
                  <td className="px-4 py-3 text-right font-mono font-semibold text-green-700">
                    {fmt(c.price)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Unchanged (collapsed) */}
      {report.unchanged.length > 0 && (
        <details className="card">
          <summary className="px-5 py-4 cursor-pointer text-sm font-semibold text-gray-600 hover:text-gray-800 select-none">
            {report.unchanged.length} items unchanged (click to expand)
          </summary>
          <table className="w-full text-sm border-t border-costco-border-gray">
            <tbody className="divide-y divide-gray-50">
              {report.unchanged.map((item) => (
                <tr key={item.item_id} className="hover:bg-gray-50">
                  <td className="px-4 py-2.5">
                    <Link to={`/items/${item.item_id}`} className="text-costco-blue hover:underline">
                      {item.friendly_name ?? item.description}
                    </Link>
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono text-gray-600">
                    {fmt(item.price)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      )}
    </div>
  )
}
