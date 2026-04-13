import { NavLink } from 'react-router-dom'

export function Nav() {
  return (
    <nav className="nav">
      <NavLink to="/" className="nav-brand">
        🔧 MakerVault
      </NavLink>
      <NavLink to="/" end className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
        Search
      </NavLink>
      <NavLink to="/parts" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
        Parts
      </NavLink>
      <NavLink to="/stock" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
        Stock
      </NavLink>
      <NavLink to="/locations" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
        Locations
      </NavLink>
      <NavLink to="/documents" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
        Documents
      </NavLink>
    </nav>
  )
}
