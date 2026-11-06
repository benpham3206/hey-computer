# e2e fixtures

`scripts/e2e_unattended.py` writes `hey_alone_placeholder.wav` here when it is missing.
It is 1 s silence, 0.5 s 440 Hz tone, 1 s silence (16 kHz mono 16-bit). It must **not** wake.
`*.wav` is gitignored, so the harness regenerates it on a fresh clone.

A real "hey computer" capture is still to do. When you have one (16 kHz mono 16-bit), run:

```sh
python -u scripts/e2e_unattended.py --mode hey-alone --input-wav tests/e2e_fixtures/hey_computer.wav --expect-wake
```
