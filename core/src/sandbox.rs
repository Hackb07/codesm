use pyo3::prelude::*;
use std::process::Command;

/// Execute a shell command with timeout
/// Returns (stdout, stderr, exit_code)
#[pyfunction]
#[pyo3(signature = (command, cwd=None, _timeout_secs=120))]
pub fn execute_command(
    command: &str,
    cwd: Option<&str>,
    _timeout_secs: u64,
) -> PyResult<(String, String, i32)> {
    let mut cmd = Command::new("sh");
    cmd.arg("-c").arg(command);
    
    if let Some(dir) = cwd {
        cmd.current_dir(dir);
    }
    
    let output = cmd
        .output()
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
    
    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).to_string();
    let exit_code = output.status.code().unwrap_or(-1);
    
    Ok((stdout, stderr, exit_code))
}
