/**
 * Tests for the Nav component.
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Nav } from '../components/Nav'

function renderNav(initialPath = '/') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Nav />
    </MemoryRouter>
  )
}

describe('Nav', () => {
  it('renders the brand name', () => {
    renderNav()
    expect(screen.getByText(/MakerVault/i)).toBeInTheDocument()
  })

  it('renders navigation links', () => {
    renderNav()
    expect(screen.getByText('Parts')).toBeInTheDocument()
    expect(screen.getByText('Stock')).toBeInTheDocument()
    expect(screen.getByText('Locations')).toBeInTheDocument()
    expect(screen.getByText('Search')).toBeInTheDocument()
  })

  it('has a link to the home page', () => {
    renderNav()
    const brand = screen.getByText(/MakerVault/i).closest('a')
    expect(brand).toHaveAttribute('href', '/')
  })
})
