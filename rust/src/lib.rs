#[macro_use(lazy_static)]
extern crate lazy_static;

use serde::de::Error;

lazy_static! {
    static ref NAME_REGEX: regex::Regex = regex::Regex::new(r"^[A-Za-z0-9_\\-\\.]+$").unwrap();
    static ref HASH_REGEX: regex::Regex = regex::Regex::new(r"^[a-f0-9]{56}$").unwrap();
    static ref DOI_REGEX: regex::Regex = regex::Regex::new(r"^10[.].+$").unwrap();
}

#[derive(Debug, Clone, PartialEq, Eq, Hash, serde::Serialize)]
pub struct Name(String);

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

#[derive(Debug, Clone, PartialEq, Eq, Hash, serde::Serialize)]
pub struct Hash(String);

impl<'de> serde::Deserialize<'de> for Hash {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: serde::Deserializer<'de>,
    {
        let string = String::deserialize(deserializer)?;
        if HASH_REGEX.is_match(&string) {
            return Ok(Hash(string));
        }
        Err(D::Error::custom(
            "the string does not match the pattern \"hash\"",
        ))
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Hash, serde::Serialize)]
pub struct Doi(String);

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

#[derive(serde::Serialize, serde::Deserialize)]
pub enum Mode {
    #[serde(rename = "disabled")]
    Disabled,

    #[serde(rename = "remote")]
    Remote,

    #[serde(rename = "local")]
    Local,

    #[serde(rename = "raw")]
    Raw,
}

#[derive(serde::Serialize, serde::Deserialize)]
pub struct DatasetSettings {
    pub name: Name,
    pub url: url::Url,
    pub mode: Mode,
    pub timeout: Option<f64>,
}

#[derive(serde::Serialize, serde::Deserialize)]
pub struct Configuration {
    pub directory: std::path::PathBuf,
    pub datasets: Vec<DatasetSettings>,
}

#[derive(serde::Serialize, serde::Deserialize)]
pub struct Version {
    pub major: u64,
    pub minor: u64,
    pub patch: u64,
}

#[derive(serde::Serialize, serde::Deserialize)]
#[serde(tag = "type")]
pub enum Compression {
    #[serde(rename = "none")]
    NoneCompression { suffix: String },
    #[serde(rename = "brotli")]
    Brotli {
        size: usize,
        hash: Hash,
        suffix: String,
    },
}

#[derive(serde::Serialize, serde::Deserialize)]
pub struct Resource {
    pub name: Name,
    pub size: usize,
    pub hash: Hash,
    pub compressions: Vec<Compression>,
}

#[derive(serde::Serialize, serde::Deserialize)]
#[serde(tag = "type")]
pub enum Properties {
    #[serde(rename = "aps")]
    Aps { width: u64, height: u64 },
    #[serde(rename = "dvs")]
    Dvs { width: u64, height: u64 },
    #[serde(rename = "imu")]
    Imu,
}

#[derive(serde::Serialize, serde::Deserialize)]
pub struct File {
    #[serde(flatten)]
    pub resource: Resource,
    pub properties: Properties,
    pub metadata: serde_json::Value,
}

#[derive(serde::Serialize, serde::Deserialize)]
pub struct OtherFile {
    #[serde(flatten)]
    pub resource: Resource,
    pub metadata: serde_json::Value,
}

#[derive(serde::Serialize, serde::Deserialize)]
pub struct Index {
    pub version: Version,
    pub doi: Doi,
    pub directories: Vec<Name>,
    pub files: Vec<File>,
    pub other_files: Vec<OtherFile>,
    pub metadata: serde_json::Value,
}

#[derive(thiserror::Error, Debug)]
pub enum ConfigurationError {
    #[error("reading the configuration file or creating the datasets directory failed")]
    Read(#[from] std::io::Error),

    #[error("parsing the configuration file failed")]
    Parse(#[from] toml::de::Error),

    #[error("two datasets share the same name")]
    Duplicate(Name),

    #[error("the path has no parent and the directory path is relative")]
    NoParent {
        path: std::path::PathBuf,
        directory: std::path::PathBuf,
    },

    #[error("the timeout is negative")]
    NegativeTimeout(f64),
}

impl Configuration {
    pub fn from_path<P: AsRef<std::path::Path>>(
        path: P,
    ) -> std::result::Result<Self, ConfigurationError> {
        let path = std::fs::canonicalize(path)?;
        let mut configuration = toml::from_str::<Configuration>(&std::fs::read_to_string(&path)?)?;
        {
            let mut names = std::collections::HashSet::new();
            for dataset in configuration.datasets.iter() {
                if names.contains(&dataset.name) {
                    return Err(ConfigurationError::Duplicate(dataset.name.clone()));
                }
                names.insert(&dataset.name);
                if let Some(timeout) = dataset.timeout {
                    if timeout < 0.0 {
                        return Err(ConfigurationError::NegativeTimeout(timeout));
                    }
                }
            }
        }
        if configuration.directory.is_relative() {
            configuration.directory = path
                .parent()
                .ok_or(ConfigurationError::NoParent {
                    path: path.clone(),
                    directory: configuration.directory.clone(),
                })?
                .join(configuration.directory);
        }
        std::fs::create_dir_all(&configuration.directory)?;
        Ok(configuration)
    }
}
