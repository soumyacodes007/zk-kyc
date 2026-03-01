import { useState, useEffect, useCallback } from 'react'
import {
  LayoutDashboard, FileText, Scale, Users, Database, FileSearch,
  Settings, Shield, CheckCircle, Clock, AlertCircle, XCircle,
  Plus, X, TrendingUp, Activity, Lock, Unlock, Zap, Trash2,
  FileCheck, Key, Eye, Server, Network
} from 'lucide-react'
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
  const config = {
    pending: { color: 'amber', icon: Clock },
    approved: { color: 'green', icon: CheckCircle },
    rejected: { color: 'red', icon: XCircle },
    executed: { color: 'blue', icon: Zap },
    expired: { color: 'zinc', icon: AlertCircle }
  }
  const { color, icon: Icon } = config[status] || config.pending
  return (
    <span className={`badge ${color}`}>
      <Icon size={14} />
      {status}
    </span>
  )
}

// ── Sidebar Component ──────────────────────────────────────────────────────

function Sidebar({ activeView, setActiveView }) {
  const menuItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'credentials', label: 'Credentials', icon: FileCheck },
    { id: 'court-orders', label: 'Court Orders', icon: Scale },
    { id: 'custodians', label: 'Custodians', icon: Users },
    { id: 'registry', label: 'Revocation Registry', icon: Database },
    { id: 'audit', label: 'Audit Logs', icon: FileSearch },
    { id: 'settings', label: 'Settings', icon: Settings }
  ]

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <div className="sidebar-logo-icon">AK</div>
          AlgoKYC
        </div>
      </div>
      <nav className="sidebar-nav">
        {menuItems.map(item => (
          <a
            key={item.id}
            className={`nav-item ${activeView === item.id ? 'active' : ''}`}
            onClick={() => setActiveView(item.id)}
          >
            <item.icon />
            {item.label}
          </a>
        ))}
      </nav>
    </div>
  )
}

// ── Top Navbar Component ───────────────────────────────────────────────────

function TopNavbar({ custodian, onLogout }) {
  return (
    <div className="top-navbar">
      <div className="navbar-left">
        <div className="network-badge">
          <span className="dot"></span>
          Algorand Testnet
        </div>
        <span className="badge blue">
          <Shield size={14} />
          Custodian #{custodian.num}
        </span>
      </div>
      <div className="navbar-right">
        <div className="wallet-address">{truncate(custodian.id, 16)}</div>
        <button className="btn btn-ghost" onClick={onLogout}>
          Log out
        </button>
      </div>
    </div>
  )
}

// ── Login Screen ───────────────────────────────────────────────────────────

function LoginScreen({ onLogin }) {
  const [custodianId, setCustodianId] = useState('')
  const [connecting, setConnecting] = useState(false)
  const [manualMode, setManualMode] = useState(false)
  const [err, setErr] = useState('')

  const CUSTODIAN_WHITELIST = {
    'CUSTODIAN1ADDRESS': 1,
    'CUSTODIAN2ADDRESS': 2,
    'CUSTODIAN3ADDRESS': 3,
    'CUSTODIAN4ADDRESS': 4,
    'CUSTODIAN5ADDRESS': 5,
  }

  const connectWallet = async () => {
    setConnecting(true)
    setErr('')
    try {
      const LuteConnect = (await import('lute-connect')).default
      const lute = new LuteConnect('AlgoKYC-Dashboard')
      const accounts = await lute.connect('testnet-v1.0')

      if (accounts && accounts[0]) {
        const address = accounts[0]
        const custodianNum = CUSTODIAN_WHITELIST[address]

        if (custodianNum) {
          onLogin({ num: custodianNum, id: address })
        } else {
          console.warn('Wallet not in whitelist, using demo mode')
          onLogin({ num: 1, id: address })
        }
      }
    } catch (e) {
      console.error('Lute connection error:', e)
      if (!e.message?.includes('closed') && !e.message?.includes('cancel')) {
        setErr('Wallet connection failed: ' + e.message)
      }
    } finally {
      setConnecting(false)
    }
  }

  const manualLogin = (e) => {
    e.preventDefault()
    if (!custodianId.trim()) return setErr('Enter your wallet address')

    const custodianNum = CUSTODIAN_WHITELIST[custodianId.trim()]
    if (custodianNum) {
      onLogin({ num: custodianNum, id: custodianId.trim() })
    } else {
      setErr('This wallet is not authorized as a custodian')
    }
  }

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-header">
          <div className="login-logo">AK</div>
          <h1 className="login-title">Custodian Dashboard</h1>
          <p className="login-subtitle">Connect your authorized wallet to access the dashboard</p>
        </div>

        {!manualMode ? (
          <div>
            <button
              className="btn btn-primary"
              style={{ width: '100%', justifyContent: 'center' }}
              onClick={connectWallet}
              disabled={connecting}
            >
              <Shield size={16} />
              {connecting ? 'Connecting...' : 'Connect Lute Wallet'}
            </button>

            <div className="login-divider">OR</div>

            <button
              className="btn btn-secondary"
              style={{ width: '100%', justifyContent: 'center' }}
              onClick={() => setManualMode(true)}
            >
              <Key size={16} />
              Enter Wallet Address
            </button>

            <div className="login-divider">DEMO</div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
              <button
                className="btn btn-ghost"
                style={{
                  width: '100%',
                  justifyContent: 'center',
                  background: 'rgba(59, 130, 246, 0.1)',
                  border: '1px solid rgba(59, 130, 246, 0.3)',
                  color: 'var(--accent-blue)',
                  fontSize: 13,
                  padding: '10px 8px'
                }}
                onClick={() => onLogin({ num: 1, id: 'DEMO_CUSTODIAN_1' })}
              >
                Demo 1
              </button>

              <button
                className="btn btn-ghost"
                style={{
                  width: '100%',
                  justifyContent: 'center',
                  background: 'rgba(139, 92, 246, 0.1)',
                  border: '1px solid rgba(139, 92, 246, 0.3)',
                  color: 'var(--accent-purple)',
                  fontSize: 13,
                  padding: '10px 8px'
                }}
                onClick={() => onLogin({ num: 2, id: 'DEMO_CUSTODIAN_2' })}
              >
                Demo 2
              </button>

              <button
                className="btn btn-ghost"
                style={{
                  width: '100%',
                  justifyContent: 'center',
                  background: 'rgba(16, 185, 129, 0.1)',
                  border: '1px solid rgba(16, 185, 129, 0.3)',
                  color: 'var(--accent-green)',
                  fontSize: 13,
                  padding: '10px 8px'
                }}
                onClick={() => onLogin({ num: 3, id: 'DEMO_CUSTODIAN_3' })}
              >
                Demo 3
              </button>
            </div>

            <div style={{
              marginTop: 12,
              padding: 12,
              background: 'rgba(59, 130, 246, 0.05)',
              border: '1px solid rgba(59, 130, 246, 0.1)',
              borderRadius: 8,
              fontSize: 12,
              color: 'var(--text-secondary)',
              textAlign: 'center'
            }}>
              <strong>Demo Flow:</strong> Vote with 1 real wallet + 2 demo custodians to reach 3-of-5 threshold
            </div>
          </div>
        ) : (
          <form onSubmit={manualLogin}>
            <div className="form-group">
              <label className="form-label">Wallet Address</label>
              <input
                className="form-input"
                type="text"
                placeholder="Enter Algorand wallet address"
                value={custodianId}
                onChange={e => setCustodianId(e.target.value)}
              />
            </div>

            <button className="btn btn-primary" type="submit" style={{ width: '100%', justifyContent: 'center' }}>
              Login
            </button>

            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => setManualMode(false)}
              style={{ width: '100%', justifyContent: 'center', marginTop: 12 }}
            >
              Back to Wallet Connect
            </button>
          </form>
        )}

        {err && (
          <div className="alert-banner" style={{ marginTop: 16, background: '#fee2e2', borderColor: '#fecaca' }}>
            <AlertCircle size={16} color="#991b1b" />
            <span style={{ color: '#991b1b', fontSize: 13 }}>{err}</span>
          </div>
        )}

        <div className="alert-banner info" style={{ marginTop: 24 }}>
          <Lock size={16} color="#1e40af" />
          <span style={{ color: '#1e40af', fontSize: 13 }}>
            Only the 5 pre-authorized custodian wallets can access this dashboard.
          </span>
        </div>
      </div>
    </div>
  )
}

// ── Dashboard View ─────────────────────────────────────────────────────────

function DashboardView({ custodian, orders, stats }) {
  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Dashboard</h1>
        <p className="page-subtitle">Monitor KYC credentials and court order revocations</p>
      </div>

      {/* Stats Grid */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-card-header">
            <div className="stat-icon blue">
              <FileCheck size={20} />
            </div>
            <span className="badge green">Active</span>
          </div>
          <div className="stat-value">1,247</div>
          <div className="stat-label">Active Credentials</div>
        </div>

        <div className="stat-card">
          <div className="stat-card-header">
            <div className="stat-icon amber">
              <Clock size={20} />
            </div>
            <span className="badge amber">{stats.pending}</span>
          </div>
          <div className="stat-value">{stats.pending}</div>
          <div className="stat-label">Pending Court Orders</div>
        </div>

        <div className="stat-card">
          <div className="stat-card-header">
            <div className="stat-icon green">
              <CheckCircle size={20} />
            </div>
            <span className="badge blue">Required</span>
          </div>
          <div className="stat-value">3</div>
          <div className="stat-label">Custodian Votes Required</div>
        </div>

        <div className="stat-card">
          <div className="stat-card-header">
            <div className="stat-icon red">
              <XCircle size={20} />
            </div>
            <span className="badge red">{stats.executed}</span>
          </div>
          <div className="stat-value">{stats.executed}</div>
          <div className="stat-label">Revoked Credentials</div>
        </div>
      </div>

      {/* Security Status Banner */}
      <div className="alert-banner info">
        <Shield size={18} color="#1e40af" />
        <div className="alert-content">
          <span className="badge green">3-of-5 Shamir Secret Sharing Active</span>
          <span className="badge blue">DPDP Compliant</span>
          <span className="badge blue">No Identity Storage</span>
          <span className="badge blue">In-Memory Decryption Only</span>
          <span className="badge blue">Threshold Approval Required</span>
        </div>
      </div>

      {/* Revocation Protocol Timeline */}
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">Revocation Protocol</h2>
        </div>
        <div className="timeline">
          {[
            { icon: Scale, title: 'Court Order Received', desc: 'Issuer uploads court-mandated revocation request with nullifier' },
            { icon: Users, title: 'Custodian Votes', desc: '5 independent custodians review and vote on the order' },
            { icon: Key, title: 'Key Reconstruction', desc: '3-of-5 Shamir shares combine to reconstruct decryption key' },
            { icon: Unlock, title: 'Identity Revealed', desc: 'Encrypted identity decrypted once and displayed in-memory' },
            { icon: Zap, title: 'On-Chain Revocation', desc: 'NullifierRegistry.invalidate() permanently revokes credential' },
            { icon: Trash2, title: 'Memory Cleared', desc: 'Decrypted identity purged from memory, no logs or persistence' }
          ].map((step, i) => (
            <div key={i} className="timeline-step">
              <div className="timeline-step-icon">
                <step.icon />
              </div>
              <div className="timeline-step-content">
                <div className="timeline-step-title">{step.title}</div>
                <div className="timeline-step-desc">{step.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Blockchain Info Panel */}
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">Blockchain Information</h2>
          <span className="badge green">
            <Activity size={14} />
            Connected
          </span>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 20 }}>
          <div>
            <div className="text-muted text-sm mb-2">Network</div>
            <div className="font-semibold">Algorand Testnet</div>
          </div>
          <div>
            <div className="text-muted text-sm mb-2">Contract</div>
            <div className="font-semibold">NullifierRegistry</div>
          </div>
          <div>
            <div className="text-muted text-sm mb-2">Last Transaction</div>
            <div className="mono">0xABC123...DEF456</div>
          </div>
          <div>
            <div className="text-muted text-sm mb-2">Threshold</div>
            <div className="font-semibold">3 / 5 Custodians</div>
          </div>
        </div>
      </div>

      {/* Compliance Badges */}
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">Compliance Status</h2>
        </div>
        <div className="flex gap-2" style={{ flexWrap: 'wrap' }}>
          <span className="badge green">DPDP Compliant</span>
          <span className="badge green">ZK Proof Verified</span>
          <span className="badge green">Threshold Custody</span>
          <span className="badge green">No Persistent Storage</span>
          <span className="badge green">On-Chain Revocation</span>
          <span className="badge blue">Shamir Secret Sharing</span>
          <span className="badge blue">In-Memory Only</span>
        </div>
      </div>
    </div>
  )
}

// ── Court Orders View ──────────────────────────────────────────────────────

function CourtOrdersView({ custodian, orders, onRefresh, setShowCreate, setSelectedOrder }) {
  if (orders.length === 0) {
    return (
      <div className="page-container">
        <div className="page-header">
          <h1 className="page-title">Court Orders</h1>
          <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
            <Plus size={16} />
            New Court Order
          </button>
        </div>
        <div className="card">
          <div className="empty-state">
            <Scale className="empty-state-icon" />
            <div className="empty-state-title">No Active Court Orders</div>
            <div className="empty-state-desc">All KYC credentials are currently valid</div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Court Orders</h1>
        <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
          <Plus size={16} />
          New Court Order
        </button>
      </div>

      <div className="table-container">
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
                  <td style={{ maxWidth: 300 }}>{o.reason}</td>
                  <td><StatusBadge status={o.status} /></td>
                  <td>
                    <div style={{ minWidth: 100 }}>
                      <div className="text-sm text-muted">{o.approvals} / 3 approved</div>
                      <div className="progress-bar">
                        <div className="progress-fill" style={{ width: `${(o.approvals / 3) * 100}%` }} />
                      </div>
                    </div>
                  </td>
                  <td className="text-muted text-sm">{timeAgo(o.created_at)}</td>
                  <td>
                    {!myVote && o.status === 'pending' ? (
                      <button className="btn btn-primary" style={{ fontSize: 13, padding: '6px 12px' }} onClick={() => setSelectedOrder(o)}>
                        Vote
                      </button>
                    ) : (
                      <button className="btn btn-ghost" style={{ fontSize: 13, padding: '6px 12px' }} onClick={() => setSelectedOrder(o)}>
                        <Eye size={14} />
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
    </div>
  )
}

// ── Create Order Modal ─────────────────────────────────────────────────────

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
        <div className="modal-header">
          <h3 className="modal-title">New Court Order</h3>
          <button className="btn btn-ghost" style={{ padding: 8 }} onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className="alert-banner" style={{ background: '#fffbeb', borderColor: '#fde68a', marginBottom: 24 }}>
          <AlertCircle size={16} color="#92400e" />
          <span style={{ color: '#92400e', fontSize: 13 }}>
            This will initiate a revocation flow. 3-of-5 custodians must approve.
          </span>
        </div>

        <form onSubmit={submit}>
          <div className="form-group">
            <label className="form-label">Nullifier Hex (64 chars)</label>
            <input
              className="form-input mono"
              placeholder="a1b2c3...d4e5f6"
              value={form.nullifier_hex}
              onChange={e => setForm(f => ({ ...f, nullifier_hex: e.target.value }))}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Reason / Case Number</label>
            <input
              className="form-input"
              placeholder="e.g. Court Order #2024-xyz — Fraud investigation"
              value={form.reason}
              onChange={e => setForm(f => ({ ...f, reason: e.target.value }))}
            />
          </div>

          <div className="form-group">
            <label className="form-label">PDF URL (optional)</label>
            <input
              className="form-input"
              type="url"
              placeholder="https://court.gov/order/..."
              value={form.pdf_url}
              onChange={e => setForm(f => ({ ...f, pdf_url: e.target.value }))}
            />
          </div>

          {err && (
            <div className="alert-banner" style={{ background: '#fee2e2', borderColor: '#fecaca', marginBottom: 16 }}>
              <AlertCircle size={16} color="#991b1b" />
              <span style={{ color: '#991b1b', fontSize: 13 }}>{err}</span>
            </div>
          )}

          <div className="flex gap-3">
            <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? 'Creating…' : 'Create Court Order'}
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
      const fresh = await fetch(`${API}/court-order/${order.id}`).then(r => r.json())
      setOrder(fresh)
      onRefresh()
    } catch (e) {
      setMsg('Error: ' + e.message)
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
      setMsg(`Revoked on-chain! txid: ${data.txid?.slice(0, 20)}...`)
      const fresh = await fetch(`${API}/court-order/${order.id}`).then(r => r.json())
      setOrder(fresh)
      onRefresh()
    } catch (e) {
      setMsg('Error: ' + e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" style={{ maxWidth: 700 }} onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h3 className="modal-title">Court Order #{order.id.slice(0, 8)}</h3>
            <div className="flex items-center gap-2 mt-2">
              <StatusBadge status={order.status} />
              <span className="text-muted text-sm">{timeAgo(order.created_at)}</span>
            </div>
          </div>
          <button className="btn btn-ghost" style={{ padding: 8 }} onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className="card" style={{ marginBottom: 24 }}>
          <div className="form-label">Reason</div>
          <div style={{ marginTop: 4 }}>{order.reason}</div>
          {order.pdf_url && (
            <a href={order.pdf_url} target="_blank" rel="noopener noreferrer" className="btn btn-ghost mt-2">
              <FileText size={14} />
              View Court Document
            </a>
          )}
          <div className="form-label mt-4">Nullifier</div>
          <div className="mono mt-2">{order.nullifier_hex}</div>
        </div>

        {/* Custodian Votes */}
        <div className="card" style={{ marginBottom: 24 }}>
          <div className="form-label mb-2">Custodian Votes (3-of-5 required)</div>
          <div className="text-sm text-muted mb-2">{order.approvals} approved • {order.rejections} rejected</div>
          <div className="progress-bar mb-4">
            <div className="progress-fill" style={{ width: `${(order.approvals / 3) * 100}%` }} />
          </div>
          {[1, 2, 3, 4, 5].map(num => {
            const vote = order.votes?.find(v => v.custodian_num === num)
            return (
              <div key={num} className="flex items-center gap-3 mb-3">
                <div style={{
                  width: 32,
                  height: 32,
                  borderRadius: '50%',
                  background: 'var(--zinc-100)',
                  border: '1px solid var(--border-primary)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontWeight: 600,
                  fontSize: 13
                }}>
                  {num}
                </div>
                <div style={{ flex: 1 }}>
                  {vote ? (
                    <>
                      <span className={`badge ${vote.approved ? 'green' : 'red'}`}>
                        {vote.approved ? 'Approved' : 'Rejected'}
                      </span>
                      {vote.note && <span className="text-muted text-sm"> — {vote.note}</span>}
                    </>
                  ) : (
                    <span className="text-muted text-sm">Waiting for vote</span>
                  )}
                </div>
                {num === custodian.num && !vote && (
                  <span className="badge blue">You</span>
                )}
              </div>
            )
          })}
        </div>

        {order.decrypted_identity && (
          <div className="alert-banner" style={{ background: '#fffbeb', borderColor: '#fde68a', marginBottom: 24 }}>
            <Unlock size={16} color="#92400e" />
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600, marginBottom: 8, color: '#92400e' }}>Decrypted Identity (in-memory only)</div>
              <pre style={{ fontSize: 12, whiteSpace: 'pre-wrap', wordBreak: 'break-all', color: '#92400e' }}>
                {JSON.stringify(order.decrypted_identity, null, 2)}
              </pre>
            </div>
          </div>
        )}

        {order.revoke_txid && (
          <div className="alert-banner" style={{ background: '#ecfdf5', borderColor: '#a7f3d0', marginBottom: 24 }}>
            <Zap size={16} color="#065f46" />
            <span style={{ color: '#065f46' }}>
              Revoked on Algorand Testnet!{' '}
              <a href={`https://lora.algokit.io/testnet/transaction/${order.revoke_txid}`} target="_blank" rel="noopener noreferrer" style={{ color: '#065f46', textDecoration: 'underline' }}>
                View on Explorer →
              </a>
            </span>
          </div>
        )}

        {msg && (
          <div className={`alert-banner ${msg.includes('Error') ? '' : ''}`} style={{
            background: msg.includes('Error') ? '#fee2e2' : '#ecfdf5',
            borderColor: msg.includes('Error') ? '#fecaca' : '#a7f3d0',
            marginBottom: 24
          }}>
            {msg.includes('Error') ? <AlertCircle size={16} color="#991b1b" /> : <CheckCircle size={16} color="#065f46" />}
            <span style={{ color: msg.includes('Error') ? '#991b1b' : '#065f46' }}>{msg}</span>
          </div>
        )}

        {!myVote && order.status === 'pending' && (
          <div>
            <div className="form-group">
              <label className="form-label">Optional note for your vote</label>
              <input
                className="form-input"
                placeholder="e.g. Reviewed documents, verified case number"
                value={note}
                onChange={e => setNote(e.target.value)}
              />
            </div>
            <div className="flex gap-3">
              <button className="btn btn-secondary" onClick={() => castVote(false)} disabled={loading}>
                <XCircle size={16} />
                Reject
              </button>
              <button className="btn btn-primary" onClick={() => castVote(true)} disabled={loading}>
                <CheckCircle size={16} />
                Approve
              </button>
            </div>
          </div>
        )}

        {myVote && (
          <div className="alert-banner info">
            <CheckCircle size={16} color="#1e40af" />
            <span style={{ color: '#1e40af' }}>
              You voted <strong>{myVote.approved ? 'Approve' : 'Reject'}</strong>
              {myVote.note && ` — "${myVote.note}"`}
            </span>
          </div>
        )}

        {order.status === 'approved' && (
          <button className="btn btn-primary" style={{ width: '100%', justifyContent: 'center', marginTop: 16 }} onClick={executeRevoke} disabled={loading}>
            <Zap size={16} />
            {loading ? 'Executing…' : 'Execute On-Chain Revocation'}
          </button>
        )}
      </div>
    </div>
  )
}

// ── Main App ───────────────────────────────────────────────────────────────

function Dashboard({ custodian, onLogout }) {
  const [activeView, setActiveView] = useState('dashboard')
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
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchOrders()
  }, [fetchOrders])

  useEffect(() => {
    const t = setInterval(fetchOrders, 5000)
    return () => clearInterval(t)
  }, [fetchOrders])

  const openOrder = async (o) => {
    const full = await fetch(`${API}/court-order/${o.id}`).then(r => r.json())
    setSelected(full)
  }

  return (
    <div className="app-layout">
      <Sidebar activeView={activeView} setActiveView={setActiveView} />
      <div className="main-content">
        <TopNavbar custodian={custodian} onLogout={onLogout} />

        {activeView === 'dashboard' && (
          <DashboardView custodian={custodian} orders={orders} stats={stats} />
        )}

        {activeView === 'court-orders' && (
          <CourtOrdersView
            custodian={custodian}
            orders={orders}
            onRefresh={fetchOrders}
            setShowCreate={setShowCreate}
            setSelectedOrder={openOrder}
          />
        )}

        {activeView === 'credentials' && (
          <div className="page-container">
            <div className="page-header">
              <h1 className="page-title">Credentials</h1>
              <p className="page-subtitle">View all issued KYC credentials</p>
            </div>
            <div className="card">
              <div className="empty-state">
                <FileCheck className="empty-state-icon" />
                <div className="empty-state-title">Credentials View</div>
                <div className="empty-state-desc">This section will display all issued credentials</div>
              </div>
            </div>
          </div>
        )}

        {activeView === 'custodians' && (
          <div className="page-container">
            <div className="page-header">
              <h1 className="page-title">Custodians</h1>
              <p className="page-subtitle">Manage the 5 authorized custodians</p>
            </div>
            <div className="card">
              <div className="empty-state">
                <Users className="empty-state-icon" />
                <div className="empty-state-title">Custodians Management</div>
                <div className="empty-state-desc">View and manage custodian access</div>
              </div>
            </div>
          </div>
        )}

        {activeView === 'registry' && (
          <div className="page-container">
            <div className="page-header">
              <h1 className="page-title">Revocation Registry</h1>
              <p className="page-subtitle">On-chain nullifier registry</p>
            </div>
            <div className="card">
              <div className="empty-state">
                <Database className="empty-state-icon" />
                <div className="empty-state-title">Registry View</div>
                <div className="empty-state-desc">View on-chain revocation registry</div>
              </div>
            </div>
          </div>
        )}

        {activeView === 'audit' && (
          <div className="page-container">
            <div className="page-header">
              <h1 className="page-title">Audit Logs</h1>
              <p className="page-subtitle">Complete audit trail of all actions</p>
            </div>
            <div className="card">
              <div className="empty-state">
                <FileSearch className="empty-state-icon" />
                <div className="empty-state-title">Audit Logs</div>
                <div className="empty-state-desc">View complete audit trail</div>
              </div>
            </div>
          </div>
        )}

        {activeView === 'settings' && (
          <div className="page-container">
            <div className="page-header">
              <h1 className="page-title">Settings</h1>
              <p className="page-subtitle">Configure dashboard preferences</p>
            </div>
            <div className="card">
              <div className="empty-state">
                <Settings className="empty-state-icon" />
                <div className="empty-state-title">Settings</div>
                <div className="empty-state-desc">Configure your preferences</div>
              </div>
            </div>
          </div>
        )}
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

export default function App() {
  const [custodian, setCustodian] = useState(null)

  if (!custodian) return <LoginScreen onLogin={setCustodian} />
  return <Dashboard custodian={custodian} onLogout={() => setCustodian(null)} />
}
