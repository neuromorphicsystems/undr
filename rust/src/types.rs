use crate::constants;
use serde::de::Error;
use sha3::Digest;
use std::io::Read;

lazy_static! {
    static ref NAME_REGEX: regex::Regex = regex::Regex::new(r"^[A-Za-z0-9_\-.]+$").unwrap();
    static ref HASH_REGEX: regex::Regex = regex::Regex::new(r"^[a-f0-9]{56}$").unwrap();
    static ref DOI_REGEX: regex::Regex = regex::Regex::new(r"^10[.].+$").unwrap();
}

#[derive(Debug, Clone, PartialEq, Eq, Hash, serde::Serialize)]
#[repr(transparent)]
pub struct Name(pub String);

impl<'de> serde::Deserialize<'de> for Name {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: serde::Deserializer<'de>,
    {
        let string = String::deserialize(deserializer)?;
        if NAME_REGEX.is_match(&string) {
            return Ok(Name(string));
        }
        Err(D::Error::custom(
            "the string does not match the pattern \"name\"",
        ))
    }
}

// PathId may only contain NAME_REGEX characters and "/"
#[derive(Debug, Clone, PartialEq, Eq, Hash, serde::Serialize)]
#[repr(transparent)]
pub struct PathId(pub String);

impl PathId {
    pub fn join(&self, name: &Name) -> PathId {
        PathId(format!("{}/{}", self.0, name.0))
    }
}

impl From<Name> for PathId {
    fn from(name: Name) -> Self {
        PathId(name.0)
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
#[repr(transparent)]
pub struct PathRoot(pub std::sync::Arc<std::path::PathBuf>);

impl PathRoot {
    pub fn join(&self, path_id: &PathId) -> std::path::PathBuf {
        if std::path::MAIN_SEPARATOR == '/' {
            self.0.join(&path_id.0)
        } else {
            self.0.join(
                path_id
                    .0
                    .chars()
                    .map(|character| {
                        if character == '/' {
                            std::path::MAIN_SEPARATOR
                        } else {
                            character
                        }
                    })
                    .collect::<std::string::String>(),
            )
        }
    }

    pub fn join_with_suffix(&self, path_id: &PathId, suffix: &str) -> std::path::PathBuf {
        self.join(&PathId(format!("{}{}", path_id.0, suffix)))
    }

    pub fn join_with_suffixes(
        &self,
        path_id: &PathId,
        first_suffix: &str,
        second_suffix: &str,
    ) -> std::path::PathBuf {
        self.join(&PathId(format!(
            "{}{}{}",
            path_id.0, first_suffix, second_suffix
        )))
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
#[repr(transparent)]
pub struct Hash(
    pub generic_array::GenericArray<u8, <sha3::Sha3_224 as digest::OutputSizeUser>::OutputSize>,
);

impl Hash {
    pub fn hasher_from_reader<R: Read>(mut reader: R) -> Result<sha3::Sha3_224, std::io::Error> {
        let mut hasher = sha3::Sha3_224::new();
        let mut buffer = [0; constants::DECOMPRESS_CHUNK_SIZE];
        loop {
            let count = reader.read(&mut buffer)?;
            if count == 0 {
                break;
            }
            hasher.update(&buffer[0..count]);
        }
        Ok(hasher)
    }
}

impl<'de> serde::Deserialize<'de> for Hash {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: serde::Deserializer<'de>,
    {
        let string = String::deserialize(deserializer)?;
        if HASH_REGEX.is_match(&string) {
            return Ok(Hash(
                generic_array::GenericArray::<
                    u8,
                    <sha3::Sha3_224 as digest::OutputSizeUser>::OutputSize,
                >::from_exact_iter(string.as_bytes().chunks(2).map(|pair| {
                    u8::from_str_radix(std::str::from_utf8(pair).unwrap(), 16).unwrap()
                }))
                .unwrap(),
            ));
        }
        Err(D::Error::custom(
            "the string does not match the pattern \"hash\"",
        ))
    }
}

impl serde::Serialize for Hash {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        serializer.serialize_str(
            &self
                .0
                .iter()
                .map(|byte| format!("{byte:02x}"))
                .collect::<Vec<String>>()
                .join(""),
        )
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Hash, serde::Serialize)]
pub struct Doi(pub String);

impl<'de> serde::Deserialize<'de> for Doi {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: serde::Deserializer<'de>,
    {
        let string = String::deserialize(deserializer)?;
        if DOI_REGEX.is_match(&string) {
            return Ok(Doi(string));
        }
        Err(D::Error::custom(
            "the string does not match the pattern \"doi\"",
        ))
    }
}

#[derive(Debug, Clone, serde::Serialize)]
pub struct DecodeProgress {
    pub path_id: PathId,
    pub initial_bytes: i64,
    pub current_bytes: i64,
    pub final_bytes: i64,
    pub complete: bool,
}

#[derive(Debug, Clone, serde::Serialize)]
pub struct RemoteProgress {
    pub path_id: PathId,
    pub initial_bytes: i64,
    pub current_bytes: i64,
    pub final_bytes: i64,
    pub complete: bool,
}

#[derive(Debug, Default, Clone, serde::Serialize)]
pub struct Value {
    pub initial_bytes: u64,
    pub final_bytes: u64,
}

#[derive(Debug, Default, Clone, serde::Serialize)]
pub struct Report {
    pub local_bytes: u64,
    pub remote_bytes: u64,
}

#[derive(Debug, Clone, serde::Serialize)]
pub struct DirectoryScanned {
    pub path_id: PathId,
    pub initial_download_count: u64,
    pub initial_process_count: u64,
    pub final_count: u64,
    pub index: Value,
    pub download: Value,
    pub process: Value,
    pub calculate_size_compressed: Report,
    pub calculate_size_raw: Report,
}

#[derive(Debug, thiserror::Error)]
pub enum DownloadError {
    #[error("connection error")]
    Connection(#[from] reqwest::Error),

    #[error("file error")]
    File(#[from] std::io::Error),

    #[error("hash error")]
    Hash {
        path_id: PathId,
        expected: Hash,
        downloaded: Hash,
    },

    #[error("size error")]
    Size {
        path_id: PathId,
        expected: u64,
        downloaded: u64,
    },

    #[error("send error")]
    Send(PathId),

    #[error("semaphore error")]
    Semaphore(#[from] tokio::sync::AcquireError),
}

#[derive(Debug, thiserror::Error)]
pub enum DecompressError {
    #[error("file error")]
    File(#[from] std::io::Error),

    #[error("decode error")]
    Decode { path_id: PathId },

    #[error("hash error")]
    Hash {
        path_id: PathId,
        expected: Hash,
        downloaded: Hash,
    },

    #[error("size error")]
    Size {
        path_id: PathId,
        expected: u64,
        downloaded: u64,
    },

    #[error("interrupted")]
    Interrupted,

    #[error("send error")]
    Send(PathId),
}

#[derive(Debug, thiserror::Error)]
pub enum ActionError {
    #[error("download error")]
    Download(#[from] DownloadError),

    #[error("decompress error")]
    Decompress(#[from] DecompressError),

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

    #[error("send error")]
    Send(PathId),

    #[error("DOI send error")]
    DoiSend,
}

#[derive(Debug, Clone, serde::Serialize)]
#[serde(tag = "status", content = "payload")]
pub enum DoiStatus {
    #[serde(rename = "start")]
    Start,

    #[serde(rename = "success")]
    Success(String),

    #[serde(rename = "error")]
    Error(String),
}

#[derive(Debug, Clone, serde::Serialize)]
#[serde(tag = "type")]
pub enum Message {
    #[serde(rename = "index_loaded")]
    IndexLoaded { path_id: PathId, children: usize },

    #[serde(rename = "directory_scanned")]
    DirectoryScanned(DirectoryScanned),

    #[serde(rename = "remote_progress")]
    RemoteProgress(RemoteProgress),

    #[serde(rename = "decode_progress")]
    DecodeProgress(DecodeProgress),

    #[serde(rename = "doi")]
    Doi { path_id: PathId, value: Doi },

    #[serde(rename = "doi_progress")]
    DoiProgress {
        value: Doi,

        #[serde(flatten)]
        status: DoiStatus,
    },
}

impl From<RemoteProgress> for Message {
    fn from(item: RemoteProgress) -> Self {
        Message::RemoteProgress(item)
    }
}

impl From<DecodeProgress> for Message {
    fn from(item: DecodeProgress) -> Self {
        Message::DecodeProgress(item)
    }
}

#[cfg(test)]
mod tests {
    #[test]
    fn test_hash_serde() {
        let hash_json = "\"10ada4f8679a20c4d4f8fea56e8552e667f01a405611ca8c0463546c\"";
        let hash: crate::types::Hash = serde_json::from_str(&hash_json).unwrap();
        let hash_json_2 = serde_json::to_string(&hash).unwrap();
        assert_eq!(hash_json, hash_json_2);
    }

    #[test]
    fn test_bibtex_message() {
        println!(
            "{}",
            serde_json::to_string(&crate::Message::IndexLoaded {
                path_id: crate::types::PathId("test".to_owned()),
                children: 1
            })
            .unwrap()
        );
        println!(
            "{}",
            serde_json::to_string(&crate::Message::DoiProgress {
                value: crate::types::Doi("10.test".to_owned()),
                status: crate::types::DoiStatus::Start,
            })
            .unwrap()
        );
        println!(
            "{}",
            serde_json::to_string(&crate::Message::DoiProgress {
                value: crate::types::Doi("10.test".to_owned()),
                status: crate::types::DoiStatus::Success("a BibTex string".to_owned()),
            })
            .unwrap()
        );
    }
}

#[derive(Debug, Clone, Copy)]
#[repr(transparent)]
pub struct DispatchDois(pub bool);

#[derive(Debug, Clone, Copy)]
#[repr(transparent)]
pub struct Force(pub bool);

#[derive(Debug, Clone, Copy)]
#[repr(transparent)]
pub struct Keep(pub bool);

#[derive(Debug, Clone, Copy)]
#[repr(transparent)]
pub struct Pretty(pub bool);

#[derive(Debug, Clone, Copy)]
#[repr(transparent)]
pub struct CalculateSize(pub bool);

#[derive(Debug, Clone, Copy)]
#[repr(transparent)]
pub struct FilePermits(pub usize);

#[derive(Debug, Clone, Copy)]
#[repr(transparent)]
pub struct DownloadIndexPermits(pub usize);

#[derive(Debug, Clone, Copy)]
#[repr(transparent)]
pub struct DownloadPermits(pub usize);

#[derive(Debug, Clone, Copy)]
#[repr(transparent)]
pub struct DownloadDoiPermits(pub usize);

#[derive(Debug, Clone, Copy)]
#[repr(transparent)]
pub struct DecodePermits(pub usize);
