use crate::types;
use serde::ser::SerializeSeq;

#[derive(Debug, serde::Serialize, serde::Deserialize)]
pub struct Version {
    pub major: u64,
    pub minor: u64,
    pub patch: u64,
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
#[serde(tag = "type")]
pub enum Compression {
    #[serde(rename = "none")]
    NoneCompression { suffix: types::Name },
    #[serde(rename = "brotli")]
    Brotli {
        size: u64,
        hash: types::Hash,
        suffix: types::Name,
    },
}

#[derive(Debug)]
pub struct Compressions {
    pub first: Compression,
    pub rest: Vec<Compression>,
}

impl serde::Serialize for Compressions {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        let mut seq = serializer.serialize_seq(Some(self.rest.len() + 1))?;
        seq.serialize_element(&self.first)?;
        for compression in &self.rest {
            seq.serialize_element(&compression)?;
        }
        seq.end()
    }
}

impl<'de> serde::Deserialize<'de> for Compressions {
    fn deserialize<D>(deserializer: D) -> Result<Compressions, D::Error>
    where
        D: serde::Deserializer<'de>,
    {
        struct CompressionVisitor;
        impl<'de> serde::de::Visitor<'de> for CompressionVisitor {
            type Value = Compressions;

            fn expecting(&self, formatter: &mut std::fmt::Formatter) -> std::fmt::Result {
                formatter.write_str("enum Compression")
            }

            fn visit_seq<V>(self, mut seq: V) -> Result<Self::Value, V::Error>
            where
                V: serde::de::SeqAccess<'de>,
            {
                let mut compressions = Compressions {
                    first: seq
                        .next_element()?
                        .ok_or_else(|| serde::de::Error::invalid_length(0, &self))?,
                    rest: Vec::new(),
                };
                while let Some(compression) = seq.next_element()? {
                    compressions.rest.push(compression);
                }
                Ok(compressions)
            }
        }
        deserializer.deserialize_seq(CompressionVisitor)
    }
}

#[derive(Debug, serde::Serialize, serde::Deserialize)]
pub struct Resource {
    pub name: types::Name,
    pub size: u64,
    pub hash: types::Hash,
    pub compressions: Compressions,
    pub doi: Option<types::Doi>,
}

pub struct CompressionProperties<'a> {
    pub size: u64,
    pub hash: &'a types::Hash,
    pub suffix: &'a types::Name,
}

impl Resource {
    fn compression_properties_from<'a>(
        &'a self,
        compression: &'a Compression,
    ) -> CompressionProperties<'a> {
        match compression {
            Compression::NoneCompression { suffix } => CompressionProperties {
                size: self.size,
                hash: &self.hash,
                suffix,
            },
            Compression::Brotli { size, hash, suffix } => CompressionProperties {
                size: *size,
                hash,
                suffix,
            },
        }
    }

    pub fn best_compression(&self) -> (&Compression, CompressionProperties) {
        self.compressions.rest.iter().fold(
            (
                &self.compressions.first,
                self.compression_properties_from(&self.compressions.first),
            ),
            |accumulator, compression| {
                let compression_properties = self.compression_properties_from(compression);
                if compression_properties.size < accumulator.1.size {
                    (compression, compression_properties)
                } else {
                    accumulator
                }
            },
        )
    }
}

#[derive(Debug, serde::Serialize, serde::Deserialize)]
#[serde(tag = "type")]
pub enum Properties {
    #[serde(rename = "aps")]
    Aps { width: u64, height: u64 },
    #[serde(rename = "dvs")]
    Dvs { width: u64, height: u64 },
    #[serde(rename = "imu")]
    Imu,
}

#[derive(Debug, serde::Serialize, serde::Deserialize)]
pub struct File {
    #[serde(flatten)]
    pub resource: Resource,
    pub properties: Properties,
    pub metadata: Option<serde_json::Value>,
}

#[derive(Debug, serde::Serialize, serde::Deserialize)]
pub struct OtherFile {
    #[serde(flatten)]
    pub resource: Resource,
    pub metadata: Option<serde_json::Value>,
}

#[derive(Debug, serde::Serialize, serde::Deserialize)]
pub struct Index {
    pub version: Version,
    pub doi: Option<types::Doi>,
    pub directories: Vec<types::Name>,
    pub files: Vec<File>,
    pub other_files: Vec<OtherFile>,
    pub metadata: Option<serde_json::Value>,
}
