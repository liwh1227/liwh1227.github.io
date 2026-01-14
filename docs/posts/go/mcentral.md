# Go 内存管理：mcentral 核心机制与架构
## 1. 核心定位与设计哲学

在 Go 内存管理的三层架构中，`mcentral` 扮演着承上启下的**“内存批发商”**角色。

- **对上（mheap）**：它是大客户。它从 `mheap` 批发大块的物理内存页（Pages），并将这些连续页切割成特定规格（Size Class）的 `mspan` 。
- **对下（mcache）**：它是供货枢纽。当 P（Processor）的本地缓存 `mcache` 缺货时，`mcentral` 负责提供新的 `mspan` 。

**设计哲学**： `mcentral` 的存在是为了平衡**锁的粒度**与**内存复用率**。

- 如果所有 P 直接向 `mheap` 申请，全局锁竞争将成为瓶颈 。
- 如果所有内存都在 `mcache` 中，会导致极高的内存碎片和浪费。
- `mcentral` 通过**按规格分类（Per-Class）和分级并发控制**，实现了并发性能与资源利用率的最优解。

## 2. 核心数据结构解析

`mcentral` 并非独立存在于堆外，而是直接内嵌在 `mheap` 结构体中。

```go
type mheap struct {
    // ... 其他字段
    // 5. 堆内存的“批发市场”(mcentral 数组)
    central [numSpanClasses]struct {
        mcentral mcentral
        pad      [cpu.CacheLinePadSize - unsafe.Sizeof(mcentral{})%cpu.CacheLinePadSize]byte
    }
}
```

- **数组结构**：`central` 是一个长度为 `numSpanClasses`（通常为 136， `68 * 2` 包含 scan 和 noscan）的数组 。这意味着每一种规格（如 8B, 16B...）都有一个独立的 `mcentral` 实例负责管理。
- **Padding 填充**：代码中的 `pad` 字段至关重要。它通过填充字节，确保数组中相邻的 `mcentral` 实例处于不同的 CPU Cache Line 中，防止多核 CPU 并发访问不同规格内存时发生**伪共享（False Sharing）** 。

### 2.1 mcentral 内部结构

```go
type mcentral struct {
    // 1. 占位符：防止结构体被分配在堆上（必须嵌入在 mheap 中）
    _ sys.NotInHeap

    // 2. 规格 ID：当前 mcentral 管理的 span 规格（如 8B, 16B...）
    spanclass spanClass

    // 3. 有空位的 Span 集合（双缓冲）
    partial [2]spanSet

    // 4. 无空位的 Span 集合（双缓冲）
    full    [2]spanSet
}
```


`mcentral` 的核心职责是管理两类 Span 链表：

1. **spanclass**：当前 mcentral 管理的 span 规格，mcentral是按class进行加锁申请和分配内存的。
2. **partial (有空位)**：包含“至少有一个空闲对象”的 Span 集合。这是 `mcache` 进货时的首选目标。
3. **full (已满/被占用)**：包含“没有空闲对象”或者“当前正在被某个 mcache 独占使用”的 Span 集合。
`mcentral`的结构示意图如下：

![](../../assets/mcentral.png)
*图1: mcentral示意图*

结合图1和源码的逻辑，`mcentral`针对`scan`和`noscan`的对象类型进行了分类，`scan`类型表示当前的区域需要进行垃圾回收，`noscan`类型则可以直接忽略，这样可以提升垃圾回收的效率，减少垃圾回收的成本。无论何种类型的内存区域，都是通过partial和full列表进行管理，这种设计也可以提升垃圾回收的效率，当mcache进行内存申请时，优先从partial列表获取，然后才回去获取full列表中的span。` partial/full [2]spanSet`是一个大小为2的数组，并不是1，在源码中，有这么一段逻辑：
```go

// partialUnswept returns the spanSet which holds partially-filled// unswept spans for this sweepgen.  
func (c *mcentral) partialUnswept(sweepgen uint32) *spanSet {  
    return &c.partial[1-sweepgen/2%2]  
}  
  
// partialSwept returns the spanSet which holds partially-filled// swept spans for this sweepgen.  
func (c *mcentral) partialSwept(sweepgen uint32) *spanSet {  
    return &c.partial[sweepgen/2%2]  
}

// fullUnswept returns the spanSet which holds unswept spans without any// free slots for this sweepgen.  
func (c *mcentral) fullUnswept(sweepgen uint32) *spanSet {  
    return &c.full[1-sweepgen/2%2]  
}  
  
// fullSwept returns the spanSet which holds swept spans without any// free slots for this sweepgen.  
func (c *mcentral) fullSwept(sweepgen uint32) *spanSet {  
    return &c.full[sweepgen/2%2]  
}
```

结合前文mheap的sweepgen成员变量，sweepgen用于标识当前GC扫描世代，结合
`1-sweepgen/2%2`和`sweepgen/2%2`计算逻辑，可以在O(1)的时间复杂度下完成已扫描和未扫描的列表转换，而无需每次GC阶段都扫描所有的span来确定状态并进行处理。

---

## 3. 核心机制：Full 与 Partial 的流转

`mcentral` 的高效运作依赖于 Span 在 `partial` 和 `full` 两个集合间的精准流转。这是一个动态平衡的过程。

### 3.1 进货逻辑 (CacheSpan)

当 `mcache` 触发 Refill 请求时，`mcentral` 需要找出一个可用的 Span：

1. **查找 Partial (Swept)**：优先查找 `partial` 列表中那些**已经完成 GC 清扫**且有空位的 Span。这是最快路径，拿到即用。

2. **查找 Partial (Unswept)**：如果没找到，尝试查找 `partial` 列表中**尚未清扫**的 Span。找到后，原地触发清扫（Sweep），如果清扫后有空位，则返回。

3. **查找 Full (Unswept)**：如果 `partial` 空了，去 `full` 列表中找那些“逻辑上满但包含死对象”的 Span。对其进行清扫，如果回收了空间，将其移入 `partial` 并返回。

4. **兜底 (Grow)**：如果以上全失败，说明当前规格真的没内存了。此时调用 `mcentral.grow()`，向 `mheap` 申请新的物理页。

### 3.2 归还逻辑 (UncacheSpan)

当 Span 在 `mcache` 中被再次填满，或者因为 GC 导致 Span 归还时：

- Span 会被移回 `mcentral`。

- 如果 Span 还有空位，放入 `partial` 集合。

- 如果 Span 满了，放入 `full` 集合。

### 3.3 refill流程图


![](../../assets/mcentral-refill.png)
 *图2: refill 流程示意*
 
---

## 4. 关键交互：mcentral 与 mheap 的扩容协议

`mcentral` 自身不持有物理内存的所有权，它只是管理者。真正的内存分配发生在 `mheap`。

### 交互流程

1. **请求**：当 `mcentral` 决定扩容时，它根据自身管理的 Size Class，查表得知需要的页数 `npages`（例如：Class 10 需要 2 页，即 16KB）。
    
2. **分配**：`mcentral` 调用 `mheap.alloc(npages, spanclass)` 。
    
3. **响应**：
    - `mheap` 锁定全局锁 `lock` 。
    - 在 Radix Tree 中查找并标记连续空闲页 。
    - `mheap` 返回分配的内存基地址。
    
4. **初始化**：`mcentral` 将这块内存初始化为 `mspan`，设置好 `allocBits` 和 `GCmarkBits`，并将其挂载到自己的 `full` 集合中（因为马上就要交给 mcache 用了）。

## 5. 总结

`mcentral` 是 Go 内存分配器中“化整为零”的关键环节。

- 它通过 **Span Class** 将内存管理标准化。
    
- 它通过 **Partial/Full 双集合** 机制，实现了内存的惰性清理与高效复用。
    
- 它通过 **Per-Class 的细粒度锁**，在避免全局锁竞争的同时，保证了多线程分配的安全性 。