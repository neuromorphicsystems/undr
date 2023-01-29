use crate::types;

#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
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

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum InstallableMode {
    Remote,
    Local,
    Raw,
}

impl TryFrom<Mode> for InstallableMode {
    type Error = ();
    fn try_from(mode: Mode) -> Result<Self, Self::Error> {
        match mode {
            Mode::Disabled => Err(()),
            Mode::Remote => Ok(InstallableMode::Remote),
            Mode::Local => Ok(InstallableMode::Local),
            Mode::Raw => Ok(InstallableMode::Raw),
        }
    }
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct DatasetSettings {
    pub name: types::Name,
    pub url: url::Url,
    pub mode: Mode,
    pub timeout: Option<f64>,
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct Configuration {
    pub directory: std::path::PathBuf,
    pub datasets: Vec<DatasetSettings>,
}

#[derive(Debug, thiserror::Error)]
pub enum ConfigurationError {
    #[error("resolving the path failed")]
    Resolve { path: std::path::PathBuf },

    #[error("reading the configuration file failed")]
    Read { path: std::path::PathBuf },

    #[error("parsing the configuration file failed")]
    Parse(#[from] toml::de::Error),

    #[error("two datasets share the same name")]
    Duplicate(types::Name),

    #[error("the path has no parent and the directory path is relative")]
    NoParent {
        path: std::path::PathBuf,
        directory: std::path::PathBuf,
    },

    #[error("the timeout is negative")]
    NegativeTimeout(f64),
}

impl Configuration {
    /// returns the parsed configuration (which contains the resolved datasets directory) and the un-resolved datasets directory.
    pub fn from_path<P: AsRef<std::path::Path>>(
        path: P,
    ) -> std::result::Result<(Self, std::path::PathBuf), ConfigurationError> {
        let path = std::fs::canonicalize(path.as_ref()).map_err(|_| ConfigurationError::Read {
            path: path.as_ref().to_owned(),
        })?;
        let mut configuration = toml::from_str::<Configuration>(
            &std::fs::read_to_string(&path)
                .map_err(|_| ConfigurationError::Read { path: path.clone() })?,
        )?;
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
        let datasets_directory = configuration.directory.clone();
        if configuration.directory.is_relative() {
            configuration.directory = path
                .parent()
                .ok_or(ConfigurationError::NoParent {
                    path: path.clone(),
                    directory: configuration.directory.clone(),
                })?
                .join(&configuration.directory)
        }
        // canonicalize only works with existing files / directories
        // std::path::PathBuf::components performs fewer but useful normalizations and does not check the file system
        configuration.directory = configuration.directory.components().collect();
        Ok((configuration, datasets_directory))
    }
}
