async fn try_bibtex() -> anyhow::Result<()> {
    let bibtex = undr::Configuration::from_path(
        std::fs::canonicalize(std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")))?
            .join("tests")
            .join("undr.toml"),
    )?
    .bibtex(
        |message| {
            println!("{:?}", message);
        },
        false,
        32,
        32,
        None,
        true,
    )
    .await?;
    std::fs::write(
        std::fs::canonicalize(std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")))?
            .join("tests")
            .join("test.bib"),
        bibtex,
    )?;
    Ok(())
}

#[tokio::test]
async fn bibtex() {
    if let Err(error) = try_bibtex().await {
        eprintln!("{:?}", error);
        eprintln!("{:#?}", error);
        std::process::exit(1);
    }
}
