import os
import sqlite3
import json
import time
from typing import Dict, Any, Optional

class CacheManager:
    def __init__(self, db_dir: str = "./data"):
        os.makedirs(db_dir, exist_ok=True)
        self.db_path = os.path.join(db_dir, "cache.db")
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Create brief cache table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS brief_cache (
                    file_hash TEXT PRIMARY KEY,
                    brief_json TEXT,
                    created_at REAL
                )
            """)
            # Create copilot Q&A cache table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS copilot_cache (
                    file_hash TEXT,
                    question TEXT,
                    answer_json TEXT,
                    created_at REAL,
                    PRIMARY KEY (file_hash, question)
                )
            """)
            # Create stats tracking table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_stats (
                    stat_name TEXT PRIMARY KEY,
                    stat_val REAL
                )
            """)
            # Initialize stats if not present
            default_stats = {
                "total_api_calls": 0.0,
                "total_tokens_used": 0.0,
                "total_cost": 0.0,
                "saved_api_calls": 0.0,  # Redundant calls prevented
                "saved_cost": 0.0,       # Dollars saved
                "cache_hits": 0.0,
                "cache_misses": 0.0
            }
            for name, val in default_stats.items():
                cursor.execute("""
                    INSERT OR IGNORE INTO system_stats (stat_name, stat_val)
                    VALUES (?, ?)
                """, (name, val))
            conn.commit()

    def get_cached_brief(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves cached brief JSON if available.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT brief_json FROM brief_cache WHERE file_hash = ?", (file_hash,))
                row = cursor.fetchone()
                if row:
                    # Record a cache hit
                    self.increment_stat("cache_hits", 1.0)
                    # We saved 3 calls by hitting the cache instead of doing 3 separate LLM calls
                    self.increment_stat("saved_api_calls", 3.0)
                    # Estimate dollars saved (assume typical brief cost is ~$0.015)
                    self.increment_stat("saved_cost", 0.015)
                    return json.loads(row[0])
        except Exception as e:
            print(f"Error reading cache ({e})")
        return None

    def save_brief_to_cache(self, file_hash: str, brief_data: Dict[str, Any]):
        """
        Caches the generated brief JSON.
        """
        try:
            brief_json = json.dumps(brief_data)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO brief_cache (file_hash, brief_json, created_at)
                    VALUES (?, ?, ?)
                """, (file_hash, brief_json, time.time()))
                conn.commit()
            self.increment_stat("cache_misses", 1.0)
        except Exception as e:
            print(f"Error saving to cache ({e})")

    def get_stats(self) -> Dict[str, float]:
        """
        Gets all metrics for the dashboard.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT stat_name, stat_val FROM system_stats")
                rows = cursor.fetchall()
                return {name: val for name, val in rows}
        except Exception as e:
            print(f"Error getting stats ({e})")
            return {}

    def increment_stat(self, name: str, amount: float = 1.0):
        """
        Increments a specific statistic.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE system_stats
                    SET stat_val = stat_val + ?
                    WHERE stat_name = ?
                """, (amount, name))
                conn.commit()
        except Exception as e:
            print(f"Error incrementing stat {name} ({e})")

    def record_llm_call(self, tokens_used: int, cost: float):
        """
        Records details of an active LLM call.
        """
        self.increment_stat("total_api_calls", 1.0)
        self.increment_stat("total_tokens_used", float(tokens_used))
        self.increment_stat("total_cost", cost)
        # By doing a single pass structured call instead of 3 individual calls, we saved 2 calls!
        self.increment_stat("saved_api_calls", 2.0)
        # Estimate saving of 2 extra calls (~$0.01)
        self.increment_stat("saved_cost", 0.01)

    def reset_stats(self):
        """
        Resets tracking stats back to zero for demonstration purposes.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE system_stats SET stat_val = 0.0")
                conn.commit()
        except Exception as e:
            print(f"Error resetting stats ({e})")

    def get_cached_copilot(self, file_hash: str, question: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves cached copilot Q&A response if available.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT answer_json FROM copilot_cache WHERE file_hash = ? AND question = ?",
                    (file_hash, question.lower().strip())
                )
                row = cursor.fetchone()
                if row:
                    # Record a cache hit
                    self.increment_stat("cache_hits", 1.0)
                    self.increment_stat("saved_api_calls", 1.0)
                    self.increment_stat("saved_cost", 0.005)
                    return json.loads(row[0])
        except Exception as e:
            print(f"Error reading copilot cache ({e})")
        return None

    def save_copilot_to_cache(self, file_hash: str, question: str, answer_data: Dict[str, Any]):
        """
        Caches the copilot Q&A response.
        """
        try:
            answer_json = json.dumps(answer_data)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO copilot_cache (file_hash, question, answer_json, created_at)
                    VALUES (?, ?, ?, ?)
                """, (file_hash, question.lower().strip(), answer_json, time.time()))
                conn.commit()
            self.increment_stat("cache_misses", 1.0)
        except Exception as e:
            print(f"Error saving to copilot cache ({e})")
