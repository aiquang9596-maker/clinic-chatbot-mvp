import React, { useEffect, useMemo, useState } from 'react'

const API = 'http://localhost:8000/api'

export function App() {
  const [conversations, setConversations] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(true)
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const [suggestions, setSuggestions] = useState([])
  const [suggestMeta, setSuggestMeta] = useState(null)
  const [suggestLoading, setSuggestLoading] = useState(false)
  const [rewriteInstruction, setRewriteInstruction] = useState('')

  useEffect(() => {
    loadConversations()
  }, [])

  // Auto-poll silently (no loading spinner) every 3s
  useEffect(() => {
    if (!selectedId) return
    const interval = setInterval(() => {
      refreshConversationsSilent()
      loadMessages(selectedId)
    }, 3000)
    return () => clearInterval(interval)
  }, [selectedId])

  async function loadConversations() {
    setLoading(true)
    const res = await fetch(`${API}/conversations`)
    const data = await res.json()
    setConversations(data)
    if (data.length && !selectedId) setSelectedId(data[0].id)
    setLoading(false)
  }

  async function refreshConversationsSilent() {
    const res = await fetch(`${API}/conversations`)
    const data = await res.json()
    setConversations(data)
  }

  useEffect(() => {
    if (!selectedId) return
    loadMessages(selectedId)
    loadSuggestions(selectedId)
  }, [selectedId])

  async function loadMessages(id) {
    const res = await fetch(`${API}/conversations/${id}/messages`)
    const data = await res.json()
    setMessages(data)
  }

  async function loadSuggestions(id, instruction = '') {
    setSuggestLoading(true)
    try {
      const res = await fetch(`${API}/conversations/${id}/suggestions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ instruction }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Suggestion failed')
      setSuggestions(data.options || [])
      setSuggestMeta(data)
    } catch (e) {
      setSuggestions([])
      setSuggestMeta({ notes: String(e.message || e), sources: [] })
    } finally {
      setSuggestLoading(false)
    }
  }

  async function sendMessage() {
    if (!selectedId || !draft.trim()) return
    setSending(true)
    setError('')
    try {
      const res = await fetch(`${API}/conversations/${selectedId}/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: draft.trim() }),
      })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || 'Send failed')
      }
      setDraft('')
      await loadMessages(selectedId)
      await loadConversations()
    } catch (e) {
      setError(String(e.message || e))
    } finally {
      setSending(false)
    }
  }

  const selected = useMemo(
    () => conversations.find((c) => c.id === selectedId),
    [conversations, selectedId]
  )

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-header">
          <h1>Inbox</h1>
          <button onClick={loadConversations}>Refresh</button>
        </div>
        {loading ? <div className="muted">Loading…</div> : null}
        <div className="conversation-list">
          {conversations.map((conv) => (
            <button
              key={conv.id}
              className={`conversation-item ${selectedId === conv.id ? 'active' : ''}`}
              onClick={() => setSelectedId(conv.id)}
            >
              <div className="conversation-name">{conv.customer.name}</div>
              <div className="conversation-meta">{conv.channel} • {conv.customer.lead_status}</div>
              <div className="conversation-meta">{conv.human_takeover ? 'human takeover' : 'ai suggest'}</div>
            </button>
          ))}
        </div>
      </aside>

      <main className="chat-panel">
        <div className="chat-header">
          <div>
            <h2>{selected?.customer?.name || 'No conversation selected'}</h2>
            <div className="muted">{selected?.channel || ''}</div>
          </div>
        </div>
        <div className="messages">
          {messages.map((m) => (
            <div key={m.id} className={`message-row ${m.direction === 'outbound' ? 'outbound' : 'inbound'}`}>
              <div className="message-bubble">
                <div>{m.content_text || '(empty)'}</div>
                <div className="message-meta">{m.sender_type} {m.risk_level ? `• ${m.risk_level}` : ''}</div>
              </div>
            </div>
          ))}
        </div>
        <div className="composer">
          <textarea
            className="composer-input"
            placeholder="Nhập tin nhắn trả lời khách..."
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
          />
          <div className="composer-actions">
            <div className="muted">{error || 'Manual send enabled'}</div>
            <button className="send-btn" onClick={sendMessage} disabled={sending || !draft.trim() || !selectedId}>
              {sending ? 'Sending...' : 'Send'}
            </button>
          </div>
        </div>
      </main>

      <aside className="detail-panel">
        <h3>AI Suggested Replies</h3>
        <div className="muted detail-section">{suggestLoading ? 'Generating 1–3 options…' : (suggestMeta?.notes || 'Suggestions based on context + KB')}</div>
        <div className="detail-section">
          {(suggestions || []).map((opt) => (
            <div key={opt.id} className="suggest-card">
              <div className="suggest-label">{opt.label || `Option ${opt.id}`}</div>
              <div className="suggest-text">{opt.text}</div>
              <button className="use-btn" onClick={() => setDraft(opt.text)}>Use in composer</button>
            </div>
          ))}
        </div>

        <div className="detail-section">
          <strong>Rewrite instruction</strong>
          <textarea
            className="rewrite-input"
            placeholder="Ví dụ: ngắn hơn, bớt sales, tiếng Anh tự nhiên hơn, đừng nhắc giá..."
            value={rewriteInstruction}
            onChange={(e) => setRewriteInstruction(e.target.value)}
          />
          <div className="suggest-actions">
            <button className="ghost-btn" onClick={() => loadSuggestions(selectedId, '')} disabled={!selectedId || suggestLoading}>Regenerate 3 options</button>
            <button className="ghost-btn" onClick={() => loadSuggestions(selectedId, rewriteInstruction)} disabled={!selectedId || suggestLoading || !rewriteInstruction.trim()}>Rewrite by instruction</button>
          </div>
        </div>

        <div className="detail-section">
          <strong>Meta</strong>
          <div className="muted">Intent: {suggestMeta?.intent || 'unknown'}</div>
          <div className="muted">Risk: {suggestMeta?.risk_level || 'unknown'}</div>
          <div className="muted">Confidence: {String(suggestMeta?.confidence ?? '')}</div>
        </div>

        <div className="detail-section">
          <strong>Sources used</strong>
          {(suggestMeta?.sources || []).length ? (
            <ul className="source-list">
              {suggestMeta.sources.map((s) => (
                <li key={s.snippet_id}><span>{s.title}</span><br /><span className="muted">{s.source_path}</span></li>
              ))}
            </ul>
          ) : (
            <div className="muted">No sources yet</div>
          )}
        </div>
      </aside>
    </div>
  )
}
