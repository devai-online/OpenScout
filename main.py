"""LeadFinder launcher. `python main.py` starts the web UI."""

import uvicorn
from config import HOST, PORT


def main():
    uvicorn.run("server.api:app", host=HOST, port=PORT, reload=False, log_level="info")


if __name__ == "__main__":
    main()
