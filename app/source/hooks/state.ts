import * as React from "react";
import { NavigateFunction, NavigateOptions, To } from "react-router-dom";
import { invoke } from "@tauri-apps/api";
import { message } from "@tauri-apps/api/dialog";
import { listen, UnlistenFn } from "@tauri-apps/api/event";
import { Preferences, StoredPreferences } from "./preferences";
import * as constants from "./constants";

export type DatasetMode = "disabled" | "remote" | "local" | "raw";

type ActionType = "calc_size" | "cite" | "install";

export interface Dataset {
    name: string;
    mode: DatasetMode;
    url: string;
    timeout: number | null;
}

export interface Configuration {
    directory: string;
    datasets: Dataset[];
}
export interface ConfigurationManager {
    path: string;
    configurationOrError: [Configuration, string] | string;
}

interface ConfigurationPayload {
    path: string;
    configuration_or_error: {
        type: string;
        payload: [Configuration, string] | string;
    };
}

interface MessageIndexLoaded {
    type: string;
    path_id: string;
    children: number;
}

interface MessageValue {
    initial_bytes: number;
    final_bytes: number;
}

interface MessageReport {
    local_bytes: number;
    remote_bytes: number;
}

interface MessageDirectoryScanned {
    type: string;
    path_id: string;
    initial_download_count: number;
    initial_process_count: number;
    final_count: number;
    index: MessageValue;
    download: MessageValue;
    process: MessageValue;
    calculate_size_compressed: MessageReport;
    calculate_size_raw: MessageReport;
}

interface MessageDoi {
    type: string;
    path_id: string;
    value: string;
}

interface MessageDoiProgress {
    type: string;
    value: string;
    status: "start" | "success" | "error";
    payload?: string;
}

interface MessageRemoteProgress {
    type: string;
    path_id: string;
    initial_bytes: number;
    current_bytes: number;
    final_bytes: number;
    complete: boolean;
}

interface MessageDecodeProgress {
    type: string;
    path_id: string;
    initial_bytes: number;
    current_bytes: number;
    final_bytes: number;
    complete: boolean;
}

type MessagePayload =
    | MessageIndexLoaded
    | MessageDirectoryScanned
    | MessageDoi
    | MessageRemoteProgress
    | MessageDecodeProgress
    | MessageDoiProgress;

interface ActionPayload {
    type: string;
    payload?: string | MessagePayload;
}

interface Value {
    initialBytes: bigint;
    currentBytes: bigint;
    finalBytes: bigint;
}

interface Report {
    localBytes: bigint;
    remoteBytes: bigint;
}

interface ActionDataset {
    name: string;
    mode: "remote" | "local" | "raw";
    index: boolean;
    currentIndexFiles: number;
    finalIndexFiles: number;
    download: Value;
    process: Value;
    calcSizeIndex: bigint;
    calcSizeCompressed: Report;
    calcSizeRaw: Report;
}

interface ActionDatasetSnapshot {
    download: Value;
    process: Value;
}

interface Doi {
    pathIds: string[];
    status: "index" | "start" | "success" | "error";
}

export interface Action {
    type: ActionType;
    configurationPath: string;
    datasets: ActionDataset[];
    status: "running" | "cancelled" | "ended" | "error";
    error: string | null;
    speed: [number, number];
    timeLeft: number | null;
    speedSamples: [number, number][];
    previousSampleTimestamp: number | null;
    previousDatasets: ActionDatasetSnapshot[] | null;
    begin: number;
    end: number | null;
    speedAverage: [number, number] | null;
    valueToDoi: {
        [key: string]: Doi;
    };
}

function editDataset(
    message:
        | MessageIndexLoaded
        | MessageDirectoryScanned
        | MessageDoi
        | MessageRemoteProgress
        | MessageDecodeProgress,
    datasets: ActionDataset[],
    editDownloadAndProcess: boolean
) {
    for (let index = 0; index < datasets.length; ++index) {
        if (
            message.path_id === datasets[index].name ||
            message.path_id.startsWith(`${datasets[index].name}/`)
        ) {
            if (editDownloadAndProcess) {
                datasets[index] = {
                    ...datasets[index],
                    download: { ...datasets[index].download },
                    process: { ...datasets[index].process },
                };
            } else {
                datasets[index] = {
                    ...datasets[index],
                };
            }
            return datasets[index];
        }
    }
    throw new Error(`no dataset found for ${message}`);
}

interface State {
    loaded: boolean;
    configurationManager: ConfigurationManager | null;
    action: Action | null;
    navigateFunction: NavigateFunction | null;
}

export function stateNavigate(state: State, to: To, options?: NavigateOptions) {
    if (state.navigateFunction == null) {
        throw new Error("navigate is not initialised");
    }
    state.navigateFunction(to, options);
}

export function mainRoute(state: State) {
    if (state.action != null) {
        return "/action";
    } else if (state.configurationManager != null) {
        return "/datasets";
    } else {
        return "/setup";
    }
}

export function navigateToMainRoute(state: State, options?: NavigateOptions) {
    stateNavigate(state, mainRoute(state), options);
}

function defaultState(): State {
    return {
        loaded: false,
        configurationManager: null,
        action: null,
        navigateFunction: null,
    };
}

interface StateAction {
    type:
        | "navigate"
        | "configuration"
        | "speed-tick"
        | "action-start"
        | "action-index-loaded"
        | "action-directory-scanned"
        | "action-doi"
        | "action-remote-progress"
        | "action-decode-progress"
        | "action-error"
        | "action-end"
        | "action-cancel"
        | "action-cancel-done"
        | "action-ok"
        | "action-doi-progress";
    payload: unknown;
}

function reducer(state: State, action: StateAction): State {
    switch (action.type) {
        case "navigate":
            return {
                ...state,
                navigateFunction: action.payload as NavigateFunction,
            };
        case "configuration":
            if (!state.loaded) {
                invoke("show_main_window").catch(error => {
                    console.error(error);
                    message(JSON.stringify(error), {
                        title: "Error",
                        type: "error",
                    });
                });
            }
            return {
                ...state,
                loaded: true,
                configurationManager: action.payload as ConfigurationManager,
            };
        case "speed-tick":
            if (
                state.action == null ||
                state.action.status === "error" ||
                state.action.status === "ended"
            ) {
                return state;
            } else {
                const timestamp = Date.now();
                const speedSample: [number, number] = [0, 0];
                if (
                    state.action.previousDatasets != null &&
                    state.action.previousSampleTimestamp != null
                ) {
                    for (
                        let index = 0;
                        index < state.action.datasets.length;
                        ++index
                    ) {
                        speedSample[0] += Number(
                            state.action.datasets[index].download.currentBytes -
                                state.action.datasets[index].download
                                    .initialBytes -
                                (state.action.previousDatasets[index].download
                                    .currentBytes -
                                    state.action.previousDatasets[index]
                                        .download.initialBytes)
                        );
                        speedSample[1] += Number(
                            state.action.datasets[index].process.currentBytes -
                                state.action.datasets[index].process
                                    .initialBytes -
                                (state.action.previousDatasets[index].process
                                    .currentBytes -
                                    state.action.previousDatasets[index].process
                                        .initialBytes)
                        );
                    }
                    speedSample[0] = Math.round(
                        speedSample[0] *
                            (1000 /
                                (timestamp -
                                    state.action.previousSampleTimestamp))
                    );
                    speedSample[1] = Math.round(
                        speedSample[1] *
                            (1000 /
                                (timestamp -
                                    state.action.previousSampleTimestamp))
                    );
                }
                const speedSamples: [number, number][] = [
                    ...state.action.speedSamples.slice(
                        -(constants.maximumSpeedSamples - 1)
                    ),
                    speedSample,
                ];
                const speed = speedSamples
                    .reduce(
                        (speed, sample) => [
                            speed[0] + sample[0],
                            speed[1] + sample[1],
                        ],
                        [0, 0]
                    )
                    .map(value => Math.round(value / speedSamples.length)) as [
                    number,
                    number
                ];
                let timeLeft: number | null = null;
                if (
                    state.action.previousDatasets != null &&
                    state.action.previousSampleTimestamp != null
                ) {
                    let downloadLeft: bigint | null = BigInt(0);
                    let processLeft: bigint | null = BigInt(0);
                    for (const dataset of state.action.datasets) {
                        if (dataset.index) {
                            downloadLeft = null;
                            processLeft = null;
                            break;
                        }
                        downloadLeft +=
                            dataset.download.finalBytes -
                            dataset.download.currentBytes;
                        if (dataset.mode === "raw") {
                            processLeft +=
                                dataset.process.finalBytes -
                                dataset.process.currentBytes;
                        }
                    }
                    if (downloadLeft != null && processLeft != null) {
                        if (speed[0] > 0 && speed[1] > 0) {
                            timeLeft = Math.ceil(
                                Math.max(
                                    Number(downloadLeft) / speed[0],
                                    Number(processLeft) / speed[1]
                                )
                            );
                        } else if (speed[0] > 0) {
                            timeLeft = Math.ceil(
                                Number(downloadLeft) / speed[0]
                            );
                        } else if (speed[1] > 0) {
                            timeLeft = Math.ceil(
                                Number(processLeft) / speed[1]
                            );
                        }
                    }
                }
                return {
                    ...state,
                    action: {
                        ...state.action,
                        speed,
                        timeLeft,
                        speedSamples,
                        previousSampleTimestamp: timestamp,
                        previousDatasets: state.action.datasets.map(
                            dataset => ({
                                download: { ...dataset.download },
                                process: { ...dataset.process },
                            })
                        ),
                    },
                };
            }
        case "action-start":
            if (
                state.configurationManager == null ||
                typeof state.configurationManager.configurationOrError ===
                    "string"
            ) {
                return state;
            } else {
                setTimeout(() => {
                    stateNavigate(state, "/action");
                }, 0);
                return {
                    ...state,
                    action: {
                        type: action.payload as ActionType,
                        configurationPath: state.configurationManager.path,
                        datasets: (
                            state.configurationManager
                                .configurationOrError as unknown as [
                                Configuration,
                                string
                            ]
                        )[0].datasets
                            .filter(dataset => dataset.mode !== "disabled")
                            .map(dataset => ({
                                name: dataset.name,
                                mode: dataset.mode as
                                    | "remote"
                                    | "local"
                                    | "raw",
                                index: true,
                                currentIndexFiles: 0,
                                finalIndexFiles: 1,
                                download: {
                                    initialBytes: BigInt(0),
                                    currentBytes: BigInt(0),
                                    finalBytes: BigInt(0),
                                },
                                process: {
                                    initialBytes: BigInt(0),
                                    currentBytes: BigInt(0),
                                    finalBytes: BigInt(0),
                                },
                                calcSizeIndex: BigInt(0),
                                calcSizeCompressed: {
                                    localBytes: BigInt(0),
                                    remoteBytes: BigInt(0),
                                },
                                calcSizeRaw: {
                                    localBytes: BigInt(0),
                                    remoteBytes: BigInt(0),
                                },
                            })),
                        status: "running",
                        error: null,
                        speed: [0, 0],
                        timeLeft: null,
                        speedSamples: [],
                        previousSampleTimestamp: null,
                        previousDatasets: null,
                        begin: Date.now(),
                        end: null,
                        speedAverage: null,
                        valueToDoi: {},
                    },
                };
            }
        case "action-index-loaded":
            if (state.action == null) {
                return state;
            } else {
                const message = action.payload as MessageIndexLoaded;
                const datasets = [...state.action.datasets];
                const dataset = editDataset(
                    action.payload as MessageIndexLoaded,
                    datasets,
                    false
                );
                dataset.finalIndexFiles += message.children;
                return {
                    ...state,
                    action: {
                        ...state.action,
                        datasets,
                    },
                };
            }
        case "action-directory-scanned":
            if (state.action == null) {
                return state;
            } else {
                const message = action.payload as MessageDirectoryScanned;
                const datasets = [...state.action.datasets];
                const dataset = editDataset(
                    action.payload as MessageIndexLoaded,
                    datasets,
                    true
                );
                ++dataset.currentIndexFiles;
                dataset.download.initialBytes += BigInt(
                    message.index.initial_bytes + message.download.initial_bytes
                );
                dataset.download.currentBytes += BigInt(
                    message.index.initial_bytes + message.download.initial_bytes
                );
                dataset.download.finalBytes += BigInt(
                    message.index.final_bytes + message.download.final_bytes
                );
                dataset.process.initialBytes += BigInt(
                    message.process.initial_bytes
                );
                dataset.process.currentBytes += BigInt(
                    message.process.initial_bytes
                );
                dataset.process.finalBytes += BigInt(
                    message.process.final_bytes
                );
                dataset.calcSizeIndex += BigInt(message.index.final_bytes);
                dataset.calcSizeCompressed.localBytes += BigInt(
                    message.calculate_size_compressed.local_bytes
                );
                dataset.calcSizeCompressed.remoteBytes += BigInt(
                    message.calculate_size_compressed.remote_bytes
                );
                dataset.calcSizeRaw.localBytes += BigInt(
                    message.calculate_size_raw.local_bytes
                );
                dataset.calcSizeRaw.remoteBytes += BigInt(
                    message.calculate_size_raw.remote_bytes
                );
                if (dataset.currentIndexFiles === dataset.finalIndexFiles) {
                    dataset.index = false;
                }
                return {
                    ...state,
                    action: {
                        ...state.action,
                        datasets,
                    },
                };
            }
        case "action-remote-progress":
            if (state.action == null) {
                return state;
            } else {
                const message = action.payload as MessageRemoteProgress;
                const datasets = [...state.action.datasets];
                const dataset = editDataset(
                    action.payload as MessageIndexLoaded,
                    datasets,
                    true
                );
                if (message.initial_bytes < 0 && !dataset.index) {
                    dataset.download.initialBytes += BigInt(
                        message.initial_bytes
                    );
                    dataset.download.currentBytes += BigInt(
                        message.current_bytes
                    );
                }
                if (message.initial_bytes === 0) {
                    dataset.download.currentBytes += BigInt(
                        message.current_bytes
                    );
                }
                return {
                    ...state,
                    action: {
                        ...state.action,
                        datasets,
                    },
                };
            }
        case "action-decode-progress":
            if (state.action == null) {
                return state;
            } else {
                const message = action.payload as MessageDecodeProgress;
                const datasets = [...state.action.datasets];
                const dataset = editDataset(
                    action.payload as MessageIndexLoaded,
                    datasets,
                    true
                );
                if (message.initial_bytes < 0) {
                    dataset.process.initialBytes += BigInt(
                        message.initial_bytes
                    );
                    dataset.process.currentBytes += BigInt(
                        message.current_bytes
                    );
                } else if (message.initial_bytes === 0) {
                    dataset.process.currentBytes += BigInt(
                        message.current_bytes
                    );
                }
                return {
                    ...state,
                    action: {
                        ...state.action,
                        datasets,
                    },
                };
            }
        case "action-error":
            if (state.action == null) {
                return state;
            } else {
                return {
                    ...state,
                    action: {
                        ...state.action,
                        status: "error",
                        error: action.payload as string,
                    },
                };
            }
        case "action-end":
            if (
                state.action == null ||
                state.action.status === "ended" ||
                state.action.status === "error"
            ) {
                return state;
            } else if (state.action.status === "cancelled") {
                const newState = {
                    ...state,
                    action: null,
                };
                setTimeout(() => {
                    navigateToMainRoute(newState);
                }, 0);
                return newState;
            } else {
                const end = Date.now();
                const delta = (end - state.action.begin) / 1000;
                const total: [bigint, bigint] = [BigInt(0), BigInt(0)];
                for (const dataset of state.action.datasets) {
                    total[0] +=
                        dataset.download.currentBytes -
                        dataset.download.initialBytes;
                    total[1] +=
                        dataset.process.currentBytes -
                        dataset.process.initialBytes;
                }
                return {
                    ...state,
                    action: {
                        ...state.action,
                        status: "ended",
                        end,
                        speedAverage: [
                            Number(total[0]) / delta,
                            Number(total[1]) / delta,
                        ],
                    },
                };
            }
        case "action-cancel":
            if (state.action == null || state.action.status !== "running") {
                return state;
            } else {
                invoke("cancel", {})
                    .then(() => {
                        (action.payload as React.Dispatch<StateAction>)({
                            type: "action-cancel-done",
                            payload: null,
                        });
                    })
                    .catch(console.error);
                return {
                    ...state,
                    action: {
                        ...state.action,
                        status: "cancelled",
                    },
                };
            }
        case "action-cancel-done":
        case "action-ok":
            if (state.action == null) {
                return state;
            } else {
                const newState = {
                    ...state,
                    action: null,
                };
                setTimeout(() => {
                    navigateToMainRoute(newState);
                }, 0);
                return newState;
            }
        case "action-doi": {
            if (state.action == null) {
                return state;
            } else {
                const message = action.payload as MessageDoi;
                if (
                    Object.prototype.hasOwnProperty.call(
                        state.action.valueToDoi,
                        message.value
                    )
                ) {
                    return {
                        ...state,
                        action: {
                            ...state.action,
                            valueToDoi: {
                                ...state.action.valueToDoi,
                                [message.value]: {
                                    ...state.action.valueToDoi[message.value],
                                    pathIds: [
                                        ...state.action.valueToDoi[
                                            message.value
                                        ].pathIds,
                                        message.path_id,
                                    ].sort((a, b) => a.localeCompare(b)),
                                },
                            },
                        },
                    };
                } else {
                    return {
                        ...state,
                        action: {
                            ...state.action,
                            valueToDoi: {
                                ...state.action.valueToDoi,
                                [message.value]: {
                                    pathIds: [message.path_id],
                                    status: "index",
                                },
                            },
                        },
                    };
                }
            }
        }
        case "action-doi-progress":
            if (state.action == null) {
                return state;
            } else {
                const message = action.payload as MessageDoiProgress;
                if (
                    Object.prototype.hasOwnProperty.call(
                        state.action.valueToDoi,
                        message.value
                    )
                ) {
                    return {
                        ...state,
                        action: {
                            ...state.action,
                            valueToDoi: {
                                ...state.action.valueToDoi,
                                [message.value]: {
                                    ...state.action.valueToDoi[message.value],
                                    status: message.status,
                                },
                            },
                        },
                    };
                } else {
                    console.error("unknown DOI", message.value);
                    return state;
                }
            }
        default:
            throw new Error(`unknown action ${action}`);
    }
}

export const StateContext = React.createContext<
    [State, React.Dispatch<StateAction>]
>([defaultState(), () => {}]);

export function useState(
    setPreferences: React.Dispatch<React.SetStateAction<Preferences>>
): [State, React.Dispatch<StateAction>] {
    const [state, dispatchStateAction] = React.useReducer(
        reducer,
        defaultState()
    );
    React.useEffect(() => {
        let unlistenCallback: UnlistenFn | null = null;
        let returnCalled = false;
        listen("configuration", event => {
            if (event.payload == null) {
                dispatchStateAction({
                    type: "configuration",
                    payload: null,
                });
            } else {
                dispatchStateAction({
                    type: "configuration",
                    payload: {
                        path: (event.payload as ConfigurationPayload).path,
                        configurationOrError: (
                            event.payload as ConfigurationPayload
                        ).configuration_or_error.payload,
                    } as ConfigurationManager,
                });
            }
        })
            .then(unlisten => {
                invoke("load_preferences")
                    .then(rawPreferencesAndAvailableParallelism => {
                        setPreferences(preferences =>
                            preferences.newWithRaw(
                                (
                                    rawPreferencesAndAvailableParallelism as [
                                        StoredPreferences,
                                        number
                                    ]
                                )[0],
                                (
                                    rawPreferencesAndAvailableParallelism as [
                                        StoredPreferences,
                                        number
                                    ]
                                )[1]
                            )
                        );
                    })
                    .catch(console.error);
                if (returnCalled) {
                    unlisten();
                } else {
                    unlistenCallback = unlisten;
                }
            })
            .catch(console.error);
        return () => {
            if (unlistenCallback == null) {
                returnCalled = true;
            } else {
                unlistenCallback();
            }
        };
    }, []);
    React.useEffect(() => {
        let unlistenCallback: UnlistenFn | null = null;
        let returnCalled = false;
        listen("action", event => {
            switch ((event.payload as ActionPayload).type) {
                case "start":
                    dispatchStateAction({
                        type: "action-start",
                        payload: (event.payload as ActionPayload)
                            .payload as ActionType,
                    });
                    break;
                case "message":
                    switch (
                        (
                            (event.payload as ActionPayload)
                                .payload as MessagePayload
                        ).type
                    ) {
                        case "index_loaded":
                            dispatchStateAction({
                                type: "action-index-loaded",
                                payload: (event.payload as ActionPayload)
                                    .payload as MessageIndexLoaded,
                            });
                            break;
                        case "directory_scanned":
                            dispatchStateAction({
                                type: "action-directory-scanned",
                                payload: (event.payload as ActionPayload)
                                    .payload as MessageDirectoryScanned,
                            });
                            break;
                        case "doi":
                            dispatchStateAction({
                                type: "action-doi",
                                payload: (event.payload as ActionPayload)
                                    .payload as MessageDoi,
                            });
                            break;
                        case "doi_progress":
                            dispatchStateAction({
                                type: "action-doi-progress",
                                payload: (event.payload as ActionPayload)
                                    .payload as MessageDoiProgress,
                            });
                            break;
                        case "remote_progress":
                            dispatchStateAction({
                                type: "action-remote-progress",
                                payload: (event.payload as ActionPayload)
                                    .payload as MessageRemoteProgress,
                            });
                            break;
                        case "decode_progress":
                            dispatchStateAction({
                                type: "action-decode-progress",
                                payload: (event.payload as ActionPayload)
                                    .payload as MessageDecodeProgress,
                            });
                            break;
                        default:
                            console.error(
                                "unknown action event type",
                                event.payload
                            );
                            break;
                    }
                    break;
                case "error":
                    dispatchStateAction({
                        type: "action-error",
                        payload: (event.payload as ActionPayload)
                            .payload as string,
                    });
                    break;
                case "end":
                    dispatchStateAction({ type: "action-end", payload: null });
                    break;
                default:
                    console.error("unknown action event type", event.payload);
                    break;
            }
        })
            .then(unlisten => {
                if (returnCalled) {
                    unlisten();
                } else {
                    unlistenCallback = unlisten;
                }
            })
            .catch(console.error);
        return () => {
            if (unlistenCallback == null) {
                returnCalled = true;
            } else {
                unlistenCallback();
            }
        };
    }, []);
    React.useEffect(() => {
        const interval = window.setInterval(() => {
            dispatchStateAction({
                type: "speed-tick",
                payload: null,
            });
        }, constants.speedInterval * 1000);
        return () => clearInterval(interval);
    }, []);
    return [state, dispatchStateAction];
}
