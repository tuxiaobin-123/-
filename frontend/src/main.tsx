import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

// ==================== 错误边界：防止组件崩溃导致白屏 ====================
class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('React ErrorBoundary caught:', error, info)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          width: '100vw', height: '100vh',
          background: '#0a1628', color: '#e0e0e0',
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          fontFamily: 'Microsoft YaHei, sans-serif', padding: 40
        }}>
          <div style={{ fontSize: 48, marginBottom: 24 }}>⚠️</div>
          <h2 style={{ color: '#ff4d4d', marginBottom: 16 }}>系统初始化异常</h2>
          <p style={{ color: '#aaa', marginBottom: 24, textAlign: 'center' }}>
            {this.state.error?.message || '未知错误'}
          </p>
          <button
            style={{
              background: '#00d4ff', color: '#0a1628', border: 'none',
              borderRadius: 8, padding: '10px 28px', cursor: 'pointer', fontSize: 16
            }}
            onClick={() => window.location.reload()}
          >
            刷新重试
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <ErrorBoundary>
    <App />
  </ErrorBoundary>
)
