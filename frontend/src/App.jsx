import { useState } from 'react'
import './App.css'

// When deployed, set VITE_API_URL to your backend URL (e.g. https://your-app.onrender.com)
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function App() {
  const [problem, setProblem] = useState('')
  const [context, setContext] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    if (!problem.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await fetch(`${API_BASE}/diagnose`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          problem: problem.trim(),
          optional_context: context.trim() || null,
        }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        const detail = data.detail
        const msg = Array.isArray(detail) ? detail.map((d) => d.msg || d).join(', ') : (detail || res.statusText)
        throw new Error(msg || 'Request failed')
      }
      const data = await res.json()
      setResult(data)
    } catch (err) {
      const isNetwork = err.message === 'Failed to fetch' || err.name === 'TypeError'
      setError(isNetwork
        ? 'Could not reach the server. If this is the live site, check: (1) VITE_API_URL is set in Vercel to your Render backend URL, (2) CORS_ORIGINS on Render includes this site, (3) Render service is awake (first request may take 30–60 s).'
        : err.message || 'Something went wrong.')
    } finally {
      setLoading(false)
    }
  }

  async function openManufacturing() {
    try {
      const res = await fetch(`${API_BASE}/manufacturing-url`)
      const data = await res.json()
      if (data.url) window.open(data.url, '_blank', 'noopener,noreferrer')
    } catch {
      window.open('https://www.google.com/maps/search/3d+printing+service+near+me', '_blank')
    }
  }

  function handle3DScan() {
    // Open 3D scanning flow (e.g. external scanner app or in-app flow)
    window.open('https://www.google.com/search?q=3d+scanning+app+orthotics', '_blank', 'noopener,noreferrer')
  }

  function handleConfirmDesign() {
    if (result?.case_id) {
      // Confirm current design; could POST to backend or open next step
      alert(`Design confirmed for case ${result.case_id}. Ready for manufacturing.`)
    } else {
      alert('Get a splint recommendation first, then confirm the design.')
    }
  }

  return (
    <div className="app">
      <header className="header">
        <a href="/" className="logo-link" aria-label="Dimension Ortho home">
          <img src="/logo.png" alt="Dimension Ortho" className="logo" />
        </a>
        <h1>Splint Advisor</h1>
        <p className="tagline">Upper extremity problem → recommended splint (PA / urgent care context)</p>
      </header>

      <main className="main">
        <form onSubmit={handleSubmit} className="form">
          <label className="label">Describe the problem</label>
          <textarea
            value={problem}
            onChange={(e) => setProblem(e.target.value)}
            placeholder="e.g. wrist pain and numbness at night, possible carpal tunnel"
            rows={3}
            className="textarea"
            disabled={loading}
          />
          <label className="label optional">Optional context</label>
          <input
            type="text"
            value={context}
            onChange={(e) => setContext(e.target.value)}
            placeholder="e.g. post-surgery, acute injury, chronic"
            className="input"
            disabled={loading}
          />
          <button type="submit" className="btn" disabled={loading}>
            {loading ? 'Diagnosing…' : 'Get splint recommendation'}
          </button>
        </form>

        {error && (
          <div className="card error">
            <strong>Error</strong>: {error}
          </div>
        )}

        {result && (
          <div className="result">
            <div className="card diagnosis">
              <h2>Diagnosis</h2>
              <p>{result.diagnosis_summary}</p>
              {result.suggested_diagnosis && (
                <p className="suggested-dx"><strong>Suggested problem (PA/urgent care):</strong> {result.suggested_diagnosis}</p>
              )}
              {result.suggested_diagnosis_terms_from_nih?.length > 0 && (
                <p className="nih-terms"><strong>NIH literature terms:</strong> {result.suggested_diagnosis_terms_from_nih.join(', ')}</p>
              )}
              <span className={`badge confidence-${result.confidence}`}>
                Confidence: {result.confidence}
              </span>
            </div>

            {result.other_recommendations?.length > 0 && (
              <div className="card other-rec">
                <h2>Other recommendations (beyond splint)</h2>
                <ul>
                  {result.other_recommendations.map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="card splint">
              <h2>Recommended splint</h2>
              <h3 className="splint-name">{result.recommended_splint.splint_name}</h3>
              <p>{result.recommended_splint.rationale}</p>
              {result.recommended_splint.alternatives?.length > 0 && (
                <div className="alternatives">
                  <strong>Alternatives:</strong>
                  <ul>
                    {result.recommended_splint.alternatives.map((a, i) => (
                      <li key={i}>{a}</li>
                    ))}
                  </ul>
                </div>
              )}
              {result.additional_splints_from_nih?.length > 0 && (
                <div className="nih-splints">
                  <strong>Additional splints suggested by NIH/PubMed:</strong>
                  <ul>
                    {result.additional_splints_from_nih.map((s, i) => (
                      <li key={i}>{s}</li>
                    ))}
                  </ul>
                </div>
              )}
              {result.recommended_splint.precautions && (
                <p className="precautions">{result.recommended_splint.precautions}</p>
              )}
            </div>

            {result.nih_articles?.length > 0 && (
              <div className="card nih-card">
                <h2>NIH / PubMed references</h2>
                <ul className="nih-list">
                  {result.nih_articles.map((a) => (
                    <li key={a.pmid}>
                      <a href={a.url} target="_blank" rel="noopener noreferrer">{a.title || a.pmid}</a>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="result-actions">
              <button type="button" className="btn btn-secondary" onClick={handle3DScan}>
                3D scanning
              </button>
              <button type="button" className="btn btn-secondary" onClick={handleConfirmDesign}>
                Confirm design
              </button>
              <button type="button" className="btn btn-secondary" onClick={openManufacturing}>
                Submit to manufacturing — locate printer (by IP)
              </button>
            </div>

            <p className="disclaimer">{result.disclaimer}</p>
            <p className="case-id">Case ID: <code>{result.case_id}</code> (saved for physician &amp; urgent care fine-tuning)</p>
          </div>
        )}
      </main>

      <footer className="footer">
        <p>Each submission is logged as JSON for physician and urgent care fine-tuning. NIH/PubMed search informs additional splints. Export from backend <code>data/</code>.</p>
      </footer>
    </div>
  )
}
