from pathlib import Path
from dotenv import dotenv_values

root = Path(__file__).resolve().parents[1]
env_path = root / ".env"
config = dotenv_values(env_path)

print("env_path =", env_path)
print("exists =", env_path.exists())
print(config)