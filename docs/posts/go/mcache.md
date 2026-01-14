# Go 内存管理：mcache 核心机制与架构

## 1. 核心定位与设计哲学

在 Go 内存管理的三级架构中，`mcache` 是最接近用户代码的一层，扮演着**“线程本地缓存（Thread-Local Cache）”**的角色。

- **定位**：它是每个 P (Processor) 独有的本地内存资源池。
    
- **职责**：负责直接为 Goroutine 分配小对象（Tiny & Small objects），是内存分配的**第一站**。

**设计哲学**： `mcache` 的核心目标是**极致的分配速度**与**零锁竞争**。

- **无锁分配 (Lock-Free)**：由于 `mcache` 是 P 独占的，且同一时刻一个 P 只能运行一个 Goroutine，因此在 `mcache` 上的内存操作**完全不需要加锁** 。这使得 Go 在处理高并发小对象分配时，性能远超传统的 `malloc`。
    
- **空间局部性 (Data Locality)**：Goroutine 申请的数据直接分配在当前 P 绑定的 `mcache` 中，极大提高了 CPU 缓存（L1/L2）的命中率。

## 2. 核心数据结构解析

`mcache` 的结构体设计紧凑，主要由“微对象分配器”和“小对象分配器”两部分组成。

```go
type mcache struct {
    // 1. 微对象分配器 (Tiny Allocator) 字段
    // 用于 < 16B 且不含指针(noscan) 的极小对象分配
    tiny             uintptr // 指向当前 tiny block 的起始地址
    tinyoffset       uintptr // 当前 tiny block 已使用的偏移量
    local_tinyallocs uintptr // 统计信息：tiny 对象分配次数

    // 2. 小对象分配器 (Small Object Allocator) 字段
    // 核心：对应 68 种规格(spanClass) 的当前可用 mspan 数组
    // numSpanClasses = 136 (68 * 2，包含 scan 和 noscan)
    alloc [numSpanClasses]*mspan

    // 3. 采样与统计
    nextSample uintptr // 下一次触发堆分析(Heap Profile)的阈值
    // ... 其他字段
}
```

### 2.1 关键组件详解

1. **`alloc` 数组**： 这是 `mcache` 的主体。它是一个包含 136 个 `*mspan` 指针的数组。
    - **职责**：数组的每个槽位 `alloc[i]` 都持有一个特定规格（`spanClass`）的 `mspan`，作为当前该规格对象的“专供弹夹”。
        
    - **工作流**：当需要分配内存时，根据对象大小计算出 `class`，直接去 `alloc[class]` 拿空闲槽位。
2. **`tiny` 系列字段**： 这是 Go 对极小对象（如 `bool`, `int`, `byte`）的特殊优化。为了避免 1 字节变量也占用 8 字节（最小 class）的浪费，Go 将它们“拼凑”在一个 16 字节的内存块中。

---

###  2.2 mcache 内部架构图

![](../../assets/mcache.png)*图1：mcache内部架构*

---

## 3. 核心机制：极速分配的两条路径

`mcache` 的高效得益于针对不同大小对象的差异化处理策略。

### 3.1 Tiny 分配机制

**适用场景**：`size < 16B` && `noscan` (不含指针)。

这是一种**Bump Pointer（指针碰撞）** 风格的分配器。

- **流程**：
    
    1. 检查当前持有的 `tiny` 块剩余空间（`16B - tinyoffset`）是否足够？
        
    2. **足够**：通过简单的指针偏移（`offset + size`），直接返回地址。
        
    3. **不足**：
        
        - 从 `alloc` 数组中（通常是 Class 2, 8B 或 16B 的 span）申请一个新的 16B 内存块替换当前的 `tiny` 块。
            
        - 旧块中剩余的碎片（如果有）就被浪费了，但因为很小，成本可控。
            
- **收益**：极大地节省了内存空间（将多个小变量塞进一个块），并减少了对 `mspan` 的访问频率。

### 3.2 小对象分配机制

**适用场景**：`16B <= size <= 32KB` 或 `size < 16B` 但含指针。

这是最常见的分配路径，完全无锁。

- **Fast Path (本地命中)**：
    
    1. **计算规格**：根据 `size` 查表得到 `spanClass`。
        
    2. **定位 Span**：找到 `mcache.alloc[spanClass]` 指向的当前 `mspan`。
        
    3. **查找空位**：利用 `mspan.allocCache`（缓存的位图）快速找到下一个空闲槽位（`nextFree`）。*注：Go 使用 ctz (Count Trailing Zeros) 指令在 CPU 周期级完成位图查找。*
        
    4. **标记与返回**：更新位图，返回对象地址。
        
- **Slow Path (Refill)**： 当 `mcache.alloc[spanClass]` 里的 `mspan` 满了（`allocCache == 0`）：
    
    1. **归还**：将这个满的 span 归还给 `mcentral`（可能触发 `full -> partial` 的流转）。
        
    2. **进货**：调用 `mcache.refill()`，从 `mcentral` 申请一个新的非满 span 。
        
    3. **替换**：将新 span 挂载到 `alloc[spanClass]`，重试 Fast Path。

---

### 3.3 mcache申请内存流程图
![](../../assets/mcache-flow.png)
*图2：mcache申请内存流程*

**⚠️：** 当 Tiny 缓冲区剩余空间不足以容纳当前对象时，会触发‘缓冲区扩容’逻辑。该逻辑本质上是**复用 Small 分配路径**申请一个 **16B** 的内存块，将其**替换**为新的 Tiny 缓冲区，随后再基于该新缓冲区完成本次内存分配。

---

## 4. 关键交互：mcache 的上下游

虽然 `mcache` 是本地缓存，但它时刻保持着与外界的动态平衡。

### 4.1 与 mcentral 的交互

- **Refill（进货）**：当 `mcache` 缺货时，它是**消费者**。它拿着空的 `alloc` 槽位向 `mcentral` 索要子弹。这是前面文档提到的 `mcentral` 查找 `partial` 列表的过程 。
    
- **Flush/Uncache（退货）**：当 P 被剥离（如 `GOMAXPROCS` 调小）或垃圾回收开始时，`mcache` 会被**清空**。它持有的所有 span（无论满没满）都会被退还给 `mcentral`，供其他 P 使用。这保证了资源不会死锁在休眠的 P 身上。

### 4.2 与 mheap 的交互

对于 `size > 32KB` 的大对象，`mcache` 会被直接**绕过**。请求直接发往 `mheap` 进行页分配 。`mcache` 仅仅在统计数据（如 `local_largefree`）上做个记录，不持有大对象的 span。

## 5. 总结

`mcache` 是 Go 内存分配器实现**高并发**的基石。

- 它将全局的内存资源**分片 (Sharding)** 到每个 P 身上，将绝大多数内存分配操作变成了**纯本地的、无锁的指针操作**。
    
- 它通过 **Tiny Allocator** 极致压榨内存空间。
    
- 它通过与 `mcentral` 的 **Refill/Flush** 机制，实现了本地缓存与全局资源池的动态平衡。