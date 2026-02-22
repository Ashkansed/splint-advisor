import { useState } from 'react'
import { Link } from 'react-router-dom'
import './App.css'

export default function ScanPage() {
  const [files, setFiles] = useState([])
  const [processing, setProcessing] = useState(false)
  const [message, setMessage] = useState(null)

  function handleFileChange(e) {
    const chosen = Array.from(e.target.files || [])
    setFiles(prev => [...prev, ...chosen])
    setMessage(null)
  }

  function removeFile(index) {
    setFiles(prev => prev.filter((_, i) => i !== index))
  }

  function handleSubmit(e) {
    e.preventDefault()
    if (files.length === 0) {
      setMessage({ type: 'error', text: 'Please add at least one hand image.' })
      return
    }
    setProcessing(true)
    setMessage(null)
    // Simulate processing; replace with real upload/reconstruction API when ready
    setTimeout(() => {
      setProcessing(false)
      setMessage({
        type: 'success',
        text: `Received ${files.length} image(s). Accurate 3D reconstruction will be processed — you'll be notified when your model is ready.`,
      })
    }, 1500)
  }

  return (
    <div className="app">
      <header className="header">
        <Link to="/" className="logo-link" aria-label="Dimension Ortho home">
          <img src="/logo.png" alt="Dimension Ortho" className="logo" />
        </Link>
        <h1>3D hand scan</h1>
        <p className="tagline">Upload simple hand images for accurate 3D reconstruction</p>
      </header>

      <main className="main scan-page">
        <div className="card scan-card">
          <p className="scan-intro">
            Upload clear photos of your hand from multiple angles. We use them to build an accurate 3D model for your splint design.
          </p>

          <form onSubmit={handleSubmit} className="scan-form">
            <label className="scan-drop">
              <input
                type="file"
                accept="image/*"
                multiple
                onChange={handleFileChange}
                className="scan-input"
                disabled={processing}
              />
              <span className="scan-drop-text">
                {files.length === 0
                  ? 'Click or drag hand images here'
                  : `${files.length} image(s) selected`}
              </span>
            </label>

            {files.length > 0 && (
              <ul className="scan-file-list">
                {files.map((f, i) => (
                  <li key={i}>
                    <span>{f.name}</span>
                    <button
                      type="button"
                      className="scan-remove"
                      onClick={() => removeFile(i)}
                      disabled={processing}
                      aria-label="Remove"
                    >
                      ×
                    </button>
                  </li>
                ))}
              </ul>
            )}

            {message && (
              <div className={`scan-message ${message.type}`}>
                {message.text}
              </div>
            )}

            <button type="submit" className="btn" disabled={processing || files.length === 0}>
              {processing ? 'Processing…' : 'Start 3D reconstruction'}
            </button>
          </form>
        </div>

        <p className="scan-back">
          <Link to="/">← Back to Splint Advisor</Link>
        </p>
      </main>
    </div>
  )
}
