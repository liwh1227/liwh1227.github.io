# Go 内存管理：mheap 核心机制与架构

## 写在前面的话

go的内存管理是这一系列文章中花费时间最长的，第一，我对内存管理的内容一直了解的比较少，第二，这部分内容却是比较多，尤其是mheap管理内存的radix树结构，我用了很长时间去理解。废话不多说，先上一副按照我梳理的思路画的图。

![](../../assets/memory-v1.png)
*图1: go内存管理整体架构*

我们沿着这张图从左到右依次进行展开介绍。

## 1. 核心定位与整体架构

在 Go 的三级内存管理架构（TCMalloc 变种）中，`mheap` 处于最顶层，是整个 Go 运行时的“内存总管”。它掌管着整个 Go 程序从操作系统申请下来的所有虚拟地址空间，并负责将其切割成页（Page）分发给下层组件。

从宏观视角来看，`mheap` 的核心职责包括：

1. **向 OS 申请内存**：通过系统调用（如 `mmap`）管理虚拟地址空间的增长。
2. **大对象直接分配**：大于 32KB 的对象跳过 `mcache` 和 `mcentral`，直接由 `mheap` 分配 。
3. **内存管理与索引**：通过 Radix Tree（基数树）管理空闲页，通过 `arenas` 建立虚拟地址到元数据的映射 。
4. **垃圾回收支持**：管理 `sweepgen` 等 GC 关键元数据 。

## 2. 核心数据结构解析

`mheap` 的结构体设计体现了 Go 对锁粒度、缓存局部性和并发性能的极致追求。以下是核心字段的深度解读：

```go
type mheap struct {
    // 1. 全局大锁：当 mcentral 缺内存或进行大对象分配时使用，保护 mheap 内部数据安全。
    lock mutex

    // 2. 页面分配器：基于位图的基数树，用于极速定位空闲连续页。
    pages pageAlloc

    // 3. Span 管理：记录所有创建的 mspan，供 GC 遍历使用。
    allspans []*mspan

    // 4. 堆元数据索引：稀疏数组，实现 "虚拟地址 -> 元数据(heapArena)" 的 O(1) 查找。
    arenas [1 << arenaL1Bits]*[1 << arenaL2Bits]*heapArena

    // 5. 中央缓存：内嵌的 mcentral 数组，作为 mcache 的上游“批发市场”。
    central [numSpanClasses]struct {
        mcentral mcentral
        pad      [cpu.CacheLinePadSize - unsafe.Sizeof(mcentral{})%cpu.CacheLinePadSize]byte
    }

    // 6. GC 扫描世代：用于并发清理的标记。
    sweepgen uint32
}
```

### 关键组件详解

- **Arenas (稀疏索引)**： Go 向 OS 申请内存的最小单位是 Arena（通常为 64MB）。为了解决虚拟地址空间不连续的问题，`mheap` 使用二级稀疏数组 `arenas` 来管理。给定任意一个内存地址，Go 可以通过位运算快速定位到其对应的 `heapArena` 元数据，从而获取该页面的状态（如 GC 标记位）。

- **Central (内嵌数组)**： 需要特别注意的是，`central` 并非指针，而是直接内嵌在 `mheap` 中的数组。为了避免伪共享（False Sharing）导致的缓存失效，每个 `mcentral` 结构体都进行了 CPU Cache Line 对齐填充（Padding）。

## 3. 基于 Bitmap 的 Radix Tree

`mheap` 对内存页的管理采用了基于 Bitmap 的 5 层 Radix Tree 结构。这是理解 Go 内存管理高性能的关键。

### 3.1 树状结构设计

- **叶子节点 (Chunk)**：最底层。每个 Chunk 包含一个 Bitmap，直接映射 Arena 中的物理页状态。Go 内存管理的最小单位是 8KB，Bitmap 中的 1 bit 对应 1 个 Page（0=可用，1=占用）。
- **中间节点 (Summary)**：Level 2 到 Level 5。它们不存具体位图，而是存储**摘要信息 (Summary)**，用于加速搜索 。

### 3.2 Summary 机制

为了在不遍历子节点的情况下快速判断是否有足够的连续空间，每个节点维护了三个核心值：

- **Start**：从左侧边界开始，连续空闲页的数量。
- **End**：从右侧边界结束，连续空闲页的数量。
- **Max**：该节点范围内，任意位置能找到的最大连续空闲页数量 。

**位压缩优化**： Go 团队强制将 `start`、`end`、`max` 各分配 21 bit。总共 63 bit，可以塞入一个 `uint64` 整数中。

> **设计哲学**：这意味着 CPU 可以通过一条原子指令（如 `LoadUint64`）读取或更新整个节点的状态，极大提升了并发性能并简化了锁机制 。

### 3.3 分配与更新流程

- **自顶向下的搜索 (Alloc)**：
    
    1. **快速路径**：通过 `searchAddr` 避免重复扫描低地址的碎片 。
    
    2. **根节点剪枝**：如果 `root.max < N`，直接返回 OOM，无需遍历 。
    
    3. **跨边界检查**：利用 Summary 的 `end` 和 `start` 属性，能够发现跨越子节点边界的连续空闲块（即 `child[i].end + child[i+1].start >= N`）。
    
- **自底向上的更新 (Update)**： 当位图变更时，状态必须向上冒泡更新。父节点的 `max` 是由所有子节点的 `max` 以及跨边界连续块的最大值决定的 。

## 4. mheap 与 mcentral 的协同机制

`mheap` 与 `mcentral` 的交互是 Go 内存流转的枢纽。当 P（处理器）持有的 `mcache` 耗尽，且 `mcentral` 的部分空闲链表也为空时，会触发向 `mheap` 的申请流程。
### 4.1 交互触发条件

当 `mcentral.cacheSpan()` 被调用但无法从 `partial` 或 `full`（通过清理）链表中获取 Span 时，它会调用 `mcentral.grow()`，进而向 `mheap` 发起 `alloc` 请求。

### 4.2 交互流程详解

1. **计算页数需求**： `mcentral` 并不直接管理字节，它管理的是 Span。根据申请的 `spanClass`，Go 运行时查表得知该规格的 Span 需要多少个连续页（`npages`）。
    - 例如：申请一个 `class` 为 10 的 Span，可能对应需要 2 个连续的 8KB 页 。
2. **加锁与分配**： 由于 `mheap` 是全局唯一的，申请过程需要获取 `mheap.lock`。随后，`mheap` 利用 Radix Tree 算法，快速找到一段长度为 `npages` 的连续空闲页 。
3. **Page 到 Span 的转换 (关键步骤)**： `mheap` 返回的是页的基地址。`mcentral` 拿到内存后，需要将其“包装”成一个 `mspan` 结构：
    - 初始化 `mspan` 元数据。
    - 将这些页对应的 `heapArena.spans` 索引指向这个新的 `mspan`。
    - **关键点**：此时，这块内存从“原始的连续页”变成了“具有特定规格（Size Class）的 Span”。
4. **切分与分发**： 获得的 `mspan` 会被加入到 `mcentral` 的 `full` 集合中（尽管刚申请时是空的，但逻辑上它被视为已分配给当前请求者），并切分出对象返回给 `mcache`。

### 4.3 大对象特例

对于大于 32KB 的对象，微型分配器（Tiny）和小对象分配器（Small）无能为力。此时请求会直接打到 `mheap`，`mheap` 会计算需要的页数，直接从 Radix Tree 中分配，并定制一个特殊的 Span（Class 0）返回给调用方，**不经过 mcentral** 。

## 5. 内存归还：Scavenger 机制

Go 需要应对突发流量导致的内存暴涨。为了避免 RSS（驻留集大小）长期居高不下，`mheap` 引入了 Scavenger 线程进行内存回收。

- **工作原理**： Scavenger 是一个后台线程，它利用 Radix Tree 的 `max` 字段作为索引，快速定位那些拥有大量连续空闲页（通常 `max >= 2MiB`）的 Chunk 。
- **归还策略**： 找到目标后，调用 `sysUnused`。
    - 在 Go 1.16+ (Linux)，默认使用 `MADV_DONTNEED`。这会通知 OS 立即收回物理内存，RSS 指标会迅速下降，虽然下次访问会触发 Page Fault，但提供了更直观的监控反馈 。
    - 这解决了早期版本使用 `MADV_FREE` 导致的“内存泄漏”假象问题 。
## 6. 总结

`mheap` 是 Go 内存管理的基石。它通过 **Arenas** 解决了虚拟地址空间的碎片化问题，通过 **Radix Tree** 实现了高效的连续内存分配，通过 **Summary 位压缩** 实现了高性能的并发更新，并配合 **Scavenger** 实现了内存的弹性伸缩。理解 `mheap` 的工作原理，是掌握 Go 高性能并发编程的关键钥匙。