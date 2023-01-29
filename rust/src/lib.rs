#[macro_use(lazy_static)]
extern crate lazy_static;

mod bibtex;
mod configuration;
mod constants;
mod decode;
mod install_directory;
mod json_index;
mod remote;
mod types;
pub use configuration::Configuration;
pub use configuration::ConfigurationError;
pub use configuration::Mode;
pub use types::ActionError;
pub use types::CalculateSize;
pub use types::DecodePermits;
pub use types::DispatchDois;
pub use types::DownloadDoiPermits;
pub use types::DownloadIndexPermits;
pub use types::DownloadPermits;
pub use types::FilePermits;
pub use types::Force;
pub use types::Keep;
pub use types::Message;
pub use types::Pretty;

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
        force: Force,
        keep: Keep,
        dispatch_dois: DispatchDois,
        calculate_size: CalculateSize,
        file_permits: FilePermits,
        download_index_permits: DownloadIndexPermits,
        download_permits: DownloadPermits,
        decode_permits: DecodePermits,
    ) -> Result<(), ActionError>
    where
        HandleMessage: FnMut(Message),
    {
        std::fs::create_dir_all(&self.directory).map_err(ActionError::Directory)?;
        let path_root = types::PathRoot(std::sync::Arc::<std::path::PathBuf>::from(
            self.directory.clone(),
        ));
        let mut join_set = tokio::task::JoinSet::new();
        let file_semaphore = std::sync::Arc::new(tokio::sync::Semaphore::new(file_permits.0 - 1));
        let download_index_semaphore =
            std::sync::Arc::new(tokio::sync::Semaphore::new(download_index_permits.0));
        let download_semaphore =
            std::sync::Arc::new(tokio::sync::Semaphore::new(download_permits.0));
        let decode_semaphore = std::sync::Arc::new(tokio::sync::Semaphore::new(decode_permits.0));
        let (sender, mut receiver) = tokio::sync::mpsc::unbounded_channel();
        for (dataset, mode) in self.datasets.iter().filter_map(|dataset| {
            configuration::InstallableMode::try_from(dataset.mode)
                .ok()
                .map(|mode| (dataset, mode))
        }) {
            join_set.spawn(install_directory::install_directory(
                running.clone(),
                remote::Server::new(&dataset.url, &dataset.timeout)?,
                sender.clone(),
                path_root.clone(),
                types::PathId(dataset.name.0.clone()),
                force,
                keep,
                dispatch_dois,
                calculate_size,
                mode,
                file_semaphore.clone(),
                download_index_semaphore.clone(),
                download_semaphore.clone(),
                decode_semaphore.clone(),
            ));
        }
        drop(sender);
        loop {
            tokio::select! {
                biased;
                Some(message) = receiver.recv() => {
                    handle_message(message);
                }
                Some(task) = join_set.join_next() => {
                    match task {
                        Ok(result) => match result {
                            Ok(()) => (),
                            Err(error) => {
                                running.store(false, std::sync::atomic::Ordering::Release);
                                return Err(error);
                            },
                        },
                        Err(error) => {
                            running.store(false, std::sync::atomic::Ordering::Release);
                            return Err(ActionError::Join(error));
                        }
                    }
                }
                else => break,
            }
        }
        Ok(())
    }

    #[allow(clippy::too_many_arguments)]
    pub async fn bibtex<HandleMessage, P: AsRef<std::path::Path>>(
        &self,
        running: std::sync::Arc<std::sync::atomic::AtomicBool>,
        mut handle_message: HandleMessage,
        force: Force,
        file_permits: FilePermits,
        download_index_permits: DownloadIndexPermits,
        download_doi_permits: DownloadDoiPermits,
        doi_timeout: Option<f64>,
        output_path: P,
        pretty: Pretty,
    ) -> Result<(), ActionError>
    where
        HandleMessage: FnMut(Message),
    {
        std::fs::create_dir_all(&self.directory).map_err(ActionError::Directory)?;
        let path_root = types::PathRoot(std::sync::Arc::<std::path::PathBuf>::from(
            self.directory.clone(),
        ));
        let mut join_set = tokio::task::JoinSet::new();
        let download_index_semaphore =
            std::sync::Arc::new(tokio::sync::Semaphore::new(download_index_permits.0));
        let file_semaphore = std::sync::Arc::new(tokio::sync::Semaphore::new(file_permits.0));
        let download_semaphore = std::sync::Arc::new(tokio::sync::Semaphore::new(1));
        let decode_semaphore = std::sync::Arc::new(tokio::sync::Semaphore::new(1));
        let (sender, mut receiver) = tokio::sync::mpsc::unbounded_channel();
        for (dataset, _mode) in self.datasets.iter().filter_map(|dataset| {
            configuration::InstallableMode::try_from(dataset.mode)
                .ok()
                .map(|mode| (dataset, mode))
        }) {
            join_set.spawn(install_directory::install_directory(
                running.clone(),
                remote::Server::new(&dataset.url, &dataset.timeout)?,
                sender.clone(),
                path_root.clone(),
                types::PathId(dataset.name.0.clone()),
                force,
                Keep(false),
                DispatchDois(true),
                CalculateSize(false),
                configuration::InstallableMode::Remote,
                file_semaphore.clone(),
                download_index_semaphore.clone(),
                download_semaphore.clone(),
                decode_semaphore.clone(),
            ));
        }
        let mut doi_to_path_ids_and_content =
            std::collections::HashMap::<types::Doi, (Vec<types::PathId>, Option<String>)>::new();
        let client = reqwest::Client::builder()
            .connect_timeout(std::time::Duration::from_secs_f64(
                doi_timeout.unwrap_or(constants::DEFAULT_TIMEOUT),
            ))
            .build()?;
        let download_doi_semaphore =
            std::sync::Arc::new(tokio::sync::Semaphore::new(download_doi_permits.0));
        let mut sender = Some(sender);
        #[derive(Debug)]
        struct DatasetProgress<'a> {
            name: &'a types::Name,
            current_index_files: usize,
            final_index_files: usize,
        }
        let mut datasets_progress = self
            .datasets
            .iter()
            .filter_map(|dataset| {
                configuration::InstallableMode::try_from(dataset.mode)
                    .ok()
                    .map(|_| DatasetProgress {
                        name: &dataset.name,
                        current_index_files: 0,
                        final_index_files: 1,
                    })
            })
            .collect::<Vec<DatasetProgress>>();
        loop {
            tokio::select! {
                biased;
                Some(message) = receiver.recv() => {
                    if let Message::Doi{path_id, value} = message {
                        handle_message(Message::Doi{path_id: path_id.clone(), value: value.clone()});
                        match doi_to_path_ids_and_content.get_mut(&value) {
                            Some(path_ids_and_content) => path_ids_and_content.0.push(path_id),
                            None => {
                                doi_to_path_ids_and_content
                                    .insert(value.clone(), (vec![path_id], None));
                                let client = client.clone();
                                let file_semaphore = file_semaphore.clone();
                                let download_doi_semaphore = download_doi_semaphore.clone();
                                let sender = sender.as_ref().unwrap().clone();
                                join_set.spawn(async move {
                                    let _download_doi_permit = download_doi_semaphore
                                        .acquire()
                                        .await?;
                                    let _file_permit = file_semaphore.acquire().await?;
                                    sender
                                        .send(Message::DoiProgress {
                                            value: value.clone(),
                                            status: types::DoiStatus::Start,
                                        })
                                        .map_err(|_| ActionError::DoiSend)?;
                                    let response = match client
                                        .get(format!("https://doi.org/{}", &value.0))
                                        .header(
                                            reqwest::header::ACCEPT,
                                            "application/x-bibtex; charset=utf-8",
                                        )
                                        .send()
                                        .await {
                                        Ok(response) => response,
                                        Err(error) => {
                                            sender
                                                .send(Message::DoiProgress {
                                                    value: value.clone(),
                                                    status: types::DoiStatus::Error(format!("{error:?}")),
                                                })
                                                .map_err(|_| ActionError::DoiSend)?;
                                            return Ok(());
                                        },
                                    };
                                    let status = response.status();
                                    let content = match response.text().await {
                                        Ok(content) => content,
                                        Err(error) => {
                                            sender
                                                .send(Message::DoiProgress {
                                                    value: value.clone(),
                                                    status: types::DoiStatus::Error(format!("{error:?}")),
                                                })
                                                .map_err(|_| ActionError::DoiSend)?;
                                            return Ok(());
                                        },
                                    };
                                    if status.is_client_error() || status.is_server_error() {
                                        sender
                                            .send(Message::DoiProgress {
                                                value: value.clone(),
                                                status: types::DoiStatus::Error(content),
                                            })
                                            .map_err(|_| ActionError::DoiSend)?;
                                        return Ok(());
                                    }
                                    if pretty.0 {
                                        sender
                                            .send(Message::DoiProgress {
                                                value: value.clone(),
                                                status: types::DoiStatus::Success(bibtex::prettify(&content)),
                                            })
                                            .map_err(|_| ActionError::DoiSend)?;
                                    } else {
                                        sender
                                            .send(Message::DoiProgress {
                                                value: value.clone(),
                                                status: types::DoiStatus::Success(content),
                                            })
                                            .map_err(|_| ActionError::DoiSend)?;
                                    }
                                    Ok::<(), ActionError>(())
                                });
                            }
                        }
                    } else if let Message::DoiProgress {value, status} = message {
                        handle_message(Message::DoiProgress {value: value.clone(), status: status.clone()});
                        match status {
                            types::DoiStatus::Start => {},
                            types::DoiStatus::Success(content) => {
                                doi_to_path_ids_and_content.get_mut(&value).unwrap().1 = Some(content);
                            },
                            types::DoiStatus::Error(error) => {
                                doi_to_path_ids_and_content.get_mut(&value).unwrap().1 = Some(error);
                            },
                        }
                        bibtex::write(&output_path, &doi_to_path_ids_and_content)?;
                    } else if let Message::IndexLoaded {path_id, children} = message {
                        handle_message(Message::IndexLoaded { path_id: path_id.clone(), children });
                        for dataset_progress in datasets_progress.iter_mut() {
                            if path_id.0.starts_with(&dataset_progress.name.0) {
                                dataset_progress.final_index_files += children;
                                break;
                            }
                        }
                    } else if let Message::DirectoryScanned(types::DirectoryScanned {
                        path_id,
                        initial_download_count,
                        initial_process_count,
                        final_count,
                        index,
                        download,
                        process,
                        calculate_size_compressed,
                        calculate_size_raw,
                    }) = message {
                        handle_message(Message::DirectoryScanned(types::DirectoryScanned {
                            path_id: path_id.clone(),
                            initial_download_count,
                            initial_process_count,
                            final_count,
                            index: index.clone(),
                            download: download.clone(),
                            process: process.clone(),
                            calculate_size_compressed: calculate_size_compressed.clone(),
                            calculate_size_raw: calculate_size_raw.clone(),
                        }));
                        for dataset_progress in datasets_progress.iter_mut() {
                            if path_id.0.starts_with(&dataset_progress.name.0) {
                                dataset_progress.current_index_files += 1;
                                break;
                            }
                        }
                        if datasets_progress.iter().all(|DatasetProgress {name: _, current_index_files, final_index_files}| current_index_files == final_index_files) {
                            sender.take();
                        }
                    } else {
                        handle_message(message);
                    }
                }
                Some(task) = join_set.join_next() => {
                    match task {
                        Ok(result) => match result {
                            Ok(()) => (),
                            Err(error) => {
                                running.store(false, std::sync::atomic::Ordering::Release);
                                return Err(error);
                            },
                        },
                        Err(error) => {
                            running.store(false, std::sync::atomic::Ordering::Release);
                            return Err(ActionError::Join(error));
                        }
                    }
                }
                else => break,
            }
        }
        Ok(())
    }
}
