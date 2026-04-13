/**
 * SuggestionsPage
 *
 * AI-assisted "What can I build with what I own?" project inspiration.
 *
 * The page lets the user enter a free-text prompt (e.g. "suggest something
 * for beginners"), triggers the backend to build an inventory-grounded context
 * and call the active AI provider, and displays the resulting project ideas.
 *
 * Past suggestions are listed below the prompt form, most recent first.
 * Each result card is expandable and shows:
 *   - project title + difficulty badge
 *   - description
 *   - owned parts (linked to inventory)
 *   - missing parts
 */

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  suggestionApi,
  type ProjectSuggestion,
  type SuggestionIdea,
} from '../api/client'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DIFFICULTY_COLORS: Record<string, string> = {
  beginner: '#059669',
  intermediate: '#d97706',
  advanced: '#dc2626',
}

const STATUS_COLORS: Record<string, string> = {
  pending: '#d97706',
  running: '#2563eb',
  done: '#059669',
  failed: '#dc2626',
}

// ---------------------------------------------------------------------------
// IdeaCard
// ---------------------------------------------------------------------------

function IdeaCard({ idea }: { idea: SuggestionIdea }) {
  const [expanded, setExpanded] = useState(false)
  const difficultyColor = DIFFICULTY_COLORS[idea.difficulty ?? ''] ?? '#6b7280'
  const ownedParts = idea.owned_parts ?? []
  const missingParts = idea.missing_parts ?? []

  return (
    <div
      style={{
        border: '1px solid #d1fae5',
        borderRadius: '8px',
        padding: '1rem',
        marginBottom: '0.75rem',
        background: '#f0fdf4',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
        <span style={{ fontWeight: 700, fontSize: '1rem' }}>{idea.title}</span>
        {idea.difficulty && (
          <span
            style={{
              fontSize: '0.72rem',
              fontWeight: 700,
              color: difficultyColor,
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
            }}
          >
            {idea.difficulty}
          </span>
        )}
        <button
          onClick={() => setExpanded(e => !e)}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            color: '#6b7280',
            fontSize: '0.78rem',
            marginLeft: 'auto',
            padding: 0,
          }}
        >
          {expanded ? '▾ Collapse' : '▸ Details'}
        </button>
      </div>

      <p style={{ margin: '0.5rem 0 0', fontSize: '0.88rem', color: '#374151' }}>
        {idea.description}
      </p>

      {expanded && (
        <div style={{ marginTop: '0.75rem' }}>
          {ownedParts.length > 0 && (
            <div style={{ marginBottom: '0.5rem' }}>
              <div
                style={{ fontWeight: 600, fontSize: '0.8rem', color: '#059669', marginBottom: '0.25rem' }}
              >
                ✓ Parts you own ({ownedParts.length})
              </div>
              <ul style={{ margin: 0, paddingLeft: '1.2rem', fontSize: '0.83rem', color: '#374151' }}>
                {ownedParts.map((p, i) => (
                  <li key={i}>{p.part_name}</li>
                ))}
              </ul>
            </div>
          )}

          {missingParts.length > 0 && (
            <div>
              <div
                style={{ fontWeight: 600, fontSize: '0.8rem', color: '#b45309', marginBottom: '0.25rem' }}
              >
                ✗ Parts you need ({missingParts.length})
              </div>
              <ul style={{ margin: 0, paddingLeft: '1.2rem', fontSize: '0.83rem', color: '#374151' }}>
                {missingParts.map((p, i) => (
                  <li key={i}>
                    <strong>{p.name}</strong>
                    {p.notes ? ` — ${p.notes}` : ''}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {ownedParts.length === 0 && missingParts.length === 0 && (
            <div style={{ fontSize: '0.8rem', color: '#9ca3af' }}>
              No part details available.
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// SuggestionCard
// ---------------------------------------------------------------------------

function SuggestionCard({
  suggestion,
  onDeleted,
}: {
  suggestion: ProjectSuggestion
  onDeleted: () => void
}) {
  const statusColor = STATUS_COLORS[suggestion.status] ?? '#6b7280'
  const ideas = suggestion.result_json?.suggestions ?? []
  const [expanded, setExpanded] = useState(suggestion.status === 'done')

  const deleteMutation = useMutation({
    mutationFn: () => suggestionApi.delete(suggestion.id),
    onSuccess: onDeleted,
  })

  return (
    <div
      style={{
        border: '1px solid #e5e7eb',
        borderRadius: '8px',
        padding: '1rem 1.2rem',
        marginBottom: '1rem',
        background: '#fff',
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.6rem', flexWrap: 'wrap' }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: '0.78rem', color: '#9ca3af', marginBottom: '0.15rem' }}>
            {new Date(suggestion.created_at).toLocaleString()}
          </div>
          <div
            style={{
              fontWeight: 600,
              fontSize: '0.92rem',
              color: '#111827',
              wordBreak: 'break-word',
            }}
          >
            "{suggestion.prompt}"
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexShrink: 0 }}>
          <span
            style={{
              fontSize: '0.72rem',
              fontWeight: 700,
              color: statusColor,
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
            }}
          >
            {suggestion.status}
          </span>
          {suggestion.provider_name && (
            <span style={{ fontSize: '0.72rem', color: '#9ca3af' }}>
              via {suggestion.provider_name}
            </span>
          )}
          {suggestion.status === 'done' && ideas.length > 0 && (
            <button
              onClick={() => setExpanded(e => !e)}
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                color: '#6b7280',
                fontSize: '0.78rem',
                padding: 0,
              }}
            >
              {expanded ? '▾ Hide' : `▸ ${ideas.length} idea${ideas.length > 1 ? 's' : ''}`}
            </button>
          )}
          <button
            onClick={() => {
              if (confirm('Delete this suggestion?')) deleteMutation.mutate()
            }}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: '#9ca3af',
              fontSize: '0.78rem',
              padding: 0,
            }}
            title="Delete"
          >
            ✕
          </button>
        </div>
      </div>

      {/* Error */}
      {suggestion.status === 'failed' && suggestion.error_message && (
        <div
          style={{
            marginTop: '0.5rem',
            padding: '0.4rem 0.6rem',
            background: '#fef2f2',
            border: '1px solid #fecaca',
            borderRadius: '4px',
            fontSize: '0.78rem',
            color: '#b91c1c',
          }}
        >
          {suggestion.error_message}
        </div>
      )}

      {/* Ideas */}
      {expanded && ideas.length > 0 && (
        <div style={{ marginTop: '0.75rem' }}>
          {ideas.map((idea, i) => (
            <IdeaCard key={i} idea={idea} />
          ))}
        </div>
      )}

      {suggestion.status === 'done' && ideas.length === 0 && (
        <div style={{ marginTop: '0.5rem', fontSize: '0.83rem', color: '#9ca3af' }}>
          No suggestions returned.
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// SuggestionsPage
// ---------------------------------------------------------------------------

export function SuggestionsPage() {
  const qc = useQueryClient()
  const [prompt, setPrompt] = useState('')
  const [runError, setRunError] = useState('')

  const queryKey = ['suggestions']

  const { data, isLoading } = useQuery({
    queryKey,
    queryFn: () => suggestionApi.list({ limit: 50 }),
  })

  const createMutation = useMutation({
    mutationFn: () => suggestionApi.create(prompt.trim()),
    onSuccess: () => {
      setPrompt('')
      setRunError('')
      qc.invalidateQueries({ queryKey })
    },
    onError: (err: any) => {
      setRunError(err?.response?.data?.detail ?? 'Failed to run suggestion')
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (prompt.trim()) createMutation.mutate()
  }

  const suggestions = data?.items ?? []

  return (
    <div style={{ maxWidth: '760px', margin: '0 auto' }}>
      <h1 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '0.25rem' }}>
        🔮 Project Inspiration
      </h1>
      <p style={{ color: '#6b7280', marginBottom: '1.5rem', fontSize: '0.92rem' }}>
        Ask AI what you could build based on your current inventory.
        Suggestions are grounded in parts you actually own.
      </p>

      {/* Prompt form */}
      <form
        onSubmit={handleSubmit}
        style={{
          display: 'flex',
          gap: '0.5rem',
          marginBottom: '1.5rem',
          alignItems: 'flex-start',
        }}
      >
        <textarea
          className="form-control"
          rows={2}
          placeholder="e.g. "What can I build for a beginner?" or "I want to make something with Wi-Fi and sensors.""
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
          style={{ flex: 1, resize: 'vertical', minHeight: '3rem' }}
        />
        <button
          type="submit"
          className="btn btn-primary"
          disabled={createMutation.isPending || !prompt.trim()}
          style={{ whiteSpace: 'nowrap' }}
        >
          {createMutation.isPending ? 'Running…' : '▶ Ask AI'}
        </button>
      </form>

      {runError && (
        <div className="alert alert-error" style={{ marginBottom: '1rem' }}>
          {runError}
        </div>
      )}

      {/* Suggestion history */}
      {isLoading ? (
        <div style={{ color: '#9ca3af' }}>Loading…</div>
      ) : suggestions.length === 0 ? (
        <div className="empty">
          <p>No suggestions yet. Ask AI for project ideas above.</p>
          <p style={{ fontSize: '0.83rem', marginTop: '0.5rem', color: '#9ca3af' }}>
            Make sure you have an AI provider configured on the{' '}
            <a href="/ai">AI Settings</a> page and some stock in your inventory.
          </p>
        </div>
      ) : (
        suggestions.map(s => (
          <SuggestionCard
            key={s.id}
            suggestion={s}
            onDeleted={() => qc.invalidateQueries({ queryKey })}
          />
        ))
      )}
    </div>
  )
}
