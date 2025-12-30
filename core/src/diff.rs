use pyo3::prelude::*;
use similar::{ChangeTag, TextDiff};

/// Generate a unified diff between two strings
#[pyfunction]
pub fn diff_files(old: &str, new: &str, _filename: &str) -> String {
    let diff = TextDiff::from_lines(old, new);
    let mut result = String::new();

    for (idx, group) in diff.grouped_ops(3).iter().enumerate() {
        if idx > 0 {
            result.push_str("...\n");
        }
        for op in group {
            for change in diff.iter_changes(op) {
                let sign = match change.tag() {
                    ChangeTag::Delete => "-",
                    ChangeTag::Insert => "+",
                    ChangeTag::Equal => " ",
                };
                result.push_str(&format!("{}{}", sign, change.value()));
            }
        }
    }
    result
}

/// Apply an edit by replacing old_content with new_content in the file
#[pyfunction]
pub fn apply_edit(content: &str, old_content: &str, new_content: &str) -> PyResult<String> {
    if !content.contains(old_content) {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "Could not find content to replace"
        ));
    }
    Ok(content.replacen(old_content, new_content, 1))
}
