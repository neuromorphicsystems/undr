use crate::constants;
use crate::types;
use sha3::Digest;
use std::io::Read;
use std::io::Write;

#[allow(clippy::too_many_arguments)]
pub fn brotli<Message>(
    running: std::sync::Arc<std::sync::atomic::AtomicBool>,
    sender: &tokio::sync::mpsc::UnboundedSender<Message>,
    path_root: types::PathRoot,
    path_id: &types::PathId,
    force: types::Force,
    keep: types::Keep,
    expected_size: u64,
    expected_hash: &types::Hash,
    suffix: &types::Name,
) -> Result<(), types::DecompressError>
where
    Message: std::convert::From<types::DecodeProgress>,
    Message: std::fmt::Debug,
{
    let file_path = path_root.join(path_id);
    if !force.0 {
        match std::fs::metadata(&file_path) {
            Ok(metadata) if metadata.file_type().is_file() => return Ok(()),
            _ => (),
        }
    }
    let compressed_path = path_root.join_with_suffix(path_id, &suffix.0);
    let decompress_path =
        path_root.join_with_suffixes(path_id, &suffix.0, constants::DECOMPRESS_SUFFIX);
    let mut hasher = sha3::Sha3_224::new();
    let mut size = 0;
    {
        let mut reader = brotli::Decompressor::new(
            std::fs::File::open(&compressed_path)?,
            constants::DECOMPRESS_CHUNK_SIZE,
        );
        let mut writer = std::fs::File::create(&decompress_path)?;
        let mut buffer = [0u8; constants::DECOMPRESS_CHUNK_SIZE];
        let mut progress_size = 0;
        loop {
            match reader.read(&mut buffer[..]) {
                Ok(chunk_size) => {
                    if chunk_size == 0 {
                        break;
                    }
                    if !running.load(std::sync::atomic::Ordering::Acquire) {
                        return Err(types::DecompressError::Interrupted);
                    }
                    writer.write_all(&buffer[0..chunk_size])?;
                    hasher.update(&buffer[0..chunk_size]);
                    size += chunk_size as u64;
                    progress_size += chunk_size as i64;
                    if progress_size >= constants::PROGRESS_SIZE {
                        sender
                            .send(
                                types::DecodeProgress {
                                    path_id: path_id.clone(),
                                    initial_bytes: 0,
                                    current_bytes: progress_size,
                                    final_bytes: progress_size,
                                    complete: false,
                                }
                                .into(),
                            )
                            .map_err(|_| types::DecompressError::Send(path_id.clone()))?;
                        progress_size = 0;
                    }
                }
                Err(error) => {
                    if let std::io::ErrorKind::Interrupted = error.kind() {
                        continue;
                    }
                    return Err(types::DecompressError::Decode {
                        path_id: path_id.clone(),
                    });
                }
            }
        }
        if progress_size > 0 {
            sender
                .send(
                    types::DecodeProgress {
                        path_id: path_id.clone(),
                        initial_bytes: 0,
                        current_bytes: progress_size,
                        final_bytes: progress_size,
                        complete: false,
                    }
                    .into(),
                )
                .map_err(|_| types::DecompressError::Send(path_id.clone()))?;
        }
    }
    let hash = hasher.finalize();
    if hash != expected_hash.0 {
        return Err(types::DecompressError::Hash {
            path_id: path_id.clone(),
            expected: expected_hash.clone(),
            downloaded: types::Hash(hash),
        });
    }
    if size != expected_size {
        return Err(types::DecompressError::Size {
            path_id: path_id.clone(),
            expected: expected_size,
            downloaded: size,
        });
    }
    std::fs::rename(&decompress_path, &file_path)?;
    if !keep.0 {
        let _ = std::fs::remove_file(compressed_path);
    }
    sender
        .send(
            types::DecodeProgress {
                path_id: path_id.clone(),
                initial_bytes: 0,
                current_bytes: 0,
                final_bytes: 0,
                complete: true,
            }
            .into(),
        )
        .map_err(|_| types::DecompressError::Send(path_id.clone()))?;
    Ok(())
}
