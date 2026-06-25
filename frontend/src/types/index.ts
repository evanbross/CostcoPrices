// ai: claude-sonnet-4-6 | 2026-06-18

export interface PriceHistoryEntry {
  id: number
  receipt_id: number
  price: string
  price_per_lb: string | null
  is_coupon: boolean
  coupon_for_item_id: number | null
  created_at: string
  shopping_date: string | null
}

export interface Item {
  id: number
  item_code: string
  description: string
  friendly_name: string | null
  tax_type: string | null
  is_by_weight: boolean
  created_at: string
  updated_at: string
  latest_price: string | null
}

export interface ItemDetail extends Item {
  price_history: PriceHistoryEntry[]
}

export interface ItemUpdate {
  friendly_name?: string | null
  tax_type?: string | null
  is_by_weight?: boolean
}

export interface ParsedLine {
  item_code: string
  description: string
  price: string
  tax_type: string | null
  is_coupon: boolean
  coupon_for_code: string | null
  line_prefix: string | null
}

export interface OcrResponse {
  lines: ParsedLine[]
  raw_text: string | null
  barcode: string | null
  detected_date: string | null
  detected_store: string | null
}

export interface ReceiptConfirmRequest {
  shopping_date: string
  store_location?: string | null
  notes?: string | null
  barcode?: string | null
  lines: ParsedLine[]
}

export interface Receipt {
  id: number
  barcode: string | null
  shopping_date: string
  store_location: string | null
  notes: string | null
  created_at: string
  line_count: number
}

export interface ReceiptLine {
  id: number
  item_id: number
  item_code: string
  description: string
  friendly_name: string | null
  price: string
  is_coupon: boolean
  coupon_for_item_id: number | null
}

export interface ReceiptDetail extends Receipt {
  lines: ReceiptLine[]
}

export interface ImportReportItem {
  item_id: number
  item_code: string
  description: string
  friendly_name: string | null
  price: string
}

export interface PriceChange {
  item_id: number
  item_code: string
  description: string
  friendly_name: string | null
  old_price: string
  new_price: string
  change: string
}

export interface ImportReport {
  receipt_id: number
  new_items: ImportReportItem[]
  price_changes: PriceChange[]
  unchanged: ImportReportItem[]
  coupons: ImportReportItem[]
}

// ---------------------------------------------------------------------------
// Shopping Lists
// ---------------------------------------------------------------------------

export interface ShoppingListItem {
  id: number
  item_id: number
  item_code: string
  description: string
  friendly_name: string | null
  is_by_weight: boolean
  quantity: string
  note: string | null
  latest_price: string | null
  latest_price_per_lb: string | null
  estimated_cost: string | null
}

export interface ShoppingList {
  id: number
  name: string
  created_at: string
  updated_at: string
  items: ShoppingListItem[]
  total_estimate: string | null
}

export interface ShoppingListSummary {
  id: number
  name: string
  created_at: string
  updated_at: string
  item_count: number
  total_estimate: string | null
}
