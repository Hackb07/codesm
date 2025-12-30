use pyo3::prelude::*;
use ignore::WalkBuilder;

/// List all files in a directory, respecting .gitignore
#[pyfunction]
#[pyo3(signature = (root, max_depth=None))]
pub fn list_files(root: &str, max_depth: Option<usize>) -> PyResult<Vec<String>> {
    let mut files = Vec::new();
    
    let mut builder = WalkBuilder::new(root);
    if let Some(depth) = max_depth {
        builder.max_depth(Some(depth));
    }
    
    for entry in builder.build() {
        match entry {
            Ok(e) => {
                if e.file_type().map(|ft| ft.is_file()).unwrap_or(false) {
                    if let Some(path) = e.path().to_str() {
                        files.push(path.to_string());
                    }
                }
            }
            Err(_) => continue,
        }
    }
    
    files.sort();
    Ok(files)
}
