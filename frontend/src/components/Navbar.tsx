// ai: claude-sonnet-4-6 | 2026-06-18
import { NavLink } from 'react-router-dom'
import { BarChart3, Home, Package, Receipt, ShoppingCart } from 'lucide-react'

const links = [
  { to: '/', label: 'Dashboard', icon: Home },
  { to: '/items', label: 'Items', icon: Package },
  { to: '/receipts', label: 'Receipts', icon: Receipt },
  { to: '/shopping-lists', label: 'Lists', icon: ShoppingCart },
]

export default function Navbar() {
  return (
    <header className="bg-costco-red shadow-md">
      <div className="max-w-7xl mx-auto px-4 flex items-center gap-6 h-16">
        {/* Logo / brand */}
        <div className="flex items-center gap-2 shrink-0">
          <div className="w-8 h-8 bg-white rounded-full flex items-center justify-center">
            <BarChart3 className="w-5 h-5 text-costco-red" />
          </div>
          <span className="text-white font-bold text-lg tracking-wide">
            Costco<span className="text-yellow-300"> Prices</span>
          </span>
        </div>

        {/* Nav links */}
        <nav className="flex items-center gap-1 ml-4">
          {links.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-white/20 text-white'
                    : 'text-white/80 hover:text-white hover:bg-white/10'
                }`
              }
            >
              <Icon className="w-4 h-4" />
              {label}
            </NavLink>
          ))}
        </nav>
      </div>
    </header>
  )
}
