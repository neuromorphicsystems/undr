use crate::types;

pub fn write<P: AsRef<std::path::Path>>(
    path: P,
    doi_to_path_ids_and_content: &std::collections::HashMap<
        types::Doi,
        (Vec<types::PathId>, Option<String>),
    >,
) -> std::io::Result<()> {
    std::fs::write(&path, {
        let mut dois_and_path_ids_and_content = doi_to_path_ids_and_content
            .iter()
            .map(|(doi, (ref path_ids, ref content))| {
                let mut path_ids = path_ids.clone();
                path_ids.sort_by(|a, b| a.0.cmp(&b.0));
                (doi, path_ids, content)
            })
            .collect::<Vec<(&types::Doi, Vec<types::PathId>, &Option<String>)>>();
        dois_and_path_ids_and_content
            .sort_by(|a, b| a.1.first().unwrap().0.cmp(&b.1.first().unwrap().0));
        let mut combined = String::new();
        for (doi, path_ids, content) in dois_and_path_ids_and_content {
            if !combined.is_empty() {
                combined.push('\n');
            }
            if path_ids.len() < 6 {
                combined.push_str(&format!(
                    "% {}\n",
                    path_ids
                        .iter()
                        .map(|path_id| &*path_id.0)
                        .collect::<Vec<&str>>()
                        .join(", "),
                ));
            } else {
                combined.push_str(&format!(
                    "% {}, ... ({} more), {}\n",
                    path_ids
                        .iter()
                        .take(3)
                        .map(|path_id| &*path_id.0)
                        .collect::<Vec<&str>>()
                        .join(", "),
                    path_ids.len() - 4,
                    path_ids.last().unwrap().0,
                ));
            }
            combined.push_str(&format!("% DOI {}\n", &doi.0));
            if let Some(content) = content {
                combined.push_str(content);
            }
        }
        combined
    })
}

pub fn prettify(bibtex: &String) -> String {
    let mut prettified_bibtex = String::new();
    prettified_bibtex.reserve(bibtex.len());
    let mut new_line = true;
    let mut depth = 0i32;
    for character in bibtex.chars() {
        if new_line && !character.is_ascii_whitespace() {
            new_line = false;
            for _ in 0..(4 * (if character == '}' { depth - 1 } else { depth })) {
                prettified_bibtex.push(' ');
            }
        }
        match character {
            '{' => {
                depth += 1;
                prettified_bibtex.push('{');
            }
            '}' => {
                depth -= 1;
                prettified_bibtex.push('}');
            }
            '\n' => {
                new_line = true;
                prettified_bibtex.push('\n');
            }
            character if character.is_ascii_whitespace() => {
                if !new_line {
                    prettified_bibtex.push(character);
                }
            }
            character => {
                prettified_bibtex.push(character);
            }
        }
    }
    if !prettified_bibtex.ends_with('\n') {
        prettified_bibtex.push('\n')
    }
    prettified_bibtex
}
