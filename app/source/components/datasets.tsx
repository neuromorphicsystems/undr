import * as React from "react";
import { invoke } from "@tauri-apps/api";
import { message, save } from "@tauri-apps/api/dialog";
import { motion } from "framer-motion";
import styled from "styled-components";
import * as constants from "../hooks/constants";
import { PreferencesContext } from "../hooks/preferences";
import {
    Configuration,
    ConfigurationManager,
    StateContext,
} from "../hooks/state";
import * as state from "../hooks/state";
import Dataset from "./dataset";
import ConfigurationPathBar from "./configurationPathBar";
import Input, { StyledInput } from "./input";
import Add from "../icons/add.svg";
import Bibtex from "../icons/bibtex.svg";
import Install from "../icons/install.svg";
import Size from "../icons/size.svg";

const StyledDatasets = styled(motion.div)`
    height: calc(100vh - ${constants.barHeight}px);
`;

const ConfigurationContainer = styled.div`
    height: calc(100vh - ${constants.barHeight * 3}px);
    overflow: auto;
`;

const Configuration = styled.div``;

const DirectoryBar = styled.div`
    height: ${constants.barHeight}px;
    border-bottom: 1px solid ${props => props.theme.background3};
    display: flex;
    align-items: center;
    padding-left: ${(constants.barHeight - constants.locationSize) / 2}px;
`;

const DatasetsDirectory = styled.div`
    display: flex;
    gap: 20px;
    & > ${StyledInput} {
        background-color: ${props => props.theme.background1};
        width: 150px;
    }
`;

const DatasetsDirectoryLabel = styled.div`
    color: ${props => props.theme.content1};
    display: flex;
    align-items: center;
`;

const Footer = styled.div`
    position: absolute;
    bottom: 0;
    width: 100vw;
    height: ${constants.barHeight}px;
    display: flex;
    align-items: center;
    justify-content: space-evenly;
    background-color: ${props => props.theme.background1};
`;

interface ActionInterface {
    readonly enabled: boolean;
}

const ActionLabel = styled.div`
    font-weight: 500;
`;

const Action = styled.div<ActionInterface>`
    display: flex;
    align-items: center;
    height: ${constants.buttonHeight}px;
    background-color: ${props => props.theme.background1};
    transition: background-color 0.2s;
    cursor: ${props => (props.enabled ? "pointer" : "auto")};
    border-radius: 5px;
    padding-left: 5px;
    padding-right: 10px;
    gap: 5px;
    &:hover {
        background-color: ${props =>
            props.enabled ? props.theme.background2 : props.theme.background1};
    }
    & svg {
        height: ${constants.buttonIconHeight}px;
    }
    & path {
        fill: ${props =>
            props.enabled ? props.theme.content0 : props.theme.content2};
        transition: fill 0.2s;
    }
    & ${ActionLabel} {
        color: ${props =>
            props.enabled ? props.theme.content0 : props.theme.content2};
        transition: color 0.2s;
    }
`;

const ErrorContainer = styled.div`
    height: calc(100vh - ${constants.barHeight * 2}px);
    padding: 20px;
`;

const ErrorTitle = styled.div`
    height: ${constants.barHeight}px;
    background-color: ${props => props.theme.error};
    font-size: ${constants.locationSize}px;
    display: flex;
    align-items: center;
    padding-left: ${(constants.barHeight - constants.locationSize) / 2}px;
    color: ${props => props.theme.content0};
    user-select: none;
`;

const ErrorWrapper = styled.div`
    height: calc(100vh - ${constants.barHeight * 3 + 40}px);
    padding: 20px;
    background-color: ${props => props.theme.background1};
    overflow: hidden;
`;

const Error = styled.div`
    overflow: auto;
    user-select: auto;
    font-weight: 500;
`;

const AddDatasetContainer = styled.div`
    padding: 10px;
    padding-right: 20px;
    display: flex;
    align-items: center;
    justify-content: flex-end;
`;

const AddDataset = styled.div<ActionInterface>`
    padding-left: 15px;
    padding-right: 20px;
    border-radius: 5px;
    background-color: ${props =>
        props.enabled ? props.theme.link : props.theme.background3};
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 5px;
    cursor: ${props => (props.enabled ? "pointer" : "auto")};
    transition: background-color 0.2s;
    & > svg {
        height: ${constants.buttonIconHeight}px;
    }

    & > svg path {
        fill: ${props => props.theme.background0};
    }
    &:hover {
        background-color: ${props =>
            props.enabled ? props.theme.linkActive : props.theme.background3};
    }
`;

const AddLabel = styled.div`
    height: 30px;
    font-weight: 500;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 5px;
    transition: border 0.2s, background-color 0.2s, color 0.2s;
    text-align: center;
    color: ${props => props.theme.background0};
`;

export default function Datasets() {
    const [state, _dispatchStateAction] = React.useContext(StateContext);
    const [preferences, _setStoredPreferences] =
        React.useContext(PreferencesContext);
    const [newDataset, setNewDataset] = React.useState<state.Dataset | null>(
        null
    );
    const actionsEnabled =
        state.configurationManager != null &&
        typeof state.configurationManager.configurationOrError !== "string" &&
        (
            state.configurationManager
                .configurationOrError[0] as unknown as Configuration
        ).datasets.some(dataset => dataset.mode !== "disabled");
    const datasetsNames =
        state.configurationManager == null ||
        typeof state.configurationManager.configurationOrError === "string"
            ? []
            : (
                  state.configurationManager
                      .configurationOrError[0] as unknown as Configuration
              ).datasets.map(dataset => dataset.name);
    return (
        <StyledDatasets
            initial={{ opacity: 1 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 1 }}
            transition={{ duration: constants.transitionDuration }}
        >
            <ConfigurationPathBar
                path={
                    state.configurationManager == null
                        ? ""
                        : state.configurationManager.path
                }
                menu={true}
            />
            {state.configurationManager == null ||
            typeof state.configurationManager.configurationOrError ===
                "string" ? (
                <ErrorContainer>
                    <ErrorTitle>Error</ErrorTitle>
                    <ErrorWrapper>
                        <Error>
                            {state.configurationManager == null
                                ? ""
                                : (state.configurationManager
                                      .configurationOrError as string)}
                        </Error>
                    </ErrorWrapper>
                </ErrorContainer>
            ) : (
                <>
                    <ConfigurationContainer>
                        <Configuration>
                            <DirectoryBar>
                                <DatasetsDirectory>
                                    <DatasetsDirectoryLabel>
                                        Datasets directory
                                    </DatasetsDirectoryLabel>
                                    <Input
                                        value={
                                            state.configurationManager
                                                .configurationOrError[1]
                                        }
                                        onChange={newValue => {
                                            invoke("save_configuration", {
                                                path: (
                                                    state.configurationManager as ConfigurationManager
                                                ).path,
                                                configuration: [
                                                    (
                                                        state.configurationManager as ConfigurationManager
                                                    ).configurationOrError[0],
                                                    newValue,
                                                ],
                                            });
                                        }}
                                        error={false}
                                        live={false}
                                        enabled={true}
                                        title={
                                            state.configurationManager
                                                .configurationOrError[0]
                                                .directory
                                        }
                                    />
                                </DatasetsDirectory>
                            </DirectoryBar>
                            {state.configurationManager.configurationOrError[0].datasets.map(
                                (dataset, index, datasets) => (
                                    <Dataset
                                        key={`${dataset.name}${index
                                            .toString()
                                            .padStart(6, "0")}`}
                                        dataset={dataset}
                                        datasetsNames={datasetsNames}
                                        datasetsNamesIndex={index}
                                        edit={false}
                                        showDelete={true}
                                        onChange={dataset => {
                                            invoke("save_configuration", {
                                                path: (
                                                    state.configurationManager as ConfigurationManager
                                                ).path,
                                                configuration: [
                                                    {
                                                        directory: (
                                                            (
                                                                state.configurationManager as ConfigurationManager
                                                            )
                                                                .configurationOrError[0] as unknown as Configuration
                                                        ).directory,
                                                        datasets: [
                                                            ...datasets.slice(
                                                                0,
                                                                index
                                                            ),
                                                            dataset,
                                                            ...datasets.slice(
                                                                index + 1
                                                            ),
                                                        ],
                                                    },
                                                    (
                                                        state.configurationManager as ConfigurationManager
                                                    ).configurationOrError[1],
                                                ],
                                            }).catch(error => {
                                                console.error(error);
                                                message(JSON.stringify(error), {
                                                    title: "Error",
                                                    type: "error",
                                                });
                                            });
                                        }}
                                        onDelete={() => {
                                            invoke("save_configuration", {
                                                path: (
                                                    state.configurationManager as ConfigurationManager
                                                ).path,
                                                configuration: [
                                                    {
                                                        directory: (
                                                            (
                                                                state.configurationManager as ConfigurationManager
                                                            )
                                                                .configurationOrError[0] as unknown as Configuration
                                                        ).directory,
                                                        datasets: [
                                                            ...datasets.slice(
                                                                0,
                                                                index
                                                            ),
                                                            ...datasets.slice(
                                                                index + 1
                                                            ),
                                                        ],
                                                    },
                                                    (
                                                        state.configurationManager as ConfigurationManager
                                                    ).configurationOrError[1],
                                                ],
                                            }).catch(error => {
                                                console.error(error);
                                                message(JSON.stringify(error), {
                                                    title: "Error",
                                                    type: "error",
                                                });
                                            });
                                        }}
                                        onCancel={() => {}}
                                    ></Dataset>
                                )
                            )}
                            {newDataset != null && (
                                <Dataset
                                    dataset={newDataset}
                                    datasetsNames={datasetsNames}
                                    datasetsNamesIndex={datasetsNames.length}
                                    edit={true}
                                    showDelete={false}
                                    onChange={dataset => {
                                        invoke("save_configuration", {
                                            path: (
                                                state.configurationManager as ConfigurationManager
                                            ).path,
                                            configuration: [
                                                {
                                                    directory: (
                                                        (
                                                            state.configurationManager as ConfigurationManager
                                                        )
                                                            .configurationOrError[0] as unknown as Configuration
                                                    ).directory,
                                                    datasets: [
                                                        ...(
                                                            (
                                                                state.configurationManager as ConfigurationManager
                                                            )
                                                                .configurationOrError[0] as unknown as Configuration
                                                        ).datasets,
                                                        dataset,
                                                    ],
                                                },
                                                (
                                                    state.configurationManager as ConfigurationManager
                                                ).configurationOrError[1],
                                            ],
                                        }).catch(error => {
                                            console.error(error);
                                            message(JSON.stringify(error), {
                                                title: "Error",
                                                type: "error",
                                            });
                                        });
                                        setNewDataset(null);
                                    }}
                                    onDelete={() => setNewDataset(null)}
                                    onCancel={() => setNewDataset(null)}
                                ></Dataset>
                            )}
                            <AddDatasetContainer>
                                <AddDataset
                                    enabled={newDataset == null}
                                    onClick={() => {
                                        if (newDataset == null) {
                                            setNewDataset({
                                                name: "",
                                                mode: "remote",
                                                url: "",
                                                timeout: null,
                                            });
                                        }
                                    }}
                                >
                                    <Add />
                                    <AddLabel>Add dataset</AddLabel>
                                </AddDataset>
                            </AddDatasetContainer>
                        </Configuration>
                    </ConfigurationContainer>
                    <Footer>
                        <Action
                            enabled={actionsEnabled}
                            onClick={() => {
                                if (actionsEnabled) {
                                    invoke("calc_size", {
                                        configuration: (
                                            state.configurationManager as ConfigurationManager
                                        ).configurationOrError[0],
                                        filePermits:
                                            preferences.parallelFileDescriptors(),
                                        downloadIndexPermits:
                                            preferences.parallelIndexDownloads(),
                                    }).catch(error => {
                                        console.error(error);
                                        message(JSON.stringify(error), {
                                            title: "Error",
                                            type: "error",
                                        });
                                    });
                                }
                            }}
                        >
                            <Size />
                            <ActionLabel>Calc. size</ActionLabel>
                        </Action>
                        <Action
                            enabled={actionsEnabled}
                            onClick={() => {
                                if (actionsEnabled) {
                                    save({
                                        title: "Save citations",
                                        defaultPath: "datasets",
                                        filters: [
                                            {
                                                name: "bibtex",
                                                extensions: ["bib"],
                                            },
                                        ],
                                    })
                                        .then(outputPath => {
                                            if (outputPath != null) {
                                                invoke("cite", {
                                                    configuration: (
                                                        state.configurationManager as ConfigurationManager
                                                    ).configurationOrError[0],
                                                    force: false,
                                                    filePermits:
                                                        preferences.parallelFileDescriptors(),
                                                    downloadIndexPermits:
                                                        preferences.parallelIndexDownloads(),
                                                    downloadDoiPermits:
                                                        preferences.parallelDoiDownloads(),
                                                    doiTimeout:
                                                        preferences.doiTimeout(),
                                                    outputPath,
                                                }).catch(error => {
                                                    console.error(error);
                                                    message(
                                                        JSON.stringify(error),
                                                        {
                                                            title: "Error",
                                                            type: "error",
                                                        }
                                                    );
                                                });
                                            }
                                        })
                                        .catch(error => {
                                            console.error(error);
                                            message(JSON.stringify(error), {
                                                title: "Error",
                                                type: "error",
                                            });
                                        });
                                }
                            }}
                        >
                            <Bibtex />
                            <ActionLabel>Cite</ActionLabel>
                        </Action>
                        <Action
                            enabled={actionsEnabled}
                            onClick={() => {
                                if (actionsEnabled) {
                                    invoke("install", {
                                        configuration: (
                                            state.configurationManager as ConfigurationManager
                                        ).configurationOrError[0],
                                        force: false,
                                        keep: preferences.storedPreferences
                                            .keep,
                                        filePermits:
                                            preferences.parallelFileDescriptors(),
                                        downloadIndexPermits:
                                            preferences.parallelIndexDownloads(),
                                        downloadPermits:
                                            preferences.parallelDownloads(),
                                        decodePermits:
                                            preferences.parallelDecompressions(),
                                    }).catch(error => {
                                        console.error(error);
                                        message(JSON.stringify(error), {
                                            title: "Error",
                                            type: "error",
                                        });
                                    });
                                }
                            }}
                        >
                            <Install />
                            <ActionLabel>Install</ActionLabel>
                        </Action>
                    </Footer>
                </>
            )}
        </StyledDatasets>
    );
}
