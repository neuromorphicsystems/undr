use futures::future::FutureExt;

#[macro_use(lazy_static)]
extern crate lazy_static;

mod configuration;
mod constants;
mod decode;
mod json_index;
mod remote;
mod types;
pub use configuration::Configuration;

#[derive(Debug)]
pub struct Value {
    initial_bytes: u64,
    final_bytes: u64,
}

impl Value {
    fn new() -> Self {
        Self {
            initial_bytes: 0,
            final_bytes: 0,
        }
    }
}

#[derive(Debug)]
pub struct DirectoryScanned {
    pub path_id: types::PathId,
    pub initial_download_count: u64,
    pub initial_process_count: u64,
    pub final_count: u64,
    pub index: Value,
    pub download: Value,
    pub process: Value,
}

#[derive(Debug)]
pub enum InstallMessage {
    Initialized {
        datasets: Vec<(types::Name, configuration::Mode)>,
    },
    IndexLoaded {
        path_id: types::PathId,
        children: usize,
    },
    DirectoryScanned(DirectoryScanned),
    Doi {
        path_id: types::PathId,
        value: types::Doi,
    },
    Progress(types::Progress),
}

impl From<types::Progress> for InstallMessage {
    fn from(item: types::Progress) -> Self {
        InstallMessage::Progress(item)
    }
}

#[derive(Debug)]
pub enum BibtexMessage {
    InstallMessage(InstallMessage),
    DoiStart(types::Doi),
    DoiSuccess(types::Doi),
    DoiError(types::Doi),
}

#[derive(Debug, thiserror::Error)]
pub enum InstallError {
    #[error("download error")]
    Download(#[from] remote::DownloadError),

    #[error("decompress error")]
    Decompress(#[from] decode::DecompressError),

    #[error("task error")]
    Join(#[from] tokio::task::JoinError),

    #[error("directory error")]
    Directory(#[from] std::io::Error),

    #[error("read error")]
    Read(std::path::PathBuf),

    #[error("index parse error")]
    Parse(#[from] serde_json::Error),

    #[error("semaphore error")]
    Semaphore(#[from] tokio::sync::AcquireError),

    #[error("TLS initialisation error")]
    Tls(#[from] reqwest::Error),

    #[error("DOI download error")]
    DoiError(String),
}

#[allow(clippy::too_many_arguments)]
fn index_directory(
    running: std::sync::Arc<std::sync::atomic::AtomicBool>,
    server: remote::Server,
    sender: tokio::sync::mpsc::UnboundedSender<InstallMessage>,
    path_root: types::PathRoot,
    path_id: types::PathId,
    force: bool,
    keep: bool,
    dispatch_dois: bool,
    mode: configuration::InstallableMode,
    download_semaphore: std::sync::Arc<tokio::sync::Semaphore>,
    decode_semaphore: std::sync::Arc<tokio::sync::Semaphore>,
) -> std::pin::Pin<
    std::boxed::Box<dyn futures::future::Future<Output = Result<(), InstallError>> + Send>,
> {
    async move {
        std::fs::create_dir_all(path_root.join(&path_id))?;
        let index_path_id = path_id.join(&types::Name("-index.json".to_owned()));
        let index_file_path = path_root.join(&index_path_id);
        let mut directory_scanned = DirectoryScanned {
            path_id: path_id.clone(),
            initial_download_count: 0,
            initial_process_count: 0,
            final_count: 0,
            index: if force {
                Value::new()
            } else {
                match std::fs::metadata(&index_file_path) {
                    Ok(metadata) if metadata.file_type().is_file() => Value {
                        initial_bytes: metadata.len(),
                        final_bytes: metadata.len(),
                    },
                    _ => match std::fs::metadata(
                        path_root.join_with_suffix(&index_path_id, constants::DOWNLOAD_SUFFIX),
                    ) {
                        Ok(metadata) if metadata.file_type().is_file() => Value {
                            initial_bytes: metadata.len(),
                            final_bytes: 0,
                        },
                        _ => Value::new(),
                    },
                }
            },
            download: Value::new(),
            process: Value::new(),
        };
        server
            .download_file(
                &sender,
                path_root.clone(),
                &index_path_id,
                force,
                None,
                None,
                &types::Name(String::new()),
            )
            .await?;
        let index: json_index::Index = serde_json::from_reader(std::io::BufReader::new(
            std::fs::File::open(path_root.join(&index_path_id))
                .map_err(|_| InstallError::Read(path_root.join(&index_path_id)))?,
        ))?;
        sender
            .send(InstallMessage::IndexLoaded {
                path_id: path_id.clone(),
                children: index.directories.len(),
            })
            .unwrap();
        if dispatch_dois {
            if let Some(doi) = &index.doi {
                sender
                    .send(InstallMessage::Doi {
                        path_id: path_id.clone(),
                        value: doi.clone(),
                    })
                    .unwrap();
            }
        }
        let mut join_set = tokio::task::JoinSet::new();
        for directory in index.directories {
            let running = running.clone();
            let server = server.clone();
            let sender = sender.clone();
            let path_root = path_root.clone();
            let path_id = path_id.join(&directory);
            let download_semaphore = download_semaphore.clone();
            let decode_semaphore = decode_semaphore.clone();
            join_set.spawn(async move {
                index_directory(
                    running,
                    server,
                    sender,
                    path_root,
                    path_id,
                    force,
                    keep,
                    dispatch_dois,
                    mode,
                    download_semaphore,
                    decode_semaphore,
                )
                .await?;
                Ok::<(), InstallError>(())
            });
        }
        if directory_scanned.index.final_bytes == 0 {
            directory_scanned.index.final_bytes = match std::fs::metadata(&index_file_path) {
                Ok(metadata) if metadata.file_type().is_file() => metadata.len(),
                _ => return Err(InstallError::Read(index_file_path)),
            }
        }
        match mode {
            configuration::InstallableMode::Local | configuration::InstallableMode::Raw => {
                for resource in index.files.iter().map(|file| &file.resource).chain(
                    index
                        .other_files
                        .iter()
                        .map(|other_file| &other_file.resource),
                ) {
                    let (_, compression_properties) = resource.best_compression();
                    directory_scanned.final_count += 1;
                    directory_scanned.download.final_bytes += compression_properties.size;
                    if mode == configuration::InstallableMode::Raw {
                        directory_scanned.process.final_bytes += resource.size;
                    }
                    let resource_path_id = path_id.join(&resource.name);
                    if dispatch_dois {
                        if let Some(doi) = &resource.doi {
                            sender
                                .send(InstallMessage::Doi {
                                    path_id: path_id.join(&resource.name),
                                    value: doi.clone(),
                                })
                                .unwrap();
                        }
                    }
                    if !force {
                        match std::fs::metadata(path_root.join(&resource_path_id)) {
                            Ok(metadata) if metadata.file_type().is_file() => {
                                directory_scanned.initial_download_count += 1;
                                directory_scanned.download.initial_bytes += metadata.len();
                                if mode == configuration::InstallableMode::Raw {
                                    directory_scanned.initial_process_count += 1;
                                    directory_scanned.process.initial_bytes += metadata.len();
                                }
                            }
                            _ => match std::fs::metadata(path_root.join_with_suffix(
                                &resource_path_id,
                                &compression_properties.suffix.0,
                            )) {
                                Ok(metadata) if metadata.file_type().is_file() => {
                                    directory_scanned.initial_download_count += 1;
                                    directory_scanned.download.initial_bytes += metadata.len();
                                }
                                _ => match std::fs::metadata(path_root.join_with_suffixes(
                                    &resource_path_id,
                                    &compression_properties.suffix.0,
                                    constants::DOWNLOAD_SUFFIX,
                                )) {
                                    Ok(metadata) if metadata.file_type().is_file() => {
                                        directory_scanned.download.initial_bytes += metadata.len();
                                    }
                                    _ => (),
                                },
                            },
                        }
                    }
                }
            }
            configuration::InstallableMode::Remote => {
                if dispatch_dois {
                    for resource in index.files.iter().map(|file| &file.resource).chain(
                        index
                            .other_files
                            .iter()
                            .map(|other_file| &other_file.resource),
                    ) {
                        if let Some(doi) = &resource.doi {
                            sender
                                .send(InstallMessage::Doi {
                                    path_id: path_id.join(&resource.name),
                                    value: doi.clone(),
                                })
                                .unwrap();
                        }
                    }
                }
            }
        }
        sender
            .send(InstallMessage::DirectoryScanned(directory_scanned))
            .unwrap();
        match mode {
            configuration::InstallableMode::Local | configuration::InstallableMode::Raw => {
                for resource in index.files.iter().map(|file| &file.resource).chain(
                    index
                        .other_files
                        .iter()
                        .map(|other_file| &other_file.resource),
                ) {
                    let running = running.clone();
                    let server = server.clone();
                    let sender = sender.clone();
                    let path_root = path_root.clone();
                    let path_id = path_id.join(&resource.name);
                    let (compression, compression_properties) = resource.best_compression();
                    let compression = compression.clone();
                    let expected_download_size = compression_properties.size;
                    let expected_download_hash = compression_properties.hash.clone();
                    let suffix = compression_properties.suffix.clone();
                    let download_semaphore = download_semaphore.clone();
                    let decode_semaphore = decode_semaphore.clone();
                    let expected_decode_size = resource.size;
                    let expected_decode_hash = resource.hash.clone();
                    join_set.spawn(async move {
                        {
                            let _permit = download_semaphore.acquire().await?;
                            server
                                .download_file(
                                    &sender,
                                    path_root.clone(),
                                    &path_id,
                                    force,
                                    Some(expected_download_size),
                                    Some(expected_download_hash),
                                    &suffix,
                                )
                                .await?;
                        }
                        if mode == configuration::InstallableMode::Raw {
                            match compression {
                                json_index::Compression::NoneCompression { suffix: _ } => (),
                                json_index::Compression::Brotli {
                                    size: _,
                                    hash: _,
                                    suffix: _,
                                } => {
                                    let permit = decode_semaphore.acquire_owned().await?;
                                    let sender = sender.clone();
                                    let path_root = path_root.clone();
                                    let suffix = suffix.clone();
                                    tokio::task::spawn_blocking(move || {
                                        decode::brotli(
                                            running,
                                            &sender,
                                            path_root,
                                            &path_id,
                                            force,
                                            keep,
                                            expected_decode_size,
                                            &expected_decode_hash,
                                            &suffix,
                                        )?;
                                        drop(permit); // drop is called even if brotli returns an error
                                                      // it tells the compiler to move 'permit' inside the spawn_blocking closure
                                        Ok::<(), decode::DecompressError>(())
                                    })
                                    .await??;
                                }
                            }
                        }
                        Ok::<(), InstallError>(())
                    });
                }
            }
            configuration::InstallableMode::Remote => (),
        }
        while let Some(task) = join_set.join_next().await {
            match task {
                Ok(result) => match result {
                    Ok(()) => (),
                    Err(error) => return Err(error),
                },
                Err(error) => return Err(InstallError::Join(error)),
            }
        }
        Ok(())
    }
    .boxed()
}

impl Configuration {
    /// Download index files and download / decompress data files for local / raw datasets
    ///
    /// # Arguments
    ///
    /// * `running` -
    /// * `handle_message` -
    /// * `force` - download and decompress even if the files are already present
    /// * `keep` - do not delete compressed files after decompressing
    /// * `download_permits` -
    /// * `decode_permits` -
    #[allow(clippy::too_many_arguments)]
    pub async fn install<HandleMessage>(
        &self,
        running: std::sync::Arc<std::sync::atomic::AtomicBool>,
        mut handle_message: HandleMessage,
        force: bool,
        keep: bool,
        dispatch_dois: bool,
        download_permits: usize,
        decode_permits: usize,
    ) -> Result<(), InstallError>
    where
        HandleMessage: FnMut(InstallMessage),
    {
        let download_semaphore = std::sync::Arc::new(tokio::sync::Semaphore::new(download_permits));
        let decode_semaphore = std::sync::Arc::new(tokio::sync::Semaphore::new(decode_permits));
        let (sender, mut receiver) = tokio::sync::mpsc::unbounded_channel();
        let path_root = types::PathRoot(std::sync::Arc::<std::path::PathBuf>::from(
            self.directory.clone(),
        ));
        let mut join_set = tokio::task::JoinSet::new();
        for (dataset, mode) in self.datasets.iter().filter_map(|dataset| {
            configuration::InstallableMode::try_from(dataset.mode)
                .ok()
                .map(|mode| (dataset, mode))
        }) {
            let download_semaphore = download_semaphore.clone();
            let decode_semaphore = decode_semaphore.clone();
            join_set.spawn(index_directory(
                running.clone(),
                remote::Server::new(&dataset.url, &dataset.timeout)?,
                sender.clone(),
                path_root.clone(),
                types::PathId(dataset.name.0.clone()),
                force,
                keep,
                dispatch_dois,
                mode,
                download_semaphore,
                decode_semaphore,
            ));
        }
        sender
            .send(InstallMessage::Initialized {
                datasets: self
                    .datasets
                    .iter()
                    .filter(|dataset| dataset.mode != configuration::Mode::Disabled)
                    .map(|dataset| (dataset.name.clone(), dataset.mode))
                    .collect(),
            })
            .unwrap();
        drop(sender);
        let mut receiver_done = false;
        loop {
            tokio::select! {
                message = receiver.recv() => {
                    match message {
                        Some(message) => handle_message(message),
                        _ => {
                            receiver_done = true;
                            break;
                        }
                    }
                }
                task = join_set.join_next() => {
                    match task {
                        Some(task) => match task {
                            Ok(result) => match result {
                                Ok(()) => (),
                                Err(error) => {
                                    running.store(false, std::sync::atomic::Ordering::Release);
                                    return Err(error)
                                },
                            },
                            Err(error) => {
                                running.store(false, std::sync::atomic::Ordering::Release);
                                return Err(InstallError::Join(error));
                            }
                        }
                        _ => {
                            break;
                        }
                    }
                }
            }
        }
        if receiver_done {
            while let Some(task) = join_set.join_next().await {
                match task {
                    Ok(result) => match result {
                        Ok(()) => (),
                        Err(error) => {
                            running.store(false, std::sync::atomic::Ordering::Release);
                            return Err(error);
                        }
                    },
                    Err(error) => {
                        running.store(false, std::sync::atomic::Ordering::Release);
                        return Err(InstallError::Join(error));
                    }
                }
            }
        } else {
            while let Some(message) = receiver.recv().await {
                handle_message(message);
            }
        }
        Ok(())
    }

    pub async fn bibtex<HandleMessage>(
        &self,
        mut handle_message: HandleMessage,
        force: bool,
        download_permits: usize,
        doi_download_permits: usize,
        doi_timeout: Option<f64>,
        pretty: bool,
    ) -> Result<String, InstallError>
    where
        HandleMessage: FnMut(BibtexMessage),
    {
        let mut doi_to_path_ids_and_content =
            std::collections::HashMap::<types::Doi, (Vec<types::PathId>, Option<String>)>::new();
        let mut join_set = tokio::task::JoinSet::new();
        let client = reqwest::Client::builder()
            .connect_timeout(std::time::Duration::from_secs_f64(
                doi_timeout.unwrap_or(constants::DEFAULT_TIMEOUT),
            ))
            .build()?;
        let doi_download_semaphore =
            std::sync::Arc::new(tokio::sync::Semaphore::new(doi_download_permits));
        Configuration {
            directory: self.directory.clone(),
            datasets: self
                .datasets
                .iter()
                .map(|dataset| configuration::DatasetSettings {
                    name: dataset.name.clone(),
                    url: dataset.url.clone(),
                    mode: configuration::Mode::Remote,
                    timeout: dataset.timeout,
                })
                .collect(),
        }
        .install(
            std::sync::Arc::<std::sync::atomic::AtomicBool>::new(
                std::sync::atomic::AtomicBool::new(true),
            ),
            |message| {
                if let InstallMessage::Doi {
                    ref path_id,
                    ref value,
                } = message
                {
                    match doi_to_path_ids_and_content.get_mut(value) {
                        Some(path_ids_and_content) => path_ids_and_content.0.push(path_id.clone()),
                        None => {
                            handle_message(BibtexMessage::DoiStart(value.clone()));
                            doi_to_path_ids_and_content
                                .insert(value.clone(), (vec![path_id.clone()], None));
                            let client = client.clone();
                            let doi = value.clone();
                            let doi_download_semaphore = doi_download_semaphore.clone();
                            join_set.spawn(async move {
                                let _permit = doi_download_semaphore
                                    .acquire()
                                    .await
                                    .map_err(|error| (doi.clone(), error.into()))?;
                                let response = client
                                    .get(format!("https://doi.org/{}", &doi.0))
                                    .header(
                                        reqwest::header::ACCEPT,
                                        "application/x-bibtex; charset=utf-8",
                                    )
                                    .send()
                                    .await
                                    .map_err(|error| (doi.clone(), error.into()))?;
                                let status = response.status();
                                let content = response
                                    .text()
                                    .await
                                    .map_err(|error| (doi.clone(), error.into()))?;
                                if status.is_client_error() || status.is_server_error() {
                                    return Err((doi.clone(), InstallError::DoiError(content)));
                                }
                                if pretty {
                                    let mut bibtex = String::new();
                                    bibtex.reserve(content.len());
                                    let mut new_line = true;
                                    let mut depth = 0i32;
                                    for character in content.chars() {
                                        if new_line && !character.is_ascii_whitespace() {
                                            new_line = false;
                                            for _ in 0..(4
                                                * (if character == '}' {
                                                    depth - 1
                                                } else {
                                                    depth
                                                }))
                                            {
                                                bibtex.push(' ');
                                            }
                                        }
                                        match character {
                                            '{' => {
                                                depth += 1;
                                                bibtex.push('{');
                                            }
                                            '}' => {
                                                depth -= 1;
                                                bibtex.push('}');
                                            }
                                            '\n' => {
                                                new_line = true;
                                                bibtex.push('\n');
                                            }
                                            character if character.is_ascii_whitespace() => {
                                                if !new_line {
                                                    bibtex.push(character);
                                                }
                                            }
                                            character => {
                                                bibtex.push(character);
                                            }
                                        }
                                    }
                                    if !bibtex.ends_with('\n') {
                                        bibtex.push('\n')
                                    }
                                    Ok((doi, bibtex))
                                } else {
                                    Ok::<(types::Doi, String), (types::Doi, InstallError)>((
                                        doi, content,
                                    ))
                                }
                            });
                        }
                    }
                }
                handle_message(BibtexMessage::InstallMessage(message));
            },
            force,
            false,
            true,
            download_permits,
            1,
        )
        .await?;
        while let Some(task) = join_set.join_next().await {
            match task {
                Ok(result) => match result {
                    Ok((doi, content)) => {
                        handle_message(BibtexMessage::DoiSuccess(doi.clone()));
                        doi_to_path_ids_and_content.get_mut(&doi).unwrap().1 = Some(content);
                    }
                    Err((doi, error)) => {
                        handle_message(BibtexMessage::DoiError(doi.clone()));
                        doi_to_path_ids_and_content.get_mut(&doi).unwrap().1 =
                            Some(format!("% {:?}\n", error));
                    }
                },
                Err(error) => {
                    return Err(InstallError::Join(error));
                }
            }
        }
        let mut dois_and_path_ids_and_content = doi_to_path_ids_and_content
            .into_iter()
            .map(|(doi, (mut path_ids, content))| {
                path_ids.sort_by(|a, b| a.0.cmp(&b.0));
                (doi, path_ids, content.unwrap_or_else(|| "".to_owned()))
            })
            .collect::<Vec<(types::Doi, Vec<types::PathId>, String)>>();
        dois_and_path_ids_and_content
            .sort_by(|a, b| a.1.first().unwrap().0.cmp(&b.1.first().unwrap().0));
        let mut combined = String::new();
        for (doi, path_ids, content) in dois_and_path_ids_and_content {
            if !combined.is_empty() {
                combined.push('\n');
            }
            if path_ids.len() > 5 {
                combined.push_str(&format!(
                    "% {}, ... ({} more), {}\n",
                    path_ids
                        .iter()
                        .map(|path_id| &*path_id.0)
                        .collect::<Vec<&str>>()
                        .join(", "),
                    path_ids.len() - 4,
                    path_ids.last().unwrap().0,
                ));
            } else {
                combined.push_str(&format!(
                    "% {}\n",
                    path_ids
                        .iter()
                        .map(|path_id| &*path_id.0)
                        .collect::<Vec<&str>>()
                        .join(", "),
                ));
            }
            combined.push_str(&format!("% DOI {}\n", &doi.0));
            combined.push_str(&content);
        }
        Ok(combined)
    }
}
