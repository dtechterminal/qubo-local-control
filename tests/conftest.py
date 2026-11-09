"""Import the protocol module without loading Home Assistant."""
from pathlib import Path
import sys
import types

root = Path(__file__).parents[1] / "custom_components" / "qubo_local"
package = types.ModuleType("qubo")
package.__path__ = [str(root)]
sys.modules["qubo"] = package
