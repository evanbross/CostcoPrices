// ai: claude-sonnet-4-6 | 2026-06-18
import { Outlet } from 'react-router-dom'
import Navbar from './Navbar'

export default function Layout() {
  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />
      <main className="flex-1 max-w-7xl mx-auto w-full px-4 py-6">
        <Outlet />
      </main>
      <footer className="bg-costco-blue text-white/60 text-xs text-center py-3">
        Costco Price Tracker — personal use only
      </footer>
    </div>
  )
}
