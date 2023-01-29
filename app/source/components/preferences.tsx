import * as React from "react";
import { useLocation } from "react-router-dom";
import { motion } from "framer-motion";
import styled, { useTheme } from "styled-components";
import * as constants from "../hooks/constants";
import { PreferencesContext } from "../hooks/preferences";
import { StateContext, navigateToMainRoute } from "../hooks/state";
import Select from "./select";
import NumberInputWitDefault from "./numberInputWithDefault";
import Close from "../icons/close.svg";
import Switch from "./switch";

const StyledPreferences = styled(motion.div)`
    position: absolute;
    left: 0;
    right: 0;
    top: 0;
    bottom: 0;
    z-index: 11;
    overflow: hidden;
    background-color: ${props => props.theme.background1};
`;

const Content = styled.div`
    height: calc(100vh - ${constants.barHeight}px);
`;

const Bar = styled.div`
    height: ${constants.barHeight}px;
    display: flex;
    align-items: center;
    justify-content: flex-end;
    padding-right: ${(constants.barHeight - constants.buttonHeight) / 2}px;
    border-bottom: 1px solid ${props => props.theme.background3};
`;

const Button = styled.div`
    width: ${constants.buttonHeight}px;
    height: ${constants.buttonHeight}px;
    padding: ${(constants.buttonHeight - constants.buttonIconHeight) / 2}px;
    cursor: pointer;
    border-radius: ${constants.buttonHeight / 2}px;
    transition: background-color 0.2s;
    &:hover {
        background-color: ${props => props.theme.background2};
    }
    & > svg {
        height: ${constants.buttonIconHeight}px;
    }
    & > svg path {
        fill: ${props => props.theme.content0};
    }
`;

const PropertiesContainer = styled.div`
    height: calc(100vh - ${constants.barHeight * 2}px);
    overflow: auto;
`;

const Properties = styled.div`
    display: flex;
    flex-direction: column;
`;

const Property = styled.div`
    display: flex;
    justify-content: flex-start;
    align-items: center;
    gap: 30px;
    padding: 20px;
    &:not(:last-of-type) {
        border-bottom: 1px solid ${props => props.theme.background2};
    }
`;

const Name = styled.div`
    user-select: auto;
    font-weight: 400;
    flex-shrink: 0;
    width: 50vw;
    text-align: right;
`;

export default function Preferences() {
    const location = useLocation();
    const [preferences, setStoredPreferences] =
        React.useContext(PreferencesContext);
    const [state, _] = React.useContext(StateContext);
    const theme = useTheme();
    return (
        <StyledPreferences
            initial={{ y: "-100%" }}
            animate={{
                y: 0,
                borderBottom: `1px solid ${theme.content2}`,
                transitionEnd: {
                    borderBottom: "none",
                },
            }}
            exit={{
                y: location.pathname === "/about" ? 0 : "-100%",
                borderBottom:
                    location.pathname === "/about"
                        ? "none"
                        : `1px solid ${theme.content2}`,
                transitionEnd: {
                    zIndex: 10,
                    borderBottom: "none",
                },
            }}
            transition={{ duration: constants.transitionDuration }}
        >
            <Content>
                <Bar>
                    <Button
                        onClick={() => {
                            navigateToMainRoute(state, {
                                state: { pathname: location.pathname },
                            });
                        }}
                    >
                        <Close />
                    </Button>
                </Bar>
                <PropertiesContainer>
                    <Properties>
                        <Property>
                            <Name>Theme</Name>
                            <Select
                                options={[
                                    ["auto", "Auto"],
                                    ["light", "Light"],
                                    ["dark", "Dark"],
                                ]}
                                value={
                                    preferences.storedPreferences.selectedTheme
                                }
                                onChange={value =>
                                    setStoredPreferences({
                                        ...preferences.storedPreferences,
                                        selectedTheme: value as
                                            | "auto"
                                            | "light"
                                            | "dark",
                                    })
                                }
                            />
                        </Property>
                        <Property>
                            <Name>Parallel file descriptors</Name>
                            <NumberInputWitDefault
                                defaultEnabled={
                                    preferences.storedPreferences
                                        .parallelFileDescriptors[0]
                                }
                                value={
                                    preferences.storedPreferences
                                        .parallelFileDescriptors[1]
                                }
                                defaultValue={
                                    constants.defaultParallelFileDescriptors
                                }
                                integer={true}
                                constraint={"two-or-more"}
                                unit={null}
                                onChange={(
                                    defaultEnabled: boolean,
                                    value: number
                                ) =>
                                    setStoredPreferences({
                                        ...preferences.storedPreferences,
                                        parallelFileDescriptors: [
                                            defaultEnabled,
                                            value,
                                        ],
                                    })
                                }
                                onErrorChange={() => {}}
                            />
                        </Property>
                        <Property>
                            <Name>Parallel index downloads</Name>
                            <NumberInputWitDefault
                                defaultEnabled={
                                    preferences.storedPreferences
                                        .parallelIndexDownloads[0]
                                }
                                value={
                                    preferences.storedPreferences
                                        .parallelIndexDownloads[1]
                                }
                                defaultValue={
                                    constants.defaultParallelIndexDownloads
                                }
                                integer={true}
                                constraint={"positive-strict"}
                                unit={null}
                                onChange={(
                                    defaultEnabled: boolean,
                                    value: number
                                ) =>
                                    setStoredPreferences({
                                        ...preferences.storedPreferences,
                                        parallelIndexDownloads: [
                                            defaultEnabled,
                                            value,
                                        ],
                                    })
                                }
                                onErrorChange={() => {}}
                            />
                        </Property>
                        <Property>
                            <Name>Parallel downloads</Name>
                            <NumberInputWitDefault
                                defaultEnabled={
                                    preferences.storedPreferences
                                        .parallelDownloads[0]
                                }
                                value={
                                    preferences.storedPreferences
                                        .parallelDownloads[1]
                                }
                                defaultValue={
                                    constants.defaultParallelDownloads
                                }
                                integer={true}
                                constraint={"positive-strict"}
                                unit={null}
                                onChange={(
                                    defaultEnabled: boolean,
                                    value: number
                                ) =>
                                    setStoredPreferences({
                                        ...preferences.storedPreferences,
                                        parallelDownloads: [
                                            defaultEnabled,
                                            value,
                                        ],
                                    })
                                }
                                onErrorChange={() => {}}
                            />
                        </Property>
                        <Property>
                            <Name>Parallel decompressions</Name>
                            <NumberInputWitDefault
                                defaultEnabled={
                                    preferences.storedPreferences
                                        .parallelDecompressions[0]
                                }
                                value={
                                    preferences.storedPreferences
                                        .parallelDecompressions[1]
                                }
                                defaultValue={preferences.availableParallelism}
                                integer={true}
                                constraint={"positive-strict"}
                                unit={null}
                                onChange={(
                                    defaultEnabled: boolean,
                                    value: number
                                ) =>
                                    setStoredPreferences({
                                        ...preferences.storedPreferences,
                                        parallelDecompressions: [
                                            defaultEnabled,
                                            value,
                                        ],
                                    })
                                }
                                onErrorChange={() => {}}
                            />
                        </Property>
                        <Property>
                            <Name>
                                Keep compressed files after decompression
                            </Name>
                            <Switch
                                value={preferences.storedPreferences.keep}
                                onChange={keep =>
                                    setStoredPreferences({
                                        ...preferences.storedPreferences,
                                        keep,
                                    })
                                }
                            />
                        </Property>
                        <Property>
                            <Name>Parallel BibTex downloads</Name>
                            <NumberInputWitDefault
                                defaultEnabled={
                                    preferences.storedPreferences
                                        .parallelDoiDownloads[0]
                                }
                                value={
                                    preferences.storedPreferences
                                        .parallelDoiDownloads[1]
                                }
                                defaultValue={
                                    constants.defaultParallelDoiDownloads
                                }
                                integer={true}
                                constraint={"positive-strict"}
                                unit={null}
                                onChange={(
                                    defaultEnabled: boolean,
                                    value: number
                                ) =>
                                    setStoredPreferences({
                                        ...preferences.storedPreferences,
                                        parallelDoiDownloads: [
                                            defaultEnabled,
                                            value,
                                        ],
                                    })
                                }
                                onErrorChange={() => {}}
                            />
                        </Property>
                        <Property>
                            <Name>BibTex timeout</Name>
                            <NumberInputWitDefault
                                defaultEnabled={
                                    preferences.storedPreferences.doiTimeout[0]
                                }
                                value={
                                    preferences.storedPreferences.doiTimeout[1]
                                }
                                defaultValue={constants.defaultTimeout}
                                integer={false}
                                constraint={"positive-strict"}
                                unit="s"
                                onChange={(
                                    defaultEnabled: boolean,
                                    value: number
                                ) =>
                                    setStoredPreferences({
                                        ...preferences.storedPreferences,
                                        doiTimeout: [defaultEnabled, value],
                                    })
                                }
                                onErrorChange={() => {}}
                            />
                        </Property>
                    </Properties>
                </PropertiesContainer>
            </Content>
        </StyledPreferences>
    );
}
