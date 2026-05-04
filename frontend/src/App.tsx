import React from 'react'
import { ConfigProvider } from 'antd'
import { CaseDataPage } from './pages/CaseDataPage'
import { MainPage } from './pages/MainPage'
import './App.css'

/**
 * 根组件 - 应用入口
 * 配置全局深色主题和样式
 */
const App: React.FC = () => {
  const isCaseDataPage = window.location.pathname === '/case-data' || new URLSearchParams(window.location.search).get('page') === 'case-data'

  return (
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: '#00d4ff',
          colorSuccess: '#00ff88',
          colorWarning: '#ffa500',
          colorError: '#ff4d4d',
          colorInfo: '#00d4ff',
          colorTextBase: '#e0e0e0',
          colorBgBase: '#0a1628',
          borderRadius: 8,
          fontFamily: "'Microsoft YaHei', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
        },
        components: {
          Button: {
            primaryColor: '#0a1628'
          },
          Slider: {
            trackBg: 'rgba(0, 212, 255, 0.2)',
            trackHoverBg: 'rgba(0, 212, 255, 0.3)'
          },
          Tabs: {
            colorBgContainer: 'transparent'
          }
        }
      }}
    >
      {isCaseDataPage ? <CaseDataPage /> : <MainPage />}
    </ConfigProvider>
  )
}

export default App
