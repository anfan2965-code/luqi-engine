# Phase 3: 随机性控制算法

## 概述

鹿栖引擎的随机性控制系统由三层组成：

```
PCGRandom（基础随机数）
    ↓
SeededRNGManager（多流管理）
    ↓
NarrativeSeedHierarchy（五级种子派生）
    ↓
DistributionToolkit（概率分布采样）
    ↓
LorenzAttractor（混沌动力学）
    ↓
EmotionalFluctuation（混沌情感耦合）
```

**设计原则**：所有随机性必须是**确定性的**——同一颗种子永远产生相同的序列。这对可复现性、测试、调试至关重要。

## 一、PCG-XSH-RR 随机数生成器

### 1.1 为什么不用 Python random？

Python 内置的 `random` 模块基于 Mersenne Twister，存在以下问题：
- 状态空间大（2.5KB），不利于快照恢复
- 不是密码学安全的（虽然我们不要求密码安全）
- 流管理不够灵活

PCG（Permuted Congruential Generator）是现代高质量 PRNG，具有：
- 极小的状态空间（128位 = 16字节）
- 优秀的统计特性（通过 BigCrush 测试套件）
- 天然支持独立流（通过不同的 increment 参数）
- 快速生成速度

### 1.2 参数

| 参数 | 值 | 说明 |
|------|-----|------|
| MULTIPLIER | 6364136223846793005 | 64位LCG乘数 |
| INCREMENT | 1442695040888963407 | 流标识符（奇数保证最长周期） |
| XORSHIFT_SHIFT | 18 | 异或移位位数 |
| OUTPUT_SHIFT | 27 | 输出移位位数 |
| ROTATION_SHIFT | 59 | 旋转位数（用于高位混合） |
| 周期 | 2^128 | 64位状态空间的满周期 |

### 1.3 核心算法

```
next_uint32():
    old_state = state
    state = (old_state × MULTIPLIER + INCREMENT) mod 2^64      // LCG 步骤
    xorshifted = ((old_state >> 18) ^ old_state) >> 27          // XSH 变换
    xorshifted &= 0xFFFFFFFF                                     // 截断到32位
    rot = old_state >> 59                                        // RR 旋转量
    return rotr32(xorshifted, rot & 31)                          // 旋转输出
```

**rotr32**（32位循环右移）：将值的低位旋转到高位，打破 LCG 的低位相关性问题。

### 1.4 uniform() — 均匀分布

使用双 32 位组合成 53 位精度浮点数：

```
uniform(low, high):
    upper = next_uint32() >> 11     // 取高21位
    lower = next_uint32() >> 21     // 取高11位
    combined = (upper << 32) | lower // 组合为53位
    result = combined / 2^53         // [0, 1) 均匀分布
    return low + result * (high - low)
```

53 位精度覆盖了 IEEE 754 双精度浮点数的全部有效尾数位，确保均匀分布没有间隙。

### 1.5 gaussian() — 正态分布（Marsaglia 极坐标法）

```
gaussian(mean, stddev):
    if has_spare:
        has_spare = False
        return mean + stddev * gaussian_spare
    repeat:
        x1 = uniform(-1, 1)
        x2 = uniform(-1, 1)
        w = x1² + x2²
    until (0 < w < 1)
    w = -2 × ln(w) / w
    sqrt_w = √w
    gaussian_spare = x2 × sqrt_w    // 缓存第二个值
    has_spare = True
    return mean + stddev × x1 × sqrt_w
```

**为什么用 Marsaglia 极坐标法而非 Box-Muller？**
- 极坐标法避免了三角函数调用（sin/cos），更快
- 拒绝采样区域更大（w > 0 即可接受 vs w ≤ 1），效率更高
- 数值稳定性更好（避免了 w 接近 0 时的除零风险）

### 1.6 weighted_choice() — 加权随机选择

```
weighted_choice(weights):
    total = sum(weights)
    threshold = uniform(0, total)
    cumulative = 0
    for idx, w in enumerate(weights):
        cumulative += w
        if cumulative >= threshold:
            return idx
    return len(weights) - 1    // 浮点误差兜底
```

返回**索引**而非元素本身，让调用方自行决定如何使用。

## 二、SeededRNGManager — 多流隔离

### 2.1 问题

如果全局只用一个 RNG，不同子系统（角色A的情感波动、角色B的行动选择、天气系统的事件生成）会互相干扰——改变角色A的逻辑可能意外影响天气系统的输出。

### 2.2 解决方案

为每个子系统分配独立的随机流，流之间完全隔离：

```python
manager = SeededRNGManager(master_seed=42)
char_rng = manager.get_stream("character")     // 流ID "character"
weather_rng = manager.get_stream("weather")    // 流ID "weather"
// char_rng 和 weather_rng 产生完全独立的序列
```

**流创建规则**：`stream_index = len(existing_streams) + 1`，每个新流的 increment = `(stream_index << 1) | 1`（保证奇数）。同一 stream_id 只创建一次，后续调用返回已有实例。

## 三、NarrativeSeedHierarchy — 五级种子层级

### 3.1 层级结构

```
root_seed (主种子)
    ├── world:world_name        (世界级)
    │   └── faction:faction_name  (阵营级)
    │       └── character:name    (角色级)
    │           └── scene:name     (场景级)
    │               └── event:name  (事件级)
```

### 3.2 种子派生算法

```
derive_seed(path_components):
    path = ":".join(path_components)           // 如 "world:艾泽拉斯:联盟:小雪"
    seed_str = root_seed + ":" + path         // 如 "42:world:艾泽拉斯:联盟:小雪"
    digest = SHA256(seed_str).hexdigest()     // 256位哈希
    derived = int(digest[:16], 16)            // 取前16字符 = 64位整数
    return derived
```

**SHA-256 的作用**：提供雪崩效应——种子路径的微小变化会导致完全不同的派生种子。同时保证**确定性**——相同路径永远产生相同种子。

### 3.3 缓存

已计算的种子会被缓存（Dict），避免重复 SHA-256 计算。可通过 `clear_cache()` 清除。

### 3.4 便捷方法

```python
hierarchy = NarrativeSeedHierarchy(root_seed=42)
hierarchy.derive_world_seed("艾泽拉斯")        // 世界种子
hierarchy.derive_faction_seed("艾泽拉斯", "联盟")  // 阵营种子
hierarchy.derive_character_seed("艾泽拉斯", "小雪") // 角色种子
hierarchy.derive_scene_seed("艾泽拉斯", "教室")    // 场景种子
hierarchy.derive_event_seed("艾泽拉斯", "遭遇战")  // 事件种子

rng = hierarchy.create_rng("world", "艾泽拉斯")    // 直接创建该层级的RNG
```

## 四、DistributionToolkit — 概率分布工具包

### 4.1 设计原则

- **零外部依赖**：不依赖 numpy/scipy
- **确定性**：所有分布基于 PCGRandom
- **自包含**：内置 Gamma 函数（Lanczos 近似）

### 4.2 支持的分布

| 分布 | 函数 | 用途 | 参数 |
|------|------|------|------|
| 正态分布 | `normal(mean, stddev)` | 自然现象建模 | μ=0, σ=1 |
| 指数分布 | `exponential(lambda)` | 等待时间建模 | λ=1 |
| 帕累托分布 | `pareto(alpha, xm)` | 幂律分布（长尾） | α=1, xm=1 |
| Beta 分布 | `beta(a, b)` | 概率/比例建模 | α=1, β=1 |
| 三角形分布 | `triangular(low, high, mode)` | 有偏好的范围 | [0,1], mode=0.5 |

### 4.3 Gamma 函数（Lanczos 近似）

用于 Beta 分布采样的内部实现：

```
gamma_func(x):
    if x <= 0: return 0
    if x < 0.5: return π / (sin(πx) × gamma(1-x))   // 反射公式
    // Lanczos 系数近似（7项，精度 ~15 位有效数字）
    a = 0.99999999999980993 + Σ(c[i]/(x+i))
    t = x + 6.5
    return √(2π) × t^(x+0.5) × e^(-t) × a
```

### 4.4 Marsaglia-Tsang Gamma 采样

Beta 分布内部使用的 Gamma 采样算法：

```
sample_gamma(shape, scale):
    if shape < 1:
        return sample_gamma(shape+1) × U^(1/shape)   // 缩放技巧
    d = shape - 1/3
    c = 1/√(9d)
    repeat:
        x ~ N(0,1); v = 1 + c×x;                    // 正态采样
        until v > 0                                   // 拒绝 v≤0
        v³; u ~ U(0,1)
        if u < 1 - 0.0331 × x⁴: return d×v³×scale   // 快速接受
        if ln(u) < 0.5×x² + d×(1-v+ln(v)): return d×v³×scale  // 对数检验
```

## 五、LorenzAttractor — Lorenz 混沌吸引子

### 5.1 为什么用混沌？

人类情感的本质特征是**确定性中的不可预测性**：
- 同样的刺激在不同时刻可能引发不同反应
- 但整体情感轨迹是有结构的（不是纯噪声）
- 对初始条件极度敏感（蝴蝶效应）

Lorenz 吸引子恰好具备这些特性：短期可预测、长期混沌、有界振荡。

### 5.2 Lorenz 方程组

```
dx/dt = σ(y - x)        // σ = 10（Prandtl数）
dy/dt = x(ρ - z) - y    // ρ = 28（Rayleigh数）
dz/dt = xy - βz          // β = 8/3（几何因子）
```

经典参数 (σ=10, ρ=28, β=8/3) 产生混沌行为。

### 5.3 RK4 积分

使用四阶 Runge-Kutta 方法求解微分方程，步长 dt=0.01：

```
rk4_step(state, dt):
    k1 = f(state)
    k2 = f(state + 0.5×dt×k1)
    k3 = f(state + 0.5×dt×k2)
    k4 = f(state + dt×k3)
    new_state = state + (dt/6)×(k1 + 2k2 + 2k3 + k4)
```

RK4 具有 O(dt^4) 阶局部截断误差，对于 dt=0.01 足够精确。

### 5.4 归一化

Lorenz 系统的原生输出范围很大（x∈[-20,20], y∈[-30,30], z∈[0,50]），需要归一化到 [0,1]：

```
normalize_x = (x - (-20)) / 40    // → [0, 1]
normalize_y = (y - (-30)) / 60    // → [0, 1]
normalize_z = (z - 0) / 50        // → [0, 1]
```

### 5.5 扰动

`perturb(rng, magnitude=0.001)` 通过高斯扰动初始状态，可以产生全新的轨迹分支（蝴蝶效应）。

## 六、EmotionalFluctuation — 混沌情感耦合

### 6.1 工作原理

将 Lorenz 混沌输出耦合到 PAD 情感空间：

```
update(current_pad):
    chaotic = attractor.step_normalized()           // 混沌输出 [0,1]^3
    accumulated = decay × accumulated + coupling × chaotic  // 累积衰减
    result = clamp(current_pad + accumulated)       // 叠加到当前情感
    return result
```

**参数**：
- `coupling`（耦合系数）：默认 0.1 — 控制混沌对情感的直接影响强度
- `decay`（衰减系数）：默认 0.95 — 累积项的自然衰减，防止混沌效应无限累积
- `intensity`（强度）：默认 0.5 — 总体振幅控制

### 6.2 效果

- 短期内情感有微小但**有结构的波动**（不是白噪声）
- 长期来看情感轨迹不可预测但有界
- 即使没有外部事件输入，角色的情感也不会静止不变——而是像真实人类一样有自然的"情绪潮汐"

## 七、设计权衡总结

| 组件 | 选择 | 原因 | 替代方案 |
|------|------|------|----------|
| PRNG | PCG-XSH-RR | 小状态(16B)、快、天然多流 | Mersenne Twister(2.5KB)、xoroshiro128++ |
| 正态采样 | Marsaglia极坐标法 | 无三角函数、快 | Box-Muller(需sin/cos)、Ziggurat(查表) |
| 种子派生 | SHA-256哈希 | 雪崩效应+确定性 | 简单线性组合(碰撞风险) |
| 混沌系统 | Lorenz吸引子 | 经典混沌、参数少、有界 | Rössler(更简单)、Chua(电路实现) |
| 数值积分 | RK4 | O(h^4)精度足够 | Euler(太粗糙)、自适应步长(过度) |
