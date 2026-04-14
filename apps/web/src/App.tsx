import { Routes, Route } from 'react-router-dom'
import { Nav } from './components/Nav'
import { HomePage } from './pages/HomePage'
import { PartsPage } from './pages/PartsPage'
import { PartDetailPage } from './pages/PartDetailPage'
import { StockPage } from './pages/StockPage'
import { LocationsPage } from './pages/LocationsPage'
import { DocumentsPage } from './pages/DocumentsPage'
import { ProjectsPage } from './pages/ProjectsPage'
import { ProjectDetailPage } from './pages/ProjectDetailPage'
import { AISettingsPage } from './pages/AISettingsPage'
import { SuggestionsPage } from './pages/SuggestionsPage'
import { UsageHistoryPage } from './pages/UsageHistoryPage'
import { ImportExportPage } from './pages/ImportExportPage'
import { IntakePage } from './pages/IntakePage'
import { HygienePage } from './pages/HygienePage'

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
          <Route path="/projects" element={<ProjectsPage />} />
          <Route path="/projects/:id" element={<ProjectDetailPage />} />
          <Route path="/ai" element={<AISettingsPage />} />
          <Route path="/suggestions" element={<SuggestionsPage />} />
          <Route path="/history" element={<UsageHistoryPage />} />
          <Route path="/import-export" element={<ImportExportPage />} />
          <Route path="/intake" element={<IntakePage />} />
          <Route path="/hygiene" element={<HygienePage />} />
        </Routes>
      </main>
    </div>
  )
}
