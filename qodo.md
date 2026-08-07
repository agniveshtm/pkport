<img src="https://img.shields.io/badge/Review_recommended-634FD1?style=flat-square" height="20px" alt="Remediation recommended">

1\. Pid heuristic cross-platform <code>🐞 Bug</code> <code>≡ Correctness</code>

<pre>
is_system_process() classifies any PID &lt; 5 as system-level on every OS, which can wrongly refuse
killing legitimate user-space services that happen to run with low PIDs in some environments (e.g.,
PID 1 in containers/minimal init setups). This makes pkport’s new kill refusal trigger based on a
Windows-specific PID assumption outside Windows.
</pre>


<details>
<summary><strong>Agent Prompt</strong></summary>

```
## Issue description
`is_system_process()` currently treats any PID `< SYSTEM_PID_THRESHOLD` (5) as a system-level process on all platforms. This threshold is justified by a Windows example (PID 4 = “System”), but on non-Windows systems low PIDs (especially PID 1) are not guaranteed to represent kernel/OS-owned processes in all environments.

## Issue Context
- `SYSTEM_PID_THRESHOLD = 5` is defined globally and used unconditionally.
- The repository explicitly targets Linux/macOS/Windows.

## Fix Focus Areas
- src/pkport/main.py[28-41]
- src/pkport/main.py[122-127]

## Suggested fix
- Apply the `pid < SYSTEM_PID_THRESHOLD` heuristic only on Windows (e.g., `sys.platform == "win32"`).
- For non-Windows, rely on the curated `SYSTEM_PROCESS_NAMES` list (and/or add a more OS-appropriate PID rule if needed).
- Add a regression test for a non-Windows-like row such as `PortRow(port=..., pids={1}, names={"myapp"})` to ensure it is **not** classified as system-level when running under the non-Windows branch of the logic.
```

<code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
</details>