"""Run the local Vridhi FastAPI sandbox with mobile local network support."""

import argparse
import socket
import uvicorn


def get_local_ip() -> str:
    """Find local Wi-Fi / LAN IP address for mobile phone access."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main() -> None:
    parser = argparse.ArgumentParser(description="Vridhi Analytics local server runner")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface (0.0.0.0 allows mobile phone access)")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default 8000)")
    args = parser.parse_args()

    local_ip = get_local_ip()
    print("=" * 65)
    print(" 🚀 VRIDHI ANALYTICS SERVER STARTED")
    print(f" 💻 PC Access URL     : http://127.0.0.1:{args.port}/app/")
    print(f" 📱 Mobile Access URL : http://{local_ip}:{args.port}/app/")
    print(" ℹ️  Ensure your mobile phone & laptop are on the SAME Wi-Fi")
    print("    or connect phone to laptop's Mobile Hotspot!")
    print("=" * 65)

    uvicorn.run("vridhi_sim.backend:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
