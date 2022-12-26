use crate::constants;
use serde::de::Error;
use sha3::Digest;
use std::io::Read;

lazy_static! {
    static ref NAME_REGEX: regex::Regex = regex::Regex::new(r"^[A-Za-z0-9_\\-\\.]+$").unwrap();
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
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
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
            hasher.update(buffer);
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
                .map(|byte| format!("{:02x}", byte))
                .collect::<Vec<String>>()
                .join(""),
        )
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

#[derive(Debug)]
pub struct Progress {
    pub path_id: PathId,
    pub initial_bytes: i64,
    pub current_bytes: i64,
    pub final_bytes: i64,
    pub complete: bool,
}
