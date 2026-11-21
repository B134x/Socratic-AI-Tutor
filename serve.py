"""Start the TUNTAS prototype from any working directory: python path/to/serve.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tuntas.server import main  # noqa: E402

if __name__ == "__main__":
    main()
