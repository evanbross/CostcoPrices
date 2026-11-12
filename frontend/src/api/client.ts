// ai: claude-sonnet-4-6 | 2026-06-20
import axios from 'axios'
import type {
  ImportReport,
  Item,
  ItemCreate,
  ItemDetail,
  ItemUpdate,
  OcrResponse,
  PriceHistoryEntry,
  Receipt,
  ReceiptConfirmRequest,
  ReceiptDetail,
  ShoppingList,
  ShoppingListItem,
  ShoppingListSummary,
} from '../types'

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

// Items
export async function getItems(): Promise<Item[]> {
  const res = await api.get<Item[]>('/items')
  return res.data
}

export async function getItem(id: number): Promise<ItemDetail> {
  const res = await api.get<ItemDetail>(`/items/${id}`)
  return res.data
}

// ai: gpt-5 | 2026-11-03
export async function createItem(payload: ItemCreate): Promise<Item> {
  const res = await api.post<Item>('/items', payload)
  return res.data
}

export async function updateItem(id: number, payload: ItemUpdate): Promise<Item> {
  const res = await api.patch<Item>(`/items/${id}`, payload)
  return res.data
}

export async function updatePriceHistoryEntry(
  entryId: number,
  pricePerLb: string | null,
): Promise<PriceHistoryEntry> {
  const res = await api.patch<PriceHistoryEntry>(`/items/history/${entryId}`, {
    price_per_lb: pricePerLb,
  })
  return res.data
}

// Receipts
export async function uploadReceiptImage(file: File): Promise<OcrResponse> {
  const form = new FormData()
  form.append('image', file)
  const res = await api.post<OcrResponse>('/receipts/upload', form, {
    headers: { 'Content-Type': undefined },
  })
  return res.data
}

export async function confirmReceipt(payload: ReceiptConfirmRequest): Promise<ImportReport> {
  const res = await api.post<ImportReport>('/receipts/confirm', payload)
  return res.data
}

export async function getReceipts(): Promise<Receipt[]> {
  const res = await api.get<Receipt[]>('/receipts')
  return res.data
}

export async function getReceipt(id: number): Promise<ReceiptDetail> {
  const res = await api.get<ReceiptDetail>(`/receipts/${id}`)
  return res.data
}

// Reports
export async function getReceiptReport(receiptId: number): Promise<ImportReport> {
  const res = await api.get<ImportReport>(`/reports/receipt/${receiptId}`)
  return res.data
}

// Shopping Lists
export async function getShoppingLists(): Promise<ShoppingListSummary[]> {
  const res = await api.get<ShoppingListSummary[]>('/shopping-lists')
  return res.data
}

export async function createShoppingList(name: string): Promise<ShoppingList> {
  const res = await api.post<ShoppingList>('/shopping-lists', { name })
  return res.data
}

export async function getShoppingList(id: number): Promise<ShoppingList> {
  const res = await api.get<ShoppingList>(`/shopping-lists/${id}`)
  return res.data
}

export async function renameShoppingList(id: number, name: string): Promise<ShoppingList> {
  const res = await api.patch<ShoppingList>(`/shopping-lists/${id}`, { name })
  return res.data
}

export async function deleteShoppingList(id: number): Promise<void> {
  await api.delete(`/shopping-lists/${id}`)
}

export async function addShoppingListItem(
  listId: number,
  itemId: number,
  quantity: number,
): Promise<ShoppingListItem> {
  const res = await api.post<ShoppingListItem>(`/shopping-lists/${listId}/items`, {
    item_id: itemId,
    quantity,
  })
  return res.data
}

export async function updateShoppingListItem(
  listId: number,
  entryId: number,
  quantity: number,
): Promise<ShoppingListItem> {
  const res = await api.patch<ShoppingListItem>(`/shopping-lists/${listId}/items/${entryId}`, {
    quantity,
  })
  return res.data
}

export async function removeShoppingListItem(listId: number, entryId: number): Promise<void> {
  await api.delete(`/shopping-lists/${listId}/items/${entryId}`)
}

export default api
