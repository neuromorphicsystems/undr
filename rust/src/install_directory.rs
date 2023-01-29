use crate::configuration;
use crate::constants;
use crate::decode;
use crate::json_index;
use crate::remote;
use crate::types;
use futures::future::FutureExt;

#[allow(clippy::too_many_arguments)]
pub fn install_directory(
    running: std::sync::Arc<std::sync::atomic::AtomicBool>,
    server: remote::Server,
    sender: tokio::sync::mpsc::UnboundedSender<types::Message>,
    path_root: types::PathRoot,
    path_id: types::PathId,
    force: types::Force,
    keep: types::Keep,
    dispatch_dois: types::DispatchDois,
    calculate_size: types::CalculateSize,
    mode: configuration::InstallableMode,
    file_semaphore: std::sync::Arc<tokio::sync::Semaphore>,
    download_index_semaphore: std::sync::Arc<tokio::sync::Semaphore>,
    download_semaphore: std::sync::Arc<tokio::sync::Semaphore>,
    decode_semaphore: std::sync::Arc<tokio::sync::Semaphore>,
) -> std::pin::Pin<
    std::boxed::Box<dyn futures::future::Future<Output = Result<(), types::ActionError>> + Send>,
> {
    async move {
        std::fs::create_dir_all(path_root.join(&path_id))?;
        let index_path_id = path_id.join(&types::Name("-index.json".to_owned()));
        let index_file_path = path_root.join(&index_path_id);
        let mut directory_scanned = types::DirectoryScanned {
            path_id: path_id.clone(),
            initial_download_count: 0,
            initial_process_count: 0,
            final_count: 0,
            index: if force.0 {
                types::Value::default()
            } else {
                match std::fs::metadata(&index_file_path) {
                    Ok(metadata) if metadata.file_type().is_file() => types::Value {
                        initial_bytes: metadata.len(),
                        final_bytes: metadata.len(),
                    },
                    _ => match std::fs::metadata(
                        path_root.join_with_suffix(&index_path_id, constants::DOWNLOAD_SUFFIX),
                    ) {
                        Ok(metadata) if metadata.file_type().is_file() => types::Value {
                            initial_bytes: metadata.len(),
                            final_bytes: 0,
                        },
                        _ => types::Value::default(),
                    },
                }
            },
            download: types::Value::default(),
            process: types::Value::default(),
            calculate_size_compressed: types::Report::default(),
            calculate_size_raw: types::Report::default(),
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
                download_index_semaphore.clone(),
                file_semaphore.clone(),
            )
            .await?;
        let index: json_index::Index = {
            let content = {
                let _permit = file_semaphore.acquire().await?;
                std::fs::read_to_string(path_root.join(&index_path_id))
                    .map_err(|_| types::ActionError::Read(path_root.join(&index_path_id)))?
            };
            serde_json::from_str(&content)?
        };
        sender
            .send(types::Message::IndexLoaded {
                path_id: path_id.clone(),
                children: index.directories.len(),
            })
            .map_err(|_| types::ActionError::Send(path_id.clone()))?;
        if dispatch_dois.0 {
            if let Some(doi) = &index.doi {
                sender
                    .send(types::Message::Doi {
                        path_id: path_id.clone(),
                        value: doi.clone(),
                    })
                    .map_err(|_| types::ActionError::Send(path_id.clone()))?;
            }
        }
        let mut join_set = tokio::task::JoinSet::new();
        for directory in index.directories {
            let running = running.clone();
            let server = server.clone();
            let sender = sender.clone();
            let path_root = path_root.clone();
            let path_id = path_id.join(&directory);
            let file_semaphore = file_semaphore.clone();
            let download_index_semaphore = download_index_semaphore.clone();
            let download_semaphore = download_semaphore.clone();
            let decode_semaphore = decode_semaphore.clone();
            join_set.spawn(async move {
                install_directory(
                    running,
                    server,
                    sender,
                    path_root,
                    path_id,
                    force,
                    keep,
                    dispatch_dois,
                    calculate_size,
                    mode,
                    file_semaphore,
                    download_index_semaphore,
                    download_semaphore,
                    decode_semaphore,
                )
                .await?;
                Ok::<(), types::ActionError>(())
            });
        }
        if directory_scanned.index.final_bytes == 0 {
            directory_scanned.index.final_bytes = match std::fs::metadata(&index_file_path) {
                Ok(metadata) if metadata.file_type().is_file() => metadata.len(),
                _ => return Err(types::ActionError::Read(index_file_path)),
            }
        }
        if dispatch_dois.0 || calculate_size.0 || mode != configuration::InstallableMode::Remote {
            for resource in index.files.iter().map(|file| &file.resource).chain(
                index
                    .other_files
                    .iter()
                    .map(|other_file| &other_file.resource),
            ) {
                if dispatch_dois.0 {
                    if let Some(doi) = &resource.doi {
                        sender
                            .send(types::Message::Doi {
                                path_id: path_id.join(&resource.name),
                                value: doi.clone(),
                            })
                            .map_err(|_| types::ActionError::Send(path_id.clone()))?;
                    }
                }
                if !calculate_size.0 && mode == configuration::InstallableMode::Remote {
                    continue;
                }
                let (_, compression_properties) = resource.best_compression();
                if mode == configuration::InstallableMode::Local
                    || mode == configuration::InstallableMode::Raw
                {
                    directory_scanned.download.final_bytes += compression_properties.size;
                    directory_scanned.final_count += 1;
                }
                if mode == configuration::InstallableMode::Raw {
                    directory_scanned.process.final_bytes += resource.size;
                }
                if calculate_size.0 {
                    directory_scanned.calculate_size_compressed.remote_bytes +=
                        compression_properties.size;
                    directory_scanned.calculate_size_raw.remote_bytes += resource.size;
                }
                if calculate_size.0 || !force.0 {
                    let resource_path_id = path_id.join(&resource.name);
                    match std::fs::metadata(path_root.join(&resource_path_id)) {
                        Ok(metadata) if metadata.file_type().is_file() => {
                            if calculate_size.0 {
                                directory_scanned.calculate_size_raw.local_bytes += metadata.len();
                                match std::fs::metadata(path_root.join_with_suffix(
                                    &resource_path_id,
                                    &compression_properties.suffix.0,
                                )) {
                                    Ok(metadata) if metadata.file_type().is_file() => {
                                        directory_scanned.calculate_size_compressed.local_bytes +=
                                            metadata.len();
                                    }
                                    _ => match std::fs::metadata(path_root.join_with_suffixes(
                                        &resource_path_id,
                                        &compression_properties.suffix.0,
                                        constants::DOWNLOAD_SUFFIX,
                                    )) {
                                        Ok(metadata) if metadata.file_type().is_file() => {
                                            directory_scanned
                                                .calculate_size_compressed
                                                .local_bytes += metadata.len();
                                        }
                                        _ => (),
                                    },
                                }
                            }
                            if !force.0 && mode != configuration::InstallableMode::Remote {
                                directory_scanned.initial_download_count += 1;
                                directory_scanned.download.initial_bytes +=
                                    compression_properties.size;
                                if mode == configuration::InstallableMode::Raw {
                                    directory_scanned.initial_process_count += 1;
                                    directory_scanned.process.initial_bytes += metadata.len();
                                }
                            }
                        }
                        _ => {
                            match std::fs::metadata(path_root.join_with_suffix(
                                &resource_path_id,
                                &compression_properties.suffix.0,
                            )) {
                                Ok(metadata) if metadata.file_type().is_file() => {
                                    if calculate_size.0 {
                                        directory_scanned.calculate_size_compressed.local_bytes +=
                                            metadata.len();
                                    }
                                    if !force.0 && mode != configuration::InstallableMode::Remote {
                                        directory_scanned.initial_download_count += 1;
                                        directory_scanned.download.initial_bytes += metadata.len();
                                    }
                                }
                                _ => match std::fs::metadata(path_root.join_with_suffixes(
                                    &resource_path_id,
                                    &compression_properties.suffix.0,
                                    constants::DOWNLOAD_SUFFIX,
                                )) {
                                    Ok(metadata) if metadata.file_type().is_file() => {
                                        if calculate_size.0 {
                                            directory_scanned
                                                .calculate_size_compressed
                                                .local_bytes += metadata.len();
                                        }
                                        if !force.0
                                            && mode != configuration::InstallableMode::Remote
                                        {
                                            directory_scanned.download.initial_bytes +=
                                                metadata.len();
                                        }
                                    }
                                    _ => (),
                                },
                            }
                        }
                    }
                }
            }
        }
        sender
            .send(types::Message::DirectoryScanned(directory_scanned))
            .map_err(|_| types::ActionError::Send(path_id.clone()))?;
        match mode {
            configuration::InstallableMode::Local | configuration::InstallableMode::Raw => {
                for resource in index.files.iter().map(|file| &file.resource).chain(
                    index
                        .other_files
                        .iter()
                        .map(|other_file| &other_file.resource),
                ) {
                    if force.0
                        || mode != configuration::InstallableMode::Raw
                        || !matches!(
                            std::fs::metadata(path_root.join(&path_id.join(&resource.name))),
                            Ok(metadata) if metadata.file_type().is_file()
                        )
                    {
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
                        let file_semaphore = file_semaphore.clone();
                        let download_semaphore = download_semaphore.clone();
                        let decode_semaphore = decode_semaphore.clone();
                        let expected_decode_size = resource.size;
                        let expected_decode_hash = resource.hash.clone();
                        join_set.spawn(async move {
                            server
                                .download_file(
                                    &sender,
                                    path_root.clone(),
                                    &path_id,
                                    force,
                                    Some(expected_download_size),
                                    Some(expected_download_hash),
                                    &suffix,
                                    download_semaphore,
                                    file_semaphore.clone(),
                                )
                                .await?;
                            if mode == configuration::InstallableMode::Raw {
                                match compression {
                                    json_index::Compression::NoneCompression { suffix: _ } => (),
                                    json_index::Compression::Brotli {
                                        size: _,
                                        hash: _,
                                        suffix: _,
                                    } => {
                                        let decode_permit =
                                            decode_semaphore.acquire_owned().await?;
                                        let file_permit =
                                            file_semaphore.acquire_many_owned(2).await?;
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
                                            drop(file_permit); // drop tells the compiler to move 'permit' inside the spawn_blocking closure
                                            drop(decode_permit);
                                            Ok::<(), types::DecompressError>(())
                                        })
                                        .await??;
                                    }
                                }
                            }
                            Ok::<(), types::ActionError>(())
                        });
                    }
                }
            }
            configuration::InstallableMode::Remote => (),
        }
        while let Some(task) = join_set.join_next().await {
            match task {
                Ok(result) => match result {
                    Ok(()) => {}
                    Err(error) => {
                        return Err(error);
                    }
                },
                Err(error) => {
                    return Err(types::ActionError::Join(error));
                }
            }
        }
        Ok(())
    }
    .boxed()
}
