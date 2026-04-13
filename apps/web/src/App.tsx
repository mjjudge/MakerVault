import { Routes, Route } from 'react-router-dom'
import { Nav } from './components/Nav'
import { HomePage } from './pages/HomePage'
import { PartsPage } from './pages/PartsPage'
import { PartDetailPage } from './pages/PartDetailPage'
import { StockPage } from './pages/StockPage'
import { LocationsPage } from './pages/LocationsPage'
import { DocumentsPage } from './pages/DocumentsPage'

export default function App() {
  return (
    <div className="layout">
      <Nav />
      <main className="main">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/parts" element={<PartsPage />} />
          <Route path="/parts/:id" element={<PartDetailPage />} />
          <Route path="/stock" element={<StockPage />} />
          <Route path="/locations" element={<LocationsPage />} />
          <Route path="/documents" element={<DocumentsPage />} />
        </Routes>
      </main>
    </div>
  )
}
