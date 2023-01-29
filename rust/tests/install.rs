async fn try_install() -> anyhow::Result<()> {
    let configuration = undr::Configuration::from_path(
        std::fs::canonicalize(std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")))?
            .join("tests")
            .join("undr.toml"),
    )?;
    configuration
        .0
        .install(
            std::sync::Arc::new(std::sync::atomic::AtomicBool::new(true)),
            |message| {
                println!("{:?}", message);
            },
            undr::Force(true),
            undr::Keep(false),
            undr::DispatchDois(false),
            undr::CalculateSize(false),
            undr::FilePermits(64),
            undr::DownloadIndexPermits(32),
            undr::DownloadPermits(32),
            undr::DecodePermits(
                std::thread::available_parallelism()
                    .unwrap_or(std::num::NonZeroUsize::new(1).unwrap())
                    .get()
                    * 2,
            ),
        )
        .await?;
    Ok(())
}

#[tokio::test]
async fn install() {
    if let Err(error) = try_install().await {
        eprintln!("{:?}", error);
        eprintln!("{:#?}", error);
        std::process::exit(1);
    }
}
