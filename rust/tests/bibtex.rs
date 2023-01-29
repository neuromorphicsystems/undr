async fn try_bibtex() -> anyhow::Result<()> {
    undr::Configuration::from_path(
        std::fs::canonicalize(std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")))?
            .join("tests")
            .join("undr.toml"),
    )?
    .0
    .bibtex(
        std::sync::Arc::new(std::sync::atomic::AtomicBool::new(true)),
        |message| {
            println!("{:?}", message);
        },
        undr::Force(false),
        undr::FilePermits(64),
        undr::DownloadIndexPermits(32),
        undr::DownloadDoiPermits(8),
        None,
        std::fs::canonicalize(std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")))?
            .join("tests")
            .join("test.bib"),
        undr::Pretty(true),
    )
    .await?;
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
