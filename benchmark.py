"""
SQL Indexes & B-Tree Performance Benchmark
===========================================
A standalone benchmark script demonstrating the mechanical performance difference
between Full Table Scans (O(N)) and B-Tree Indexes (O(log N)), as well as measuring
the Write Penalty and Composite Index column ordering behavior.

Companion code for the video:
"Why Akainu's SQL Query Destroyed Marineford (How Indexes Saved Zoro)"
Watch here: https://youtu.be/qAj1LYHhS0s?si=O-h82alkIn5IAA7L
"""

import sys
import sqlite3
import time
import random
from typing import List, Tuple

# Enable UTF-8 output on Windows terminals if supported
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Configuration
NUM_RECORDS = 1_000_000
WRITE_BATCH_SIZE = 10_000
DB_FILE = ":memory:"  # In-memory database for rapid, reproducible execution

CREWS = [
    "Straw Hat Pirates",
    "Red Hair Pirates",
    "Heart Pirates",
    "Blackbeard Pirates",
    "Cross Guild",
    "Whitebeard Pirates",
    "Beast Pirates",
    "Big Mom Pirates",
    "Roger Pirates",
    "Marines",
]

FIRST_NAMES = ["Roronoa", "Monkey", "Trafalgar", "Nami", "Usopp", "Sanji", "Tony", "Nico", "Franky", "Brook", "Jinbe", "Shanks", "Buggy", "Marshall", "Edward"]
LAST_NAMES = ["Zoro", "Luffy", "Law", "Robin", "Chopper", "Kurohige", "Teach", "Newgate", "Flamingo", "Mihawk", "Crocodile", "Smoker", "Koby"]


def generate_random_name() -> str:
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def setup_database(conn: sqlite3.Connection):
    """Creates the initial unindexed pirate bounty registry."""
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS pirate_bounties;")
    cursor.execute("""
        CREATE TABLE pirate_bounties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            crew TEXT NOT NULL,
            bounty_berries INTEGER NOT NULL,
            threat_level TEXT NOT NULL,
            island_origin TEXT NOT NULL
        );
    """)
    conn.commit()


def seed_database(conn: sqlite3.Connection, count: int) -> str:
    """
    Populates the database with `count` random pirate records.
    Inserts a guaranteed target: 'Roronoa Zoro' in the Straw Hat Pirates crew.
    """
    print(f"[*] Seeding database with {count:,} records (please wait a few seconds)...")
    cursor = conn.cursor()
    
    islands = ["Wano", "Dressrosa", "Alabasta", "Water 7", "Sabaody", "Loguetown", "Fish-Man Island", "Elbaf"]
    threats = ["Low", "Medium", "High", "Calamity", "Emperor"]

    batch_size = 50_000
    rows = []
    
    for i in range(count - 1):
        name = generate_random_name()
        crew = random.choice(CREWS)
        bounty = random.randint(1_000_000, 4_000_000_000)
        threat = random.choice(threats)
        island = random.choice(islands)
        rows.append((name, crew, bounty, threat, island))
        
        if len(rows) >= batch_size:
            cursor.executemany(
                "INSERT INTO pirate_bounties (name, crew, bounty_berries, threat_level, island_origin) VALUES (?, ?, ?, ?, ?)",
                rows
            )
            rows = []

    # Insert specific search target near the end of the dataset to simulate worst-case scan
    target_name = "Roronoa Zoro"
    target_crew = "Straw Hat Pirates"
    rows.append((target_name, target_crew, 1_111_000_000, "Calamity", "Wano"))
    
    cursor.executemany(
        "INSERT INTO pirate_bounties (name, crew, bounty_berries, threat_level, island_origin) VALUES (?, ?, ?, ?, ?)",
        rows
    )
    conn.commit()
    print("[+] Seeding complete!\n")
    return target_name


def benchmark_search(conn: sqlite3.Connection, query: str, params: tuple, runs: int = 5) -> Tuple[float, List[Tuple]]:
    """Runs a query multiple times and returns average execution time in milliseconds."""
    cursor = conn.cursor()
    times = []
    result = []
    
    for _ in range(runs):
        start = time.perf_counter()
        cursor.execute(query, params)
        result = cursor.fetchall()
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        times.append(elapsed_ms)
        
    avg_time = sum(times) / len(times)
    return avg_time, result


def run_full_table_scan_vs_btree_test(conn: sqlite3.Connection, target_name: str):
    """Demonstrates Read Performance: Full Table Scan vs Single-Column B-Tree."""
    print("=" * 70)
    print("TEST 1: READ PERFORMANCE - Full Table Scan vs. B-Tree Index")
    print("=" * 70)
    
    query = "SELECT id, name, crew, bounty_berries FROM pirate_bounties WHERE name = ?;"
    
    # 1. Full Table Scan (No Index)
    print("[1.1] Executing Query WITHOUT Index (Full Table Scan)...")
    explain_cursor = conn.cursor()
    explain_cursor.execute(f"EXPLAIN QUERY PLAN {query}", (target_name,))
    plan_unindexed = explain_cursor.fetchone()[3]
    print(f"      Query Plan: {plan_unindexed}")
    
    time_unindexed, results = benchmark_search(conn, query, (target_name,))
    print(f"      Found {len(results)} match(es): {results[0] if results else 'None'}")
    print(f"      Average Execution Time: {time_unindexed:.3f} ms\n")
    
    # 2. Add B-Tree Index
    print("[1.2] Building B-Tree Index: CREATE INDEX idx_pirate_name ON pirate_bounties(name)...")
    idx_start = time.perf_counter()
    conn.execute("CREATE INDEX idx_pirate_name ON pirate_bounties(name);")
    conn.commit()
    idx_time = (time.perf_counter() - idx_start) * 1000.0
    print(f"      Index Build Time: {idx_time:.2f} ms\n")
    
    # 3. Indexed Query Execution
    print("[1.3] Executing Query WITH B-Tree Index...")
    explain_cursor.execute(f"EXPLAIN QUERY PLAN {query}", (target_name,))
    plan_indexed = explain_cursor.fetchone()[3]
    print(f"      Query Plan: {plan_indexed}")
    
    time_indexed, results_idx = benchmark_search(conn, query, (target_name,))
    print(f"      Average Execution Time: {time_indexed:.5f} ms\n")
    
    # Summary
    speedup = time_unindexed / max(time_indexed, 0.00001)
    print(f"--> Speedup Factor: {speedup:,.1f}x FASTER with B-Tree Index!")
    print("=" * 70 + "\n")


def run_write_penalty_test(conn: sqlite3.Connection):
    """
    Demonstrates Write Performance (The Write Penalty):
    Measures time to insert rows when 1 vs 5 indexes must be updated per insert.
    """
    print("=" * 70)
    print("TEST 2: WRITE PENALTY - Cost of Over-Indexing on INSERT Speeds")
    print("=" * 70)
    
    batch = [
        (generate_random_name(), random.choice(CREWS), random.randint(1_000_000, 500_000_000), "Medium", "Loguetown")
        for _ in range(WRITE_BATCH_SIZE)
    ]
    
    cursor = conn.cursor()
    
    # State A: 1 Index Active (from Test 1)
    start = time.perf_counter()
    cursor.executemany(
        "INSERT INTO pirate_bounties (name, crew, bounty_berries, threat_level, island_origin) VALUES (?, ?, ?, ?, ?)",
        batch
    )
    conn.commit()
    time_1_idx = (time.perf_counter() - start) * 1000.0
    print(f"[+] Inserting {WRITE_BATCH_SIZE:,} rows with 1 Index:    {time_1_idx:.2f} ms")
    
    # State B: Add 4 More Indexes (Total 5 Indexes)
    print("[*] Adding 4 more indexes (idx_crew, idx_bounty, idx_threat, idx_island)...")
    conn.execute("CREATE INDEX idx_crew ON pirate_bounties(crew);")
    conn.execute("CREATE INDEX idx_bounty ON pirate_bounties(bounty_berries);")
    conn.execute("CREATE INDEX idx_threat ON pirate_bounties(threat_level);")
    conn.execute("CREATE INDEX idx_island ON pirate_bounties(island_origin);")
    conn.commit()
    
    # Measure inserts with 5 indexes
    start = time.perf_counter()
    cursor.executemany(
        "INSERT INTO pirate_bounties (name, crew, bounty_berries, threat_level, island_origin) VALUES (?, ?, ?, ?, ?)",
        batch
    )
    conn.commit()
    time_5_idx = (time.perf_counter() - start) * 1000.0
    print(f"[+] Inserting {WRITE_BATCH_SIZE:,} rows with 5 Indexes:  {time_5_idx:.2f} ms")
    
    overhead = ((time_5_idx - time_1_idx) / time_1_idx) * 100.0
    print(f"--> Write Overhead Increase: +{overhead:.1f}% slower due to index tree rebalancing!")
    print("=" * 70 + "\n")


def run_composite_index_test(conn: sqlite3.Connection):
    """
    Demonstrates Composite Index Ordering (Left-to-Right Prefix Rule):
    Shows why searching by the second column does not use the composite index.
    """
    print("=" * 70)
    print("TEST 3: COMPOSITE INDEXES - Column Order Matters")
    print("=" * 70)
    
    # Create composite index on (crew, name)
    print("[*] Creating Composite Index: CREATE INDEX idx_composite_crew_name ON pirate_bounties(crew, name)...")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_composite_crew_name ON pirate_bounties(crew, name);")
    conn.commit()
    
    cursor = conn.cursor()
    
    # Query A: Searching by Leading Column (crew) + Second Column (name) -> Uses Composite Index
    query_both = "SELECT id, name, crew FROM pirate_bounties WHERE crew = ? AND name = ?;"
    cursor.execute(f"EXPLAIN QUERY PLAN {query_both}", ("Straw Hat Pirates", "Roronoa Zoro"))
    plan_both = cursor.fetchone()[3]
    print("\n[3.1] Query WHERE crew = ? AND name = ? (Matches Left Prefix):")
    print(f"      Plan: {plan_both}")
    
    # Query B: Searching ONLY by Second Column (name) -> Ignores Composite Index!
    # Drop single name index first to test purely composite index behavior
    conn.execute("DROP INDEX IF EXISTS idx_pirate_name;")
    conn.commit()
    
    query_name_only = "SELECT id, name, crew FROM pirate_bounties WHERE name = ?;"
    cursor.execute(f"EXPLAIN QUERY PLAN {query_name_only}", ("Roronoa Zoro",))
    plan_name_only = cursor.fetchone()[3]
    print("\n[3.2] Query WHERE name = ? (Bypasses Leading Column 'crew'):")
    print(f"      Plan: {plan_name_only}")
    print("      Note: Without the leading column 'crew', the database cannot jump into the B-Tree!")
    print("=" * 70 + "\n")


def main():
    print("\n" + "#" * 70)
    print("  SQL INDEXES & B-TREE BENCHMARK SUITE")
    print("  Simulating 1,000,000 Marine Bounty Records")
    print("#" * 70 + "\n")
    
    conn = sqlite3.connect(DB_FILE)
    
    try:
        setup_database(conn)
        target_name = seed_database(conn, NUM_RECORDS)
        
        run_full_table_scan_vs_btree_test(conn, target_name)
        run_write_penalty_test(conn)
        run_composite_index_test(conn)
        
        print("All benchmarks completed successfully.")
        print("Watch the full video breakdown: https://youtu.be/qAj1LYHhS0s?si=O-h82alkIn5IAA7L\n")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
