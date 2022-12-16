use crate::constants;
use crate::types;
use sha3::Digest;
use std::io::Read;
use std::io::Write;

#[derive(Debug, thiserror::Error)]
pub enum DecompressError {
    #[error("file error")]
    File(#[from] std::io::Error),

    #[error("decode error")]
    Decode { path_id: types::PathId },

    #[error("hash error")]
    Hash {
        path_id: types::PathId,
        expected: types::Hash,
        downloaded: types::Hash,
    },

    #[error("size error")]
    Size {
        path_id: types::PathId,
        expected: u64,
        downloaded: u64,
    },

    #[error("interrupted")]
    Interrupted,
}

#[allow(clippy::too_many_arguments)]
pub fn brotli<Message>(
    running: std::sync::Arc<std::sync::atomic::AtomicBool>,
    sender: &tokio::sync::mpsc::UnboundedSender<Message>,
    path_root: types::PathRoot,
    path_id: &types::PathId,
    force: bool,
    keep: bool,
    expected_size: u64,
    expected_hash: &types::Hash,
    suffix: &types::Name,
) -> Result<(), DecompressError>
where
    Message: std::convert::From<types::Progress>,
    Message: std::fmt::Debug,
{
    let file_path = path_root.join(path_id);
    if !force {
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
        loop {
            match reader.read(&mut buffer[..]) {
                Ok(chunk_size) => {
                    if chunk_size == 0 {
                        break;
                    }
                    if !running.load(std::sync::atomic::Ordering::Acquire) {
                        return Err(DecompressError::Interrupted);
                    }
                    writer.write_all(&buffer[0..chunk_size])?;
                    hasher.update(&buffer[0..chunk_size]);
                    size += chunk_size as u64;
                    sender
                        .send(
                            types::Progress {
                                path_id: path_id.clone(),
                                initial_bytes: 0,
                                current_bytes: size as i64,
                                final_bytes: size as i64,
                                complete: false,
                            }
                            .into(),
                        )
                        .unwrap();
                }
                Err(error) => {
                    if let std::io::ErrorKind::Interrupted = error.kind() {
                        continue;
                    }
                    return Err(DecompressError::Decode {
                        path_id: path_id.clone(),
                    });
                }
            }
        }
    }
    let hash = hasher.finalize();
    if hash != expected_hash.0 {
        return Err(DecompressError::Hash {
            path_id: path_id.clone(),
            expected: expected_hash.clone(),
            downloaded: types::Hash(hash),
        });
    }
    if size != expected_size {
        return Err(DecompressError::Size {
            path_id: path_id.clone(),
            expected: expected_size,
            downloaded: size,
        });
    }
    std::fs::rename(&decompress_path, &file_path)?;
    if !keep {
        let _ = std::fs::remove_file(compressed_path);
    }
    sender
        .send(
            types::Progress {
                path_id: path_id.clone(),
                initial_bytes: 0,
                current_bytes: 0,
                final_bytes: 0,
                complete: true,
            }
            .into(),
        )
        .unwrap();
    Ok(())
}
