import * as React from "react";
import { invoke } from "@tauri-apps/api";
import { message, open } from "@tauri-apps/api/dialog";
import { motion } from "framer-motion";
import styled from "styled-components";
import * as constants from "../hooks/constants";
import { PreferencesContext } from "../hooks/preferences";

const StyledSetup = styled(motion.div)`
    position: absolute;
    left: 0;
    right: 0;
    top: 0;
    bottom: 0;
    z-index: 0;
    overflow: hidden;
    background-color: ${props => props.theme.background0};
`;

const Decoration = styled.div`
    height: 52px;
    background-color: ${props => props.theme.background1};
`;

const Container = styled.div`
    padding: 20px;
    height: calc(100% - 52px);
    display: flex;
    align-items: center;
    justify-content: center;
`;

const Buttons = styled.div`
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 52px;
    width: 100%;
    height: 100%;
    background-color: ${props => props.theme.background1};
`;

const Button = styled.div`
    height: 52px;
    font-size: 18px;
    font-weight: 500;
    display: flex;
    align-items: center;
    justify-content: center;
    width: min(100% - 40px, 250px);
    border-radius: 20px;
    cursor: pointer;
    border: 1px solid ${props => props.theme.link};
    transition: border 0.2s, background-color 0.2s, color 0.2s;
    text-align: center;
`;

const ClearButton = styled(Button)`
    color: ${props => props.theme.link};
    &:hover {
        color: ${props => props.theme.background0};
        background-color: ${props => props.theme.link};
        border: 1px solid ${props => props.theme.link};
    }
`;

const OpaqueButton = styled(Button)`
    background-color: ${props => props.theme.link};
    color: ${props => props.theme.background0};
    &:hover {
        color: ${props => props.theme.background0};
        background-color: ${props => props.theme.linkActive};
        border: 1px solid ${props => props.theme.linkActive};
    }
`;

export default function Setup() {
    const [preferences, setStoredPreferences] =
        React.useContext(PreferencesContext);
    return (
        <StyledSetup
            initial={{ opacity: 1 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 1 }}
            transition={{ duration: constants.transitionDuration }}
        >
            <Decoration />
            <Container>
                <Buttons>
                    <ClearButton
                        onClick={() => {
                            invoke("create_configuration", {
                                content: UNDR_DEFAULT_TOML,
                            })
                                .then(configurationPath => {
                                    if (configurationPath != null) {
                                        setStoredPreferences({
                                            ...preferences.storedPreferences,
                                            configurationPath:
                                                configurationPath as string,
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
                        }}
                    >
                        New configuration
                    </ClearButton>
                    <OpaqueButton
                        onClick={() => {
                            open({
                                title: "Open configuration",
                                multiple: false,
                                filters: [
                                    {
                                        name: "configuration",
                                        extensions: ["toml"],
                                    },
                                ],
                            })
                                .then(configurationPath => {
                                    if (
                                        configurationPath != null &&
                                        configurationPath.length > 0
                                    ) {
                                        setStoredPreferences({
                                            ...preferences.storedPreferences,
                                            configurationPath:
                                                configurationPath as string,
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
                        }}
                    >
                        Open configuration
                    </OpaqueButton>
                </Buttons>
            </Container>
        </StyledSetup>
    );
}
