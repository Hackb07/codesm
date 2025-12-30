use pyo3::prelude::*;

mod diff;
mod sandbox;
mod index;
mod platform;

use diff::{diff_files, apply_edit};
use sandbox::execute_command;
use index::list_files;
use platform::get_platform_info;

/// Python module for codesm core functionality
#[pymodule]
fn codesm_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(diff_files, m)?)?;
    m.add_function(wrap_pyfunction!(apply_edit, m)?)?;
    m.add_function(wrap_pyfunction!(execute_command, m)?)?;
    m.add_function(wrap_pyfunction!(list_files, m)?)?;
    m.add_function(wrap_pyfunction!(get_platform_info, m)?)?;
    Ok(())
}
