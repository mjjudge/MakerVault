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
      <NavLink to="/projects" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
        Projects
      </NavLink>
      <NavLink to="/ai" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
        AI
      </NavLink>
      <NavLink to="/suggestions" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
        Inspire
      </NavLink>
      <NavLink to="/history" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
        History
      </NavLink>
      <NavLink to="/import-export" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
        Import/Export
      </NavLink>
      <NavLink to="/intake" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
        Intake
      </NavLink>
      <NavLink to="/hygiene" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
        Hygiene
      </NavLink>
    </nav>
  )
}
