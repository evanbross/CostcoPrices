// ai: claude-sonnet-4-6 | 2026-06-20
import { useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Check, Pencil, Search, ShoppingCart } from 'lucide-react'
import toast from 'react-hot-toast'
import {
  addShoppingListItem,
  createShoppingList,
  getItems,
  getShoppingList,
  getShoppingLists,
  removeShoppingListItem,
} from '../api/client'
import EditItemDialog from '../components/EditItemDialog'
import type { Item } from '../types'

function fmt(price: string | null) {
  if (!price) return '—'
  return `$${parseFloat(price).toFixed(2)}`
}

export default function Items() {
  const queryClient = useQueryClient()
  const { data: items = [], isLoading } = useQuery({ queryKey: ['items'], queryFn: getItems })
  const { data: shoppingLists = [] } = useQuery({
    queryKey: ['shopping-lists'],
    queryFn: getShoppingLists,
  })

  const [search, setSearch] = useState('')
  const [editingItem, setEditingItem] = useState<Item | null>(null)
  const [selectedListId, setSelectedListId] = useState<number | null>(null)
  const [creatingList, setCreatingList] = useState(false)
  const [newListName, setNewListName] = useState('')
  const [togglingItemId, setTogglingItemId] = useState<number | null>(null)
  const selectRef = useRef<HTMLSelectElement>(null)

  // Fetch full list details so we know which items are already on it
  const { data: selectedList } = useQuery({
    queryKey: ['shopping-list', selectedListId],
    queryFn: () => getShoppingList(selectedListId!),
    enabled: selectedListId !== null,
  })

  // item_id → shopping list entry id (first occurrence if duplicates)
  const listItemMap = new Map<number, number>()
  for (const entry of selectedList?.items ?? []) {
    if (!listItemMap.has(entry.item_id)) listItemMap.set(entry.item_id, entry.id)
  }

  const filtered = items.filter((item) => {
    const q = search.toLowerCase()
    return (
      item.item_code.includes(q) ||
      item.description.toLowerCase().includes(q) ||
      (item.friendly_name?.toLowerCase().includes(q) ?? false)
    )
  })

  function handleSaved(updated: Item) {
    queryClient.setQueryData<Item[]>(['items'], (old = []) =>
      old.map((i) => (i.id === updated.id ? updated : i)),
    )
  }

  function handleListSelect(e: React.ChangeEvent<HTMLSelectElement>) {
    const val = e.target.value
    if (val === '__new__') {
      if (selectRef.current) selectRef.current.value = selectedListId?.toString() ?? ''
      setCreatingList(true)
      setNewListName('')
    } else {
      setSelectedListId(val ? parseInt(val) : null)
    }
  }

  async function handleCreateList() {
    const name = newListName.trim() || 'My List'
    try {
      const created = await createShoppingList(name)
      await queryClient.invalidateQueries({ queryKey: ['shopping-lists'] })
      setSelectedListId(created.id)
      setCreatingList(false)
      setNewListName('')
      toast.success(`"${created.name}" created`)
    } catch {
      toast.error('Failed to create list')
    }
  }

  async function handleToggle(item: Item, checked: boolean) {
    if (!selectedListId) return
    setTogglingItemId(item.id)
    const listName = shoppingLists.find((l) => l.id === selectedListId)?.name ?? 'list'
    try {
      if (checked) {
        await addShoppingListItem(selectedListId, item.id, 1)
        toast.success(`Added to "${listName}"`)
      } else {
        const entryId = listItemMap.get(item.id)!
        await removeShoppingListItem(selectedListId, entryId)
        toast.success(`Removed from "${listName}"`)
      }
      await queryClient.invalidateQueries({ queryKey: ['shopping-list', selectedListId] })
    } catch {
      toast.error(checked ? 'Failed to add item' : 'Failed to remove item')
    } finally {
      setTogglingItemId(null)
    }
  }

  const selectedListName = shoppingLists.find((l) => l.id === selectedListId)?.name

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-costco-blue">Items</h1>
          <p className="text-sm text-gray-500">{items.length} tracked items</p>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          {/* Shopping list selector */}
          <div className="flex items-center gap-2">
            <ShoppingCart className="w-4 h-4 text-gray-400 shrink-0" />
            {creatingList ? (
              <div className="flex items-center gap-1.5">
                <input
                  className="input w-44 text-sm py-1.5"
                  placeholder="New list name…"
                  value={newListName}
                  onChange={(e) => setNewListName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleCreateList()
                    if (e.key === 'Escape') setCreatingList(false)
                  }}
                  autoFocus
                />
                <button
                  className="btn-primary py-1.5 px-3 text-sm flex items-center gap-1"
                  onClick={handleCreateList}
                >
                  <Check className="w-3.5 h-3.5" />
                </button>
                <button
                  className="btn-ghost py-1.5 px-3 text-sm"
                  onClick={() => setCreatingList(false)}
                >
                  ✕
                </button>
              </div>
            ) : (
              <select
                ref={selectRef}
                className="input text-sm py-1.5 pr-8 w-52"
                value={selectedListId?.toString() ?? ''}
                onChange={handleListSelect}
              >
                <option value="">— No list selected —</option>
                {shoppingLists.map((l) => (
                  <option key={l.id} value={l.id.toString()}>
                    {l.name}
                  </option>
                ))}
                <option value="__new__">+ New list…</option>
              </select>
            )}
          </div>

          {/* Search */}
          <div className="relative w-72">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              className="input pl-9"
              placeholder="Search item code or name…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </div>
      </div>

      {selectedListId && (
        <p className="text-xs text-costco-blue font-medium">
          Checking an item adds it to &ldquo;{selectedListName}&rdquo;
        </p>
      )}

      <div className="card overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-gray-400 text-sm">Loading…</div>
        ) : filtered.length === 0 ? (
          <div className="p-8 text-center text-gray-400 text-sm">
            {search ? 'No items match your search.' : 'No items yet — import a receipt to get started.'}
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-costco-border-gray">
              <tr>
                <th className="text-left px-4 py-3 font-semibold text-gray-600 w-28">Code</th>
                <th className="w-8" />
                <th className="text-left px-4 py-3 font-semibold text-gray-600">Name</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600">Receipt description</th>
                <th className="text-center px-4 py-3 font-semibold text-gray-600 w-16">Tax</th>
                {/* ai: claude-opus-5-5 | 2026-09-28 */}
                <th className="text-right px-4 py-3 font-semibold text-gray-600 w-32">Last Purchased</th>
                <th className="text-right px-4 py-3 font-semibold text-gray-600 w-28">Latest Price</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {filtered.map((item) => {
                const inList = listItemMap.has(item.id)
                const toggling = togglingItemId === item.id
                return (
                  <tr key={item.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3 font-mono text-xs text-gray-500">{item.item_code}</td>
                    <td className="py-3 pl-2 pr-0">
                      <input
                        type="checkbox"
                        checked={inList}
                        disabled={!selectedListId || toggling}
                        onChange={(e) => handleToggle(item, e.target.checked)}
                        className={`w-4 h-4 rounded accent-costco-red ${
                          !selectedListId ? 'opacity-25 cursor-not-allowed' : 'cursor-pointer'
                        }`}
                        title={selectedListId ? `${inList ? 'Remove from' : 'Add to'} "${selectedListName}"` : 'Select a list first'}
                      />
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5">
                        <button
                          onClick={() => setEditingItem(item)}
                          className="p-0.5 rounded text-gray-400 hover:text-costco-blue hover:bg-blue-50 transition-colors shrink-0"
                          title={item.friendly_name ? 'Edit item' : 'Add a friendly name'}
                        >
                          <Pencil className="w-3 h-3" />
                        </button>
                        <Link
                          to={`/items/${item.id}`}
                          className={`hover:underline font-medium ${item.friendly_name ? 'text-costco-blue' : 'text-gray-600'}`}
                        >
                          {item.friendly_name ?? item.description}
                        </Link>
                        {item.is_by_weight && (
                          <span className="text-xs text-gray-400">· lb</span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-gray-500">
                      {item.friendly_name ? item.description : <span className="text-gray-300">—</span>}
                    </td>
                    <td className="px-4 py-3 text-center text-xs text-gray-500">
                      {item.tax_type ?? '—'}
                    </td>
                    {/* ai: claude-opus-5-5 | 2026-09-28 */}
                    <td className="px-4 py-3 text-right text-gray-600 whitespace-nowrap">
                      {item.last_purchased ?? '—'}
                    </td>
                    <td className="px-4 py-3 text-right font-mono font-semibold text-gray-800">
                      {fmt(item.latest_price)}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      {editingItem && (
        <EditItemDialog
          item={editingItem}
          onClose={() => setEditingItem(null)}
          onSaved={handleSaved}
        />
      )}
    </div>
  )
}
