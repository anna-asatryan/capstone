from __future__ import annotations

import argparse

from dash import Dash, html

from codes.summary_app.data_loader import load_analysis_bundle
from codes.summary_app.layout import build_layout


def create_app(data_dir: str | None = None) -> Dash:
    bundle = load_analysis_bundle(data_dir)
    app = Dash(__name__, title="Loan Decision Study — Results Explorer")
    app.layout = html.Div(build_layout(bundle))
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the summary visualization app.")
    parser.add_argument("--data-dir", default=None, help="Analysis bundle directory to visualize.")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface for the Dash server.")
    parser.add_argument("--port", default=8050, type=int, help="Port for the Dash server.")
    parser.add_argument("--debug", action="store_true", help="Run Dash in debug mode.")
    args = parser.parse_args()

    app = create_app(args.data_dir)
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
