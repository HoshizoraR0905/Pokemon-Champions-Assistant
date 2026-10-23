#!/bin/sh
set -eu
report_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_dir=$(CDPATH= cd -- "$report_dir/../.." && pwd)
build_dir="$repo_dir/.cache/document-build/m352"
mkdir -p "$build_dir"
cd "$report_dir"
for pass in 1 2 3; do
  pdflatex -interaction=nonstopmode -halt-on-error -file-line-error \
    -output-directory="$build_dir" report.tex > "$build_dir/pass-$pass.stdout"
done
cp "$build_dir/report.pdf" "$report_dir/report.pdf"
printf 'Built %s\n' "$report_dir/report.pdf"
