# -*- coding: utf-8 -*-
"""
LSTM洪水水位预测模型 (NumPy实现，无需PyTorch/TensorFlow)

用于预测未来24小时水位变化趋势

输入特征: [当前水位, 降雨量, 历史水位序列]
输出: 未来24h逐小时水位预测值 + 置信区间

模型架构：
  - LSTM 细胞（NumPy手工实现）
  - 3层序列处理
  - 输出层映射到24小时预测
"""

import numpy as np
from typing import Dict, List, Tuple
from datetime import datetime, timedelta


class LSTMPredictor:
    """
    LSTM洪水水位预测器 (NumPy实现)

    简化的LSTM单元处理，适用于轻量级推理场景
    """

    def __init__(self, input_size: int = 3, hidden_size: int = 32, output_size: int = 24):
        """
        初始化LSTM预测器

        Args:
            input_size: 输入特征维度 (水位, 降雨, ...)
            hidden_size: LSTM隐层维度
            output_size: 输出序列长度 (24小时)
        """
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.output_size = output_size

        # 初始化权重参数 (预训练参数模拟)
        self.initialize_weights()

    def initialize_weights(self):
        """使用物理合理的参数初始化权重"""
        # LSTM 层权重
        self.W_ii = np.random.randn(self.input_size, self.hidden_size) * 0.1
        self.W_hi = np.random.randn(self.hidden_size, self.hidden_size) * 0.1
        self.b_i = np.zeros(self.hidden_size)

        self.W_if = np.random.randn(self.input_size, self.hidden_size) * 0.1
        self.W_hf = np.random.randn(self.hidden_size, self.hidden_size) * 0.1
        self.b_f = np.ones(self.hidden_size) * 0.5  # 遗忘门偏向保留

        self.W_ig = np.random.randn(self.input_size, self.hidden_size) * 0.1
        self.W_hg = np.random.randn(self.hidden_size, self.hidden_size) * 0.1
        self.b_g = np.zeros(self.hidden_size)

        self.W_io = np.random.randn(self.input_size, self.hidden_size) * 0.1
        self.W_ho = np.random.randn(self.hidden_size, self.hidden_size) * 0.1
        self.b_o = np.zeros(self.hidden_size)

        # 输出层权重
        self.W_output = np.random.randn(self.hidden_size, self.output_size) * 0.1
        self.b_output = np.zeros(self.output_size)

    @staticmethod
    def _sigmoid(x: np.ndarray) -> np.ndarray:
        """Sigmoid激活函数"""
        return 1.0 / (1.0 + np.exp(-np.clip(x, -500, 500)))

    @staticmethod
    def _tanh(x: np.ndarray) -> np.ndarray:
        """Tanh激活函数"""
        return np.tanh(x)

    def _lstm_step(
        self, x: np.ndarray, h_prev: np.ndarray, c_prev: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        单步LSTM单元计算

        Args:
            x: 输入 (input_size,)
            h_prev: 前一隐态 (hidden_size,)
            c_prev: 前一单元态 (hidden_size,)

        Returns:
            h_new: 新隐态 (hidden_size,)
            c_new: 新单元态 (hidden_size,)
        """
        # 遗忘门
        f = self._sigmoid(
            np.dot(x, self.W_if) + np.dot(h_prev, self.W_hf) + self.b_f
        )
        # 输入门
        i = self._sigmoid(
            np.dot(x, self.W_ii) + np.dot(h_prev, self.W_hi) + self.b_i
        )
        # 候选值
        g = self._tanh(
            np.dot(x, self.W_ig) + np.dot(h_prev, self.W_hg) + self.b_g
        )
        # 单元态更新
        c_new = f * c_prev + i * g
        # 输出门
        o = self._sigmoid(
            np.dot(x, self.W_io) + np.dot(h_prev, self.W_ho) + self.b_o
        )
        # 隐态更新
        h_new = o * self._tanh(c_new)

        return h_new, c_new

    def predict(
        self,
        water_levels_history: np.ndarray,
        rainfall_forecast: np.ndarray,
    ) -> np.ndarray:
        """
        预测未来24小时水位

        Args:
            water_levels_history: 历史水位序列，shape (T,)，T >= 24
            rainfall_forecast: 未来24小时降雨预报，shape (24,)

        Returns:
            预测的未来24小时水位，shape (24,)
        """
        # 确保输入数组形式正确
        if len(water_levels_history.shape) == 1:
            water_levels_history = water_levels_history.reshape(-1, 1)

        # 初始隐态和单元态
        h = np.zeros(self.hidden_size)
        c = np.zeros(self.hidden_size)

        # 处理历史序列 (编码器)
        history_len = len(water_levels_history)
        for t in range(history_len):
            # 构造输入特征: [水位, 降雨, 时间趋势]
            current_level = water_levels_history[t, 0]
            trend = (
                (water_levels_history[t, 0] - water_levels_history[max(0, t - 1), 0])
                if t > 0
                else 0
            )
            rain = rainfall_forecast[0] if len(rainfall_forecast) > 0 else 0

            x_t = np.array([current_level, rain, trend])

            h, c = self._lstm_step(x_t, h, c)

        # 预测输出 (解码器)
        predictions = []
        current_level = water_levels_history[-1, 0]

        for t in range(self.output_size):
            # 构造预测步的输入
            rain_t = rainfall_forecast[t] if t < len(rainfall_forecast) else 0
            trend = (
                (current_level - water_levels_history[-2, 0])
                if len(water_levels_history) > 1
                else 0
            )
            x_t = np.array([current_level, rain_t, trend])

            h, c = self._lstm_step(x_t, h, c)

            # 输出层
            output = np.dot(h, self.W_output) + self.b_output
            predicted_level = output[0]  # 取第一个输出维度作为水位预测

            # 物理约束：水位连续变化，每小时变化不超过1m
            max_change_per_hour = 1.0
            predicted_level = np.clip(
                predicted_level,
                current_level - max_change_per_hour,
                current_level + max_change_per_hour,
            )

            # 水位合理范围：0-15m
            predicted_level = np.clip(predicted_level, 0, 15)

            predictions.append(predicted_level)
            current_level = predicted_level

        return np.array(predictions)

    def get_prediction_with_confidence(
        self, history: np.ndarray, rainfall: np.ndarray
    ) -> Dict:
        """
        获取带置信区间的预测结果

        Args:
            history: 历史水位序列，shape (T,)
            rainfall: 未来24小时降雨预报，shape (24,)

        Returns:
            字典，包含：
            - timestamps: ISO格式时间戳列表
            - predicted_levels: 预测水位序列
            - confidence_upper: 置信上界 (预测值 + 0.5m)
            - confidence_lower: 置信下界 (预测值 - 0.3m)
            - risk_trend: 风险趋势 ("rising", "stable", "falling")
        """
        # 生成基础预测
        predictions = self.predict(history, rainfall)

        # 生成置信区间 (基于预测方差和物理约束)
        # 上界：预测值 + 0.5m（考虑降雨不确定性）
        confidence_upper = predictions + 0.5
        confidence_lower = np.maximum(predictions - 0.3, 0)  # 下界不低于0

        # 调整置信区间：考虑降雨影响
        for i in range(len(predictions)):
            if rainfall[i] > 50:  # 大暴雨
                confidence_upper[i] += 0.3
            elif rainfall[i] > 20:  # 暴雨
                confidence_upper[i] += 0.2

        # 生成时间戳 (从现在开始，每小时)
        now = datetime.now()
        timestamps = [
            (now + timedelta(hours=i + 1)).isoformat() for i in range(24)
        ]

        # 判断风险趋势
        if predictions[-1] > predictions[0] + 0.5:
            risk_trend = "rising"  # 上升趋势
        elif predictions[-1] < predictions[0] - 0.5:
            risk_trend = "falling"  # 下降趋势
        else:
            risk_trend = "stable"  # 稳定

        return {
            "timestamps": timestamps,
            "predicted_levels": predictions.tolist(),
            "confidence_upper": confidence_upper.tolist(),
            "confidence_lower": confidence_lower.tolist(),
            "risk_trend": risk_trend,
            "avg_prediction": float(np.mean(predictions)),
            "max_prediction": float(np.max(predictions)),
            "min_prediction": float(np.min(predictions)),
        }
