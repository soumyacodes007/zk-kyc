import { useState, useEffect, useCallback } from 'react'
import './index.css'

const API = 'http://127.0.0.1:8000/api/v1'
const ISSUER_KEY = 'algokyc-dev-secret-change-in-production'

// ── Helpers ────────────────────────────────────────────────────────────────

function timeAgo(ts) {
  const diff = Date.now() / 1000 - ts
  if (diff < 60) return `${Math.floor(diff)}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

function truncate(str, n = 20) {
  return str?.length > n ? str.slice(0, n) + '…' : str
}

function StatusBadge({ status }) {
  return <span className={`badge badge-${status}`}>
    {status === 'pending' && '⏳'}
    {status === 'approved' && '✅'}
    {status === 'rejected' && '❌'}
    {status === 'executed' && '⚡'}
    {status === 'expired' && '💀'}
    {' '}{status}
  </span>
}

function VoteBar({ approvals, rejections, threshold = 3, total = 5 }) {
  const pct = Math.min(100, (approvals / threshold) * 100)
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>
        <span>✅ {approvals} approved</span>
        <span>{threshold} needed</span>
        <span>❌ {rejections} rejected</span>
      </div>
      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${pct}%` }} />
      </div>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
        {5 - approvals - rejections} custodians haven't voted
      </div>
    </div>
  )
}

// ── Login Screen ───────────────────────────────────────────────────────────

function LoginScreen({ onLogin }) {
  const [custodianNum, setCustodianNum] = useState('')
  const [custodianId, setCustodianId] = useState('')
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')

  const submit = async (e) => {
    e.preventDefault()
    const num = parseInt(custodianNum)
    if (num < 1 || num > 5) return setErr('Custodian number must be 1–5')
    if (!custodianId.trim()) return setErr('Enter your custodian wallet address or ID')
    setLoading(true)
    setErr('')
    // For demo: just accept any valid number + ID
    setTimeout(() => {
      onLogin({ num, id: custodianId.trim() })
      setLoading(false)
    }, 600)
  }

  return (
    <div className="login-wrap">
      <div className="login-card">
        <div className="login-logo">
          <div style={{ fontSize: 48 }}>🛡️</div>
          <h1>AlgoKYC</h1>
          <p>Custodian Dashboard</p>
        </div>
        <form onSubmit={submit}>
          <div className="form-group">
            <label className="label">Your Custodian Number (1–5)</label>
            <input className="input" type="number" min="1" max="5"
              placeholder="e.g. 1"
              value={custodianNum}
              onChange={e => setCustodianNum(e.target.value)} />
          </div>
          <div className="form-group">
            <label className="label">Your Wallet Address / ID</label>
            <input className="input" type="text"
              placeholder="e.g. 6AUB... or custodian1@example.com"
              value={custodianId}
              onChange={e => setCustodianId(e.target.value)} />
          </div>
          {err && <div className="alert alert-error">{err}</div>}
          <button className="btn btn-primary w-full mt-4" type="submit" disabled={loading}>
            {loading ? '⏳ Authenticating…' : '🔑 Enter Dashboard'}
          </button>
        </form>
        <div className="alert alert-info mt-4" style={{ fontSize: 12 }}>
          🔒 3-of-5 threshold. You are one of 5 custodians. Any 3 approvals unlock identity decryption.
        </div>
      </div>
    </div>
  )
}

// ── Create Court Order Modal (Issuer) ─────────────────────────────────────

function CreateOrderModal({ onClose, onCreated }) {
  const [form, setForm] = useState({ nullifier_hex: '', reason: '', pdf_url: '' })
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')

  const submit = async (e) => {
    e.preventDefault()
    if (!form.nullifier_hex.trim()) return setErr('Nullifier hex is required')
    if (!form.reason.trim()) return setErr('Reason is required')
    setLoading(true)
    setErr('')
    try {
      const res = await fetch(`${API}/court-order`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-API-Key': ISSUER_KEY },
        body: JSON.stringify(form),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Failed')
      onCreated(data)
      onClose()
    } catch (e) {
      setErr(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 style={{ fontSize: 18, fontWeight: 700 }}>⚖️ New Court Order</h3>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>✕</button>
        </div>
        <div className="alert alert-warning">
          ⚠️ This will initiate a revocation flow. 3-of-5 custodians must approve before any identity is revealed.
        </div>
        <form onSubmit={submit}>
          <div className="form-group">
            <label className="label">Nullifier Hex (64 chars)</label>
            <input className="input mono" placeholder="a1b2c3...d4e5f6"
              value={form.nullifier_hex}
              onChange={e => setForm(f => ({ ...f, nullifier_hex: e.target.value }))} />
          </div>
          <div className="form-group">
            <label className="label">Reason / Case Number</label>
            <input className="input" placeholder="e.g. Court Order #2024-xyz — Fraud investigation"
              value={form.reason}
              onChange={e => setForm(f => ({ ...f, reason: e.target.value }))} />
          </div>
          <div className="form-group">
            <label className="label">PDF URL (optional)</label>
            <input className="input" type="url" placeholder="https://court.gov/order/..."
              value={form.pdf_url}
              onChange={e => setForm(f => ({ ...f, pdf_url: e.target.value }))} />
          </div>
          {err && <div className="alert alert-error">{err}</div>}
          <div className="flex gap-3 mt-4">
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? '⏳ Creating…' : '⚖️ Create Court Order'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── Order Detail Modal ─────────────────────────────────────────────────────

function OrderDetailModal({ order: initialOrder, custodian, onClose, onRefresh }) {
  const [order, setOrder] = useState(initialOrder)
  const [loading, setLoading] = useState(false)
  const [msg, setMsg] = useState('')
  const [note, setNote] = useState('')

  const myVote = order.votes?.find(v => v.custodian_id === custodian.id)

  const castVote = async (approved) => {
    setLoading(true)
    setMsg('')
    try {
      const res = await fetch(`${API}/court-order/${order.id}/vote`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          custodian_id: custodian.id,
          custodian_num: custodian.num,
          approved,
          note,
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail)
      setMsg(data.message)
      // Refresh order
      const fresh = await fetch(`${API}/court-order/${order.id}`).then(r => r.json())
      setOrder(fresh)
      onRefresh()
    } catch (e) {
      setMsg('❌ ' + e.message)
    } finally {
      setLoading(false)
    }
  }

  const executeRevoke = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API}/court-order/${order.id}/execute`, {
        method: 'POST',
        headers: { 'X-API-Key': ISSUER_KEY },
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail)
      setMsg(`✅ Revoked on-chain! txid: ${data.txid?.slice(0, 20)}...`)
      const fresh = await fetch(`${API}/court-order/${order.id}`).then(r => r.json())
      setOrder(fresh)
      onRefresh()
    } catch (e) {
      setMsg('❌ ' + e.message)
    } finally {
      setLoading(false)
    }
  }

  const custodianNums = [1, 2, 3, 4, 5]

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" style={{ maxWidth: 560 }} onClick={e => e.stopPropagation()}>

        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 style={{ fontSize: 18, fontWeight: 700 }}>Court Order #{order.id}</h3>
            <div className="flex items-center gap-2 mt-1">
              <StatusBadge status={order.status} />
              <span className="text-muted text-sm">{timeAgo(order.created_at)}</span>
            </div>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>✕</button>
        </div>

        <div className="card mb-4" style={{ background: 'var(--bg-base)' }}>
          <div className="label">Reason</div>
          <div style={{ marginTop: 4 }}>{order.reason}</div>
          {order.pdf_url && (
            <a href={order.pdf_url} target="_blank" rel="noopener noreferrer"
              className="btn btn-ghost btn-sm mt-2" style={{ display: 'inline-flex' }}>
              📄 View Court Document
            </a>
          )}
          <div className="label mt-4">Nullifier</div>
          <div className="mono mt-1">{order.nullifier_hex}</div>
        </div>

        {/* Votes */}
        <div className="mb-4">
          <div className="label mb-2">Custodian Votes (3-of-5 required)</div>
          <VoteBar approvals={order.approvals} rejections={order.rejections} />
          <div className="mt-2">
            {custodianNums.map(num => {
              const vote = order.votes?.find(v => v.custodian_num === num)
              return (
                <div key={num} className="vote-row">
                  <div className="vote-num">{num}</div>
                  <div style={{ flex: 1 }}>
                    {vote ? (
                      <>
                        <span className="vote-status">{vote.approved ? '✅' : '❌'}</span>
                        {' '}
                        <span style={{ fontSize: 13 }}>{truncate(vote.custodian_id, 24)}</span>
                        {vote.note && <span className="text-muted text-sm"> — {vote.note}</span>}
                      </>
                    ) : (
                      <span className="text-muted text-sm">— waiting for vote</span>
                    )}
                  </div>
                  {num === custodian.num && !vote && (
                    <span className="badge" style={{ background: '#63b3ed22', color: 'var(--accent-blue)', border: '1px solid #63b3ed44' }}>
                      👤 You
                    </span>
                  )}
                </div>
              )
            })}
          </div>
        </div>

        {/* Decrypted identity */}
        {order.decrypted_identity && (
          <div className="alert alert-warning mb-4">
            <strong>🔓 Decrypted Identity (in-memory only)</strong>
            <div className="alert alert-error mt-2" style={{ fontSize: 12 }}>
              {order.identity_warning}
            </div>
            <pre style={{ marginTop: 8, fontSize: 12, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
              {JSON.stringify(order.decrypted_identity, null, 2)}
            </pre>
          </div>
        )}

        {order.revoke_txid && (
          <div className="alert alert-success mb-4">
            ⚡ Revoked on Algorand Testnet!{' '}
            <a href={`https://allo.info/tx/${order.revoke_txid}`} target="_blank" rel="noopener noreferrer"
              style={{ color: 'var(--accent-green)' }}>
              View on Explorer →
            </a>
          </div>
        )}

        {msg && <div className={`alert ${msg.startsWith('❌') ? 'alert-error' : 'alert-success'} mb-4`}>{msg}</div>}

        {/* Vote UI — only if this custodian hasn't voted yet */}
        {!myVote && order.status === 'pending' && (
          <div>
            <div className="form-group">
              <label className="label">Optional note for your vote</label>
              <input className="input" placeholder="e.g. Reviewed documents, verified case number"
                value={note} onChange={e => setNote(e.target.value)} />
            </div>
            <div className="flex gap-3">
              <button className="btn btn-danger" onClick={() => castVote(false)} disabled={loading}>
                ❌ Reject
              </button>
              <button className="btn btn-success" onClick={() => castVote(true)} disabled={loading}>
                ✅ Approve
              </button>
            </div>
          </div>
        )}

        {myVote && (
          <div className="alert alert-info">
            You voted <strong>{myVote.approved ? '✅ Approve' : '❌ Reject'}</strong>
            {myVote.note && ` — "${myVote.note}"`}
          </div>
        )}

        {/* Execute button (only issuer / when approved) */}
        {order.status === 'approved' && (
          <button className="btn btn-primary w-full mt-4" onClick={executeRevoke} disabled={loading}>
            {loading ? '⏳ Executing…' : '⚡ Execute On-Chain Revocation'}
          </button>
        )}
      </div>
    </div>
  )
}

// ── Dashboard ──────────────────────────────────────────────────────────────

function Dashboard({ custodian, onLogout }) {
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedOrder, setSelected] = useState(null)
  const [showCreate, setShowCreate] = useState(false)
  const [stats, setStats] = useState({ total: 0, pending: 0, approved: 0, executed: 0 })

  const fetchOrders = useCallback(async () => {
    try {
      const data = await fetch(`${API}/court-orders`).then(r => r.json())
      setOrders(data)
      setStats({
        total: data.length,
        pending: data.filter(o => o.status === 'pending').length,
        approved: data.filter(o => o.status === 'approved').length,
        executed: data.filter(o => o.status === 'executed').length,
      })
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { fetchOrders() }, [fetchOrders])

  // Poll every 5s for real-time vote updates
  useEffect(() => {
    const t = setInterval(fetchOrders, 5000)
    return () => clearInterval(t)
  }, [fetchOrders])

  const openOrder = async (o) => {
    const full = await fetch(`${API}/court-order/${o.id}`).then(r => r.json())
    setSelected(full)
  }

  return (
    <div className="app">
      {/* Navbar */}
      <nav className="navbar">
        <div className="navbar-brand">
          <div className="logo-icon">🛡️</div>
          AlgoKYC
          <span className="nav-badge">CUSTODIAN</span>
        </div>
        <div className="flex items-center gap-3">
          <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
            👤 Custodian #{custodian.num} — {truncate(custodian.id, 16)}
          </div>
          <button className="btn btn-ghost btn-sm" onClick={onLogout}>Log out</button>
        </div>
      </nav>

      <div className="main">
        {/* Stats */}
        <div className="stats-grid">
          {[
            { label: 'Total Orders', value: stats.total, icon: '📋', color: 'var(--accent-blue)' },
            { label: 'Pending', value: stats.pending, icon: '⏳', color: 'var(--accent-amber)' },
            { label: 'Approved', value: stats.approved, icon: '✅', color: 'var(--accent-green)' },
            { label: 'Executed', value: stats.executed, icon: '⚡', color: 'var(--accent-purple)' },
          ].map(s => (
            <div key={s.label} className="card">
              <div className="card-title">{s.label}</div>
              <div className="card-value" style={{ color: s.color }}>
                {s.icon} {s.value}
              </div>
            </div>
          ))}
        </div>

        {/* Info banner */}
        <div className="alert alert-info mb-6">
          🔐 <strong>3-of-5 Shamir Secret Sharing active.</strong> Your approval is share #{custodian.num} of 5.
          Any 3 approvals automatically reconstruct the decryption key and display the identity <strong>in-memory only</strong>.
          No identity data is ever stored or logged (DPDP compliant).
        </div>

        {/* Court Orders table */}
        <div className="section-header">
          <div className="section-title">⚖️ Court Orders</div>
          <button className="btn btn-primary btn-sm" onClick={() => setShowCreate(true)}>
            + New Order
          </button>
        </div>

        {loading ? (
          <div className="card" style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>
            ⏳ Loading orders…
          </div>
        ) : orders.length === 0 ? (
          <div className="card" style={{ textAlign: 'center', padding: 40 }}>
            <div style={{ fontSize: 48, marginBottom: 12 }}>⚖️</div>
            <div style={{ fontSize: 18, fontWeight: 600 }}>No Court Orders</div>
            <div className="text-muted mt-2">All KYC credentials are currently valid.</div>
          </div>
        ) : (
          <div className="table-wrap card" style={{ padding: 0 }}>
            <table>
              <thead>
                <tr>
                  <th>Order ID</th>
                  <th>Nullifier</th>
                  <th>Reason</th>
                  <th>Status</th>
                  <th>Votes</th>
                  <th>Created</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {orders.map(o => {
                  const myVote = o.votes?.find(v => v.custodian_num === custodian.num)
                  return (
                    <tr key={o.id}>
                      <td><span className="mono">#{o.id.slice(0, 8)}</span></td>
                      <td><span className="mono">{o.nullifier_hex.slice(0, 12)}…</span></td>
                      <td style={{ maxWidth: 200 }}>{o.reason}</td>
                      <td><StatusBadge status={o.status} /></td>
                      <td>
                        <div style={{ minWidth: 120 }}>
                          <VoteBar approvals={o.approvals} rejections={o.rejections} />
                        </div>
                      </td>
                      <td className="text-muted text-sm">{timeAgo(o.created_at)}</td>
                      <td>
                        {!myVote && o.status === 'pending' ? (
                          <button className="btn btn-primary btn-sm" onClick={() => openOrder(o)}>
                            🗳️ Vote
                          </button>
                        ) : (
                          <button className="btn btn-ghost btn-sm" onClick={() => openOrder(o)}>
                            View
                          </button>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Protocol explanation */}
        <div className="card mt-6" style={{ marginTop: 24 }}>
          <div className="section-title mb-4">🔒 Revocation Protocol</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 16 }}>
            {[
              { step: '1', icon: '🏛️', title: 'Court Order Received', desc: 'Issuer uploads a court-mandated revocation request with nullifier and documentation.' },
              { step: '2', icon: '🗳️', title: 'Custodians Vote', desc: '5 independent custodians review the order. Shamir shares only activate on 3+ approvals.' },
              { step: '3', icon: '🔑', title: 'Key Reconstruction', desc: '3-of-5 Shamir shares are combined to reconstruct the ECIES decryption key in-memory.' },
              { step: '4', icon: '🔓', title: 'Identity Revealed', desc: 'Encrypted identity blob is decrypted once, displayed once, then erased from memory.' },
              { step: '5', icon: '⚡', title: 'On-Chain Revocation', desc: 'NullifierRegistry.invalidate() is called — the credential is permanently revoked.' },
              { step: '6', icon: '🗑️', title: 'Data Cleared', desc: 'Decrypted identity purged from memory. No logs, no persistence. DPDP compliant.' },
            ].map(s => (
              <div key={s.step} style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
                <div style={{
                  width: 32, height: 32, borderRadius: '50%', flexShrink: 0,
                  background: 'linear-gradient(135deg, #63b3ed33, #b794f433)',
                  border: '1px solid var(--border-glow)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 16,
                }}>{s.icon}</div>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>{s.title}</div>
                  <div style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: 4, lineHeight: 1.5 }}>{s.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {showCreate && (
        <CreateOrderModal onClose={() => setShowCreate(false)} onCreated={fetchOrders} />
      )}
      {selectedOrder && (
        <OrderDetailModal
          order={selectedOrder}
          custodian={custodian}
          onClose={() => setSelected(null)}
          onRefresh={fetchOrders}
        />
      )}
    </div>
  )
}

// ── Root ─────────────────────────────────────────────────────────────────────

export default function App() {
  const [custodian, setCustodian] = useState(null)

  if (!custodian) return <LoginScreen onLogin={setCustodian} />
  return <Dashboard custodian={custodian} onLogout={() => setCustodian(null)} />
}
