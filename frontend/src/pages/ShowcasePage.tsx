import React from 'react'

export const ShowcasePage: React.FC = () => {
  return (
    <div style={{ width: '100vw', height: '100vh', background: '#060e1a', overflow: 'hidden' }}>
      <div
        style={{
          position: 'fixed',
          top: 12,
          right: 16,
          zIndex: 10,
          display: 'flex',
          gap: 10
        }}
      >
        <button
          type="button"
          onClick={() => {
            window.location.href = '/'
          }}
          style={{
            border: '1px solid rgba(0, 212, 255, 0.32)',
            borderRadius: 999,
            padding: '8px 16px',
            background: 'rgba(6, 14, 26, 0.78)',
            color: '#dff8ff',
            cursor: 'pointer'
          }}
        >
          返回主系统
        </button>
      </div>
      <iframe
        title="Flood Twin Showcase"
        src="/showcase.html"
        style={{ width: '100%', height: '100%', border: 0 }}
      />
    </div>
  )
}
