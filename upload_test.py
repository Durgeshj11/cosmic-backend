import os
from pinecone import Pinecone
import numpy as np

# 1. Connect to your live index
pc = Pinecone(api_key="pcsk_73tb2T_GzxuRjuN1yDh82mSobnKVscAm37JcR4NySuR8TyT7ZWP6t4MXLwTNVTsVudpnxU")
index = pc.Index("cosmic-resonance-grid")

def add_user_to_grid(user_id, name, sign, life_path):
    # This creates the 1024D vector that matches your index settings
    vibe_vector = np.random.uniform(-1, 1, 1024).tolist()
    
    index.upsert(
        vectors=[{
            "id": user_id, 
            "values": vibe_vector, 
            "metadata": {"name": name, "sign": sign, "life_path": life_path}
        }]
    )
    print(f"✅ Successfully indexed {name}!")

# 2. Run the test
if __name__ == "__main__":
    add_user_to_grid("test_01", "Aria", "Leo", 7)