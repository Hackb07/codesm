use pyo3::prelude::*;
use std::env;

/// Get platform information
#[pyfunction]
pub fn get_platform_info() -> PyResult<(String, String, String)> {
    let os = env::consts::OS.to_string();
    let arch = env::consts::ARCH.to_string();
    let family = env::consts::FAMILY.to_string();
    Ok((os, arch, family))
}
