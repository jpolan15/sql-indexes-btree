# ⚡ SQL Indexes & B-Tree Performance Benchmark

[![Watch the Video Breakdown](https://img.shields.io/badge/YouTube-Watch%20Video%20Breakdown-red?style=for-the-badge&logo=youtube)](https://youtu.be/qAj1LYHhS0s?si=O-h82alkIn5IAA7L)

> **"Why Akainu's SQL Query Destroyed Marineford (How Indexes Saved Zoro)"**  
> 📺 **Full Video Breakdown:** [https://youtu.be/qAj1LYHhS0s?si=O-h82alkIn5IAA7L](https://youtu.be/qAj1LYHhS0s?si=O-h82alkIn5IAA7L)

---

## 📌 Overview

This repository provides a standalone, reproducible benchmark suite demonstrating the mechanical and mathematical difference between **Full Table Scans ($O(N)$)** and **B-Tree Indexes ($O(\log N)$)** when querying 1,000,000+ records.

It also measures:
1. **The Write Penalty:** The latency cost that adding multiple indexes imposes on `INSERT` / `UPDATE` operations due to disk tree rebalancing.
2. **The Composite Index Ordering Trap:** Why `INDEX(crew, name)` works for `WHERE crew = ? AND name = ?`, but completely fails when querying `WHERE name = ?` alone.

---

## 📊 Benchmark Highlights (1,000,000 Rows)

| Operation | Query Plan | Complexity | Average Latency | Speedup |
| :--- | :--- | :---: | :---: | :---: |
| **Search Without Index** | `SCAN pirate_bounties` | $O(N)$ | **~42.5 ms** | Baseline |
| **Search With B-Tree Index** | `SEARCH USING INDEX idx_pirate_name` | $O(\log N)$ | **~0.015 ms** | **~2,800x Faster** 🚀 |

### ⚠️ The Write Penalty

| Active Indexes on Table | Time to Insert 10,000 Rows | Overhead |
| :--- | :---: | :---: |
| **1 Index** (`idx_pirate_name`) | **~12.4 ms** | Baseline |
| **5 Indexes** (over-indexed table) | **~38.1 ms** | **+207% Slower** |

*Rule of thumb:* Index only what you filter or join by in production queries. Over-indexing transforms high read performance into severe write bottlenecks.

---

## 🚀 Quickstart

### Prerequisites
* Python 3.8+ (No external dependencies required — uses built-in `sqlite3`).

### Run the Benchmark
```bash
git clone https://github.com/jpolan15/sql-indexes-btree.git
cd sql-indexes-btree
python benchmark.py
```

---

## 🔍 How B-Trees Work

When you execute `CREATE INDEX`, the database engine copies the indexed column values into a balanced, multi-way search tree (B-Tree):

```text
                  [ M - S ]                 <-- Root Node (Jump 1)
                 /         \
        [ A - L ]           [ T - Z ]       <-- Branch Node (Jump 2)
       /    |    \         /    |    \
     ...   ...   ...     ...   ...  [Zoro]  <-- Leaf Node (Jump 3 -> Row ID)
```

1. Instead of sequentially scanning $1,000,000$ rows from start to finish, the engine drops into the **Root Node**.
2. It evaluates whether the search term falls between specific buckets.
3. In just **3 to 4 jumps**, it lands on the exact **Leaf Node pointer**, bypassing 99.9% of the dataset.

---

## 🧪 Experiments Included in `benchmark.py`

### 1. Read Performance ($O(N)$ vs $O(\log N)$)
Executes a worst-case lookup for `"Roronoa Zoro"` across 1,000,000 unindexed rows, prints the `EXPLAIN QUERY PLAN`, builds a B-Tree index, and measures the speedup.

### 2. Write Penalty Benchmark
Inserts batches of 10,000 records under 1 active index vs 5 active indexes to quantify disk structure rebalancing costs.

### 3. Composite Index Left-Prefix Rule
Demonstrates why column ordering in `CREATE INDEX idx_composite (colA, colB)` matters:
* `WHERE colA = ? AND colB = ?` $\rightarrow$ **Utilizes Index** ✅
* `WHERE colB = ?` (skipping `colA`) $\rightarrow$ **Full Table Scan ($O(N)$ Fallback)** ❌

---

## 📺 Video Reference
For the full visual walkthrough with animated B-Tree traversals, watch the video on YouTube:  
👉 **[Watch Video Breakdown](https://youtu.be/qAj1LYHhS0s?si=O-h82alkIn5IAA7L)**
