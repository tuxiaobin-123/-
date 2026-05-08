import React, { useState } from 'react'
import './PINNPage.css'

interface FormulaCard {
  id: string
  title: string
  latex: string
  description: string
  color: string
}

const FORMULAS: FormulaCard[] = [
  {
    id: 'swe',
    title: '浅水方程（SWE）— 物理约束核心',
    latex: '∂h/∂t + ∂(hu)/∂x + ∂(hv)/∂y = r',
    description: '水深 h 随时间演变的守恒方程，r 为降雨源项。PINN 将此方程嵌入损失函数，使神经网络输出必须满足质量守恒。',
    color: '#00d4ff',
  },
  {
    id: 'momentum',
    title: '动量方程 — 流速物理约束',
    latex: '∂(hu)/∂t + ∂(hu²+gh²/2)/∂x = -ghS_f',
    description: 'S_f 为摩阻坡度（Manning 公式）。神经网络预测的流速场必须满足此方程，防止物理上不可能的预测结果出现。',
    color: '#7c3aed',
  },
  {
    id: 'pinn_loss',
    title: 'PINN 复合损失函数',
    latex: 'L = λ₁·L_data + λ₂·L_pde + λ₃·L_bc',
    description: 'L_data：与观测数据的均方误差；L_pde：SWE 方程残差；L_bc：边界条件约束。三项加权平衡使模型既拟合数据又遵守物理规律。',
    color: '#059669',
  },
  {
    id: 'advantage',
    title: '对比纯 LSTM 的优势',
    latex: 'RMSE_PINN < RMSE_LSTM（数据稀疏时）',
    description: '在传感器数据缺失或历史记录不足时，物理约束替代数据补充信息，使预测结果仍保持物理合理性，不会出现"负水深"等荒谬预测。',
    color: '#d97706',
  },
]

const PIPELINE_STEPS = [
  {
    step: 1,
    title: '多源数据融合',
    icon: '📡',
    detail: '桑干河 4 个水文站（逐小时水位/流量）+ 和风天气降雨预报 + DEM 地形数据 → 统一时空格网',
  },
  {
    step: 2,
    title: '神经网络设计',
    icon: '🧠',
    detail: '全连接网络（输入：坐标 x,y,t + 降雨量）→ 输出水深 h(x,y,t) 和流速 u,v。激活函数：tanh（与 SWE 相容）',
  },
  {
    step: 3,
    title: '物理残差计算',
    icon: '⚙️',
    detail: '对网络输出自动微分（AD），计算 ∂h/∂t、∂(hu)/∂x 等偏导数，代入 SWE 方程计算残差 L_pde',
  },
  {
    step: 4,
    title: '复合损失反传',
    icon: '📉',
    detail: 'Adam 优化器最小化 L = L_data + λ·L_pde，物理约束权重 λ 从小到大退火，先拟合数据再强化物理',
  },
  {
    step: 5,
    title: '24 h 水位预测',
    icon: '🌊',
    detail: '训练后的 PINN 输出桑干河怀仁段未来 24 小时水位场，提供比纯 LSTM 更可靠的极端工况预测',
  },
]

const ComparisonTable: React.FC = () => (
  <div className="pinn-comparison">
    <h3 className="pinn-section-title">方法对比</h3>
    <table className="pinn-table">
      <thead>
        <tr>
          <th>维度</th>
          <th>纯 LSTM</th>
          <th>PINN（本项目方向）</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>物理一致性</td>
          <td className="cell-bad">不保证</td>
          <td className="cell-good">硬约束 SWE</td>
        </tr>
        <tr>
          <td>数据需求</td>
          <td className="cell-warn">大量标注数据</td>
          <td className="cell-good">可小样本泛化</td>
        </tr>
        <tr>
          <td>极端工况预测</td>
          <td className="cell-bad">外推不稳定</td>
          <td className="cell-good">物理约束保底</td>
        </tr>
        <tr>
          <td>可解释性</td>
          <td className="cell-bad">黑盒</td>
          <td className="cell-good">方程参数可追溯</td>
        </tr>
        <tr>
          <td>训练复杂度</td>
          <td className="cell-good">低</td>
          <td className="cell-warn">较高（自动微分）</td>
        </tr>
        <tr>
          <td>工程部署</td>
          <td className="cell-good">轻量易部署</td>
          <td className="cell-warn">需 PyTorch/JAX</td>
        </tr>
      </tbody>
    </table>
  </div>
)

export const PINNPage: React.FC = () => {
  const [activeFormula, setActiveFormula] = useState<string | null>(null)
  const [activeStep, setActiveStep] = useState<number | null>(null)

  return (
    <div className="pinn-page">
      <div className="pinn-header">
        <div className="pinn-badge">技术创新方向</div>
        <h1 className="pinn-title">Physics-Informed Neural Network</h1>
        <h2 className="pinn-subtitle">物理信息神经网络 — 下一代洪水预测架构</h2>
        <p className="pinn-intro">
          传统 LSTM 仅从历史数据中学习模式，在训练数据稀疏或极端工况下预测不稳定。
          PINN 将浅水方程（SWE）作为硬约束嵌入神经网络损失函数，使预测结果天然满足水动力学物理规律，
          实现"数据驱动 + 物理约束"的双重保障。
        </p>
      </div>

      <div className="pinn-section">
        <h3 className="pinn-section-title">核心数学框架</h3>
        <div className="formula-grid">
          {FORMULAS.map((f) => (
            <div
              key={f.id}
              className={`formula-card ${activeFormula === f.id ? 'is-active' : ''}`}
              style={{ '--accent': f.color } as React.CSSProperties}
              onClick={() => setActiveFormula(activeFormula === f.id ? null : f.id)}
            >
              <div className="formula-title">{f.title}</div>
              <div className="formula-latex">{f.latex}</div>
              {activeFormula === f.id && (
                <div className="formula-detail">{f.description}</div>
              )}
              <div className="formula-hint">点击展开说明</div>
            </div>
          ))}
        </div>
      </div>

      <div className="pinn-section">
        <h3 className="pinn-section-title">桑干河 PINN 实施流程</h3>
        <div className="pipeline">
          {PIPELINE_STEPS.map((s, idx) => (
            <React.Fragment key={s.step}>
              <div
                className={`pipeline-step ${activeStep === s.step ? 'is-active' : ''}`}
                onClick={() => setActiveStep(activeStep === s.step ? null : s.step)}
              >
                <div className="step-icon">{s.icon}</div>
                <div className="step-num">Step {s.step}</div>
                <div className="step-title">{s.title}</div>
                {activeStep === s.step && (
                  <div className="step-detail">{s.detail}</div>
                )}
              </div>
              {idx < PIPELINE_STEPS.length - 1 && (
                <div className="pipeline-arrow">→</div>
              )}
            </React.Fragment>
          ))}
        </div>
      </div>

      <ComparisonTable />

      <div className="pinn-section pinn-roadmap">
        <h3 className="pinn-section-title">实施路线图</h3>
        <div className="roadmap-items">
          <div className="roadmap-item done">
            <span className="roadmap-tag">已完成</span>
            NumPy LSTM 轻量化实现，无需深度学习框架
          </div>
          <div className="roadmap-item done">
            <span className="roadmap-tag">已完成</span>
            SWE 浅水方程有限体积法数值求解（hydraulic.py）
          </div>
          <div className="roadmap-item current">
            <span className="roadmap-tag current">进行中</span>
            桑干河历史水文数据 LSTM 训练（scripts/train_lstm_sanggan.py）
          </div>
          <div className="roadmap-item future">
            <span className="roadmap-tag future">规划中</span>
            PyTorch PINN 实现：SWE 残差作为物理损失项
          </div>
          <div className="roadmap-item future">
            <span className="roadmap-tag future">规划中</span>
            PINN 预测结果与 SWE 数值模拟双重验证
          </div>
        </div>
      </div>

      <div className="pinn-footer">
        <div className="pinn-ref">
          参考文献：Raissi et al., "Physics-Informed Neural Networks", JCP 2019 &nbsp;|&nbsp;
          Kabir et al., "PINN for Flood Inundation Mapping", Water 2023
        </div>
      </div>
    </div>
  )
}
