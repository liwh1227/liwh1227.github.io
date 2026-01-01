---
title: go gmp模型
description: 关于go gmp模型的知识梳理
date: 2026-01-01
tags:
  - Go
  - Runtime
---

# gmp
## 背景

go引入了goroutine为了解决c10k的问题，传统的并发模型中往往依赖于系统线程提供的能力来解决问题，而thread本身存在占用空间大、上下文切换慢等问题，一般情况下，线程占1mb-8mb，若尝试创建10000个线程，那么就大概占用几百g的内存空间，并且线程的调度需要操作系统内核完成，上下文的切换也
![](../../assets/gm-model.png)
*图 1: GMP 调度模型概览*

