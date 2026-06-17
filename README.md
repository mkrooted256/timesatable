# TimeSATable
A timetable compiler for personal usage based on WBO SAT solver.

Usage

```bash
# in repo dir
uv sync
uv run timesatable example
uv run timesatable validate example.yaml
uv run timesatable solve example.yaml
```

**Note:** bin/wbo is a WBO binary from https://sat.inesc-id.pt/wbo/index.html.  
I included it in the repo to make things simpler, but I am not sure about its license.
Please, contact me if you think I am violating your rights.
