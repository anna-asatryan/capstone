#!/usr/bin/env bash
set -euo pipefail

uvx --from quarto-cli quarto render paper.qmd

# ./slides_preview.sh tableau 1