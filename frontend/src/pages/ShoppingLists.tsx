// ai: claude-sonnet-4-6 | 2026-06-20
import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Plus, ShoppingCart, Trash2 } from 'lucide-react'
import toast from 'react-hot-toast'
import { createShoppingList, deleteShoppingList, getShoppingLists } from '../api/client'

function fmt(v: string | null) {
  if (!v) return null
  return `$${parseFloat(v).toFixed(2)}`
}

export default function ShoppingLists() {
  const queryClient = useQueryClient()
  const { data: lists = [], isLoading } = useQuery({
    queryKey: ['shopping-lists'],
    queryFn: getShoppingLists,
  })
  const [creating, setCreating] = useState(false)
  const [newName, setNewName] = useState('')

  async function handleCreate() {
    const name = newName.trim() || 'My List'
    try {
      const created = await createShoppingList(name)
      await queryClient.invalidateQueries({ queryKey: ['shopping-lists'] })
      setNewName('')
      setCreating(false)
      toast.success(`"${created.name}" created`)
    } catch {
      toast.error('Failed to create list')
    }
  }

  async function handleDelete(id: number, name: string) {
    if (!window.confirm(`Delete "${name}"?`)) return
    try {
      await deleteShoppingList(id)
      queryClient.setQueryData(['shopping-lists'], lists.filter((l) => l.id !== id))
      toast.success('List deleted')
    } catch {
      toast.error('Failed to delete list')
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-costco-blue">Shopping Lists</h1>
          <p className="text-sm text-gray-500">{lists.length} list{lists.length !== 1 ? 's' : ''}</p>
        </div>
        <button
          className="btn-primary flex items-center gap-2"
          onClick={() => setCreating(true)}
        >
          <Plus className="w-4 h-4" />
          New List
        </button>
      </div>

      {creating && (
        <div className="card p-4 flex items-center gap-3">
          <input
            className="input flex-1"
            placeholder="List name…"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleCreate(); if (e.key === 'Escape') setCreating(false) }}
            autoFocus
          />
          <button className="btn-primary" onClick={handleCreate}>Create</button>
          <button className="btn-ghost" onClick={() => setCreating(false)}>Cancel</button>
        </div>
      )}

      <div className="card overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-gray-400 text-sm">Loading…</div>
        ) : lists.length === 0 ? (
          <div className="p-10 text-center space-y-3">
            <ShoppingCart className="w-12 h-12 mx-auto text-gray-200" />
            <p className="text-gray-500">No shopping lists yet.</p>
            <button className="btn-primary" onClick={() => setCreating(true)}>
              Create your first list
            </button>
          </div>
        ) : (
          <ul className="divide-y divide-gray-50">
            {lists.map((list) => (
              <li key={list.id} className="flex items-center px-5 py-4 hover:bg-gray-50 transition-colors group">
                <Link to={`/shopping-lists/${list.id}`} className="flex-1 min-w-0">
                  <p className="font-semibold text-costco-blue hover:underline">{list.name}</p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {list.item_count} item{list.item_count !== 1 ? 's' : ''}
                    {list.total_estimate && (
                      <> · <span className="font-medium text-gray-600">~{fmt(list.total_estimate)}</span></>
                    )}
                  </p>
                </Link>
                <button
                  onClick={() => handleDelete(list.id, list.name)}
                  className="text-gray-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity ml-4"
                  title="Delete list"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
