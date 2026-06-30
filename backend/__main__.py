"""Entry point: `python -m backend`."""
import uvicorn

from backend.config import get_settings


def main() -> None:
    s = get_settings()
    uvicorn.run(
        "backend.main:app",
        host=s.host,
        port=s.port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()