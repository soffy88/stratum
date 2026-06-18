import asyncio
import os
import sys
import duckdb

# Add src to path
sys.path.append("/app/src")

from stratum.services.graph_builder_service import build_graph_from_substrate
from stratum.utils.user_id_hash import hash_user_id
from stratum.api.main import _register_providers

async def main():
    _register_providers()
    user_id = "soffy88@gmail.com"
    uh = hash_user_id(user_id)
    
    # Substrates to process
    # You can customize this list or query DuckDB for substrates missing graph data
    sids = [
        "01KVA1543MHXGSWQ79SSRBGR83", # 基础拓扑学讲义
        "01KVA18DGJJD77G8MHNCQWA5AS", # 哈工大泛函分析课程笔记
        "01KVA1KZS57MJGBNJZ4RMR4ARR", # 泛函分析－侯友良
    ]
    
    for sid in sids:
        print(f"Building graph for {sid}...")
        try:
            res = await build_graph_from_substrate(sid, uh)
            print(f"  Result: {res}")
        except Exception as e:
            print(f"  Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
