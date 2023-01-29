import * as React from "react";
import { useLocation } from "react-router-dom";
import { motion } from "framer-motion";
import styled, { useTheme } from "styled-components";
import * as constants from "../hooks/constants";
import { Dimensions } from "../hooks/dimensions";
import { Action, StateContext } from "../hooks/state";
import * as utilities from "../hooks/utilities";
import ConfigurationPathBar from "./configurationPathBar";
import Progress from "./progress";
import Close from "../icons/close.svg";
import DecompressHeavy from "../icons/decompress-heavy.svg";
import Download from "../icons/download.svg";
import DownloadHeavy from "../icons/download-heavy.svg";
import Hourglass from "../icons/hourglass.svg";
import Tick from "../icons/tick.svg";
import Wait from "../icons/wait.svg";

const spacing = (constants.barHeight - constants.progressHeight) / 2;

const StyledActionDisplay = styled(motion.div)`
    position: absolute;
    left: 0;
    right: 0;
    top: 0;
    bottom: 0;
    z-index: 5;
    overflow: hidden;
    background-color: ${props => props.theme.background0};
`;

const Content = styled.div`
    height: calc(100vh - ${3 * constants.barHeight}px);
    overflow: hidden;
`;

interface FooterInterface {
    readonly right: boolean;
}

const Footer = styled.div<FooterInterface>`
    position: absolute;
    bottom: 0;
    width: 100vw;
    height: ${constants.barHeight}px;
    display: flex;
    align-items: center;
    justify-content: ${props => (props.right ? "flex-end" : "space-between")};
    background-color: ${props => props.theme.background1};
    padding-left: ${(constants.barHeight - constants.buttonHeight) / 2}px;
    padding-right: ${(constants.barHeight - constants.buttonHeight) / 2}px;
`;

interface ActionInterface {
    readonly enabled: boolean;
}

const ActionLabel = styled.div`
    font-weight: 500;
`;

const ActionWithIcon = styled.div<ActionInterface>`
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

const Datasets = styled.div``;

const Dataset = styled.div`
    display: flex;
    height: ${constants.barHeight}px;
    align-items: center;
    border-bottom: 1px solid ${props => props.theme.background3};
    overflow: hidden;
    padding-left: ${spacing}px;
    padding-right: ${spacing}px;
    gap: ${spacing}px;
`;

const ReportLeft = styled.div`
    width: 0;
    flex-grow: 2;
`;

const ReportName = styled.div`
    user-select: auto;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    color: ${props => props.theme.content0};
`;

const ReportIndex = styled.div`
    user-select: auto;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    font-size: 12px;
    font-weight: 500;
    padding-top: 3px;
`;

const ReportLabel = styled.span`
    color: ${props => props.theme.content2};
`;

const ReportValue = styled.span`
    padding-left: 10px;
    color: ${props => props.theme.content1};
`;

const ReportRight = styled.div`
    width: 0;
    flex-grow: 3;
`;

const ReportSize = styled.div`
    user-select: auto;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    font-size: 12px;
    font-weight: 500;
    padding-top: 3px;
    color: ${props => props.theme.content1};
`;

interface NamesRulerInterface {
    skip: boolean;
}

const NamesRuler = styled.div<NamesRulerInterface>`
    visibility: hidden;
    display: ${props => (props.skip ? "none" : "inline-block")};
`;

const Name = styled.div`
    font-weight: 500;
`;

const NameRuler = styled(Name)``;

interface NameDisplayInterface {
    readonly mode: "remote" | "local" | "raw" | "complete";
    readonly nameWidth: number;
}

const NameDisplay = styled(Name)<NameDisplayInterface>`
    user-select: auto;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    color: ${props => {
        switch (props.mode) {
            case "remote":
                return props.theme.remote;
            case "local":
                return props.theme.local;
            case "raw":
                return props.theme.raw;
            case "complete":
                return props.theme.complete;
        }
    }};
    flex-shrink: 0;
    width: ${props => props.nameWidth}px;
`;

const StatusContainer = styled.div`
    flex-shrink: 0;
    width: ${constants.progressStatusWidth}px;
`;

const Status = styled.div`
    display: flex;
    align-items: center;
`;

const StatusIcon = styled.div`
    padding-right: 5px;
    width: 29px;
    height: 24px;
    & > svg {
        width: 24px;
        height: 24px;
    }
    & > svg path {
        fill: ${props => props.theme.content1};
    }
`;

const StatusLabel = styled.div`
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    color: ${props => props.theme.content1};
`;

const StatusSmall = styled.div`
    display: flex;
    align-items: center;
    & > ${StatusIcon} {
        padding-right: 3px;
        width: 19px;
        height: 16px;
        & > svg {
            width: 16px;
            height: 16px;
        }
    }
    & > ${StatusLabel} {
        font-size: 12px;
        font-weight: 500;
    }
`;

const SpeedAndTime = styled.div`
    display: flex;
    gap: 20px;
    align-items: center;
`;

const SpeedContainer = styled.div`
    flex-shrink: 0;
    width: ${constants.speedStatusWidth}px;
`;

const SpeedContainerAverage = styled(SpeedContainer)`
    width: ${constants.speedAverageStatusWidth}px;
`;

const TimeContainer = styled(Status)`
    width: ${constants.timeStatusWidth}px;
    & ${StatusIcon} {
        flex-shrink: 0;
    }
`;

const Dois = styled.div``;

const Doi = styled.div`
    display: flex;
    height: ${constants.barHeight}px;
    align-items: center;
    border-bottom: 1px solid ${props => props.theme.background3};
    overflow: hidden;
    padding-left: ${(constants.barHeight - constants.buttonHeight) / 2}px;
    padding-right: ${(constants.barHeight - constants.buttonHeight) / 2}px;
    & > ${Status} {
        width: 100%;
    }
`;

const DoiLink = styled.a`
    font-weight: 500;
    user-select: auto;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    text-decoration: none;
    padding-right: ${(constants.barHeight - constants.buttonHeight) / 2}px;
    color: ${props => props.theme.content0};
    cursor: pointer;
    &:hover {
        text-decoration: underline;
        color: ${props => props.theme.content1};
    }
`;

const DoiDatasets = styled.span`
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    color: ${props => props.theme.content1};
`;

const ErrorContainer = styled.div`
    height: calc(100vh - ${3 * constants.barHeight}px);
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
    height: calc(100vh - ${constants.barHeight * 4 + 40}px);
    padding: 20px;
    background-color: ${props => props.theme.background1};
    overflow: hidden;
`;

const Error = styled.div`
    overflow: auto;
    user-select: auto;
    font-weight: 500;
`;

export default function ActionDisplay() {
    const location = useLocation();
    const [state, dispatchStateAction] = React.useContext(StateContext);
    const [action, setAction] = React.useState<Action>(
        state.action == null
            ? {
                  type: "install",
                  configurationPath: "",
                  datasets: [],
                  status: null as unknown as
                      | "running"
                      | "cancelled"
                      | "ended"
                      | "error", // use null to avoid showing actions until action is available
                  error: null,
                  speed: [0, 0],
                  timeLeft: null,
                  speedSamples: [],
                  previousSampleTimestamp: null,
                  previousDatasets: null,
                  begin: 0,
                  end: null,
                  speedAverage: null,
                  valueToDoi: {},
              }
            : state.action
    );
    React.useEffect(() => {
        if (state.action != null) {
            setAction(state.action);
        }
    }, [state.action]);
    const theme = useTheme();
    const namesRulerRef = React.useRef<HTMLDivElement>(null);
    const [namesRulerDimensions, setNamesRulerDimensions] =
        React.useState<Dimensions>({
            width: null,
            height: null,
        });
    React.useEffect(() => {
        setNamesRulerDimensions({
            width: (namesRulerRef.current as HTMLDivElement).offsetWidth,
            height: (namesRulerRef.current as HTMLDivElement).offsetHeight,
        });
    }, [action.status == null]);
    const [windowWidth, setWindowWidth] = React.useState(window.innerWidth);
    React.useEffect(() => {
        const listener = utilities.debounce(
            () => setWindowWidth(window.innerWidth),
            16
        );
        window.addEventListener("resize", listener);
        return () => {
            window.removeEventListener("resize", listener);
            listener.reset();
        };
    });
    const nameWidth =
        namesRulerDimensions.width == null || namesRulerDimensions.width === 0
            ? null
            : Math.min(
                  windowWidth -
                      4 * spacing -
                      constants.progressStatusWidth -
                      constants.progressMinimumBarWidth,
                  namesRulerDimensions.width + 1
              );
    const showProcessSpeed =
        action.type === "install" &&
        action.datasets.some(dataset => dataset.mode === "raw");
    return (
        <StyledActionDisplay
            initial={{
                y:
                    location.state != null &&
                    (location.state.pathname === "/about" ||
                        location.state.pathname === "/preferences")
                        ? 0
                        : "100%",
            }}
            animate={{
                y: 0,
                borderTop: `1px solid ${theme.content2}`,
                transitionEnd: {
                    borderTop: "none",
                },
            }}
            exit={{
                y:
                    location.pathname === "/about" ||
                    location.pathname === "/preferences"
                        ? 0
                        : "100%",
                borderTop:
                    location.pathname === "/about" ||
                    location.pathname === "/preferences"
                        ? "none"
                        : `1px solid ${theme.content2}`,
                transitionEnd: {
                    borderTop: "none",
                },
            }}
            transition={{ duration: constants.transitionDuration }}
        >
            <ConfigurationPathBar
                path={action.configurationPath}
                menu={false}
            />
            {action.status === "error" ? (
                <ErrorContainer>
                    <ErrorTitle>Error</ErrorTitle>
                    <ErrorWrapper>
                        <Error>{action.error}</Error>
                    </ErrorWrapper>
                </ErrorContainer>
            ) : (
                <Content>
                    <NamesRuler
                        ref={namesRulerRef}
                        skip={
                            namesRulerDimensions.width != null &&
                            namesRulerDimensions.width > 0
                        }
                    >
                        {action.datasets.map((dataset, index) => (
                            <NameRuler
                                key={`${dataset.name}${index
                                    .toString()
                                    .padStart(6, "0")}`}
                            >
                                {dataset.name}
                            </NameRuler>
                        ))}
                    </NamesRuler>
                    {nameWidth != null && (
                        <Datasets>
                            {(action.type === "cite"
                                ? action.datasets.filter(
                                      dataset => dataset.index
                                  )
                                : action.datasets
                            ).map((dataset, index) => {
                                if (
                                    action.type === "calc_size" &&
                                    !dataset.index
                                ) {
                                    return (
                                        <Dataset
                                            key={`${dataset.name}${index
                                                .toString()
                                                .padStart(6, "0")}${
                                                dataset.index
                                            }`}
                                        >
                                            <ReportLeft>
                                                <ReportName>
                                                    {dataset.name}
                                                </ReportName>
                                                <ReportIndex>
                                                    <ReportLabel>
                                                        Index files
                                                    </ReportLabel>
                                                    <ReportValue>
                                                        {utilities.sizeToString(
                                                            dataset.calcSizeIndex
                                                        )}
                                                    </ReportValue>
                                                </ReportIndex>
                                            </ReportLeft>
                                            <ReportRight>
                                                <ReportSize>
                                                    <ReportLabel>
                                                        Compressed files
                                                    </ReportLabel>
                                                    <ReportValue>
                                                        {`${utilities.sizeToString(
                                                            dataset
                                                                .calcSizeCompressed
                                                                .localBytes
                                                        )} / ${utilities.sizeToString(
                                                            dataset
                                                                .calcSizeCompressed
                                                                .remoteBytes
                                                        )} (local / remote)`}
                                                    </ReportValue>
                                                </ReportSize>
                                                <ReportSize>
                                                    <ReportLabel>
                                                        Raw files
                                                    </ReportLabel>
                                                    <ReportValue>
                                                        {`${utilities.sizeToString(
                                                            dataset.calcSizeRaw
                                                                .localBytes
                                                        )} / ${utilities.sizeToString(
                                                            dataset.calcSizeRaw
                                                                .remoteBytes
                                                        )} (local / remote)`}
                                                    </ReportValue>
                                                </ReportSize>
                                            </ReportRight>
                                        </Dataset>
                                    );
                                }
                                const downloadProgress =
                                    dataset.download.finalBytes === BigInt(0)
                                        ? 1.0
                                        : Number(
                                              dataset.download.currentBytes
                                          ) /
                                          Number(dataset.download.finalBytes);
                                const processProgress =
                                    dataset.process.finalBytes === BigInt(0)
                                        ? 1.0
                                        : Number(dataset.process.currentBytes) /
                                          Number(dataset.process.finalBytes);
                                const complete =
                                    !dataset.index &&
                                    dataset.download.currentBytes ===
                                        dataset.download.finalBytes &&
                                    dataset.process.currentBytes ===
                                        dataset.process.finalBytes;
                                return (
                                    <Dataset
                                        key={`${dataset.name}${index
                                            .toString()
                                            .padStart(6, "0")}${dataset.index}`}
                                    >
                                        <NameDisplay
                                            mode={
                                                complete
                                                    ? "complete"
                                                    : dataset.mode
                                            }
                                            nameWidth={nameWidth}
                                        >
                                            {dataset.name}
                                        </NameDisplay>
                                        <Progress
                                            mode={
                                                complete
                                                    ? "complete"
                                                    : dataset.index
                                                    ? "index"
                                                    : dataset.mode
                                            }
                                            value={
                                                complete ||
                                                dataset.index ||
                                                dataset.mode === "remote"
                                                    ? null
                                                    : dataset.mode === "local"
                                                    ? downloadProgress
                                                    : [
                                                          downloadProgress,
                                                          processProgress,
                                                      ]
                                            }
                                        />
                                        <StatusContainer>
                                            {complete ||
                                            action.type === "calc_size" ||
                                            action.type === "cite" ||
                                            dataset.index ||
                                            dataset.mode === "remote" ||
                                            dataset.mode === "local" ? (
                                                dataset.index ? (
                                                    <Status>{`Index ${dataset.currentIndexFiles} / ${dataset.finalIndexFiles}`}</Status>
                                                ) : complete ? (
                                                    <Status>
                                                        <StatusIcon>
                                                            <Tick />
                                                        </StatusIcon>
                                                        <StatusLabel>
                                                            Complete
                                                        </StatusLabel>
                                                    </Status>
                                                ) : (
                                                    <StatusSmall>
                                                        <StatusIcon>
                                                            <DownloadHeavy />
                                                        </StatusIcon>
                                                        <StatusLabel>
                                                            {`${utilities.sizeToString(
                                                                dataset.download
                                                                    .currentBytes
                                                            )} / ${utilities.sizeToString(
                                                                dataset.download
                                                                    .finalBytes
                                                            )}`}
                                                        </StatusLabel>
                                                    </StatusSmall>
                                                )
                                            ) : (
                                                <>
                                                    <StatusSmall>
                                                        <StatusIcon>
                                                            <DownloadHeavy />
                                                        </StatusIcon>
                                                        <StatusLabel>
                                                            {`${utilities.sizeToString(
                                                                dataset.download
                                                                    .currentBytes
                                                            )} / ${utilities.sizeToString(
                                                                dataset.download
                                                                    .finalBytes
                                                            )}`}
                                                        </StatusLabel>
                                                    </StatusSmall>
                                                    <StatusSmall>
                                                        <StatusIcon>
                                                            <DecompressHeavy />
                                                        </StatusIcon>
                                                        <StatusLabel>
                                                            {`${utilities.sizeToString(
                                                                dataset.process
                                                                    .currentBytes
                                                            )} / ${utilities.sizeToString(
                                                                dataset.process
                                                                    .finalBytes
                                                            )}`}
                                                        </StatusLabel>
                                                    </StatusSmall>
                                                </>
                                            )}
                                        </StatusContainer>
                                    </Dataset>
                                );
                            })}
                        </Datasets>
                    )}
                    {action.type === "cite" && (
                        <Dois>
                            {Object.entries(action.valueToDoi).map(
                                ([value, doi]) => (
                                    <Doi key={value}>
                                        <Status>
                                            <StatusIcon>
                                                {(() => {
                                                    switch (doi.status) {
                                                        case "error":
                                                            return <Close />;
                                                        case "index":
                                                            return <Wait />;
                                                        case "start":
                                                            return <Download />;
                                                        case "success":
                                                            return <Tick />;
                                                    }
                                                })()}
                                            </StatusIcon>
                                            <StatusLabel>
                                                <DoiLink
                                                    href={`https://doi.org/${value}`}
                                                    target="_blank"
                                                >{`https://doi.org/${value}`}</DoiLink>
                                                <DoiDatasets>
                                                    {utilities.sliceEllipsis(
                                                        doi.pathIds,
                                                        6
                                                    )}
                                                </DoiDatasets>
                                            </StatusLabel>
                                        </Status>
                                    </Doi>
                                )
                            )}
                        </Dois>
                    )}
                </Content>
            )}
            <Footer right={action.status === "error"}>
                {(action.status === "running" ||
                    action.status === "cancelled") && (
                    <>
                        <ActionWithIcon
                            enabled={action.status === "running"}
                            onClick={() => {
                                dispatchStateAction({
                                    type: "action-cancel",
                                    payload: dispatchStateAction,
                                });
                            }}
                        >
                            <Close />
                            <ActionLabel>Cancel</ActionLabel>
                        </ActionWithIcon>
                        <SpeedAndTime>
                            <SpeedContainer>
                                {showProcessSpeed ? (
                                    <>
                                        <StatusSmall>
                                            <StatusIcon>
                                                <DownloadHeavy />
                                            </StatusIcon>
                                            <StatusLabel>
                                                {utilities.speedToString(
                                                    action.speed[0]
                                                )}
                                            </StatusLabel>
                                        </StatusSmall>
                                        <StatusSmall>
                                            <StatusIcon>
                                                <DecompressHeavy />
                                            </StatusIcon>
                                            <StatusLabel>
                                                {utilities.speedToString(
                                                    action.speed[1]
                                                )}
                                            </StatusLabel>
                                        </StatusSmall>
                                    </>
                                ) : (
                                    <StatusSmall>
                                        <StatusIcon>
                                            <DownloadHeavy />
                                        </StatusIcon>
                                        <StatusLabel>
                                            {utilities.speedToString(
                                                action.speed[0]
                                            )}
                                        </StatusLabel>
                                    </StatusSmall>
                                )}
                            </SpeedContainer>
                            {action.timeLeft != null && (
                                <TimeContainer>
                                    <StatusIcon>
                                        <Hourglass />
                                    </StatusIcon>
                                    <StatusLabel>
                                        {utilities.durationToString(
                                            action.timeLeft
                                        )}
                                    </StatusLabel>
                                </TimeContainer>
                            )}
                        </SpeedAndTime>
                    </>
                )}
                {(action.status === "error" || action.status === "ended") && (
                    <>
                        {action.status === "ended" &&
                            action.speedAverage != null && (
                                <SpeedContainerAverage>
                                    {showProcessSpeed ? (
                                        <>
                                            <StatusSmall>
                                                <StatusIcon>
                                                    <DownloadHeavy />
                                                </StatusIcon>
                                                <StatusLabel>
                                                    {`${utilities.speedToString(
                                                        action.speedAverage[0]
                                                    )} (average)`}
                                                </StatusLabel>
                                            </StatusSmall>
                                            <StatusSmall>
                                                <StatusIcon>
                                                    <DecompressHeavy />
                                                </StatusIcon>
                                                <StatusLabel>
                                                    {`${utilities.speedToString(
                                                        action.speedAverage[1]
                                                    )} (average)`}
                                                </StatusLabel>
                                            </StatusSmall>
                                        </>
                                    ) : (
                                        <StatusSmall>
                                            <StatusIcon>
                                                <DownloadHeavy />
                                            </StatusIcon>
                                            <StatusLabel>
                                                {`${utilities.speedToString(
                                                    action.speedAverage[0]
                                                )} (average)`}
                                            </StatusLabel>
                                        </StatusSmall>
                                    )}
                                </SpeedContainerAverage>
                            )}
                        <ActionWithIcon
                            enabled={true}
                            onClick={() => {
                                dispatchStateAction({
                                    type: "action-ok",
                                    payload: null,
                                });
                            }}
                        >
                            <Tick />
                            <ActionLabel>OK</ActionLabel>
                        </ActionWithIcon>
                    </>
                )}
            </Footer>
        </StyledActionDisplay>
    );
}
