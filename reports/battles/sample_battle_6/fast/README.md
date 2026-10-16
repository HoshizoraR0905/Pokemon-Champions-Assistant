# Battle 6 adaptive fast profile experiment

The M2.3.7 baseline remains frozen and separate. Profile implementation and
commands: [fast-recognition.md](../../../../docs/fast-recognition.md).

Current run: `fast-v2-cold-1`. Its cold benchmark includes the normal CLI process,
source decoding, adaptive inspection, model inference, existing StateEngine
replay, event/evidence comparisons and offline viewer packaging. Completion,
measured results, limitations and exact resume instructions will be recorded
here after validation. This is an experiment, not independent semantic acceptance.

Earlier attempts are retained locally: `fast-v1-probe` failed at an OCR adapter
signature mismatch; `fast-v1-probe-2` completed a 30-second pipeline probe.
`fast-v1-cold-1` was deliberately interrupted after a synthetic one-character
change regression exposed overly permissive reuse. Its successful prefix,
source archive and interruption note remain intact. None is a substitute for a
completed full-video cold benchmark. No original Battle 6 or human annotation
artifact is replaced by these experiments.

Resume the current run only if its process has stopped and its identity still
matches:

```sh
.venv/bin/python main.py --video tests/fixtures/sample_battle_6.mp4 \
  --profile fast --run-id fast-v2-cold-1 --resume
```

A resumed run is not a fresh cold benchmark. Do not run a duplicate process.
