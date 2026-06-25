// ai: claude-sonnet-4-6 | 2026-06-20
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Items from './pages/Items'
import ItemDetail from './pages/ItemDetail'
import Receipts from './pages/Receipts'
import Reports from './pages/Reports'
import ShoppingLists from './pages/ShoppingLists'
import ShoppingListDetail from './pages/ShoppingListDetail'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="/items" element={<Items />} />
          <Route path="/items/:id" element={<ItemDetail />} />
          <Route path="/receipts" element={<Receipts />} />
          <Route path="/reports/:receiptId" element={<Reports />} />
          <Route path="/shopping-lists" element={<ShoppingLists />} />
          <Route path="/shopping-lists/:id" element={<ShoppingListDetail />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
