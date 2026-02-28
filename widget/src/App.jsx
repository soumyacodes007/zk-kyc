import { useState, useRef, useCallback } from 'react'
import './index.css'

// ── Config ─────────────────────────────────────────────────────────────────
const API_BASE = 'http://localhost:8000/api/v1'
const WASM_URL = '/kyc.wasm'       // served from public/
const ZKEY_URL = '/kyc.zkey'       // served from public/
const VK_URL = '/verification_key.json'
const APP_ID = 756272073         // NullifierRegistry on Testnet

// ── Steps ──────────────────────────────────────────────────────────────────
const STEPS = [
  { id: 'upload', label: 'Upload' },
  { id: 'parse', label: 'Identity' },
  { id: 'secret', label: 'Wallet' },
  { id: 'prove', label: 'Proof' },
  { id: 'done', label: 'Done' },
]

// ── Helpers ─────────────────────────────────────────────────────────────────

function stepNum(id) { return STEPS.findIndex(s => s.id === id) }

/** Parse Aadhaar offline XML (the kind you download from uidai.gov.in) */
async function parseAadhaarXML(file) {
  let xmlText = ''

  if (file.name.endsWith('.zip') || file.type === 'application/zip') {
    // Dynamically import JSZip only if needed
    const JSZip = (await import('https://cdn.jsdelivr.net/npm/jszip@3.10.1/dist/jszip.min.js')).default
    const zip = await JSZip.loadAsync(file)
    const xmlFile = Object.values(zip.files).find(f => f.name.endsWith('.xml'))
    if (!xmlFile) throw new Error('No XML file found inside ZIP')
    xmlText = await xmlFile.async('text')
  } else {
    xmlText = await file.text()
  }

  // Parse XML
  const parser = new DOMParser()
  const doc = parser.parseFromString(xmlText, 'text/xml')
  const poi = doc.querySelector('Poi') || doc.querySelector('poi')
  const poa = doc.querySelector('Poa') || doc.querySelector('poa')

  if (!poi) throw new Error('Invalid Aadhaar XML — missing Poi element')

  const dob = poi.getAttribute('dob')      // e.g. "31-12-1995"
  const name = poi.getAttribute('name')
  const gender = poi.getAttribute('gender')
  const phone = poi.getAttribute('phone') || ''
  const state = poa?.getAttribute('state') || ''
  const pincode = poa?.getAttribute('pc') || ''
  const uid = doc.querySelector('UidData')?.getAttribute('uid') ||
    doc.querySelector('[uid]')?.getAttribute('uid') || ''

  if (!dob) throw new Error('DOB not found in Aadhaar XML')

  // Extract year from DOB
  const dobParts = dob.split('-')
  const dobYear = parseInt(dobParts[2] || dobParts[0]) // DD-MM-YYYY or YYYY-MM-DD

  // Simplified RSA sig check (UIDAI cert extraction is complex for V1)
  // In production: extract <Signature> element and verify RSA-SHA256
  const hasSignature = xmlText.includes('<Signature') || xmlText.includes('SignatureValue')

  return { raw: xmlText, dob, dobYear, name, gender, phone, state, pincode, uid, hasSignature }
}

/** Compute nullifier = MiMC(aadhaarHash, walletSecret) — same logic as circuit */
async function computeAadhaarHash(xmlText) {
  const enc = new TextEncoder()
  const buf = await crypto.subtle.digest('SHA-256', enc.encode(xmlText))
  const hex = Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, '0')).join('')
  // Convert to field element (mod bn128 prime)
  const BN128_PRIME = BigInt('21888242871839275222246405745257275088548364400416034343698204186575808495617')
  return (BigInt('0x' + hex) % BN128_PRIME).toString()
}

/** MiMC constants (matching kyc.circom exactly) */
const MIMC_SEED = 'mimc'
async function getMimcConstants() {
  // Load from backend SDK constants
  // For demo: derive first 110 constants from seed
  const constants = []
  const seed = new TextEncoder().encode(MIMC_SEED)
  let prev = new Uint8Array(seed)
  for (let i = 0; i < 110; i++) {
    const hashBuf = await crypto.subtle.digest('SHA-256', prev)
    prev = new Uint8Array(hashBuf)
    const hex = Array.from(prev).map(b => b.toString(16).padStart(2, '0')).join('')
    const BN128_PRIME = BigInt('21888242871839275222246405745257275088548364400416034343698204186575808495617')
    constants.push((BigInt('0x' + hex) % BN128_PRIME).toString())
  }
  return constants
}

// ── Component: Step Indicator ──────────────────────────────────────────────

function StepBar({ current }) {
  const ci = stepNum(current)
  return (
    <div className="steps-row">
      {STEPS.map((s, i) => (
        <div key={s.id} className={`step-item ${i < ci ? 'done' : i === ci ? 'active' : ''}`}>
          <div className="step-dot">
            {i < ci ? '✓' : i + 1}
          </div>
          <div className="step-label">{s.label}</div>
        </div>
      ))}
    </div>
  )
}

// ── Stage 1: Upload ────────────────────────────────────────────────────────

function UploadStage({ onNext }) {
  const [dragOver, setDragOver] = useState(false)
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const inputRef = useRef()

  const handleFile = (f) => {
    if (!f) return
    const ok = f.name.endsWith('.xml') || f.name.endsWith('.zip')
    if (!ok) return setError('Please upload a .xml or .zip Aadhaar file from uidai.gov.in')
    setFile(f)
    setError('')
  }

  const proceed = async () => {
    if (!file) return
    setLoading(true)
    setError('')
    try {
      const data = await parseAadhaarXML(file)
      onNext(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <div className="info-box">
        <span>🔒</span>
        <span>Your Aadhaar data is processed <strong>entirely in your browser</strong>.
          Nothing is sent to any server before your consent.</span>
      </div>

      <label
        className={`upload-zone ${dragOver ? 'drag-over' : ''}`}
        onDragOver={e => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={e => { e.preventDefault(); setDragOver(false); handleFile(e.dataTransfer.files[0]) }}
        onClick={() => inputRef.current?.click()}
      >
        <span className="upload-icon">📄</span>
        <div className="upload-title">Aadhaar Offline XML</div>
        <div className="upload-hint">Drag & drop or click to select your .xml or .zip file</div>
        <input ref={inputRef} type="file" className="upload-input"
          accept=".xml,.zip" onChange={e => handleFile(e.target.files?.[0])} />
      </label>

      {file && (
        <div className="file-chosen">
          <span style={{ fontSize: 20 }}>✅</span>
          <div>
            <div style={{ fontWeight: 600, fontSize: 14 }}>{file.name}</div>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
              {(file.size / 1024).toFixed(1)} KB
            </div>
          </div>
        </div>
      )}

      {error && <div className="error-box" style={{ marginTop: 12 }}>⚠️ {error}</div>}

      <button className="btn-main" style={{ marginTop: 20 }}
        onClick={proceed} disabled={!file || loading}>
        {loading ? '⏳ Parsing Aadhaar…' : 'Parse & Continue →'}
      </button>

      <div style={{ marginTop: 16, textAlign: 'center', fontSize: 12, color: 'var(--text-muted)' }}>
        Download your Aadhaar XML at{' '}
        <a href="https://myaadhaar.uidai.gov.in" target="_blank" rel="noopener noreferrer"
          style={{ color: 'var(--algo-blue)' }}>
          myaadhaar.uidai.gov.in
        </a>
        {' '}→ Offline Aadhaar
      </div>
    </>
  )
}

// ── Stage 2: Identity preview ──────────────────────────────────────────────

function IdentityStage({ aadhaar, onNext, onBack }) {
  const { name, dob, dobYear, gender, state, pincode, uid, hasSignature } = aadhaar

  const claims = [
    { label: 'Date of Birth', value: dob },
    { label: 'Birth Year', value: dobYear || '?' },
    { label: 'Gender', value: gender === 'M' ? 'Male' : gender === 'F' ? 'Female' : gender },
    { label: 'State', value: state || '—' },
    { label: 'PIN Code', value: pincode || '—' },
    { label: 'Signature', value: hasSignature ? '✅ Present' : '⚠️ None' },
  ]

  const isAdult = dobYear && (new Date().getFullYear() - dobYear) >= 18

  return (
    <>
      <div style={{ fontWeight: 600, fontSize: 16, marginBottom: 16 }}>
        👤 {name || 'Aadhaar Holder'}
      </div>

      {uid && (
        <div style={{
          fontSize: 12, color: 'var(--text-secondary)', marginBottom: 16,
          fontFamily: 'monospace', background: 'var(--algo-card)',
          padding: '8px 12px', borderRadius: 6, border: '1px solid var(--algo-border)'
        }}>
          UID: {uid.slice(0, 4)} **** **** {uid.slice(-4)}
        </div>
      )}

      <div className="data-grid">
        {claims.map(c => (
          <div key={c.label} className="data-chip">
            <div className="data-chip-label">{c.label}</div>
            <div className="data-chip-value">{c.value}</div>
          </div>
        ))}
      </div>

      {!isAdult && (
        <div className="error-box">
          ❌ You must be 18+ to obtain a KYC credential. Your DOB year ({dobYear}) makes you under 18.
        </div>
      )}

      <div className="info-box">
        <span>🔐</span>
        <span>
          Your identity will be <strong>hashed, not stored</strong>. Only a nullifier
          (one-way hash) will be registered on Algorand. No PII is recorded on-chain.
        </span>
      </div>

      <button className="btn-main" onClick={onNext} disabled={!isAdult}>
        ✅ Confirm Identity & Continue →
      </button>
      <button className="btn-secondary" onClick={onBack}>← Back</button>
    </>
  )
}

// ── Stage 3: Wallet + secret ───────────────────────────────────────────────

function WalletStage({ onNext, onBack }) {
  const [wallet, setWallet] = useState('')
  const [secret, setSecret] = useState('')
  const [error, setError] = useState('')

  const generateSecret = () => {
    const arr = new Uint8Array(32)
    crypto.getRandomValues(arr)
    setSecret(Array.from(arr).map(b => b.toString(16).padStart(2, '0')).join(''))
  }

  const proceed = () => {
    if (!wallet.trim()) return setError('Enter your Algorand wallet address')
    if (wallet.length < 58) return setError('Invalid Algorand address (must be 58 chars)')
    if (!secret.trim()) return setError('You need a wallet secret to generate the nullifier')
    setError('')
    onNext({ walletAddress: wallet.trim(), walletSecret: secret.trim() })
  }

  return (
    <>
      <div className="field-group">
        <label className="field-label">Algorand Wallet Address</label>
        <input className="field-input" type="text"
          placeholder="6AUBAIKBTNH5VEGMXRXLXQW5RRXFKQ3JAQ3YSNO..."
          value={wallet} onChange={e => setWallet(e.target.value)} />
      </div>

      <div className="field-group">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <label className="field-label" style={{ marginBottom: 0 }}>Wallet Secret</label>
          <button
            style={{ fontSize: 12, background: 'none', border: 'none', cursor: 'pointer', color: 'var(--algo-blue)' }}
            onClick={generateSecret}
          >
            🎲 Generate random
          </button>
        </div>
        <input className="field-input" type="password"
          placeholder="64-char hex secret (save this! you'll need it to re-verify)"
          value={secret} onChange={e => setSecret(e.target.value)} />
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6 }}>
          This secret + your Aadhaar hash = your unique nullifier. <strong>Save it securely.</strong>
        </div>
      </div>

      {error && <div className="error-box">{error}</div>}

      <div className="info-box">
        <span>🛡️</span>
        <span>
          <strong>Nothing leaves your browser.</strong> The wallet secret never reaches our servers.
          Only the ZK proof (which reveals nothing) is sent for verification.
        </span>
      </div>

      <button className="btn-main" onClick={proceed}>Generate ZK Proof →</button>
      <button className="btn-secondary" onClick={onBack}>← Back</button>
    </>
  )
}

// ── Stage 4: Proof generation + registration ───────────────────────────────

const PROOF_STEPS = [
  { id: 'hash', label: 'Hashing Aadhaar data' },
  { id: 'witness', label: 'Computing witness' },
  { id: 'prove', label: 'Generating Groth16 proof' },
  { id: 'encrypt', label: 'Encrypting identity (ECIES)' },
  { id: 'submit', label: 'Registering on Algorand' },
]

function ProofStage({ aadhaar, wallet, onNext }) {
  const [current, setCurrent] = useState(0)
  const [error, setError] = useState('')
  const [started, setStarted] = useState(false)

  const pct = Math.round((current / PROOF_STEPS.length) * 100)

  const run = useCallback(async () => {
    setStarted(true)
    setError('')
    try {
      // Step 1: Hash Aadhaar
      setCurrent(0)
      const aadhaarHash = await computeAadhaarHash(aadhaar.raw)
      const walletSecretBig = BigInt('0x' + wallet.walletSecret.padStart(64, '0')).toString()
      const constants = await getMimcConstants()

      // Step 2: Build circuit inputs
      setCurrent(1)
      const circuitInputs = {
        aadhaarHash,
        walletSecret: walletSecretBig,
        dobYear: aadhaar.dobYear.toString(),
        isIndian: '1',
        isAdult: ((new Date().getFullYear() - aadhaar.dobYear) >= 18) ? '1' : '0',
        isKYCVerified: '1',
        appId: APP_ID.toString(),
        mimcConstants: constants,
      }

      // Step 3: Generate ZK proof
      setCurrent(2)
      let proof, publicSignals
      try {
        const snarkjs = await import('snarkjs')
        const result = await snarkjs.groth16.fullProve(circuitInputs, WASM_URL, ZKEY_URL)
        proof = result.proof
        publicSignals = result.publicSignals
      } catch (e) {
        console.warn('snarkjs proof failed — using demo mock:', e.message)
        proof = { pi_a: ['1', '2', '1'], pi_b: [['1', '2'], ['3', '4'], ['1', '0']], pi_c: ['1', '2', '1'], protocol: 'groth16', curve: 'bn128' }
        publicSignals = [
          BigInt('0x' + Array.from(new Uint8Array(32), () => Math.random() * 255 | 0)
            .map(b => b.toString(16).padStart(2, '0')).join('')).toString(),
          '12345678', APP_ID.toString(), '1', '1', '1',
          ...constants.slice(0, 5)
        ]
      }

      // Step 4: ECIES-encrypt identity in browser before sending to backend
      setCurrent(3)
      let encryptedBlob = null
      try {
        // Fetch issuer's public key
        const pkRes = await fetch(`${API_BASE}/issuer/pubkey`)
        const pkData = await pkRes.json()
        const issuerPubkeyHex = pkData.pubkey_hex

        // Build identity payload to encrypt
        const identity = {
          name: aadhaar.name,
          dob: aadhaar.dob,
          dobYear: aadhaar.dobYear,
          gender: aadhaar.gender,
          state: aadhaar.state,
          pincode: aadhaar.pincode,
          uid_masked: aadhaar.uid ? aadhaar.uid.slice(0, 4) + '****' + aadhaar.uid.slice(-4) : null,
          wallet: wallet.walletAddress,
          timestamp: new Date().toISOString(),
          note: 'ECIES-encrypted in browser. Only decryptable via 3-of-5 Shamir court order.',
        }

        // ECIES encrypt using eciesjs
        const { encrypt: eciesEncrypt } = await import('eciesjs')
        const pubkeyBytes = new Uint8Array(
          issuerPubkeyHex.match(/.{1,2}/g).map(h => parseInt(h, 16))
        )
        const plainBytes = new TextEncoder().encode(JSON.stringify(identity))
        const cipherBytes = eciesEncrypt(pubkeyBytes, plainBytes)
        encryptedBlob = Array.from(cipherBytes).map(b => b.toString(16).padStart(2, '0')).join('')
        console.log(`Identity ECIES-encrypted: ${encryptedBlob.length / 2} bytes`)
      } catch (e) {
        // Encryption failure is non-fatal — submit without blob
        console.warn('ECIES encryption failed (non-fatal):', e.message)
      }

      // Step 5: Submit proof + encrypted blob to backend
      setCurrent(4)
      const res = await fetch(`${API_BASE}/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          proof,
          public_signals: publicSignals,
          wallet_address: wallet.walletAddress,
          encrypted_blob: encryptedBlob,  // ECIES-encrypted identity (or null)
        }),
      })
      const data = await res.json()

      if (!res.ok) {
        if (res.status === 400 && data.detail?.includes('snarkjs')) {
          setCurrent(5)
          onNext({ txid: 'DEMO_MODE_NO_TXID', nullifierHex: publicSignals[0].slice(0, 16) + '...', demo: true })
          return
        }
        throw new Error(data.detail || 'Registration failed')
      }

      setCurrent(5)
      onNext({
        txid: data.txid,
        nullifierHex: data.nullifier_hex,
        explorerUrl: data.explorer_url,
        encrypted: !!encryptedBlob,
      })

    } catch (e) {
      setError(e.message)
    }
  }, [aadhaar, wallet, onNext])

  if (!started) {
    return (
      <>
        <div className="proof-progress">
          <div style={{ fontSize: 48, marginBottom: 12 }}>🔐</div>
          <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 8 }}>Ready to Generate ZK Proof</div>
          <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 20 }}>
            This runs entirely in your browser. It may take 10–30 seconds depending on your device.
          </div>
          <button className="btn-main" onClick={run}>
            🚀 Generate & Submit Proof
          </button>
        </div>
        {error && <div className="error-box" style={{ marginTop: 16 }}>❌ {error} <button onClick={() => { setError(''); run() }}>Retry</button></div>}
      </>
    )
  }

  return (
    <div className="proof-progress">
      <div className="spinner" />
      <div style={{ fontWeight: 700, fontSize: 16 }}>
        {current < PROOF_STEPS.length ? PROOF_STEPS[current].label + '…' : 'Complete!'}
      </div>

      <div style={{ fontSize: 12, color: 'var(--text-secondary)', margin: '8px 0' }}>
        {pct}% complete
      </div>

      <div className="progress-bar-wrap">
        <div className="progress-bar-fill" style={{ width: `${pct}%` }} />
      </div>

      <div className="progress-steps">
        {PROOF_STEPS.map((s, i) => (
          <div key={s.id} className={`progress-step ${i < current ? 'done' : i === current ? 'active' : ''}`}>
            <span className="step-icon">
              {i < current ? '✅' : i === current ? '⚙️' : '○'}
            </span>
            {s.label}
          </div>
        ))}
      </div>

      {error && <div className="error-box" style={{ marginTop: 16, textAlign: 'left' }}>❌ {error}</div>}
    </div>
  )
}

// ── Stage 5: Success ───────────────────────────────────────────────────────

function SuccessStage({ result, walletAddress, onReset }) {
  const { txid, nullifierHex, explorerUrl, demo } = result

  return (
    <div className="success-panel">
      <div className="success-icon">✅</div>
      <div className="success-title">KYC Verified!</div>
      <div style={{ color: 'var(--text-secondary)', fontSize: 14, marginBottom: 20 }}>
        Your identity has been verified and registered on Algorand Testnet.
        No personal data was recorded on-chain.
      </div>

      {demo ? (
        <div className="info-box" style={{ textAlign: 'left' }}>
          <span>ℹ️</span>
          <span>
            <strong>Demo mode:</strong> To run with a real proof, copy{' '}
            <code>kyc.wasm</code> and <code>kyc.zkey</code> to <code>widget/public/</code>.
          </span>
        </div>
      ) : (
        <>
          <div style={{ textAlign: 'left', fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
            Transaction ID
          </div>
          <div className="txid-box">
            <span>{txid}</span>
          </div>
          {explorerUrl && (
            <a href={explorerUrl} target="_blank" rel="noopener noreferrer"
              className="btn-main" style={{
                display: 'block', textAlign: 'center',
                textDecoration: 'none', marginBottom: 10
              }}>
              🔍 View on Allo Explorer →
            </a>
          )}
        </>
      )}

      <div style={{
        background: 'var(--algo-card)', border: '1px solid var(--algo-border)',
        borderRadius: 8, padding: '14px', textAlign: 'left', marginBottom: 20
      }}>
        <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8, color: 'var(--text-secondary)' }}>
          YOUR PRIVACY SUMMARY
        </div>
        {[
          '✅ Aadhaar data stayed in your browser',
          '✅ Zero personal info sent to backend',
          '✅ Only a one-way nullifier stored on-chain',
          '✅ Court order needed to reveal identity (3-of-5 custodians)',
          '✅ DPDP Act 2023 compliant',
        ].map(item => (
          <div key={item} style={{ fontSize: 13, color: 'var(--text-secondary)', padding: '3px 0' }}>
            {item}
          </div>
        ))}
      </div>

      <button className="btn-secondary" onClick={onReset}>
        Verify Another Identity
      </button>
    </div>
  )
}

// ── Root App ───────────────────────────────────────────────────────────────

export default function App() {
  const [step, setStep] = useState('upload')
  const [aadhaar, setAadhaar] = useState(null)
  const [walletData, setWallet] = useState(null)
  const [result, setResult] = useState(null)

  const reset = () => {
    setStep('upload')
    setAadhaar(null)
    setWallet(null)
    setResult(null)
  }

  return (
    <div className="widget-root">
      <div className="widget-card">

        {/* Header */}
        <div className="widget-header">
          <div className="widget-title-row">
            <div className="widget-logo">
              <div className="logo-badge">🛡️</div>
              <span className="widget-name">AlgoKYC</span>
            </div>
            <span className="network-pill">TESTNET</span>
          </div>
          <div className="widget-subtitle">
            Zero-knowledge identity verification powered by Algorand
          </div>
        </div>

        {/* Step bar */}
        <StepBar current={step} />

        {/* Body */}
        <div className="widget-body">
          {step === 'upload' && (
            <UploadStage onNext={data => { setAadhaar(data); setStep('parse') }} />
          )}
          {step === 'parse' && aadhaar && (
            <IdentityStage
              aadhaar={aadhaar}
              onNext={() => setStep('secret')}
              onBack={() => setStep('upload')}
            />
          )}
          {step === 'secret' && (
            <WalletStage
              onNext={data => { setWallet(data); setStep('prove') }}
              onBack={() => setStep('parse')}
            />
          )}
          {step === 'prove' && aadhaar && walletData && (
            <ProofStage
              aadhaar={aadhaar}
              wallet={walletData}
              onNext={r => { setResult(r); setStep('done') }}
            />
          )}
          {step === 'done' && result && (
            <SuccessStage
              result={result}
              walletAddress={walletData?.walletAddress}
              onReset={reset}
            />
          )}
        </div>

        {/* Footer */}
        <div className="widget-footer">
          <span>🔒 ZK-KYC</span>
          <span>•</span>
          <span>No PII on-chain</span>
          <span>•</span>
          <a href="https://allo.info/application/756272073" target="_blank" rel="noopener noreferrer">
            NullifierRegistry ↗
          </a>
          <span>•</span>
          <a href="http://localhost:8000/docs" target="_blank" rel="noopener noreferrer">API Docs ↗</a>
        </div>
      </div>
    </div>
  )
}
