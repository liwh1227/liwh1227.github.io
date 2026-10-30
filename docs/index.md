---
title: Li · Go、区块链与系统设计
description: Li 的技术博客。记录 Go 运行时、联盟链研发与系统设计，分享碳普惠平台、tinycache 和工程实践中的思考。
template: home.html
hide:
  - navigation
  - toc
---

<div class="home-hero" markdown="1">
<div class="hero-copy" markdown="1">

<p class="eyebrow">LI / ENGINEERING NOTES</p>

# 从 Go 底层，<br>到真实的业务系统。

<p class="hero-description">我是 Li，一名专注 Go 后端与联盟链研发的工程师。这里记录源码里的机制、系统演进中的取舍，以及把想法写成代码的过程。</p>

<div class="hero-actions" markdown="1">

[开始阅读 <span aria-hidden="true">↗</span>](#selected){ .action-primary }
[看看项目 <span aria-hidden="true">→</span>](projects.md){ .action-secondary }

</div>

<p class="hero-footnote">Go Runtime <span>/</span> 分布式系统 <span>/</span> Blockchain</p>

</div>

<aside class="explore-card" aria-labelledby="explore-title" markdown="1">

<p class="explore-kicker">EXPLORE THE NOTES <span>阅读入口</span></p>
<h2 id="explore-title">从一个问题开始</h2>
<p class="explore-hint">点开感兴趣的问题，找到下一篇值得读的文章。</p>

<details class="explore-item" name="home-explorer" open markdown="1">
<summary><span class="explore-number" aria-hidden="true">01</span><span class="explore-question"><span class="explore-topic">系统实践</span>上链很慢，接口也要跟着等吗？</span><span class="explore-toggle" aria-hidden="true"></span></summary>
<div class="explore-answer" markdown="1">

在允许异步确认的业务里，先将请求落库，再异步投递上链，失败后重试补偿。看看这层设计如何解耦处理节奏。

[阅读：异步上链与补偿 →](posts/系统架构/00.%20碳普惠系统演进.md#223){ .explore-link }

</div>
</details>

<details class="explore-item" name="home-explorer" markdown="1">
<summary><span class="explore-number" aria-hidden="true">02</span><span class="explore-question"><span class="explore-topic">缓存设计</span>缓存越大，GC 压力就越大吗？</span><span class="explore-toggle" aria-hidden="true"></span></summary>
<div class="explore-answer" markdown="1">

除了条目数量，数据结构中的指针也很关键。看看 tinycache 如何围绕无指针索引、分片与空间复用设计缓存。

[阅读：指针扫描与缓存设计 →](posts/系统架构/01.%20设计和实现高性能%20Go%20本地缓存.md#22-gc){ .explore-link }

</div>
</details>

<details class="explore-item" name="home-explorer" markdown="1">
<summary><span class="explore-number" aria-hidden="true">03</span><span class="explore-question"><span class="explore-topic">Go 运行时</span>Goroutine 是怎么被调度的？</span><span class="explore-toggle" aria-hidden="true"></span></summary>
<div class="explore-answer" markdown="1">

从 G、M、P 的分工开始，理解运行队列、工作窃取和抢占如何协作，再沿着源码继续深入。

[阅读：GMP 的调度循环 →](posts/go/00.%20GMP%20模型总览.md#31){ .explore-link }

</div>
</details>

<div class="explore-footer" markdown="1">

[查看完整阅读地图 <span aria-hidden="true">↗</span>](reading.md)

</div>
</aside>
</div>

<section class="home-section selected-section" markdown="1">
<div class="section-heading" markdown="1">

<p class="eyebrow">01 / SELECTED WRITING</p>

## 先读这几篇 { #selected }

从一个真实系统、一段动手实践，到支撑它们的底层机制。

</div>

<div class="article-row" markdown="1">
<div class="article-index">01 <span>架构复盘</span></div>
<div class="article-copy" markdown="1">

### [碳普惠系统演进：在业务增长中做取舍](posts/系统架构/00.%20碳普惠系统演进.md)

从存证到资产流转，再到亿级数据治理。记录类 UTXO 模型、分表、异步上链与服务拆分背后的问题和代价。

<p class="article-tags">Go · ChainMaker · 系统演进</p>

</div>
<span class="row-arrow" aria-hidden="true">↗</span>
</div>

<div class="article-row" markdown="1">
<div class="article-index">02 <span>开源实践</span></div>
<div class="article-copy" markdown="1">

### [tinycache：从理解 GC 到实现本地缓存](posts/系统架构/01.%20设计和实现高性能%20Go%20本地缓存.md)

从 map 的指针扫描和锁竞争出发，探索无指针索引、分片与空间复用，把运行时知识落到可阅读的代码里。

<p class="article-tags">Go · 内存管理 · 缓存设计</p>

</div>
<span class="row-arrow" aria-hidden="true">↗</span>
</div>

<div class="article-row" markdown="1">
<div class="article-index">03 <span>源码笔记</span></div>
<div class="article-copy" markdown="1">

### [GMP 模型：理解 Go 并发的起点](posts/go/00.%20GMP%20模型总览.md)

串起 Goroutine、Machine 与 Processor，再沿着调度、内存、GC 和网络模型继续向下读。

<p class="article-tags">Go Runtime · 调度器 · 并发</p>

</div>
<span class="row-arrow" aria-hidden="true">↗</span>
</div>

</section>

<section class="home-section" markdown="1">
<div class="section-heading" markdown="1">

<p class="eyebrow">02 / EXPLORE BY TOPIC</p>

## 沿着问题，继续深入

</div>

<div class="topic-grid" markdown="1">
<div class="topic" markdown="1">

<span class="topic-number">01</span>

### Go 运行时

GMP、内存分配、垃圾回收、网络与并发原语。从整体模型走向实现细节。

[沿阅读路线展开 →](reading.md#go-runtime)

</div>
<div class="topic" markdown="1">

<span class="topic-number">02</span>

### 系统设计与实践

服务边界、数据分表、本地缓存。先看问题与约束，再看方案和取舍。

[从工程案例开始 →](reading.md#system-design)

</div>
<div class="topic" markdown="1">

<span class="topic-number">03</span>

### 联盟链与数字资产

碳积分合约、BaaS、DID，以及共识节点遴选、UTXO 治理和隐私验证研究。

[了解项目与研究 →](projects.md#blockchain)

</div>
</div>

</section>

<section class="home-about" markdown="1">
<div markdown="1">

<p class="eyebrow">BEYOND THE CODE</p>

## 认真写代码，也给生活找点乐子。

球场上喜欢对抗和篮板，训练时享受一点点突破，也读教育与认知科学。博客里除了技术，还有不定期的生活与思考。

</div>
<div class="about-links" markdown="1">

[更多关于我 ↗](about.md)
[浮生半日 →](posts/浮生半日/关于ai.md)
[GitHub ↗](https://github.com/liwh1227)

</div>
</section>
