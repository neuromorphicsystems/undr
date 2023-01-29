use crate::constants;
use crate::types;
use sha3::Digest;
use std::io::Write;

#[derive(Debug, Clone)]
pub struct Server {
    client: reqwest::Client,
    url: std::sync::Arc<str>,
    url_ends_with_separator: bool,
}

pub enum DownloadState<Context> {
    Complete(),
    Partial { skip: u64, context: Context },
    NotStarted(Context),
}

struct DownloadFileContext {
    file: std::fs::File,
    hasher: Option<sha3::Sha3_224>,
    size: Option<u64>,
    download_permit: tokio::sync::OwnedSemaphorePermit,
    file_permit: tokio::sync::OwnedSemaphorePermit,
}

impl Server {
    pub fn new(url: &url::Url, timeout: &Option<f64>) -> Result<Self, reqwest::Error> {
        Ok(Server {
            client: reqwest::Client::builder()
                .connect_timeout(std::time::Duration::from_secs_f64(
                    timeout.unwrap_or(constants::DEFAULT_TIMEOUT),
                ))
                .build()?,
            url: std::sync::Arc::<str>::from(url.as_str()),
            url_ends_with_separator: url.as_str().ends_with('/'),
        })
    }

    pub fn url_from_path_id_and_suffix(
        &self,
        path_id: &types::PathId,
        suffix: &types::Name,
    ) -> String {
        if let Some((position, _)) = path_id
            .0
            .char_indices()
            .find(|(_, character)| *character == '/')
        {
            format!(
                "{}{}{}{}",
                self.url,
                if self.url_ends_with_separator {
                    ""
                } else {
                    "/"
                },
                &path_id.0[position + 1..],
                &suffix.0,
            )
        } else {
            self.url.to_string()
        }
    }

    pub async fn start_download<OnBegin, OnBeginOutput, OnRangeFailed, Context>(
        &self,
        path_id: &types::PathId,
        suffix: &types::Name,
        on_begin: OnBegin,
        on_range_failed: OnRangeFailed,
    ) -> Result<Option<(reqwest::Response, Context)>, types::DownloadError>
    where
        OnBegin: Fn() -> OnBeginOutput,
        OnBeginOutput:
            std::future::Future<Output = Result<DownloadState<Context>, types::DownloadError>>,
        OnRangeFailed: Fn(u64, Context) -> Result<Context, types::DownloadError>,
    {
        match on_begin().await? {
            DownloadState::Complete() => Ok(None),
            DownloadState::NotStarted(context) => Ok(Some((
                self.client
                    .get(&self.url_from_path_id_and_suffix(path_id, suffix))
                    .send()
                    .await?,
                context,
            ))),
            DownloadState::Partial { skip, context } => {
                let response = self
                    .client
                    .get(&self.url_from_path_id_and_suffix(path_id, suffix))
                    .header(reqwest::header::RANGE, &format!("bytes={skip}-"))
                    .send()
                    .await?;
                if response.status() == 206 {
                    Ok(Some((response, context)))
                } else {
                    let context = on_range_failed(skip, context)?;
                    Ok(Some((
                        self.client
                            .get(&self.url_from_path_id_and_suffix(path_id, suffix))
                            .send()
                            .await?,
                        context,
                    )))
                }
            }
        }
    }

    #[allow(clippy::too_many_arguments)]
    pub async fn download_file<Message>(
        &self,
        sender: &tokio::sync::mpsc::UnboundedSender<Message>,
        path_root: types::PathRoot,
        path_id: &types::PathId,
        force: types::Force,
        expected_size: Option<u64>,
        expected_hash: Option<types::Hash>,
        suffix: &types::Name,
        download_semaphore: std::sync::Arc<tokio::sync::Semaphore>,
        file_semaphore: std::sync::Arc<tokio::sync::Semaphore>,
    ) -> Result<(), types::DownloadError>
    where
        Message: std::convert::From<types::RemoteProgress>,
        Message: std::fmt::Debug,
    {
        let download_path =
            path_root.join_with_suffixes(path_id, &suffix.0, constants::DOWNLOAD_SUFFIX);
        let file_path = path_root.join_with_suffix(path_id, &suffix.0);
        if let Some((mut response, mut context)) = self
            .start_download(
                path_id,
                suffix,
                || {
                    let path_id = path_id.clone();
                    let download_path = download_path.clone();
                    let file_path = file_path.clone();
                    let expected_hash = expected_hash.clone();
                    let file_semaphore = file_semaphore.clone();
                    let download_semaphore = download_semaphore.clone();
                    async move {
                        if force.0 {
                            let download_permit = download_semaphore.acquire_owned().await?;
                            let file_permit = file_semaphore.acquire_many_owned(2).await?;
                            Ok(DownloadState::NotStarted(DownloadFileContext {
                                file: std::fs::File::create(&download_path)?,
                                hasher: expected_hash.as_ref().map(|_| sha3::Sha3_224::new()),
                                size: expected_size.map(|_| 0),
                                download_permit,
                                file_permit,
                            }))
                        } else {
                            match std::fs::metadata(&file_path) {
                                Ok(metadata) if metadata.file_type().is_file() => {
                                    let size = expected_size.unwrap_or(metadata.len()) as i64;
                                    sender
                                        .send(
                                            types::RemoteProgress {
                                                path_id: path_id.clone(),
                                                initial_bytes: size,
                                                current_bytes: size,
                                                final_bytes: size,
                                                complete: true,
                                            }
                                            .into(),
                                        )
                                        .map_err(|_| types::DownloadError::Send(path_id.clone()))?;
                                    Ok(DownloadState::Complete())
                                }
                                _ => match std::fs::metadata(&download_path) {
                                    Ok(metadata) if metadata.file_type().is_file() => {
                                        let download_permit = download_semaphore.acquire_owned().await?;
                                        let file_permit = file_semaphore.acquire_many_owned(2).await?;
                                        let hasher = expected_hash
                                            .as_ref()
                                            .map(|_| {
                                                types::Hash::hasher_from_reader(
                                                    std::fs::File::open(&download_path)?,
                                                )
                                            })
                                            .transpose()?;
                                        Ok(DownloadState::Partial {
                                            skip: metadata.len(),
                                            context: DownloadFileContext {
                                                file: std::fs::File::options()
                                                    .append(true)
                                                    .open(&download_path)?,
                                                hasher,
                                                size: expected_size.map(|_| metadata.len()),
                                                download_permit,
                                                file_permit,
                                            },
                                        })
                                    }
                                    _ => {
                                        let download_permit = download_semaphore.acquire_owned().await?;
                                        let file_permit = file_semaphore.acquire_many_owned(2).await?;
                                        Ok(DownloadState::NotStarted(DownloadFileContext {
                                            file: std::fs::File::create(&download_path)?,
                                            hasher: expected_hash
                                                .as_ref()
                                                .map(|_| sha3::Sha3_224::new()),
                                            size: expected_size.map(|_| 0),
                                            download_permit,
                                            file_permit,
                                        }))
                                    }
                                },
                            }
                        }
                    }
                },
                |skip, context| {
                    let size = -(skip as i64);
                    sender
                        .send(
                            types::RemoteProgress {
                                path_id: path_id.clone(),
                                initial_bytes: size,
                                current_bytes: size,
                                final_bytes: size,
                                complete: false,
                            }
                            .into(),
                        )
                        .map_err(|_| types::DownloadError::Send(path_id.clone()))?;
                    drop(context.file);
                    Ok(DownloadFileContext {
                        file: std::fs::File::create(&download_path)?,
                        hasher: expected_hash.as_ref().map(|_| sha3::Sha3_224::new()),
                        size: expected_size.map(|_| 0),
                        file_permit: context.file_permit,
                        download_permit: context.download_permit,
                    })
                },
            )
            .await?
        {
            let mut progress_size = 0;
            while let Some(chunk) = response.chunk().await? {
                context.file.write_all(&chunk)?;
                if let Some(hasher) = context.hasher.as_mut() {
                    hasher.update(&chunk);
                }
                if let Some(size) = context.size.as_mut() {
                    *size += chunk.len() as u64;
                }
                progress_size += chunk.len() as i64;
                if progress_size >= constants::PROGRESS_SIZE {
                    sender
                        .send(
                            types::RemoteProgress {
                                path_id: path_id.clone(),
                                initial_bytes: 0,
                                current_bytes: progress_size,
                                final_bytes: progress_size,
                                complete: false,
                            }
                            .into(),
                        )
                        .map_err(|_| types::DownloadError::Send(path_id.clone()))?;
                    progress_size = 0;
                }
            }
            if progress_size > 0 {
                sender
                    .send(
                        types::RemoteProgress {
                            path_id: path_id.clone(),
                            initial_bytes: 0,
                            current_bytes: progress_size,
                            final_bytes: progress_size,
                            complete: false,
                        }
                        .into(),
                    )
                    .map_err(|_| types::DownloadError::Send(path_id.clone()))?;
            }
            drop(context.file);
            drop(context.file_permit);
            drop(context.download_permit);
            if let (Some(hasher), Some(expected_hash)) = (context.hasher, expected_hash) {
                let hash = hasher.finalize();
                if hash != expected_hash.0 {
                    return Err(types::DownloadError::Hash {
                        path_id: path_id.clone(),
                        expected: expected_hash,
                        downloaded: types::Hash(hash),
                    });
                }
            }
            if let (Some(size), Some(expected_size)) = (context.size, expected_size) {
                if size != expected_size {
                    return Err(types::DownloadError::Size {
                        path_id: path_id.clone(),
                        expected: expected_size,
                        downloaded: size,
                    });
                }
            }
            std::fs::rename(&download_path, &file_path)?;
            sender
                .send(
                    types::RemoteProgress {
                        path_id: path_id.clone(),
                        initial_bytes: 0,
                        current_bytes: 0,
                        final_bytes: 0,
                        complete: true,
                    }
                    .into(),
                )
                .map_err(|_| types::DownloadError::Send(path_id.clone()))?;
        }
        Ok(())
    }
}
