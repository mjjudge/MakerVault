/**
 * Smoke tests for the API client module.
 */
import { describe, it, expect } from 'vitest'
import { apiClient, partsApi, stockApi, locationsApi, containersApi, categoriesApi } from '../api/client'

describe('apiClient', () => {
  it('has correct base URL', () => {
    expect(apiClient.defaults.baseURL).toBe('/api')
  })

  it('has JSON content-type header', () => {
    expect(apiClient.defaults.headers['Content-Type']).toBe('application/json')
  })
})

describe('API modules', () => {
  it('partsApi exports list, get, create, update, delete', () => {
    expect(typeof partsApi.list).toBe('function')
    expect(typeof partsApi.get).toBe('function')
    expect(typeof partsApi.create).toBe('function')
    expect(typeof partsApi.update).toBe('function')
    expect(typeof partsApi.delete).toBe('function')
  })

  it('stockApi exports CRUD functions', () => {
    expect(typeof stockApi.list).toBe('function')
    expect(typeof stockApi.create).toBe('function')
  })

  it('locationsApi exports CRUD functions', () => {
    expect(typeof locationsApi.list).toBe('function')
    expect(typeof locationsApi.create).toBe('function')
  })

  it('containersApi exports CRUD functions', () => {
    expect(typeof containersApi.list).toBe('function')
    expect(typeof containersApi.create).toBe('function')
  })

  it('categoriesApi exports CRUD functions', () => {
    expect(typeof categoriesApi.list).toBe('function')
    expect(typeof categoriesApi.create).toBe('function')
  })
})
