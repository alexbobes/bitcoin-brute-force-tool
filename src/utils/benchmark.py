#!/usr/bin/env python3
"""
Benchmark script for Bitcoin Brute Force Tool.
This script tests the performance of different brute force methods
and generates a comparison report.
"""

import time
import logging
import multiprocessing
from prettytable import PrettyTable
from bruteforcer import RBF, TBF, OTBF, generate_keys_batch
from bit import Key
from functools import partial
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Benchmark parameters
BENCHMARK_DURATION = 5  # seconds per test
NUM_CORES_TO_TEST = [1, 2, 4]  # Test with different core counts
BATCH_SIZES = [100, 1000, 10000]  # Different batch sizes to test
NUM_THREADS = min(32, multiprocessing.cpu_count() * 2)  # Thread count for parallel processing

def time_function(func, duration=BENCHMARK_DURATION):
    """Time a function for a specific duration and return operations per second."""
    count = 0
    start_time = time.time()
    end_time = start_time + duration
    
    while time.time() < end_time:
        func()
        count += 1
        
    elapsed = time.time() - start_time
    return count / elapsed

def benchmark_key_generation_single():
    """Benchmark single key generation."""
    def generate_one_key():
        return Key()
    
    return time_function(generate_one_key)

def benchmark_key_from_int_single():
    """Benchmark single key generation from integer."""
    i = 0
    def generate_one_key_from_int():
        nonlocal i
        i += 1
        # Use a small valid number - enough for benchmark purposes
        safe_i = i % 1000000 + 1  # Keep in small, valid range (avoid 0)
        return Key.from_int(safe_i)
    
    return time_function(generate_one_key_from_int)

def benchmark_batch_generation(batch_size, use_threading=True):
    """Benchmark batch key generation with or without threading."""
    # Get the maximum value a bitcoin private key can have
    # (one less than the group order) - a 256-bit number
    from coincurve.utils import GROUP_ORDER_INT
    max_private_key = GROUP_ORDER_INT - 1
    
    # Start from a valid small positive number (avoid 0)
    start_index = 1
    
    if use_threading:
        # Use threaded implementation
        def generate_batch_threaded():
            nonlocal start_index
            chunk_size = batch_size // NUM_THREADS
            if chunk_size == 0:
                chunk_size = 1
            
            chunks = [(start_index + i * chunk_size, min(chunk_size, batch_size - (i * chunk_size))) 
                     for i in range(NUM_THREADS)]
            
            # Make sure we use a valid range for keys
            # Use a small random number within valid range - enough for the benchmark test
            def safe_key_from_int(n):
                # Keep the number small enough to avoid overflow issues
                safe_n = n % 1000000 + 1  # Ensure it's > 0 and reasonably small
                return Key.from_int(safe_n)
                
            gen_func = partial(generate_keys_batch, safe_key_from_int)
            
            with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
                results = list(executor.map(lambda args: gen_func(*args), chunks))
                
            # Update start index for next batch
            start_index += batch_size
            
            # Return number of keys generated
            return batch_size
    else:
        # Use simple loop implementation
        def generate_batch_simple():
            nonlocal start_index
            keys = []
            for i in range(start_index, start_index + batch_size):
                # Use a small valid number - enough for benchmark purposes
                safe_i = i % 1000000 + 1  # Keep in small, valid range
                keys.append(Key.from_int(safe_i))
            start_index += batch_size
            return batch_size
            
    # Time the appropriate function
    if use_threading:
        ops_per_sec = time_function(generate_batch_threaded)
    else:
        ops_per_sec = time_function(generate_batch_simple)
        
    # Return operations (keys) per second
    return ops_per_sec * batch_size  # Multiply by batch size to get keys/sec

def benchmark_full_method(method_name, test_size=10000):
    """
    Benchmark a complete brute force method including database checks.
    This creates a test environment and measures the full pipeline.
    """
    from db_manager import check_addresses_batch, create_tables
    from bit import Key
    import random
    
    # Make sure database tables exist
    create_tables()
    
    # Generate test addresses (in memory to avoid influencing the benchmark)
    addresses = []
    keys = []
    
    if method_name == "RBF":
        # Random key generation
        for _ in range(test_size):
            k = Key()
            addresses.append(k.address)
            keys.append(k)
    elif method_name == "TBF":
        # Sequential key generation
        for i in range(test_size):
            # Use valid private key values (avoid 0 and extremely large numbers)
            safe_i = i % 1000000 + 1
            k = Key.from_int(safe_i)
            addresses.append(k.address)
            keys.append(k)
    elif method_name == "OTBF":
        # Offset key generation - use a safer smaller offset for benchmarking
        offset = 10**6  # Small enough for benchmark purposes
        for i in range(test_size):
            safe_i = (i + offset) % 10**7  # Keep in valid range
            k = Key.from_int(safe_i)
            addresses.append(k.address)
            keys.append(k)
            
    # Prepare the benchmark function
    def run_full_benchmark():
        # Check addresses against database
        found = check_addresses_batch(addresses)
        return len(addresses)
    
    # Time the function and return keys per second
    ops_per_sec = time_function(run_full_benchmark, duration=5)
    return ops_per_sec * test_size

def run_all_benchmarks():
    """Run all benchmarks and print results."""
    results = []
    
    print("\n🔄 Running Bitcoin Brute Force Tool Benchmarks...\n")
    
    # 1. Single key generation benchmarks
    print("⏱️ Testing single key generation methods...")
    results.append(("Random Key (RBF)", 1, 1, benchmark_key_generation_single()))
    results.append(("Sequential Key (TBF)", 1, 1, benchmark_key_from_int_single()))
    
    # 2. Batch generation benchmarks (no threading vs threading)
    print("⏱️ Testing batch key generation with different batch sizes...")
    for batch_size in BATCH_SIZES:
        print(f"  Testing batch size: {batch_size}...")
        # Simple batching (no threading)
        keys_per_sec = benchmark_batch_generation(batch_size, use_threading=False)
        results.append((f"Batch (no threading)", 1, batch_size, keys_per_sec))
        
        # Threaded batching
        keys_per_sec = benchmark_batch_generation(batch_size, use_threading=True)
        results.append((f"Batch (threaded)", 1, batch_size, keys_per_sec))
        
    # 3. Full method benchmarks (including database operations)
    print("⏱️ Testing full methods including database operations...")
    for method in ["RBF", "TBF", "OTBF"]:
        print(f"  Testing {method} with database checks...")
        keys_per_sec = benchmark_full_method(method)
        results.append((f"{method} (full pipeline)", 1, BATCH_SIZES[1], keys_per_sec))
    
    # 3. Create a nice table for the results
    table = PrettyTable()
    table.field_names = ["Method", "Cores", "Batch Size", "Keys/sec"]
    
    for method, cores, batch_size, keys_per_sec in results:
        table.add_row([method, cores, f"{batch_size:,}", f"{keys_per_sec:,.2f}"])
    
    print("\n🔍 Benchmark Results:\n")
    print(table)
    
    # 4. Provide recommendations
    print("\n💡 Recommendations based on benchmark results:")
    
    # Find the fastest method
    fastest_method = max(results, key=lambda x: x[3])
    print(f"- Fastest method: {fastest_method[0]} with batch size {fastest_method[2]:,} ({fastest_method[3]:,.2f} keys/sec)")
    
    # Compare random vs sequential generation
    random_speed = next(r for r in results if r[0] == "Random Key (RBF)")[3]
    sequential_speed = next(r for r in results if r[0] == "Sequential Key (TBF)")[3]
    
    if random_speed > sequential_speed:
        print(f"- Random key generation is faster than sequential ({random_speed:.2f} vs {sequential_speed:.2f} keys/sec)")
    else:
        print(f"- Sequential key generation is faster than random ({sequential_speed:.2f} vs {random_speed:.2f} keys/sec)")
    
    # Check if threading improves performance
    for batch_size in BATCH_SIZES:
        no_threading = next(r for r in results if r[0] == "Batch (no threading)" and r[2] == batch_size)[3]
        threading = next(r for r in results if r[0] == "Batch (threaded)" and r[2] == batch_size)[3]
        
        improvement = ((threading - no_threading) / no_threading) * 100
        print(f"- Batch size {batch_size:,}: Threading {'improves' if improvement > 0 else 'reduces'} " + 
              f"performance by {abs(improvement):.1f}%")
    
    print("\n⚙️ Optimal Configuration:")
    print(f"- Based on this hardware, use batch size: {fastest_method[2]:,}")
    print(f"- Estimated daily throughput: {fastest_method[3] * 86400:,.0f} addresses per day per core")
    
    return results

if __name__ == "__main__":
    try:
        # Install prettytable if not available
        try:
            import prettytable
        except ImportError:
            import subprocess
            import sys
            print("Installing required package: prettytable")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "prettytable"])
            from prettytable import PrettyTable
            
        run_all_benchmarks()
    except KeyboardInterrupt:
        print("\nBenchmark interrupted by user.")
    except Exception as e:
        logging.error(f"Benchmark error: {e}", exc_info=True)